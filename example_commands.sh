#!/bin/bash
# Example commands for using the mask_and_save_multi_level scripts

# Example 1: Process a single SVS file
# This processes a single file, applies tissue detection, cleans the mask, and saves with multiple levels
#./mask_and_save_multi_level.py \
#  --input TCGA-A6-2686-01Z-00-DX1.0540a027-2a0c-46c7-9af0-7b8672631de7.svs \
#  --output ./output/TCGA-A6-2686-01Z-00-DX1.tiff \
#  --clean-mask \
#  --save-mask \
#  --sigma 1.5 \
#  --levels 0,1,2

# Example 2: Use the default config.json file
# Make sure you've updated config.json with appropriate paths and settings
python3 run_mask_and_save_multi_level.py

# Example 3: Use a custom config file
# Create a custom config file for different processing settings
#cat > ./custom_config.json << 'EOF'
#{
#  "input_dir": ".",
#  "output_dir": "./output_png",
#  "output_format": "png",
#  "clean_mask": true,
#  "save_mask": true,
#  "sigma": 1.5,
#  "max_level": 2
#}
#EOF

#./run_mask_and_save_multi_level.py --config ./custom_config.json

# Example 4: Use a config file with pyramid output
#cat > ./pyramid_config.json << 'EOF'
#{
#  "input_dir": ".",
#  "output_dir": "./output_pyramid",
#  "output_format": "tiff",
#  "pyramid": true,
#  "clean_mask": true,
#  "compression": "lzw",
#  "max_level": 3
#}
#EOF

#./run_mask_and_save_multi_level.py --config ./pyramid_config.json --force

# Note: Output directories will be created automatically if they don't exist
# The --force flag will overwrite directories without asking for confirmation