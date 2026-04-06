import os
from abstract_utilities import (
    safe_read_from_json,
    safe_dump_to_json,
    make_list,
    get_any_value,
    capitalize,
)
from typing import Any, Dict, List, Optional
import json

CAPS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def split_caps(string: str) -> List[str]:
    """
    Split a string on capital letters, preserving order.

    Example:
        "uploadDate" -> ["upload", "date"]
    """
    parts = [""]
    for char in string:
        if char in CAPS:
            parts.append("")
        parts[-1] += char.lower()
    return [part for part in parts if part]


def make_underscore(string: str) -> str:
    """
    Convert CamelCase / mixedCase -> snake_case-ish.
    """
    parts = split_caps(string)
    return "_".join(parts).lower()


def get_all_string(strings: Any) -> List[str]:
    """
    Generate a list of variant key names for a given string or list of strings:
    - original
    - underscore version
    - Capitalized underscore version
    - split parts
    """
    strings = make_list(strings)
    all_strings: List[str] = []

    for s in strings:
        s = str(s)
        split_string = split_caps(s)
        underscore_str = make_underscore(s)
        capitalize_str = capitalize(underscore_str)
        all_strings.extend([s, underscore_str, capitalize_str] + split_string)

    return all_strings


def get_or_default(datas: List[Dict[str, Any]], keys: Any, default: Any) -> Any:
    """
    Try a list of keys across multiple dicts, with fuzzy/variant matching.
    - `datas`: list of dict-like objects
    - `keys`: a key or list of keys (e.g. "description" or ["uploader_id", "author"])
    - returns first non-empty value found, or default
    """
    keys = make_list(keys)

    # 1) direct hits first
    for data in datas:
        if not isinstance(data, dict):
            continue
        for key in keys:
            if not isinstance(key, str):
                continue
            value = data.get(key)
            if value not in (None, ""):
                return value

    # 2) fuzzy / variant search via get_any_value
    for key in keys:
        if not isinstance(key, str):
            continue
        for variant in get_all_string(key):
            for data in datas:
                if not isinstance(data, dict):
                    continue
                value = get_any_value(data, variant)
                # get_any_value might return list / None / scalar
                value = make_list(value or "")
                if value and value[0] not in (None, ""):
                    return value[0]

    return default


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_keywords(
    schema_keywords_raw: Any,
    info_keywords_raw: Any,
    meta_keywords_raw: Any,
) -> List[str]:
    """
    Normalize/merge keywords:
    1) Prefer schema_markup.keywords (array)
    2) Then info["keywords"]
    3) Then meta["keywords"] (string or list)
    """
    # schema: usually a list already
    schema_keywords = [
        str(kw).replace(" ", "_")
        for kw in make_list(schema_keywords_raw)
        if kw not in (None, "")
    ]

    # info keywords (can be list or comma-separated str)
    info_keywords: List[str] = []
    if isinstance(info_keywords_raw, str):
        info_keywords = [
            kw.strip()
            for kw in info_keywords_raw.split(",")
            if kw and kw.strip()
        ]
    else:
        info_keywords = [
            str(kw)
            for kw in make_list(info_keywords_raw)
            if kw not in (None, "")
        ]

    # meta keywords (your meta.json top-level "keywords" field)
    meta_keywords: List[str] = []
    if isinstance(meta_keywords_raw, str):
        meta_keywords = [
            kw.strip()
            for kw in meta_keywords_raw.split(",")
            if kw and kw.strip()
        ]
    else:
        meta_keywords = [
            str(kw)
            for kw in make_list(meta_keywords_raw)
            if kw not in (None, "")
        ]

    if schema_keywords:
        return schema_keywords
    if info_keywords:
        return info_keywords
    if meta_keywords:
        return meta_keywords

    return ["clownworld", "bolshevid"]


def derive_video_details(
    info_path,
    meta_path,
    response_data: Optional[Dict[str, Any]] = None,
    video_url: Optional[str] = None,
    source_video_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Derive video metadata + player config from:
      - info.json  (yt-dlp / raw info)
      - meta.json  (your SEO JSON used for the page)

    This is meant to produce the JSON payload that your React video player /
    <VideoDetails> component can consume.

    Fields returned:
      - keywords, keywords_str
      - title, description, upload_date
      - thumbnail, video_url, optimized_video_url, file_name
      - uploader, uploader_id, uploader_url
      - comment_count, repost_count, like_count, view_count, duration
      - webpage_url (for sharing/SEO)
    """
    # Core data sources
    info = safe_read_from_json(info_path) or {}
    info_data = safe_read_from_json(meta_path) or {}

    # Treat meta.json as your SEO dict directly
    seodata = info_data  # alias
    og = info_data.get("og", {}) or {}
    twitter = info_data.get("twitter", {}) or {}
    other = info_data.get("other", {}) or {}
    schema_markup = info_data.get("schema_markup", {}) or {}

    # Bundled list for get_or_default searches
    datas = [info, info_data, schema_markup, og, twitter, other]

    # 1) Normalize / pick keywords
    keywords_list = _normalize_keywords(
        schema_keywords_raw=schema_markup.get("keywords"),
        info_keywords_raw=info.get("keywords"),
        meta_keywords_raw=info_data.get("keywords"),
    )

    # 2) Keywords string with fallbacks
    keywords_str = (
        ",".join(keywords_list) if keywords_list else None
    ) or info.get("keywords_str") or info_data.get("keywords_str") or "#clownworld #bolshevid"

    # 3) Title / thumbnail
    title = (
        get_or_default(datas, "title", None)
        or seodata.get("title")
        or info.get("title")
        or "Untitled Video"
    )

    thumbnail = (
        schema_markup.get("thumbnailUrl")
        or info_data.get("thumbnail_resized_link")
        or info_data.get("thumbnail_link")
        or info_data.get("thumbnail")
        or (response_data or {}).get("thumbnail")
        or "https://clownworld.biz/imgs/no_image.jpg"
    )

    # 4) Page URL (for sharing + VideoDetails.webpageUrl)
    webpage_url = get_or_default(
        datas,
        ["canonical", "webpage_url", "original_url", "url"],
        "https://clownworld.biz",
    )

    # 5) Actual video stream URL(s)
    # Prefer explicit contentUrl/og.video
    content_url = get_or_default(
        datas,
        ["contentUrl", "video_url", "video"],
        None,
    )

    resolved_video_url = (
        content_url
        or video_url
        or source_video_url
    )

    optimized_video_url = (
        info.get("optimized_video_url")
        or info_data.get("optimized_video_url")
        or resolved_video_url  # fallback to main video URL
    )

    # 6) File name (on disk)
    file_name = (
        (response_data or {}).get("file_name")
        or info_data.get("file_name")
        or "video.mp4"
    )

    # 7) Text metadata
    description = get_or_default(
        datas,
        ["description", "description_html"],
        "Check out this video",
    )

    upload_date = get_or_default(
        datas,
        ["upload_date", "uploadDate"],
        "Unknown",
    )

    uploader = get_or_default(
        datas,
        ["uploader", "author"],
        "Unknown",
    )

    uploader_id = get_or_default(
        datas,
        ["uploader_id", "author_id"],
        "Unknown",
    )

    uploader_url = get_or_default(
        datas,
        ["uploader_url", "uploaderUrl"],
        "Unknown",
    )

    # 8) Numeric metadata
    comment_count = _coerce_int(
        get_or_default(datas, "comment_count", 0),
        default=0,
    )
    repost_count = _coerce_int(
        get_or_default(datas, "repost_count", 0),
        default=0,
    )
    like_count = _coerce_int(
        get_or_default(datas, "like_count", 0),
        default=0,
    )
    view_count = _coerce_int(
        get_or_default(datas, "view_count", 0),
        default=0,
    )

    duration_raw = get_or_default(
        datas,
        ["duration", "length_seconds"],
        100,
    )
    duration = _coerce_int(duration_raw, default=100)

    # Ensure keywords is a list
    keywords = make_list(keywords_list)
    keywords_str = ",".join(keywords)

    return {
        # SEO-ish
        "title": title,
        "description": description,
        "keywords": keywords,
        "keywords_str": keywords_str,
        "thumbnail": thumbnail,
        "upload_date": upload_date,
        "webpage_url": webpage_url,
        # Player URLs
        "video_url": resolved_video_url,
        "optimized_video_url": optimized_video_url,
        "file_name": file_name,
        # Uploader / social
        "uploader": uploader,
        "uploader_id": uploader_id,
        "uploader_url": uploader_url,
        # Counts
        "comment_count": comment_count,
        "repost_count": repost_count,
        "duration": duration,
        "like_count": like_count,
        "view_count": view_count,
    }


def build_page_json(directory,
    response_data: Optional[Dict[str, Any]] = None,
    video_url: Optional[str] = None,
    source_video_url: Optional[str] = None
                    ) -> Dict[str, Any]:
    """
    Combine SEO (meta.json) + player details (derived) into a single
    'json_page' object suitable for your React page.

    Structure:
    {
      "seo": {... contents of meta.json ...},
      "video": {... fields expected by your VideoDetails / player ...}
    }
    """
    info_path= os.path.join(directory,"info.json")
    meta_path= os.path.join(directory,"meta.json")
    page_path= os.path.join(directory,"page.json")
    seo_dict = safe_read_from_json(meta_path) or {}
    video_details = derive_video_details(
        info_path=info_path,
        meta_path=meta_path,
        response_data = response_data,
        video_url = video_url,
        source_video_url = source_video_url
        )

    page_json = {
        "seo": seo_dict,
        "video": video_details,
    }
    safe_dump_to_json(data=page_json, file_path=page_path)
    return page_json



