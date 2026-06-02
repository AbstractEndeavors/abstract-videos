"""
Video API endpoints.

Thin, request-friendly wrappers around the videoDownloader ("download manager")
and `VideoPipeline` that the Flask blueprint registers as routes.

Each function accepts flexible keyword arguments coming straight from the
request body (``url`` / ``video_url`` / ``video_id`` / ``video_path`` …) and
returns a JSON-serializable result. Heavy pipeline imports are deferred to call
time so importing this module never requires whisper / hugpy / a model / the DB
to be present — only invoking an endpoint does.

Routing convention (see ``videos_bp.py``):
    get_video_info          -> registry/info lookup (download manager)
    get_video_download      -> download the file       (download manager)
    get_video_thumbnails    -> frame extraction + OCR   (pipeline)
    get_video_transcription -> whisper transcript       (pipeline)
    get_video_metadata      -> title/summary/keywords   (pipeline)
    get_video_seodata       -> SEO payload              (pipeline)
    get_all                 -> everything               (pipeline)
"""
import logging

logger = logging.getLogger("abstract_videos.api")

__all__ = [
    "get_video_info",
    "get_video_download",
    "get_video_thumbnails",
    "get_video_transcription",
    "get_video_metadata",
    "get_video_seodata",
    "get_all",
]


# ── helpers ────────────────────────────────────────────────────────────────

def _source(url=None, video_url=None, video_id=None, video_path=None, **_):
    """Return the first usable source identifier, or raise if none given."""
    src = url or video_url or video_id or video_path
    if not src:
        raise ValueError(
            "one of url, video_url, video_id, or video_path is required"
        )
    return src


def _build_pipeline(url=None, video_url=None, video_path=None,
                    force_refresh=False, whisper_model=None,
                    videos_root=None, documents_root=None, **_ignored):
    """Construct a VideoPipeline from request kwargs (lazy import)."""
    from ..video_pipeline import VideoPipeline
    return VideoPipeline(
        video_url=url or video_url,
        video_path=video_path,
        force_refresh=bool(force_refresh),
        whisper_model=whisper_model,
        videos_root=videos_root,
        documents_root=documents_root,
    )


def _error(name, exc):
    # Missing/invalid input is a client error — log quietly, no stack trace.
    if isinstance(exc, ValueError):
        logger.info("%s: %s", name, exc)
    else:
        logger.exception("%s failed", name)
    return {"ok": False, "error": str(exc)}


# ── endpoints ──────────────────────────────────────────────────────────────

def get_video_info(url=None, video_url=None, video_id=None, video_path=None,
                   force_refresh=False, video_root=None, **kwargs):
    """Registry-backed info lookup. Cheap — never loads the whisper model."""
    try:
        _source(url=url, video_url=video_url, video_id=video_id,
                video_path=video_path)
        # A bare video_id can be answered straight from the record store.
        if video_id and not (url or video_url or video_path):
            from ..videoDownloader import get_video_record
            return get_video_record(video_id, hide_audio=True) or {}
        from ..videoDownloader.utils import get_video_info as dl_get_video_info
        return dl_get_video_info(
            url=url or video_url,
            video_url=video_url,
            video_id=video_id,
            video_path=video_path,
            video_root=video_root,
            force_refresh=bool(force_refresh),
        ) or {}
    except Exception as e:
        return _error("get_video_info", e)


def get_video_download(url=None, video_url=None, video_id=None, video_path=None,
                       force_refresh=False, video_root=None,
                       output_filename=None, **kwargs):
    """Download the media file via the download manager. Returns its info."""
    try:
        _source(url=url, video_url=video_url, video_id=video_id,
                video_path=video_path)
        from ..videoDownloader.videoDownloader import download_video
        info = download_video(
            url=url or video_url,
            video_url=video_url,
            video_path=video_path,
            download_directory=video_root,
            output_filename=output_filename,
            download_video=True,
            force_refresh=bool(force_refresh),
        )
        return info or {}
    except Exception as e:
        return _error("get_video_download", e)


def get_video_thumbnails(**kwargs):
    """Extract + OCR thumbnail frames (pipeline)."""
    try:
        _source(**kwargs)
        return _build_pipeline(**kwargs).get_thumbnails()
    except Exception as e:
        return _error("get_video_thumbnails", e)


def get_video_transcription(**kwargs):
    """Whisper transcription result (pipeline)."""
    try:
        _source(**kwargs)
        return _build_pipeline(**kwargs).get_whisper()
    except Exception as e:
        return _error("get_video_transcription", e)


def get_video_metadata(**kwargs):
    """Derived title / summary / keywords / category (pipeline)."""
    try:
        _source(**kwargs)
        return _build_pipeline(**kwargs).get_metadata()
    except Exception as e:
        return _error("get_video_metadata", e)


def get_video_seodata(**kwargs):
    """SEO payload (pipeline)."""
    try:
        _source(**kwargs)
        return _build_pipeline(**kwargs).get_seodata()
    except Exception as e:
        return _error("get_video_seodata", e)


def get_all(**kwargs):
    """Full pipeline: info, transcript, captions, metadata, thumbnails, seo."""
    try:
        _source(**kwargs)
        return _build_pipeline(**kwargs).get_all()
    except Exception as e:
        return _error("get_all", e)
