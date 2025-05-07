# HistoPrep Scripts

This directory contains utility scripts for processing histological slide images.

## mask_and_save_multi_level.py

Script to read an SVS file, apply a tissue mask, save with multiple resolution levels, and output metadata as JSON.

### Usage

```bash
./mask_and_save_multi_level.py --input INPUT_FILE.svs --output OUTPUT_FILE.tiff [OPTIONS]
```

### Options

- `--input`, `-i`: Path to the input SVS file (required)
- `--output`, `-o`: Path to save the output file(s) (required)
- `--threshold`, `-t`: Threshold for tissue detection (0-255). If not specified, Otsu's method will be used
- `--multiplier`, `-m`: Multiplier for Otsu's threshold (default: 1.05)
- `--sigma`, `-s`: Sigma for Gaussian blur (default: 1.0)
- `--clean-mask`, `-c`: Clean the tissue mask to remove small artifacts and fill holes
- `--min-area`: Minimum area in pixels for contours when cleaning mask (default: 10)
- `--save-mask`: Save the tissue mask as a separate PNG file
- `--pyramid`, `-p`: Save as a single pyramid TIFF with multiple resolution levels
- `--compression`: Lossless compression method (choices: lzw, zlib, none; default: lzw)
- `--max-level`: Maximum level to process (0 is highest resolution)
- `--levels`, `-l`: Comma-separated list of specific levels to process (e.g., '0,2,3')

### Output

The script outputs:
1. Processed image file(s) with the tissue mask applied
2. A JSON metadata file containing information about the slide and processing parameters
3. Optionally, a tissue mask file if `--save-mask` is specified

## run_mask_and_save_multi_level.py

Script to run mask_and_save_multi_level.py on all SVS files in a directory using configuration from a JSON file.

### Usage

```bash
./run_mask_and_save_multi_level.py [--config CONFIG_FILE] [--force]
```

### Options

- `--config`, `-c`: Path to configuration JSON file (default: config.json)
- `--force`, `-f`: Force overwrite output directory if it exists without asking

### Configuration File

A JSON file containing all processing parameters. The following fields are available:

```json
{
  "input_dir": "/path/to/svs/files",  // Required: Directory containing SVS files
  "output_dir": "/path/to/output",    // Required: Directory to save output files
  "output_format": "png",             // Output file format (png, tiff, etc.)
  
  "threshold": null,                  // Tissue detection threshold (null for auto)
  "multiplier": 1.05,                 // Multiplier for Otsu's threshold
  "sigma": 1.0,                       // Sigma for Gaussian blur
  "clean_mask": true,                 // Clean tissue mask
  "min_area": 10,                     // Minimum area for contours
  "save_mask": true,                  // Save tissue mask as PNG
  
  "pyramid": false,                   // Save as pyramid TIFF
  "compression": "lzw",               // Compression method
  
  "max_level": null,                  // Maximum level to process
  "levels": "0,1,2"                   // Specific levels to process
}
```

### Directory Handling

- If the output directory doesn't exist, it will be created
- If the output directory exists and has content:
  - With `--force`: It will overwrite content without asking
  - Without `--force`: It will ask for confirmation before proceeding

### Example

Create a config.json file with your settings, then run:

```bash
./run_mask_and_save_multi_level.py --config my_config.json
```

This will:
1. Load configuration from `my_config.json`
2. Find all SVS files in the specified input directory
3. Process each file with the configured parameters
4. Save the results in the specified output directory
5. Generate a metadata JSON file for each processed image