import os
import shutil
import tempfile
import subprocess
import json
import argparse
from .main_utils import handle_output_option, create_unique_filename

def is_video_optimized(input_file):
    """
    Checks if the video is already optimized for Safari.
    Returns True if the video has faststart and compatible codecs.
    """
    try:
        # Check moov atom position and codecs using ffprobe
        probe_command = [
            "ffprobe", "-v", "quiet", "-print_format", "json", 
            "-show_format", "-show_streams", input_file
        ]
        result = subprocess.run(probe_command, capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)

        # Check if moov atom is at the start (faststart)
        format_info = metadata.get("format", {})
        is_faststart = format_info.get("format_name", "").find("ismv") != -1 or \
                       format_info.get("tags", {}).get("major_brand", "").find("isom") != -1

        # Check video codec (should be h264)
        video_stream = next((s for s in metadata.get("streams", []) if s["codec_type"] == "video"), None)
        is_h264 = video_stream and video_stream.get("codec_name") == "h264"

        # Check audio codec (should be aac)
        audio_stream = next((s for s in metadata.get("streams", []) if s["codec_type"] == "audio"), None)
        is_aac = audio_stream and audio_stream.get("codec_name") == "aac"

        # Check pixel format and profile
        is_yuv420p = video_stream and video_stream.get("pix_fmt") == "yuv420p"
        is_baseline = video_stream and video_stream.get("profile", "").lower() in ["baseline", "main"]

        return is_faststart and is_h264 and is_aac and is_yuv420p and is_baseline
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error probing video: {e}")
        return False


def is_video_optimized(input_file):
    try:
        probe_command = [
            "ffprobe", "-v", "quiet", "-print_format", "json", 
            "-show_format", "-show_streams", input_file
        ]
        result = subprocess.run(probe_command, capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)
        format_info = metadata.get("format", {})
        is_faststart = format_info.get("format_name", "").find("ismv") != -1 or \
                       format_info.get("tags", {}).get("major_brand", "").find("isom") != -1
        video_stream = next((s for s in metadata.get("streams", []) if s["codec_type"] == "video"), None)
        is_h264 = video_stream and video_stream.get("codec_name") == "h264"
        audio_stream = next((s for s in metadata.get("streams", []) if s["codec_type"] == "audio"), None)
        is_aac = audio_stream and audio_stream.get("codec_name") == "aac"
        is_yuv420p = video_stream and video_stream.get("pix_fmt") == "yuv420p"
        is_baseline = video_stream and video_stream.get("profile", "").lower() in ["baseline", "main"]
        return is_faststart and is_h264 and is_aac and is_yuv420p and is_baseline
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error probing video: {e}")
        return False

def optimize_video_for_safari(input_file, output_option="copy", output_path=None, reencode=False):
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file {input_file} does not exist")
    
    # Debug input parameters
    print(f"optimize_video_for_safari: input_file={input_file}, output_option={output_option}, output_path={output_path}, reencode={reencode}")
    
    # Ensure output_path is unique and uses .mp4
    if output_path is None or output_path == input_file:
        output_path = create_unique_filename(input_file.replace(".flv", ".mp4"))
        output_option = "copy"
    
    # Force reencode for .flv files
    if input_file.lower().endswith('.flv'):
        print(f"Forcing reencode for .flv input: {input_file}")
        reencode = True

    if not reencode and is_video_optimized(input_file):
        print(f"Video {input_file} is already optimized for Safari. Skipping processing.")
        return input_file

    tmp_dir = tempfile.mkdtemp()
    try:
        local_input = os.path.join(tmp_dir, os.path.basename(input_file))
        shutil.copy2(input_file, local_input)
        
        # Ensure output is .mp4
        base, _ = os.path.splitext(local_input)
        local_output = f"{base}_optimized.mp4"

        # Build ffmpeg command
        if reencode:
            command = [
                "ffmpeg", "-i", local_input,
                "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.0", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "faststart",
                local_output
            ]
        else:
            command = [
                "ffmpeg", "-i", local_input,
                "-c", "copy", "-movflags", "faststart",
                local_output
            ]

        # Run ffmpeg command
        print(f"Running ffmpeg command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")

        # Verify local_output exists
        if not os.path.exists(local_output):
            raise FileNotFoundError(f"ffmpeg did not create output file: {local_output}")

        # Log temporary directory contents
        print(f"Temporary directory contents: {os.listdir(tmp_dir)}")
        
        final_output = handle_output_option(input_file,local_output, output_path, output_option)
        return final_output
    except Exception as e:
        print(f"Error during optimization: {e}")
        raise
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
