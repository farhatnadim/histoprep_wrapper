import os
import glob
import shutil

# --- Configuration ---
# This should be the SAME as MAIN_OUTPUT_DIR from your processing script
# and PROCESSED_SLIDES_BASE_DIR from your cleanup script
PROCESSED_SLIDES_BASE_DIR = "processed_slides_output"
FINAL_EXPORT_DIR_BASE = "final_export_data" # New base directory for exported clean files

def export_clean_files_for_subject(subject_processed_dir, export_base_dir):
    """
    Copies files from the 'clean' subdirectory of a subject's processed folder
    to a new subject-specific directory in the export_base_dir.
    """
    subject_name = os.path.basename(subject_processed_dir)
    clean_source_dir = os.path.join(subject_processed_dir, "clean")

    if not os.path.isdir(clean_source_dir):
        print(f"  - No 'clean' directory found for subject '{subject_name}' in {subject_processed_dir}. Skipping.")
        return

    subject_export_target_dir = os.path.join(export_base_dir, subject_name)
    os.makedirs(subject_export_target_dir, exist_ok=True)

    print(f"  + Exporting clean files for subject '{subject_name}':")
    print(f"    From: {clean_source_dir}")
    print(f"    To:   {subject_export_target_dir}")

    copied_count = 0
    failed_count = 0
    for item_name in os.listdir(clean_source_dir):
        source_item_path = os.path.join(clean_source_dir, item_name)
        target_item_path = os.path.join(subject_export_target_dir, item_name)

        if os.path.isfile(source_item_path):
            try:
                # print(f"      Copying: {item_name}")
                shutil.copy2(source_item_path, target_item_path) # copy2 preserves more metadata
                copied_count += 1
            except Exception as e:
                print(f"      ERROR copying file {item_name}: {e}")
                failed_count += 1
        # Optionally, handle directories within 'clean' if necessary, though typically it's just files
        # elif os.path.isdir(source_item_path):
        #     print(f"      Skipping directory within clean: {item_name}")
        #     pass

    print(f"    Finished exporting for '{subject_name}'. Copied: {copied_count} files, Failed: {failed_count} files.")


# --- Main script execution ---
if __name__ == "__main__":
    abs_processed_slides_base_dir = os.path.abspath(PROCESSED_SLIDES_BASE_DIR)
    abs_final_export_dir_base = os.path.abspath(FINAL_EXPORT_DIR_BASE)

    if not os.path.isdir(abs_processed_slides_base_dir):
        print(f"Error: Base directory for processed slides not found: {abs_processed_slides_base_dir}")
        print("Please ensure the processing and cleanup scripts have run correctly or check the path.")
    else:
        print(f"Starting export of clean files from: {abs_processed_slides_base_dir}")
        print(f"Exporting to: {abs_final_export_dir_base}")
        os.makedirs(abs_final_export_dir_base, exist_ok=True) # Create the main export directory

        # Iterate through each item in the base directory of processed slides
        # These items are expected to be the subject/slide root_name directories
        subjects_processed = 0
        for subject_dir_name in os.listdir(abs_processed_slides_base_dir):
            subject_processed_full_path = os.path.join(abs_processed_slides_base_dir, subject_dir_name)
            if os.path.isdir(subject_processed_full_path):
                export_clean_files_for_subject(subject_processed_full_path, abs_final_export_dir_base)
                subjects_processed +=1
            else:
                print(f"  Skipping non-directory item in processed base: {subject_dir_name}")
        
        if subjects_processed > 0:
            print(f"\nExport process completed for {subjects_processed} subjects.")
        else:
            print(f"\nNo subject directories found to process in {abs_processed_slides_base_dir}.")