from ...imports import *

def if_none_get_default(obj=None,default=None):
    if obj == None:
        obj = default
    return obj
def compute_file_hash(file_path, chunk_size=8192):
    """
    Compute MD5 hash of the file content.
    """
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def find_duplicate_video(new_video_path, complete_video_directory):
    """
    Checks if there is an existing video in complete_video_directory
    with the same hash as new_video_path.
    Returns the path to the duplicate if found; otherwise, returns None.
    """
    new_video_hash = compute_file_hash(new_video_path)
    for root, dirs, files in os.walk(complete_video_directory):
        for file in files:
            if file.lower().endswith(('.mp4', '.webm', '.mkv', '.avi')):
                existing_video_path = os.path.join(root, file)
                # Skip comparing the file with itself if found in the same directory
                if os.path.abspath(existing_video_path) == os.path.abspath(new_video_path):
                    continue
                if compute_file_hash(existing_video_path) == new_video_hash:
                    return existing_video_path
    return None
def get_video_metadata(file_path):
    video = mp.VideoFileClip(file_path)
    
    metadata = {
        'resolution': f"{video.w}x{video.h}",
        'format': 'MP4',
        'file_size_mb': os.path.getsize(file_path) / (1024 * 1024)
    }
    
    video.close()
    return metadata
def generate_file_id(path: str, max_length: int = 50) -> str:
    base = os.path.splitext(os.path.basename(path))[0]
    base = unicodedata.normalize('NFKD', base).encode('ascii', 'ignore').decode('ascii')
    base = base.lower()
    base = re.sub(r'[^a-z0-9]+', '-', base).strip('-')
    base = re.sub(r'-{2,}', '-', base)
    if len(base) > max_length:
        h = hashlib.sha1(base.encode()).hexdigest()[:8]
        base = base[: max_length - len(h) - 1].rstrip('-') + '-' + h
    return base
def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^a-zA-Z0-9\s:.,-]', '', text)
    text = text.strip()
    return text
def get_frame_number(file_path):
    file_path = '.'.join(file_path.split('.')[:-1])
    return int(file_path.split('_')[-1])
def sort_frames(frames=None,directory=None):
    if frames in [None,[]] and directory and os.path.isdir(directory):
        frames = get_all_file_types(types=['image'],directory=directory)
    frames = frames or []
    frames = sorted(
        frames,
        key=lambda x: get_frame_number(x) 
    )
    return frames
def handle_output_option(input_file, local_output, output_path, output_option):
    if not os.path.exists(local_output):
        raise FileNotFoundError(f"Temporary output file {local_output} does not exist")
    
    # Ensure output_path uses .mp4 if input was .flv
    if input_file.lower().endswith('.flv') and output_path and not output_path.lower().endswith('.mp4'):
        output_path = os.path.splitext(output_path)[0] + '.mp4'

    if output_option == "overwrite":
        final_output = input_file
        shutil.move(local_output, final_output)
        print(f"Optimized video saved as {final_output}")
    elif output_option == "rename":
        if output_path:
            final_output = output_path
        else:
            base, _ = os.path.splitext(input_file)
            final_output = f"{base}_optimized.mp4"  # Force .mp4
        shutil.move(local_output, final_output)
        print(f"Optimized video saved as {final_output}")
    elif output_option == "copy":
        if not output_path:
            raise ValueError("output_path must be specified for 'copy' option")
        final_output = output_path
        shutil.move(local_output, final_output)
        print(f"Optimized video saved as {final_output}")
    else:
        raise ValueError("Invalid output_option. Use 'overwrite', 'rename', or 'copy'")
    return final_output
def get_video_exts():
    return list(MIME_TYPES.get('video').keys()) or []

def extract_filename(item):
    if not item:
        return None
    ext=extract_ext(item)
    if ext:
        item = item[:-len(ext)]
    return item
def extract_ext(item):
    if not item:
        return
    for ext in get_video_exts():
        if item.endswith(ext):
            return ext
def extract_filename_ext(item=None):
    if not item:
        return None,None
    ext = extract_ext(item)
    filename = extract_filename(item)
    return filename,ext
def create_unique_filename(item):
    dirname = os.path.dirname(item)
    basename = os.path.basename(item)
    filename, ext = extract_filename_ext(basename)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    new_basename = f"{filename}_{timestamp}{ext}"
    return os.path.join(dirname, new_basename)
def get_path(path,output_dir=None,output_path=None,new_filename=None):
    if output_path:
        return output_path
    original_dirname=os.path.dirname(path)
    original_basename=os.path.basename(path)
    original_filename,original_ext = extract_filename_ext(original_basename)
    dirname = output_dir or original_dirname
    new_filename,new_ext = extract_filename_ext(new_filename)
    ext = new_ext or original_ext
    filename = new_filename or original_filename
    return os.path.join(dirname,f"{filename}{ext}")

def bool_or_default(obj,default=True):
    if obj == None:
        obj =  default
    return obj


def get_video_url(url=None, video_url=None):
    video_url = url or video_url
    if video_url:
        video_url = get_corrected_url(video_url)
    return video_url

def return_num_str(obj):
    return int(obj) if is_number(obj) else obj
