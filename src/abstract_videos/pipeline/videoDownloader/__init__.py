from .infoRegistry import infoRegistry
from .videoDownloader import *

# Self-contained, dependency-light downloader. Guarded so that importing the
# package never fails just because an optional heavy dependency is missing.
try:
    from .simple_downloader import (
        SimpleVideoDownloader,
        download_video as simple_download_video,
        download_videos as simple_download_videos,
        get_video_info as simple_get_video_info,
        check_dependencies,
        DownloadError,
    )
except Exception:  # pragma: no cover - defensive
    pass
