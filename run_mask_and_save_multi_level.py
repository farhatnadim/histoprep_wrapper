#!/usr/bin/env python
"""
Script to run mask_and_save_multi_level.py on all SVS files in a directory.

This script searches for all SVS files in the input directory, creates an output directory,
and runs mask_and_save_multi_level.py on each SVS file with the configuration from config.json.
If the output directory exists, it gives the user the option to overwrite or exit.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def create_parser():
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Run mask_and_save_multi_level.py on all SVS files in a directory using config.json."
    )
    
    parser.add_argument(
        "--config", "-c", 
        type=str, 
        default="config.json",
        help="Path to configuration JSON file. Default: config.json"
    )
    
    parser.add_argument(
        "--force", "-f", 
        action="store_true",
        help="Force overwrite output directory if it exists without asking."
    )
    
    return parser


def check_output_directory(output_dir, force=False):
    """Check if output directory exists and handle accordingly.
    
    Args:
        output_dir: Path to output directory
        force: Whether to force overwriting without asking
        
    Returns:
        bool: True if directory is ready to use, False if user chose to exit
    """
    output_dir = Path(output_dir)
    
    # If directory doesn't exist, create it
    if not output_dir.exists():
        print(f"Creating output directory: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
        return True
    
    # Directory exists, check if it's empty
    if not any(output_dir.iterdir()):
        return True  # Directory is empty, ok to use
    
    # Directory exists and has contents
    if force:
        print(f"Output directory {output_dir} exists and has content. Overwriting as requested.")
        return True
    
    # Ask user for confirmation
    while True:
        response = input(f"Output directory {output_dir} exists and has content. Overwrite? [y/n]: ").lower()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            print("Exiting without processing files.")
            return False
        else:
            print("Please enter 'y' or 'n'")


def load_config(config_path):
    """Load configuration from JSON file.
    
    Args:
        config_path: Path to config.json file
        
    Returns:
        dict: Configuration dictionary
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Validate required fields
    required_fields = ['input_dir', 'output_dir']
    missing_fields = [field for field in required_fields if field not in config]
    if missing_fields:
        raise ValueError(f"Missing required fields in config file: {', '.join(missing_fields)}")
    
    return config


def build_command_args(config):
    """Build command line arguments from config dictionary.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        list: Command line arguments
    """
    args = []
    
    # Processing parameters
    if 'threshold' in config and config['threshold'] is not None:
        args.extend(["--threshold", str(config['threshold'])])
    
    if 'multiplier' in config and config['multiplier'] != 1.05:
        args.extend(["--multiplier", str(config['multiplier'])])
    
    if 'sigma' in config and config['sigma'] != 1.0:
        args.extend(["--sigma", str(config['sigma'])])
    
    if config.get('clean_mask', False):
        args.append("--clean-mask")
    
    if 'min_area' in config and config['min_area'] != 10:
        args.extend(["--min-area", str(config['min_area'])])
    
    if config.get('save_mask', False):
        args.append("--save-mask")
    
    if config.get('pyramid', False):
        args.append("--pyramid")
    
    if 'compression' in config and config['compression'] != "lzw":
        args.extend(["--compression", config['compression']])
    
    if 'max_level' in config and config['max_level'] is not None:
        args.extend(["--max-level", str(config['max_level'])])
    
    if 'levels' in config and config['levels'] is not None:
        args.extend(["--levels", config['levels']])
    
    return args


def main():
    """Main function."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Load configuration from JSON file
    try:
        config = load_config(args.config)
        print(f"Loaded configuration from {args.config}")
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1
    
    # Get input and output directories from config
    input_dir = Path(config['input_dir'])
    output_dir = Path(config['output_dir'])
    output_format = config.get('output_format', 'png')
    
    # Validate input directory
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Input directory not found or is not a directory: {input_dir}", file=sys.stderr)
        return 1
    
    # Check/prepare output directory
    if not check_output_directory(output_dir, args.force):
        return 0  # User chose not to overwrite
    
    # Find all SVS files in the input directory
    svs_files = list(input_dir.glob("*.svs"))
    if not svs_files:
        print(f"No SVS files found in {input_dir}")
        return 0
    
    print(f"Found {len(svs_files)} SVS files in {input_dir}")
    
    # Build command line arguments for mask_and_save_multi_level.py
    base_args = build_command_args(config)
    
    # Path to the mask_and_save_multi_level.py script
    script_path = Path(os.path.dirname(os.path.abspath(__file__))) / "mask_and_save_multi_level.py"
    if not script_path.exists():
        print(f"Script not found: {script_path}", file=sys.stderr)
        return 1
    
    # Process each SVS file
    for i, svs_file in enumerate(svs_files, 1):
        print(f"\nProcessing file {i}/{len(svs_files)}: {svs_file.name}")
        
        # Define output filename
        output_filename = f"{svs_file.stem}.{output_format}"
        output_path = output_dir / output_filename
        
        # Build command
        cmd = [
            sys.executable,  # Use the current Python interpreter
            str(script_path),
            "--input", str(svs_file),
            "--output", str(output_path)
        ] + base_args
        
        # Run the command
        print(f"Running command: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print(f"STDERR: {result.stderr}", file=sys.stderr)
        except subprocess.CalledProcessError as e:
            print(f"Error processing {svs_file.name}:", file=sys.stderr)
            print(f"STDOUT: {e.stdout}", file=sys.stderr)
            print(f"STDERR: {e.stderr}", file=sys.stderr)
            print(f"Exit code: {e.returncode}", file=sys.stderr)
            # Continue processing other files even if one fails
            continue
    
    print("\nProcessing complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())