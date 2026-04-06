from ..imports import *
from ..functions import *
from ..functions.utils.main_utils import *
from ..functions.utils.compatability_utils import *
from ..config import *
# src/pipeline.py
from .utilities import *
from ..videoDownloader import infoRegistry, VideoDownloader, get_video_record,StorageConfig

from ..aggregate import *

def get_yt_dlp_opts(js_runtime: str | None = None) -> dict:
    runtime = (
        js_runtime
        or os.getenv("YT_DLP_JS_RUNTIME")
        or _detect_js_runtime()
    )
    opts = {}
    if runtime:
        opts["extractor_args"] = {"youtube": {"js_runtimes": [runtime]}}
    return opts


def _detect_js_runtime() -> str | None:
    for rt in ("deno", "node", "nodejs"):
        if shutil.which(rt):
            return rt
    return None


def get_thumbnails(video_id: str, video_path: str, thumbnails_path: str):
    paths = extract_video_frames_unique(video_path, thumbnails_path)
    texts = [ocr_image(p) for p in paths]
    thumbnails = {"paths": paths, "texts": texts}
    upsert_video(video_id, thumbnails=thumbnails)
    return thumbnails
