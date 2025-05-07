#!/usr/bin/env python
"""
Script to read an SVS file, apply a tissue mask, and save the result as either:
1. A single pyramid TIFF file with multiple resolution levels, or
2. Multiple TIFF files (one per level) with lossless compression

You can specify which levels to process using the --levels option with a comma-separated 
list of level indices (e.g., --levels 0,2,3), or process all levels up to a maximum 
using the --max-level option.

The script also outputs metadata as a JSON file containing information about the slide
and processing parameters.
"""

import argparse
import json
from pathlib import Path
import datetime

import numpy as np
from PIL import Image

from histoprep import SlideReader
import histoprep.functional as F


def create_parser():
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Read an SVS file, apply a tissue mask, save with multiple resolution levels, and output metadata as JSON."
    )
    
    parser.add_argument(
        "--input", "-i", 
        type=str, 
        required=True,
        help="Path to the input SVS file."
    )
    
    parser.add_argument(
        "--output", "-o", 
        type=str, 
        required=True,
        help="Path to save the output file(s)."
    )
    
    parser.add_argument(
        "--threshold", "-t", 
        type=int, 
        default=None,
        help="Threshold for tissue detection (0-255). If not specified, Otsu's method will be used."
    )
    
    parser.add_argument(
        "--multiplier", "-m", 
        type=float, 
        default=1.05,
        help="Multiplier for Otsu's threshold. Default: 1.05"
    )
    
    parser.add_argument(
        "--sigma", "-s", 
        type=float, 
        default=1.0,
        help="Sigma for Gaussian blur. Default: 1.0"
    )
    
    parser.add_argument(
        "--clean-mask", "-c", 
        action="store_true",
        help="Clean the tissue mask to remove small artifacts and fill holes."
    )
    
    parser.add_argument(
        "--min-area", 
        type=int, 
        default=10,
        help="Minimum area in pixels for contours when cleaning mask. Default: 10"
    )
    
    parser.add_argument(
        "--save-mask", 
        action="store_true",
        help="Save the tissue mask as a separate PNG file."
    )
    
    parser.add_argument(
        "--pyramid", "-p",
        action="store_true",
        help="Save as a single pyramid TIFF with multiple resolution levels."
    )
    
    parser.add_argument(
        "--compression", 
        type=str,
        default="lzw",
        choices=["lzw", "zlib", "none"],
        help="Lossless compression method. Default: lzw"
    )
    
    parser.add_argument(
        "--max-level", 
        type=int, 
        default=None,
        help="Maximum level to process (0 is highest resolution). Default: process all levels."
    )
    
    parser.add_argument(
        "--levels", "-l",
        type=str,
        default=None,
        help="Comma-separated list of specific levels to process (e.g., '0,2,3'). Overrides --max-level if provided."
    )
    
    return parser


def main():
    """Main function."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    # Create output directory if needed
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Ensure output has .tiff extension
    if args.pyramid and output_path.suffix.lower() not in ['.tiff', '.tif']:
        output_path = output_path.with_suffix('.tiff')
    
    print(f"Reading slide file: {input_path}")
    slide_reader = SlideReader(path=input_path)
    
    # Get information about available levels
    level_dimensions = slide_reader.level_dimensions
    
    print(f"Slide has {len(level_dimensions)} levels:")
    for level, dims in level_dimensions.items():
        print(f"  Level {level}: {dims[1]}x{dims[0]} (width x height)")
    
    # Determine which level(s) to process
    if args.levels is not None:
        try:
            # Parse comma-separated list of levels
            requested_levels = [int(level.strip()) for level in args.levels.split(',')]
            
            # Validate all requested levels
            invalid_levels = [lvl for lvl in requested_levels if lvl not in level_dimensions]
            if invalid_levels:
                raise ValueError(f"Invalid level(s): {invalid_levels}. Available levels: {list(level_dimensions.keys())}")
            
            levels_to_process = requested_levels
            print(f"Processing specific levels: {', '.join(map(str, levels_to_process))}")
        except ValueError as e:
            if "invalid literal for int" in str(e):
                raise ValueError(f"Invalid level format in '{args.levels}'. Please provide comma-separated integers.")
            else:
                raise
    else:
        max_level = args.max_level if args.max_level is not None else max(level_dimensions.keys())
        levels_to_process = list(range(max_level + 1))
        print(f"Processing levels 0 to {max_level}")
    
    # Get tissue mask from one of the smaller levels for efficiency
    # We'll use the tissue detection level to create the mask
    mask_level = slide_reader.level_from_max_dimension()
    
    print(f"Generating tissue mask from level {mask_level}...")
    threshold, tissue_mask = slide_reader.get_tissue_mask(
        level=mask_level,
        threshold=args.threshold,
        multiplier=args.multiplier,
        sigma=args.sigma
    )
    
    print(f"Tissue mask generated with threshold: {threshold}")
    
    # Clean tissue mask if requested
    if args.clean_mask:
        print("Cleaning tissue mask...")
        tissue_mask = F.clean_tissue_mask(
            tissue_mask=tissue_mask,
            min_area_pixel=args.min_area
        )
    
    # Save mask if requested
    if args.save_mask:
        mask_path = output_path.with_name(f"{output_path.stem}_mask.png")
        print(f"Saving mask to: {mask_path}")
        # Convert mask (0=background, 1=tissue) to image format (0=black, 255=white)
        mask_image = Image.fromarray((1 - tissue_mask) * 255).convert("L")
        mask_image.save(mask_path)
    
    # Process each level
    masked_images = []
    level_metadata = {}
    
    for level in levels_to_process:
        print(f"Processing level {level}...")
        
        # Read the image at current level
        image = slide_reader.read_level(level)
        level_h, level_w = image.shape[:2]
        
        # Store level metadata
        # Convert numpy floats to regular Python floats for JSON serialization
        downsample_h, downsample_w = slide_reader.level_downsamples[level]
        level_metadata[str(level)] = {
            "dimensions": {
                "width": int(level_w),
                "height": int(level_h)
            },
            "downsample_factor": {
                "height": float(downsample_h),
                "width": float(downsample_w)
            }
        }
        
        # Scale the mask to the current level's dimensions if needed
        if level != mask_level:
            # Calculate resize factor based on dimensions
            mask_h, mask_w = tissue_mask.shape
            scale_h, scale_w = level_h / mask_h, level_w / mask_w
            
            if scale_h != 1.0 or scale_w != 1.0:
                print(f"  Scaling mask by factors: {scale_h:.2f}, {scale_w:.2f}")
                
                # Use simple nearest neighbor scaling for binary mask
                import cv2
                scaled_mask = cv2.resize(
                    tissue_mask.astype(np.uint8), 
                    (level_w, level_h),
                    interpolation=cv2.INTER_NEAREST
                )
            else:
                scaled_mask = tissue_mask
        else:
            scaled_mask = tissue_mask
        
        # Apply the mask to the image
        print(f"  Applying mask to level {level} image...")
        masked_image = image.copy()
        # Expand mask to have same shape as image for broadcasting
        mask_3d = np.repeat(scaled_mask[:, :, np.newaxis], 3, axis=2)
        # Apply mask: where mask is 0, set to white (255)
        masked_image[mask_3d == 0] = 255
        
        # Calculate tissue percentage in the level
        tissue_percentage = (scaled_mask.sum() / (level_w * level_h)) * 100
        level_metadata[str(level)]["tissue_percentage"] = float(tissue_percentage)
        
        # If saving as individual files
        if not args.pyramid:
            # Create level-specific filename
            if level == 0:
                level_path = output_path
            else:
                level_path = output_path.with_name(f"{output_path.stem}_level{level}{output_path.suffix}")
            
            print(f"  Saving level {level} to: {level_path}")
            
            # Use PIL to save the image
            result_image = Image.fromarray(masked_image)
            
            # Set compression based on args
            compression = None
            if args.compression == "lzw":
                compression = "tiff_lzw"
            elif args.compression == "zlib":
                compression = "tiff_deflate"
            
            # Save with appropriate compression
            result_image.save(level_path, compression=compression)
            
            # Store output path in metadata
            level_metadata[str(level)]["output_path"] = str(level_path)
        else:
            # Add to list for pyramid TIFF
            masked_images.append(masked_image)
    
    # If saving as pyramid TIFF
    final_output_path = None
    if args.pyramid:
        # Special handling if only one level was processed
        if len(masked_images) == 1 and len(levels_to_process) == 1:
            print(f"Only one level ({levels_to_process[0]}) was processed. Saving as regular TIFF to: {output_path}")
            level_image = masked_images[0]
            result_image = Image.fromarray(level_image)
        else:
            print(f"Warning: Pyramid TIFF saving requires the tifffile package.")
            print(f"Falling back to saving the highest resolution level only to: {output_path}")
            
            # Find the highest resolution image in our masked_images list
            # When processing multiple levels, we need to find the one with lowest level number
            # (which corresponds to highest resolution)
            highest_res_idx = levels_to_process.index(min(levels_to_process))
            highest_res_image = masked_images[highest_res_idx]
            result_image = Image.fromarray(highest_res_image)
        
        # Set compression based on args
        compression = None
        if args.compression == "lzw":
            compression = "tiff_lzw"
        elif args.compression == "zlib":
            compression = "tiff_deflate"
        
        # Save with appropriate compression
        print(f"Saving to: {output_path}")
        result_image.save(output_path, compression=compression)
        final_output_path = output_path
    
    # Create and save metadata as JSON
    metadata = {
        "slide_info": {
            "name": slide_reader.name,
            "path": slide_reader.path,
            "suffix": slide_reader.suffix,
            "backend_name": slide_reader.backend_name,
            "dimensions": {
                "width": int(slide_reader.dimensions[1]),
                "height": int(slide_reader.dimensions[0])
            },
            "level_count": slide_reader.level_count,
            "data_bounds": [int(x) for x in slide_reader.data_bounds]
        },
        "processing_params": {
            "threshold": int(threshold),
            "multiplier": float(args.multiplier),
            "sigma": float(args.sigma),
            "clean_mask": bool(args.clean_mask),
            "min_area": int(args.min_area) if args.clean_mask else None,
            "compression": args.compression,
            "pyramid_mode": bool(args.pyramid),
            "mask_level": int(mask_level),
            "processed_levels": [int(level) for level in levels_to_process],
            "timestamp": datetime.datetime.now().isoformat()
        },
        "levels": level_metadata
    }
    
    # If pyramid mode is active, add the final output path
    if args.pyramid:
        metadata["output"] = {
            "path": str(final_output_path),
            "is_pyramid": True
        }
    
    # Save metadata to JSON file
    json_path = output_path.with_name(f"{output_path.stem}_metadata.json")
    print(f"Saving metadata to: {json_path}")
    with open(json_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print("Processing complete!")


if __name__ == "__main__":
    main()