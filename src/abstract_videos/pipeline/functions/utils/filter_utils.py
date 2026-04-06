from ...imports import *
from abstract_utilities import (
    safe_read_from_json,
    safe_dump_to_json,
    make_list,
    get_any_value,
    capitalize,
    eatAll,
    get_closest_match_from_list
)

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


def get_key_tree(data: Dict[str, Any]) -> Dict[str, Any]:
    branch: Dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            branch[key] = get_key_tree(value)
        else:
            branch[key] = None
    return branch


def get_key_paths(data: Dict[str, Any], prefix: str = "", paths: Optional[List[str]] = None) -> List[str]:
    if paths is None:
        paths = []
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        paths.append(path)
        if isinstance(value, dict):
            get_key_paths(value, path, paths)
    return paths


def get_all_keys(data: Any, out: Optional[Dict[str, List[str]]] = None) -> Dict[str, List[str]]:
    if out is None:
        out = {}

    if not isinstance(data, dict):
        return out

    for key, value in data.items():
        if isinstance(value, dict):
            out[key] = list(value.keys())
            get_all_keys(value, out)

    return out


def search_keys_nested(data: Any, query: str, path: Optional[List[str]] = None,
                       results: Optional[Dict[str, List[str]]] = None) -> Dict[str, List[str]]:
    """
    Search all dictionary keys (recursively) for matches to `query`
    and categorize results by the branch where they occur.

    Returns:
        {
            "a.b.c": ["matching_key1", "matching_key2"],
            ...
        }
    """
    if results is None:
        results = {}

    if path is None:
        path = []

    if not isinstance(data, dict):
        return results

    for key, value in data.items():
        current_path = path + [key]

        # Check if key matches the search text
        if query.lower() in key.lower():
            branch = ".".join(path) or "<root>"
            results.setdefault(branch, []).append(key)

        # Recurse into dicts
        if isinstance(value, dict):
            search_keys_nested(value, query, current_path, results)

        # Recurse into lists of dicts
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                if isinstance(item, dict):
                    list_path = current_path + [f"[{idx}]"]
                    search_keys_nested(item, query, list_path, results)

    return results


def get_by_path(data: Any, path: str) -> Any:
    """
    Resolve a dotted / list-indexed path such as 'a.b[0].c'
    and return the corresponding data value.
    """

    # Break "a.b[0].c" into tokens: ["a", "b", 0, "c"]
    tokens: List[Any] = []
    for part in path.split("."):
        # split off list indexes like "formats[0][1]"
        m = re.findall(r"[^\[\]]+|\[\d+\]", part)
        for seg in m:
            if seg.startswith("[") and seg.endswith("]"):
                idx = int(seg[1:-1])
                tokens.append(idx)
            else:
                tokens.append(seg)

    current = data
    for tok in tokens:
        if isinstance(tok, int):
            current = current[tok]
        else:
            if not isinstance(current, dict):
                return None
            current = current.get(tok)
            if current is None:
                return None
    return current


def get_key_from_dict(comp_key: str, dict_obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Fuzzy match comp_key against nested dict_obj and return the
    'best' candidate with its path/value.
    """
    if not comp_key:
        return None

    keys = list(dict_obj.keys())

    # 1) Exact top-level hit
    if comp_key in keys:
        pathkey = search_keys_nested(dict_obj, comp_key)
        path = list(pathkey.keys())[0] if pathkey else comp_key
        key_head = path.split('.')[0]
        return {
            "count": 1,
            "path": path,
            "key": comp_key,
            "top": key_head,
            "value": dict_obj.get(comp_key),
        }

    # 2) Partial top-level hit
    for key in keys:
        if comp_key in key:
            pathkey = search_keys_nested(dict_obj, key)
            path = list(pathkey.keys())[0] if pathkey else key
            key_head = path.split('.')[0]
            return {
                "count": 1,
                "path": path,
                "key": key,
                "top": key_head,
                "value": dict_obj.get(key),
            }

    # 3) Fully nested fuzzy search
    result = search_keys_nested(dict_obj, comp_key)
    collect_vals: Dict[str, Dict[str, Dict[str, Any]]] = {}
    all_keys: List[str] = []

    for branch_path, values in result.items():
        key_head = branch_path.split('.')[0] if branch_path != "<root>" else "<root>"
        if key_head not in collect_vals:
            collect_vals[key_head] = {}

        for value_key in values:
            # Full path to this value (branch_path + key)
            full_path = (
                value_key if branch_path in ("", "<root>")
                else f"{branch_path}.{value_key}"
            )

            if value_key not in collect_vals[key_head]:
                collect_vals[key_head][value_key] = {
                    "count": 0,
                    "path": full_path,
                    "key": value_key,
                    "top": key_head,
                    "value": get_by_path(dict_obj, full_path),
                }
                all_keys.append(value_key)

            collect_vals[key_head][value_key]["count"] += 1

    if not collect_vals:
        return None

    # choose closest key name, then highest count
    closest_match = get_closest_match_from_list(comp_key, all_keys)
    highest: Optional[Dict[str, Any]] = None

    for _, keys_for_top in collect_vals.items():
        main_vals = keys_for_top.get(closest_match)
        if not main_vals:
            continue
        count = main_vals["count"]
        if count is not None and main_vals.get("value") is not None:
            if highest is None or count > highest["count"]:
                highest = main_vals

    return highest


# The React props "template" you want to infer from the pipeline dict
STRINGS_VARS = """videoId={video.videoId || video.video_id || video.id}
thumbnail={video.thumbnail || 'https://clownworld.biz/imgs/no_image.jpg'}
description={video.description || seo.description || 'Check out this video'}
likeCount={video.like_count ?? video.likeCount ?? 0}
repostCount={video.repost_count ?? video.repostCount ?? 0}
commentCount={video.comment_count ?? video.commentCount ?? 0}
duration={video.duration ?? 0}
webpageUrl={video.webpage_url || `https://clownworld.biz`}
filename={video.file_name || null}
keywords={video.keywords || []}
keywords_str={video.keywords_str || ''}
video_url={video.video_url}
optimized_video_url={video.optimized_video_url || video.video_url}
uploader={video.uploader || 'Unknown'}
uploaderId={video.uploader_id || 'Unknown'}
uploadDate={video.upload_date || 'Unknown'}
uploader_url={video.uploader_url || 'Unknown'}
viewCount={video.view_count ?? video.viewCount ?? 0}
file_name={video.file_name || 'video.mp4'}"""


def get_vars(line: str) -> List[str]:
    """
    From a line like:
        'videoId={video.videoId || video.video_id || video.id}'
    return:
        ['videoId', 'videoId', 'video_id', 'id']
    """
    left, _, right = line.partition("=")
    var = eatAll(left, [' ', '\t', '\n', ''])

    right_clean = eatAll(right, ['\n', '\t'])
    # Split on '||' and '??' tokens rather than plain space
    tokens = re.split(r"\|\||\?\?|\s+", right_clean)
    field_names: List[str] = []

    for tok in tokens:
        tok = tok.strip("{}() ")
        if not tok or "." not in tok:
            continue
        # take the last segment after '.', e.g. 'video.video_id' -> 'video_id'
        field_names.append(tok.split(".")[-1])

    return [var] + field_names


def get_values(strings_block: str, dict_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    For each line in strings_block, try to find the best matching
    value in dict_obj using fuzzy key search.
    """
    values: Dict[str, Any] = {}
    lines = [line for line in strings_block.splitlines() if line.strip()]

    for line in lines:
        candidates = get_vars(line)
        # Expand variants: camelCase, snake_case, etc.
        variant_keys = get_all_string(candidates)
        key_values = []

        for comp_key in set(variant_keys):
            key_from_dict = get_key_from_dict(comp_key, dict_obj)
            if key_from_dict:
                key_values.append(key_from_dict)

        prop_name = candidates[0]
        best: Dict[str, Any] = {}
        for kv in key_values:
            if not best or (
                best.get("count", 0) < kv.get("count", 0)
                and kv.get("value") is not None
            ):
                best = kv

        values[prop_name] = best.get("value")

    return values

def _pick_thumbnail(info: Dict[str, Any]) -> Optional[str]:
    """
    Prefer explicit `thumbnail`, otherwise fall back to the best entry
    in `thumbnails`.
    """
    if info.get("thumbnail"):
        return info["thumbnail"]

    thumbs = info.get("thumbnails") or []
    if not thumbs:
        return None

    # Take the one with the largest resolution / last in list
    def _score(t: Dict[str, Any]) -> int:
        return int(t.get("height") or 0) * int(t.get("width") or 0)

    best = max(thumbs, key=_score)
    return best.get("url") or best.get("id")


def _pick_video_url(info: Dict[str, Any]) -> Optional[str]:
    """
    Try to find a reasonably good playable URL.

    Priority:
      1. Any pre-computed `optimized_video_url` or `video_url`.
      2. `requested_formats` from yt-dlp (preferred).
      3. Best-looking format from `formats`.
    """
    # 1) If your pipeline already added these, trust them
    if info.get("optimized_video_url"):
        return info["optimized_video_url"]
    if info.get("video_url"):
        return info["video_url"]

    # 2) yt-dlp sometimes puts chosen formats in `requested_formats`
    requested = info.get("requested_formats") or []
    for f in requested:
        url = f.get("url")
        if url:
            return url

    # 3) Fallback: best from `formats`
    formats = info.get("formats") or []
    best: Optional[Dict[str, Any]] = None

    for f in formats:
        url = f.get("url")
        if not url:
            continue

        # Prefer higher resolution; if missing, fall back to tbr (bitrate)
        height = int(f.get("height") or 0)
        tbr = float(f.get("tbr") or 0.0)

        if best is None:
            best = f
            continue

        best_height = int(best.get("height") or 0)
        best_tbr = float(best.get("tbr") or 0.0)

        if height > best_height or (height == best_height and tbr > best_tbr):
            best = f

    return best.get("url") if best else None


def _pick_keywords(info: Dict[str, Any]) -> List[str]:
    """
    yt-dlp usually exposes tags and categories; normalize to a simple list.
    """
    tags = info.get("tags") or []
    cats = info.get("categories") or []

    out: List[str] = []
    for src in (tags, cats):
        if isinstance(src, (list, tuple)):
            out.extend(str(x) for x in src if x)
        elif isinstance(src, str):
            out.extend([s for s in src.split(",") if s.strip()])

    # Deduplicate while preserving order
    seen = set()
    deduped: List[str] = []
    for k in out:
        if k not in seen:
            seen.add(k)
            deduped.append(k)
    return deduped


def _pick_upload_date(info: Dict[str, Any]) -> Optional[str]:
    """
    yt-dlp uses 'YYYYMMDD'. We can pass that through as-is or
    pretty-format later in the React layer.
    """
    date = info.get("upload_date")
    if not date:
        return None
    return str(date)  # keep '20250503' style; frontend can format it


def extract_video_fields(info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministically map a yt-dlp info dict to your VideoDetails-shaped dict.

    Returns something like:

    {
      "videoId": "...",
      "thumbnail": "...",
      "description": "...",
      "likeCount": ...,
      "repostCount": ...,
      "commentCount": ...,
      "duration": ...,
      "webpageUrl": "...",
      "filename": ...,
      "keywords": [...],
      "keywords_str": "...",
      "video_url": "...",
      "optimized_video_url": "...",
      "uploader": "...",
      "uploaderId": "...",
      "uploadDate": "...",
      "uploader_url": "...",
      "viewCount": ...,
      "file_name": "..."
    }
    """

    # ---- core basics ----
    video_id = (
        info.get("id")
        or info.get("video_id")
        or info.get("display_id")
        or "0"
    )

    thumbnail = _pick_thumbnail(info)
    description = (
        info.get("description")
        or info.get("full_description")
        or ""
    )

    like_count = info.get("like_count") or 0
    comment_count = info.get("comment_count") or 0
    # yt-dlp doesn't really have "repost" count → keep 0 for now
    repost_count = info.get("repost_count") or 0

    duration = info.get("duration") or 0.0

    webpage_url = (
        info.get("webpage_url")
        or info.get("original_url")
        or info.get("url")
        or None
    )

    uploader = info.get("uploader") or "Unknown"
    uploader_id = info.get("uploader_id") or "Unknown"
    uploader_url = info.get("uploader_url") or None

    upload_date = _pick_upload_date(info)
    view_count = info.get("view_count") or 0

    # ---- video URLs ----
    video_url = _pick_video_url(info)
    optimized_video_url = video_url  # if you add a transcoding step, change here

    # ---- keywords / tags ----
    keywords = _pick_keywords(info)
    keywords_str = ",".join(keywords) if keywords else None

    # ---- file name (if available) ----
    # yt-dlp sometimes exposes these in extra keys; keep it simple for now
    file_name = (
        info.get("file_name")
        or info.get("filename")
        or None
    )

    # Match your React prop names exactly
    return {
        "videoId": video_id,
        "thumbnail": thumbnail,
        "description": description,
        "likeCount": like_count,
        "repostCount": repost_count,
        "commentCount": comment_count,
        "duration": float(duration) if duration is not None else 0.0,
        "webpageUrl": webpage_url,
        "filename": file_name,
        "keywords": keywords or None,
        "keywords_str": keywords_str,
        "video_url": video_url,
        "optimized_video_url": optimized_video_url,
        "uploader": uploader,
        "uploaderId": uploader_id,
        "uploadDate": upload_date,
        "uploader_url": uploader_url,
        "viewCount": view_count,
        "file_name": file_name,
    }
def get_dict_example():
    return {
    "raw":[],
    "aggregated": {
        "aggregated": {
            "audio_path": None,
            "best_clip": {},
            "candidate_clips": None,
            "canonical_url": None,
            "category": None,
            "description": None,
            "duration": None,
            "hashtags": None,
            "id": None,
            "keywords": None,
            "publication_date": None,
            "schema_markup": None,
            "social_metadata": None,
            "source_flags": {},
            "thumbnails_ranked": None,
            "title": None,
            "transcript_excerpt": None,
            "uploader": {},
            "video_path": None
        },
        "aggregated_path": None,
        "best_clip": None,
        "best_clip_path": None,
        "hashtags": None,
        "hashtags_path": None,
        "metadata": None,
        "metadata_path": None,
        "total_path": None
    },
    "captions": None,
    "info": {
        "aggregated": {
            "aggregated": {
                "audio_path": None,
                "best_clip": {},
                "candidate_clips": None,
                "canonical_url": None,
                "category": None,
                "description": None,
                "duration": None,
                "hashtags": None,
                "id": None,
                "keywords": None,
                "publication_date": None,
                "schema_markup": None,
                "social_metadata": None,
                "source_flags": {},
                "thumbnails_ranked": None,
                "title": None,
                "transcript_excerpt": None,
                "uploader": {},
                "video_path": None
            },
            "aggregated_path": None,
            "best_clip": None,
            "best_clip_path": None,
            "hashtags": None,
            "hashtags_path": None,
            "metadata": None,
            "metadata_path": None,
            "total_path": None
        },
        "audio_format": None,
        "audio_path": None,
        "captions": None,
        "created_at": None,
        "id": None,
        "info": {
            "_format_sort_fields": None,
            "_has_drm": None,
            "abr": None,
            "acodec": None,
            "age_limit": None,
            "aggregated_dir_aggregated_json_path": None,
            "aggregated_dir_aggregated_metadata_path": None,
            "aggregated_dir_best_clip_path": None,
            "aggregated_dir_hashtags_path": None,
            "aggregated_directory": None,
            "aspect_ratio": None,
            "asr": None,
            "audio_channels": None,
            "audio_path": None,
            "automatic_captions": {},
            "availability": None,
            "average_rating": None,
            "captions_path": None,
            "categories": None,
            "channel": None,
            "channel_follower_count": None,
            "channel_id": None,
            "channel_is_verified": None,
            "channel_url": None,
            "chapters": None,
            "comment_count": None,
            "description": None,
            "directory": None,
            "display_id": None,
            "duration": None,
            "duration_string": None,
            "dynamic_range": None,
            "epoch": None,
            "ext": None,
            "extractor": None,
            "extractor_key": None,
            "filesize_approx": None,
            "format": None,
            "format_id": None,
            "format_note": None,
            "formats": None,
            "fps": None,
            "fulltitle": None,
            "heatmap": None,
            "height": None,
            "id": None,
            "info_path": None,
            "is_live": None,
            "language": None,
            "like_count": None,
            "live_status": None,
            "media_type": None,
            "metadata_path": None,
            "original_url": None,
            "playable_in_embed": None,
            "playlist": None,
            "playlist_index": None,
            "protocol": None,
            "release_timestamp": None,
            "release_year": None,
            "requested_formats": None,
            "requested_subtitles": None,
            "resolution": None,
            "schema_paths": {
                "aggregated_dir": {
                    "aggregated_json_path": None,
                    "aggregated_metadata_path": None,
                    "best_clip_path": None,
                    "hashtags_path": None
                },
                "aggregated_directory": None,
                "audio_path": None,
                "captions_path": None,
                "info_path": None,
                "metadata_path": None,
                "thumbnail_path": None,
                "thumbnails_dir": {
                    "frames": None
                },
                "thumbnails_directory": None,
                "thumbnails_path": None,
                "total_aggregated_path": None,
                "total_info_path": None,
                "video_path": None,
                "whisper_path": None
            },
            "stretched_ratio": None,
            "subtitles": {},
            "tags": None,
            "tbr": None,
            "thumbnail": None,
            "thumbnail_path": None,
            "thumbnails": None,
            "thumbnails_dir_frames": None,
            "thumbnails_directory": None,
            "thumbnails_path": None,
            "timestamp": None,
            "title": None,
            "total_aggregated_path": None,
            "total_info_path": None,
            "upload_date": None,
            "uploader": None,
            "uploader_id": None,
            "uploader_url": None,
            "vbr": None,
            "vcodec": None,
            "video_id": None,
            "video_path": None,
            "view_count": None,
            "was_live": None,
            "webpage_url": None,
            "webpage_url_basename": None,
            "webpage_url_domain": None,
            "whisper_path": None,
            "width": None
        },
        "metadata": {
            "category": None,
            "keywords": None,
            "summary": None,
            "title": None
        },
        "metatags": {
            "canonical": None,
            "description": None,
            "description_html": None,
            "keywords": None,
            "og": {
                "description": None,
                "image": None,
                "image_alt": None,
                "image_height": None,
                "image_type": None,
                "image_width": None,
                "locale": None,
                "site_name": None,
                "title": None,
                "type": None,
                "url": None,
                "video": None
            },
            "other": {
                "application-name": None,
                "author": None,
                "bingbot": None,
                "charset": None,
                "color_scheme": None,
                "content_type": None,
                "distribution": None,
                "googlebot": None,
                "manifest": None,
                "rating": None,
                "revisit-after": None,
                "robots": None,
                "theme_color": None,
                "viewport": None,
                "yahooContent": None
            },
            "schema_markup": {
                "@context": None,
                "@type": None,
                "contentUrl": None,
                "description": None,
                "duration": None,
                "keywords": None,
                "name": None,
                "thumbnailUrl": None,
                "uploadDate": None
            },
            "thumbnail": None,
            "thumbnail_link": None,
            "thumbnail_resized_link": None,
            "title": None,
            "twitter": {
                "card": None,
                "creator": None,
                "description": None,
                "domain": None,
                "image": None,
                "image_alt": None,
                "image_type": None,
                "site": None,
                "title": None
            },
            "variants": None
        },
        "pagedata": {
            "seo": {
                "canonical": None,
                "description": None,
                "description_html": None,
                "keywords": None,
                "og": {
                    "description": None,
                    "image": None,
                    "image_alt": None,
                    "image_height": None,
                    "image_type": None,
                    "image_width": None,
                    "locale": None,
                    "site_name": None,
                    "title": None,
                    "type": None,
                    "url": None,
                    "video": None
                },
                "other": {
                    "application-name": None,
                    "author": None,
                    "bingbot": None,
                    "charset": None,
                    "color_scheme": None,
                    "content_type": None,
                    "distribution": None,
                    "googlebot": None,
                    "manifest": None,
                    "rating": None,
                    "revisit-after": None,
                    "robots": None,
                    "theme_color": None,
                    "viewport": None,
                    "yahooContent": None
                },
                "schema_markup": {
                    "@context": None,
                    "@type": None,
                    "contentUrl": None,
                    "description": None,
                    "duration": None,
                    "keywords": None,
                    "name": None,
                    "thumbnailUrl": None,
                    "uploadDate": None
                },
                "thumbnail": None,
                "thumbnail_link": None,
                "thumbnail_resized_link": None,
                "title": None,
                "twitter": {
                    "card": None,
                    "creator": None,
                    "description": None,
                    "domain": None,
                    "image": None,
                    "image_alt": None,
                    "image_type": None,
                    "site": None,
                    "title": None
                },
                "variants": None
            },
            "video": {
                "comment_count": None,
                "description": None,
                "duration": None,
                "file_name": None,
                "keywords": None,
                "keywords_str": None,
                "like_count": None,
                "optimized_video_url": None,
                "repost_count": None,
                "thumbnail": None,
                "title": None,
                "upload_date": None,
                "uploader": None,
                "uploader_id": None,
                "uploader_url": None,
                "video_url": None,
                "view_count": None,
                "webpage_url": None
            }
        },
        "seodata": {
            "seo_data": {
                "canonical_url": None,
                "categories": {},
                "category": None,
                "duration_formatted": None,
                "duration_seconds": None,
                "keywords_str": None,
                "publication_date": None,
                "schema_markup": {
                    "@context": None,
                    "@type": None,
                    "contentUrl": None,
                    "description": None,
                    "duration": None,
                    "keywords": None,
                    "name": None,
                    "thumbnailUrl": None,
                    "uploadDate": None
                },
                "seo_description": None,
                "seo_tags": None,
                "seo_title": None,
                "social_metadata": {
                    "og:description": None,
                    "og:image": None,
                    "og:title": None,
                    "og:video": None,
                    "twitter:card": None,
                    "twitter:description": None,
                    "twitter:image": None,
                    "twitter:title": None
                },
                "thumbnail": {
                    "alt_text": None,
                    "file_path": None
                },
                "uploader": {
                    "name": None,
                    "url": None
                },
                "video_metadata": {
                    "file_size_mb": None,
                    "format": None,
                    "resolution": None
                }
            }
        },
        "thumbnails": {
            "paths": None,
            "texts": None
        },
        "total_info": None,
        "updated_at": None,
        "video_id": None,
        "whisper": {
            "language": None,
            "segments": None,
            "text": None
        }
    },
    "metadata": {
        "category": None,
        "keywords": None,
        "summary": None,
        "title": None
    },
    "metatags": {
        "canonical": None,
        "description": None,
        "description_html": None,
        "keywords": None,
        "og": {
            "description": None,
            "image": None,
            "image_alt": None,
            "image_height": None,
            "image_type": None,
            "image_width": None,
            "locale": None,
            "site_name": None,
            "title": None,
            "type": None,
            "url": None,
            "video": None
        },
        "other": {
            "application-name": None,
            "author": None,
            "bingbot": None,
            "charset": None,
            "color_scheme": None,
            "content_type": None,
            "distribution": None,
            "googlebot": None,
            "manifest": None,
            "rating": None,
            "revisit-after": None,
            "robots": None,
            "theme_color": None,
            "viewport": None,
            "yahooContent": None
        },
        "schema_markup": {
            "@context": None,
            "@type": None,
            "contentUrl": None,
            "description": None,
            "duration": None,
            "keywords": None,
            "name": None,
            "thumbnailUrl": None,
            "uploadDate": None
        },
        "thumbnail": None,
        "thumbnail_link": None,
        "thumbnail_resized_link": None,
        "title": None,
        "twitter": {
            "card": None,
            "creator": None,
            "description": None,
            "domain": None,
            "image": None,
            "image_alt": None,
            "image_type": None,
            "site": None,
            "title": None
        },
        "variants": None
    },
    "pagedata": {
        "seo": {
            "canonical": None,
            "description": None,
            "description_html": None,
            "keywords": None,
            "og": {
                "description": None,
                "image": None,
                "image_alt": None,
                "image_height": None,
                "image_type": None,
                "image_width": None,
                "locale": None,
                "site_name": None,
                "title": None,
                "type": None,
                "url": None,
                "video": None
            },
            "other": {
                "application-name": None,
                "author": None,
                "bingbot": None,
                "charset": None,
                "color_scheme": None,
                "content_type": None,
                "distribution": None,
                "googlebot": None,
                "manifest": None,
                "rating": None,
                "revisit-after": None,
                "robots": None,
                "theme_color": None,
                "viewport": None,
                "yahooContent": None
            },
            "schema_markup": {
                "@context": None,
                "@type": None,
                "contentUrl": None,
                "description": None,
                "duration": None,
                "keywords": None,
                "name": None,
                "thumbnailUrl": None,
                "uploadDate": None
            },
            "thumbnail": None,
            "thumbnail_link": None,
            "thumbnail_resized_link": None,
            "title": None,
            "twitter": {
                "card": None,
                "creator": None,
                "description": None,
                "domain": None,
                "image": None,
                "image_alt": None,
                "image_type": None,
                "site": None,
                "title": None
            },
            "variants": None
        },
        "video": {
            "comment_count": None,
            "description": None,
            "duration": None,
            "file_name": None,
            "keywords": None,
            "keywords_str": None,
            "like_count": None,
            "optimized_video_url": None,
            "repost_count": None,
            "thumbnail": None,
            "title": None,
            "upload_date": None,
            "uploader": None,
            "uploader_id": None,
            "uploader_url": None,
            "video_url": None,
            "view_count": None,
            "webpage_url": None
        }
    },
    "seodata": {
        "seo_data": {
            "canonical_url": None,
            "categories": {},
            "category": None,
            "duration_formatted": None,
            "duration_seconds": None,
            "keywords_str": None,
            "publication_date": None,
            "schema_markup": {
                "@context": None,
                "@type": None,
                "contentUrl": None,
                "description": None,
                "duration": None,
                "keywords": None,
                "name": None,
                "thumbnailUrl": None,
                "uploadDate": None
            },
            "seo_description": None,
            "seo_tags": None,
            "seo_title": None,
            "social_metadata": {
                "og:description": None,
                "og:image": None,
                "og:title": None,
                "og:video": None,
                "twitter:card": None,
                "twitter:description": None,
                "twitter:image": None,
                "twitter:title": None
            },
            "thumbnail": {
                "alt_text": None,
                "file_path": None
            },
            "uploader": {
                "name": None,
                "url": None
            },
            "video_metadata": {
                "file_size_mb": None,
                "format": None,
                "resolution": None
            }
        }
    },
    "thumbnails": {
        "paths": None,
        "texts": None
    },
    "whisper": {
        "language": None,
        "segments": None,
        "text": None
    }
}
