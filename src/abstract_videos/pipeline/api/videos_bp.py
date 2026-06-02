"""
Flask blueprint for the video API.

Register it on your app under the prefix the frontend expects:

    from abstract_videos.pipeline.api.videos_bp import videos_bp
    app.register_blueprint(videos_bp, url_prefix="/api/video")

That makes the clownworld frontend's call resolve exactly:
    POST https://clownworld.biz/api/video/get_pipeline_data
        body: { "key": "player", "video_url": "...", "video_id": "..." }

Two ways to call the API are exposed:

1. The single ``/get_pipeline_data`` route — what the frontend uses. It reads a
   ``key`` from the body and dispatches to the right operation, returning
   ``{"result": <data>}`` (the shape the frontend reads via ``raw?.result ?? raw``).
2. The per-operation named routes registered by ``register_categories`` — handy
   for direct/manual calls.
"""
from abstract_videos import *
from abstract_flask import *
from flask import request, jsonify

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


def _request_payload():
    """Robustly merge JSON body + form/query params into one dict."""
    data = {}
    try:
        if request.is_json:
            data.update(request.get_json(silent=True) or {})
    except Exception:
        pass
    try:
        for k, v in request.values.items():
            data.setdefault(k, v)
    except Exception:
        pass
    return data


@videos_bp.route("/get_pipeline_data", methods=["POST", "GET"])
def get_pipeline_data_route():
    """Single entry point the frontend calls; `key` selects the operation."""
    data = _request_payload()
    key = data.pop("key", None)
    result = get_pipeline_data(key=key, **data)
    return jsonify({"result": result})
