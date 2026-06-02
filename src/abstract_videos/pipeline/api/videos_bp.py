"""
Flask blueprint for the video API.

Register it on your app, e.g.:

    from abstract_videos.pipeline.api.videos_bp import videos_bp
    app.register_blueprint(videos_bp, url_prefix="/api/video")

The view functions are the thin wrappers in ``video_endpoints`` and are
exported from the top-level package, so ``from abstract_videos import *``
brings them into scope. ``register_categories`` (from abstract_flask) turns
each entry into a route that parses the request body and JSON-encodes the
return value.
"""
from abstract_videos import *
from abstract_flask import *

videos_bp, logger = get_bp("videos_bp", __name__)

videos_funcs = {
    "videos": {
        "get_video_info": get_video_info,
        "get_video_download": get_video_download,
        "get_video_thumbnails": get_video_thumbnails,
        "get_video_transcription": get_video_transcription,
        "get_video_metadata": get_video_metadata,
        "get_video_seodata": get_video_seodata,
        "get_all": get_all,
    }
}

register_categories(videos_bp, videos_funcs)
