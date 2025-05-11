import os
import glob
import shutil # For moving files

# --- Configuration ---
# This should be the SAME as MAIN_OUTPUT_DIR from your processing script
PROCESSED_SLIDES_BASE_DIR = "processed_slides_output"
MAX_TIFFSPLIT_LEVELS_TO_KEEP = 4 # Up to level 3 (0, 1, 2, 3)

# Keywords to identify files for the 'dirty' directory
# These are substrings that might appear in the filenames of associated images.
DIRTY_FILE_KEYWORDS = ["_thumbnail", "_macro", "_label", "_associated_"]


def organize_slide_directory(slide_dir_path):
    """
    Organizes files within a single processed slide directory into 'clean' and 'dirty' subdirs.
    Renames and moves tiffsplit TIFF files.
    """
    print(f"\n--- Organizing directory: {slide_dir_path} ---")
    root_name = os.path.basename(slide_dir_path)

    clean_dir = os.path.join(slide_dir_path, "clean")
    dirty_dir = os.path.join(slide_dir_path, "dirty")

    os.makedirs(clean_dir, exist_ok=True)
    os.makedirs(dirty_dir, exist_ok=True)

    # --- Handle tiffsplit files first (renaming and moving) ---
    # tiffsplit typically names files with an alphabetic suffix: aaa, aab, aac, ...
    # We map these to levels 0, 1, 2, 3
    # Note: The order tiffsplit outputs files might not always directly correspond
    # to the pyramid level order in the original SVS. This renaming assumes
    # the first few IFDs tiffsplit extracts are the ones you want as level 0, 1, etc.
    # This is a common assumption but not universally guaranteed for all TIFF structures.

    # Generate expected suffixes for tiffsplit based on number of levels
    # aaa, aab, aac, aad, aae, ...
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    tiffsplit_suffixes = []
    for i in range(26): # first char
        for j in range(26): # second char
            for k in range(26): # third char
                if len(tiffsplit_suffixes) < MAX_TIFFSPLIT_LEVELS_TO_KEEP:
                    tiffsplit_suffixes.append(f"{alphabet[i]}{alphabet[j]}{alphabet[k]}")
                else:
                    break
            if len(tiffsplit_suffixes) >= MAX_TIFFSPLIT_LEVELS_TO_KEEP:
                break
        if len(tiffsplit_suffixes) >= MAX_TIFFSPLIT_LEVELS_TO_KEEP:
            break
    
    print(f"  Looking for tiffsplit suffixes: {tiffsplit_suffixes[:MAX_TIFFSPLIT_LEVELS_TO_KEEP]}")

    # Find all tiffsplit files
    # Example pattern: my_slide1_tiffsplit_aaa.tif
    tiffsplit_pattern = os.path.join(slide_dir_path, f"{root_name}_tiffsplit_*.tif")
    all_tiffsplit_files = sorted(glob.glob(tiffsplit_pattern)) # Sort to get them in 'aaa', 'aab' order

    processed_tiffsplit_count = 0
    for i, suffix_char_code in enumerate(tiffsplit_suffixes):
        if i >= MAX_TIFFSPLIT_LEVELS_TO_KEEP:
            break # Stop after processing desired number of levels

        # Construct the expected old filename for this level
        # e.g., if root_name is "slide1", prefix is "slide1_tiffsplit_", suffix is "aaa"
        # old_filename_pattern should match "slide1_tiffsplit_aaa.tif"
        old_tiff_filename = f"{root_name}_tiffsplit_{suffix_char_code}.tif"
        old_tiff_path = os.path.join(slide_dir_path, old_tiff_filename)

        if os.path.exists(old_tiff_path):
            new_tiff_filename = f"{root_name}_level_{i}.tif"
            new_tiff_path = os.path.join(clean_dir, new_tiff_filename)
            try:
                print(f"    Moving and renaming: {old_tiff_filename} -> clean/{new_tiff_filename}")
                shutil.move(old_tiff_path, new_tiff_path)
                processed_tiffsplit_count += 1
            except Exception as e:
                print(f"      Error moving/renaming {old_tiff_filename}: {e}")
        else:
            # This can happen if tiffsplit produced fewer files than MAX_TIFFSPLIT_LEVELS_TO_KEEP
            # print(f"    Tiffsplit file not found for suffix {suffix_char_code} (level {i}): {old_tiff_filename}")
            pass


    # Move any remaining tiffsplit files (beyond MAX_TIFFSPLIT_LEVELS_TO_KEEP or not matching pattern) to dirty
    remaining_tiffsplit_files = glob.glob(os.path.join(slide_dir_path, f"{root_name}_tiffsplit_*.tif"))
    for r_ts_file_path in remaining_tiffsplit_files:
        try:
            print(f"    Moving remaining tiffsplit file to dirty: {os.path.basename(r_ts_file_path)}")
            shutil.move(r_ts_file_path, os.path.join(dirty_dir, os.path.basename(r_ts_file_path)))
        except Exception as e:
            print(f"      Error moving remaining tiffsplit file {os.path.basename(r_ts_file_path)}: {e}")


    # --- Handle other files (.png, .json, .txt) ---
    for item_name in os.listdir(slide_dir_path):
        item_path = os.path.join(slide_dir_path, item_name)

        if os.path.isdir(item_path): # Skip 'clean' and 'dirty' directories themselves
            if item_name in ["clean", "dirty"]:
                continue
            else: # Move unexpected directories to dirty
                print(f"    Found unexpected directory '{item_name}', moving to dirty.")
                try:
                    shutil.move(item_path, os.path.join(dirty_dir, item_name))
                except Exception as e:
                    print(f"      Error moving directory {item_name}: {e}")
                continue

        # Check if it's a file to be moved
        if os.path.isfile(item_path):
            is_dirty_file = False
            for keyword in DIRTY_FILE_KEYWORDS:
                if keyword in item_name.lower(): # Make keyword check case-insensitive
                    is_dirty_file = True
                    break
            
            # Also consider .tif files that weren't processed tiffsplit files as potentially dirty
            # (though most should have been caught by the specific tiffsplit handling above)
            if item_name.endswith(".tif") and not item_name.startswith(f"{root_name}_level_"):
                 is_dirty_file = True


            destination_dir = dirty_dir if is_dirty_file else clean_dir
            try:
                # print(f"    Moving: {item_name} -> {os.path.basename(destination_dir)}/")
                shutil.move(item_path, os.path.join(destination_dir, item_name))
            except Exception as e:
                # This might happen if a tiffsplit file was already moved, then listdir finds it again
                # before the loop finishes with the original list.
                # Or if trying to move to same location (shouldn't happen with this logic).
                if os.path.exists(os.path.join(destination_dir, item_name)): # Already moved
                    pass
                else:
                    print(f"      Error moving file {item_name}: {e}")
    
    print(f"  Finished organizing {slide_dir_path}.")


# --- Main script execution ---
if __name__ == "__main__":
    abs_processed_slides_base_dir = os.path.abspath(PROCESSED_SLIDES_BASE_DIR)

    if not os.path.isdir(abs_processed_slides_base_dir):
        print(f"Error: Base directory for processed slides not found: {abs_processed_slides_base_dir}")
        print("Please run the processing script first or check the PROCESSED_SLIDES_BASE_DIR path.")
    else:
        print(f"Starting cleanup in: {abs_processed_slides_base_dir}")
        
        # Iterate through each item in the base directory
        # These items are expected to be the root_name directories (e.g., 'my_slide1')
        for slide_root_name in os.listdir(abs_processed_slides_base_dir):
            slide_dir_full_path = os.path.join(abs_processed_slides_base_dir, slide_root_name)
            if os.path.isdir(slide_dir_full_path):
                organize_slide_directory(slide_dir_full_path)
            else:
                print(f"  Skipping non-directory item: {slide_root_name}")
        
        print("\nCleanup process completed.")