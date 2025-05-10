import openslide
from PIL import Image
import os
import glob
import json
import subprocess
import re # For regular expression parsing

# --- Configuration ---
SVS_INPUT_DIR = "."
MAIN_OUTPUT_DIR = "processed_slides_output"
MAX_DIM_FOR_FULL_PNG = 8000

# --- Helper Functions ---
def save_pil_image_as_png(pil_image, output_path):
    """Saves a PIL image as PNG, converting RGBA/P to RGB if necessary."""
    try:
        current_mode = pil_image.mode
        if pil_image.mode == 'RGBA':
            pil_image = pil_image.convert('RGB')
        elif pil_image.mode == 'P':
            pil_image = pil_image.convert('RGB')
        elif pil_image.mode not in ['RGB', 'L']:
            print(f"    Image mode is {current_mode}, attempting to convert to RGB for {os.path.basename(output_path)}")
            try:
                pil_image = pil_image.convert('RGB')
            except Exception as conv_e:
                print(f"      Could not convert {current_mode} to RGB: {conv_e}. Skipping save for this image.")
                return False
        pil_image.save(output_path, "PNG")
        print(f"    Successfully saved: {os.path.basename(output_path)}")
        return True
    except Exception as e:
        print(f"    Error saving image {os.path.basename(output_path)}: {e}")
        return False

def parse_tiffinfo_output(tiffinfo_text):
    """
    Parses the text output of tiffinfo into a structured dictionary (list of IFDs).
    This is a simplified parser and might need adjustments for complex TIFFs.
    """
    ifds_data = []
    current_ifd_data = {}
    current_ifd_index = -1

    # Regex to find "TagName: Value" lines, allowing for spaces around colon
    # and capturing tag name and value separately.
    # It also tries to capture multi-word tag names.
    tag_value_re = re.compile(r"^\s*([\w\s]+)\s*:\s*(.*)")
    ifd_header_re = re.compile(r"IFD #(\d+) \((0x[\da-fA-F]+)\)") # e.g., IFD #0 (0x2780)

    lines = tiffinfo_text.splitlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        ifd_match = ifd_header_re.match(line)
        if ifd_match:
            if current_ifd_data: # Save previous IFD data if it exists
                ifds_data.append(current_ifd_data)
            
            current_ifd_index = int(ifd_match.group(1))
            current_ifd_data = {"ifd_index": current_ifd_index, "offset_hex": ifd_match.group(2)}
            continue

        tag_match = tag_value_re.match(line)
        if tag_match:
            tag_name = tag_match.group(1).strip()
            tag_value_str = tag_match.group(2).strip()

            # Attempt to convert common value types
            # This is very basic; more sophisticated type inference could be added
            if tag_value_str.lower() == "true":
                tag_value = True
            elif tag_value_str.lower() == "false":
                tag_value = False
            elif tag_value_str.isdigit():
                tag_value = int(tag_value_str)
            else:
                try:
                    tag_value = float(tag_value_str)
                except ValueError:
                    tag_value = tag_value_str # Keep as string if not clearly number/boolean

            # Handle potential duplicate tag names within an IFD (less common but possible)
            # by making the value a list if the key already exists
            if tag_name in current_ifd_data:
                if isinstance(current_ifd_data[tag_name], list):
                    current_ifd_data[tag_name].append(tag_value)
                else:
                    current_ifd_data[tag_name] = [current_ifd_data[tag_name], tag_value]
            else:
                current_ifd_data[tag_name] = tag_value
        # else:
            # Line doesn't match IFD header or tag:value, could be continuation or other info
            # print(f"      [tiffinfo_parser] Unmatched line: {line}") # For debugging

    if current_ifd_data: # Append the last IFD
        ifds_data.append(current_ifd_data)
    
    # If no IFDs were explicitly found (e.g. very simple TIFF or different tiffinfo format)
    # treat all found tags as part of a single, implicit IFD 0.
    if not ifds_data and current_ifd_data and "ifd_index" not in current_ifd_data:
         # This case happens if tiffinfo output doesn't have clear "IFD #" lines
         # but just lists tags. We'll assume a single IFD.
        all_tags_as_ifd0 = {}
        for line_again in lines: # Re-parse without IFD context
            tag_match_again = tag_value_re.match(line_again.strip())
            if tag_match_again:
                tag_name = tag_match_again.group(1).strip()
                tag_value_str = tag_match_again.group(2).strip()
                if tag_value_str.isdigit(): tag_value = int(tag_value_str)
                else: tag_value = tag_value_str
                all_tags_as_ifd0[tag_name] = tag_value
        if all_tags_as_ifd0:
             ifds_data.append({"ifd_index": 0, **all_tags_as_ifd0})


    # For SVS, Aperio-specific metadata is often outside standard IFDs
    # It might be at the top. We can try to capture that too.
    # This part is highly experimental and depends on tiffinfo version and SVS specifics
    header_info = {}
    first_ifd_started = False
    for line in lines:
        line = line.strip()
        if ifd_header_re.match(line):
            first_ifd_started = True
            break
        if not first_ifd_started:
            tag_match = tag_value_re.match(line)
            if tag_match:
                tag_name = tag_match.group(1).strip()
                tag_value_str = tag_match.group(2).strip()
                header_info[tag_name] = tag_value_str # Keep as string

    # Combine header_info with the IFD list, or return IFD list if no separate header
    if header_info and ifds_data:
        return {"header": header_info, "ifds": ifds_data}
    elif ifds_data:
        return {"ifds": ifds_data}
    elif header_info: # Only header found, no clear IFDs
        return {"header": header_info}
    else:
        return {"raw_output": tiffinfo_text, "parsing_notes": "Could not parse into structured IFDs or header."}


def run_system_command(command_list, working_dir=None, capture_stdout=True):
    """
    Runs a system command and returns its stdout, stderr, and return code.
    If capture_stdout is False, stdout is not captured (e.g., for tiffsplit).
    """
    print(f"    Executing: {' '.join(command_list)}")
    try:
        process = subprocess.run(
            command_list,
            cwd=working_dir,
            capture_output=capture_stdout, # Only capture if needed
            text=True,
            check=False
        )
        return process.stdout if capture_stdout else None, process.stderr, process.returncode
    except FileNotFoundError:
        print(f"      Error: Command '{command_list[0]}' not found. Ensure it's installed and in PATH.")
        return None, f"Command '{command_list[0]}' not found.", -1 # Indicate error
    except Exception as e:
        print(f"      Error executing command: {e}")
        return None, str(e), -1 # Indicate error

# --- Main Processing Function ---
def process_svs_file(svs_file_path, base_output_dir):
    print(f"\n--- Processing SVS file: {svs_file_path} ---")
    original_svs_abs_path = os.path.abspath(svs_file_path)

    try:
        root_name = os.path.splitext(os.path.basename(svs_file_path))[0]
        slide_output_dir = os.path.join(base_output_dir, root_name)
        os.makedirs(slide_output_dir, exist_ok=True)
        print(f"  Output directory: {slide_output_dir}")

        slide = openslide.OpenSlide(svs_file_path)

        # 1. Save OpenSlide properties as JSON
        openslide_json_path = os.path.join(slide_output_dir, f"{root_name}_openslide_properties.json")
        print(f"\n  1. Saving OpenSlide metadata...")
        try:
            serializable_properties = {k: (str(v) if not isinstance(v, (str, int, float, bool, list, dict, type(None))) else v) for k, v in slide.properties.items()}
            with open(openslide_json_path, 'w') as f: json.dump(serializable_properties, f, indent=4)
            print(f"    Saved OpenSlide metadata to: {os.path.basename(openslide_json_path)}")
        except Exception as e: print(f"    Error saving OpenSlide metadata JSON: {e}")

        # 2. Save Associated Images
        print(f"\n  2. Saving associated images (from OpenSlide)...")
        if slide.associated_images:
            for name, assoc_img_pil in slide.associated_images.items():
                safe_name = "".join(c if c.isalnum() or c in ['_','-'] else "_" for c in name)
                assoc_output_path = os.path.join(slide_output_dir, f"{root_name}_associated_{safe_name}.png")
                print(f"    Attempting to save '{name}'...")
                save_pil_image_as_png(assoc_img_pil, assoc_output_path)
        else: print("    No associated images found by OpenSlide.")

        # 3. Save pyramid levels as PNGs
        print(f"\n  3. Saving pyramid levels as PNGs (from OpenSlide)...")
        for level in range(slide.level_count):
            level_dims = slide.level_dimensions[level]
            print(f"\n    Processing Level {level}: Dimensions: {level_dims}")
            if level_dims[0] == 0 or level_dims[1] == 0: print(f"      Skipping Level {level}, zero dimension."); continue
            
            png_filename = f"{root_name}_level_{level}_dims_{level_dims[0]}x{level_dims[1]}.png"
            output_path = os.path.join(slide_output_dir, png_filename)

            if level_dims[0] > MAX_DIM_FOR_FULL_PNG or level_dims[1] > MAX_DIM_FOR_FULL_PNG:
                print(f"      Level {level} too large. Skipping direct save of full level."); continue
            try:
                print(f"      Reading full level {level} data...")
                img_pil = slide.read_region(location=(0, 0), level=level, size=level_dims)
                save_pil_image_as_png(img_pil, output_path)
            except Exception as e: print(f"      Error processing level {level}: {e}")
        
        slide.close()

        # 4. Run tiffinfo and save output as JSON
        print(f"\n  4. Running tiffinfo and saving as JSON...")
        tiffinfo_json_path = os.path.join(slide_output_dir, f"{root_name}_tiffinfo_header.json")
        tiffinfo_command = ["tiffinfo", original_svs_abs_path]
        
        stdout, stderr, returncode = run_system_command(tiffinfo_command, capture_stdout=True)

        if returncode == 0 and stdout:
            print(f"      tiffinfo command successful. Parsing output...")
            parsed_tiff_data = parse_tiffinfo_output(stdout)
            try:
                with open(tiffinfo_json_path, 'w') as f:
                    json.dump(parsed_tiff_data, f, indent=4)
                print(f"      tiffinfo data saved to: {os.path.basename(tiffinfo_json_path)}")
            except Exception as e:
                print(f"      Error saving parsed tiffinfo to JSON: {e}")
                # Save raw output as fallback
                with open(os.path.join(slide_output_dir, f"{root_name}_tiffinfo_header_raw.txt"), 'w') as f_raw:
                    f_raw.write(stdout)
                print(f"      Raw tiffinfo output saved to _raw.txt instead.")
        else:
            print(f"      tiffinfo command failed or produced no output.")
            if stderr: print(f"      Stderr:\n{stderr.strip()}")
            if stdout: print(f"      Stdout (if any):\n{stdout.strip()}")


        # 5. Run tiffsplit
        print(f"\n  5. Running tiffsplit...")
        tiffsplit_prefix = os.path.join(slide_output_dir, f"{root_name}_tiffsplit_")
        tiffsplit_command = ["tiffsplit", original_svs_abs_path, tiffsplit_prefix]
        
        _, stderr_ts, returncode_ts = run_system_command(tiffsplit_command, capture_stdout=False) # No need to capture tiffsplit stdout

        if returncode_ts == 0:
            print(f"      tiffsplit command successful.")
        else:
            print(f"      tiffsplit command failed with return code {returncode_ts}.")
            if stderr_ts: print(f"      Stderr:\n{stderr_ts.strip()}")

        print(f"--- Finished processing {svs_file_path} ---")

    except openslide.OpenSlideError as e: print(f"OpenSlide Error for {svs_file_path}: {e}")
    except FileNotFoundError as e: print(f"File Not Found Error for {svs_file_path}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred with {svs_file_path}: {e}")
        import traceback
        traceback.print_exc()

# --- Main script execution ---
if __name__ == "__main__":
    abs_svs_input_dir = os.path.abspath(SVS_INPUT_DIR)
    abs_main_output_dir = os.path.abspath(MAIN_OUTPUT_DIR)
    os.makedirs(abs_main_output_dir, exist_ok=True)

    svs_files = glob.glob(os.path.join(abs_svs_input_dir, "*.svs"))
    
    if not svs_files:
        print(f"No .svs files found in: {abs_svs_input_dir}")
    else:
        print(f"Found {len(svs_files)} SVS files from: {abs_svs_input_dir}")
        print(f"Output to subdirectories under: {abs_main_output_dir}")
        for svs_file_path in svs_files:
            process_svs_file(svs_file_path, abs_main_output_dir)
    
    print("\nAll SVS files processing attempted.")