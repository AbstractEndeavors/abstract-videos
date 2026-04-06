import re
YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
DATA_SCHEMA = {
    "data_id": None,
    "url": None,
    "file_path": None,
    "info_path": "info.json",

    # text + metadata
    "text_path": "document.txt",
    "metadata_path": "metadata.json",
    "summary_path": "summary.txt",
    "keywords_path": "keywords.json",

    # optional audio/video derivatives
    "audio_path": "audio.wav",
    "speech_path": "speech.json",
    "preview_image": "preview.jpg",

    # aggregations
    "total_info_path": "total_info.json",
    "total_aggregated_path": "total_aggregated.json",

    # analysis
    "embeddings_path": "embeddings.npy",
    "entities_path": "entities.json",
    "topics_path": "topics.json",
}



# Full schema
VIDEO_SCHEMA = {
    "video_path": "video.mp4",
    "info_path": "info.json",
    "audio_path": "audio.wav",
    "whisper_path": "whisper.json",
    "captions_path": "captions.srt",
    "metadata_path": "metadata.json",
    "thumbnail_path": "thumb.jpg",
    "thumbnails_path": "thumbnails.json",
    "total_info_path": "total_info.json",
    "total_aggregated_path": "total_aggregated.json",
    "aggregated_directory": "aggregated",
    "aggregated_dir": {
        "aggregated_json_path": "aggregated.json",
        "aggregated_metadata_path": "aggregated_metadata.json",
        "best_clip_path": "best_clip.txt",
        "hashtags_path": "hashtags.txt",
    },
    "thumbnails_directory": "thumbnails",
    "thumbnails_dir": {
        "frames": "{video_id}_frame_{i}.jpg",  # pattern
    }
}
REMOVE_PHRASES = ['Video Converter', 'eeso', 'Auseesott', 'Aeseesott', 'esoft']
