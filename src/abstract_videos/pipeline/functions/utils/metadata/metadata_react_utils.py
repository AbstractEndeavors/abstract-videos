from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
from urllib.parse import urljoin

def fs_path_to_url(path: str | None, base_url: str) -> str | None:
    """
    Convert known filesystem-style paths (/var/www/..., /mnt/24T/..., /media/...)
    to a public URL for the given base_url.

    IMPORTANT: We only rewrite paths that clearly look like file/media paths.
    Other strings (video_id, titles, random text) are returned unchanged.
    """
    if not path:
        return None

    # Already a URL? leave it alone
    if path.startswith("http://") or path.startswith("https://"):
        return path

    base_url = base_url.rstrip("/")

    # Known media roots on disk
    var_media_root = "/var/www/media/DATA"
    mnt_media_root = "/mnt/24T/media/DATA"

    # Map /var/www/media/DATA/... → https://domain/...
    if path.startswith(var_media_root):
        rel = path[len(var_media_root):]
        return f"{base_url}/{rel.lstrip('/')}"

    # Map /mnt/24T/media/DATA/... → https://domain/...
    if path.startswith(mnt_media_root):
        rel = path[len(mnt_media_root):]
        return f"{base_url}/{rel.lstrip('/')}"

    # Site-root resource paths we *do* want to expose
    site_roots = (
        "/media/",
        "/static/",
        "/imgs/",
        "/images/",
        "/thumbnails/",
        "/videos/",
    )
    if any(path.startswith(pfx) for pfx in site_roots):
        return f"{base_url}{path}"

    # Anything else: leave it exactly as-is (to avoid mangling ids, titles, etc.)
    return path


def convert_paths_to_urls(obj, base_url: str):
    """
    Recursively walk a nested structure (dict/list/str) and apply fs_path_to_url
    to any string values.

    This is used at the *boundary* where data leaves the backend and goes to
    React, so DB internals can keep using raw filesystem paths.
    """
    if isinstance(obj, str):
        return fs_path_to_url(obj, base_url) or obj

    if isinstance(obj, list):
        return [convert_paths_to_urls(x, base_url) for x in obj]

    if isinstance(obj, dict):
        return {
            k: convert_paths_to_urls(v, base_url)
            for k, v in obj.items()
        }

    # Numbers, bools, None, custom objects, etc. – leave as-is
    return obj


# ─────────────────────────────────────────────────────────────
# FS path → public URL
# ─────────────────────────────────────────────────────────────

##def fs_path_to_url(path: Optional[str], base_url: str) -> Optional[str]:
##    """
##    Convert a filesystem-style path (/var/www/..., /mnt/24T/..., /...) to a public URL.
##
##    This version assumes that:
##      - /var/www/media/DATA  →  <base_url>/videos/... (or similar)
##      - /mnt/24T/media/DATA  →  <base_url>/videos/... (same mapping)
##      - Any other absolute path (/imgs/..., /media/...) is treated as site-root relative.
##    """
##    if not path:
##        return None
##
##    # Already a URL? leave it alone
##    if path.startswith("http://") or path.startswith("https://"):
##        return path
##
##    base_url = base_url.rstrip("/")
##
##    # IMPORTANT: fix the double-slash bug here
##    if path.startswith("/var/www/media/DATA"):
##        root = "/var/www/media/DATA"
##        rel = path[len(root):]
##        return f"{base_url}/{rel.lstrip('/')}"
##
##    if path.startswith("/mnt/24T/media/DATA"):
##        root = "/mnt/24T/media/DATA"
##        rel = path[len(root):]
##        return f"{base_url}/{rel.lstrip('/')}"
##
##    # Generic site-root path
##    if path.startswith("/"):
##        return f"{base_url}{path}"
##
##    # Fallback – join relative against base
##    return urljoin(base_url + "/", path)


# ─────────────────────────────────────────────────────────────
# Normalize pipeline result → meta dict
# ─────────────────────────────────────────────────────────────

def normalize_base_url(base_url: Optional[str], seo_data: Dict[str, Any]) -> str:
    """
    Ensure we end up with something like 'https://clownworld.biz'
    even if canonical_url is just 'clownworld.biz'.
    """
    canonical = seo_data.get("canonical_url") or base_url or ""
    canonical = canonical.strip()

    if not canonical:
        raise ValueError("A base_url or seo_data['canonical_url'] is required")

    if not canonical.startswith(("http://", "https://")):
        canonical = "https://" + canonical.lstrip("/")

    return canonical.rstrip("/")


def build_seo_meta_from_result(result: Dict[str, Any], base_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Take the giant pipeline `result` (the blob you pasted) and turn it into
    a compact `meta` dict suitable for generate_meta_tags(...) and JSON export.
    """
    # Top-level slices
    metadata = result.get("metadata") or {}
    seodata = (result.get("seodata") or {}).get("seo_data") or {}
    info_outer = result.get("info") or {}
    info_inner = info_outer.get("info") or {}
    thumbnails = result.get("thumbnails") or {}
    whisper = result.get("whisper") or {}
    aggregated = result.get("aggregated") or {}

    # Normalize base URL (canonical root)
    canonical_root = normalize_base_url(base_url, seodata)
    base_domain = canonical_root.split("://", 1)[-1]  # e.g. 'clownworld.biz'

    # Video id
    video_id = (
        info_inner.get("video_id")
        or info_outer.get("video_id")
        or result.get("video_id")
    )

    # Decide the public page URL pattern
    # e.g. https://clownworld.biz/?video_id=mIMMZQJ1H6E
    page_path = f"/?video_id={video_id}" if video_id else "/"
    canonical_url = urljoin(canonical_root + "/", page_path.lstrip("/"))

    # Derive FS paths
    # 1) Thumbnail
    thumb_file = (
        (seodata.get("thumbnail") or {}).get("file_path")
        or info_inner.get("thumbnail_path")
        or info_inner.get("schema_paths", {}).get("thumbnail_path")
        or (thumbnails.get("paths") or [None])[0]
    )

    # 2) Video
    video_fs_path = (
        info_inner.get("video_path")
        or info_inner.get("schema_paths", {}).get("video_path")
        or (seodata.get("schema_markup") or {}).get("contentUrl")
        or aggregated.get("aggregated", {}).get("video_path")
    )

    # Convert FS paths → URLs
    thumb_url = fs_path_to_url(thumb_file, canonical_root) if thumb_file else None
    video_url = fs_path_to_url(video_fs_path, canonical_root) if video_fs_path else None

    # Titles / descriptions / keywords
    title = (
        seodata.get("seo_title")
        or metadata.get("title")
        or seodata.get("schema_markup", {}).get("name")
        or (video_id or "Untitled Video")
    )

    description = (
        seodata.get("seo_description")
        or metadata.get("summary")
        or seodata.get("schema_markup", {}).get("description")
        or whisper.get("text", "")[:300]
    )

    kw_list: List[str] = (
        seodata.get("seo_tags")
        or metadata.get("keywords")
        or seodata.get("schema_markup", {}).get("keywords")
        or []
    )
    if isinstance(kw_list, str):
        kw_list = [kw.strip() for kw in kw_list.split(",") if kw.strip()]

    keywords_str = ", ".join(dict.fromkeys(kw_list))  # dedupe, preserve order

    # Social metadata
    social = seodata.get("social_metadata") or {}

    og_image = fs_path_to_url(
        social.get("og:image") or thumb_file,
        canonical_root,
    ) if (social.get("og:image") or thumb_file) else None

    twitter_image = fs_path_to_url(
        social.get("twitter:image") or thumb_file,
        canonical_root,
    ) if (social.get("twitter:image") or thumb_file) else None

    # Build OG block
    og = {
        "title": social.get("og:title", title),
        "description": social.get("og:description", description),
        "url": social.get("og:url", canonical_url),
        "image": og_image,
        "image_alt": (seodata.get("thumbnail") or {}).get("alt_text"),
        "image_width": "1200",
        "image_height": "627",
        "image_type": "image/jpeg",
        "type": "video.other",
        "site_name": seodata.get("uploader", {}).get("name", "Clown World"),
        "locale": "en_US",
        "video": video_url or social.get("og:video"),
    }

    # Build Twitter block
    twitter = {
        "card": social.get("twitter:card", "player"),
        "title": social.get("twitter:title", title),
        "description": social.get("twitter:description", description),
        "image": twitter_image,
        "image_alt": (seodata.get("thumbnail") or {}).get("alt_text"),
        "image_type": "image/jpeg",
        "site": social.get("twitter:site", "@clownworld"),
        "creator": social.get("twitter:creator", "@clownworld"),
        "domain": base_domain,
    }

    # Other generic meta
    other = {
        "robots": "index, follow",
        "googlebot": "index, follow",
        "bingbot": "noarchive",
        "yahooContent": "article",
        "author": seodata.get("uploader", {}).get("name", "Clown World"),
        "revisit-after": "7 days",
        "rating": seodata.get("category", "General"),
        "distribution": "global",
        "viewport": "width=device-width, initial-scale=1",
        "application-name": "Clown World",
        "theme_color": "#000000",
        "color_scheme": "dark",
        "charset": "utf-8",
        "content_type": "text/html; charset=utf-8",
        # optional fields you can override later if you want PWA:
        "manifest": None,
    }

    # Return normalized meta dict
    meta = {
        "title": title,
        "description": description,
        "description_html": None,  # if you later generate a rich HTML version
        "keywords": keywords_str,
        "canonical": f"https://clownworld.biz/?video_id={video_id}",
        "variants": [
            canonical_url,
            f"{canonical_root}/video/{video_id}" if video_id else canonical_root,
        ],
        "thumbnail": thumb_url,
        "thumbnail_resized_link": thumb_url,
        "thumbnail_link": thumb_url,
        "og": og,
        "twitter": twitter,
        "other": other,
    }

    # Optionally, keep a copy of raw seodata/schema for debug or extra use:
    meta["schema_markup"] = seodata.get("schema_markup")

    return meta


# ─────────────────────────────────────────────────────────────
# Meta → <head> tags (your original function, with no FS logic)
# ─────────────────────────────────────────────────────────────

def generate_meta_tags(meta: Dict[str, Any],
                       base_url: Optional[str] = None,
                       json_path: Optional[str] = None,
                       **kwargs) -> str:
    base_url = base_url or (meta.get("variants") or [None])[0] or ""
    base_url = base_url.rstrip("/")

    tags: List[str] = []
    json_path = (json_path or "").split("json_pages/")[-1]

    # Base Tags
    tags.append(f'<title>{meta.get("title")}</title>')
    tags.append(
        '<meta name="description" content="{}" />'.format(
            meta.get("description_html")
            or meta.get("description")
            or "Explore content from Clown World."
        )
    )
    tags.append(f'<meta name="keywords" content="{meta.get("keywords", "")}" />')

    # Favicon
    favicon = (
        meta.get("thumbnail_resized_link")
        or (meta.get("og", {}).get("image") if meta.get("og") else None)
        or meta.get("thumbnail_link")
        or meta.get("thumbnail")
        or "/imgs/favicon.ico"
    )
    tags.append(f'<link rel="icon" href="{favicon}" type="image/x-icon" />')

    # Universal Crawler Tags
    other = meta.get("other", {})
    tags.append(f'<meta name="robots" content="{other.get("robots", "index, follow")}" />')
    tags.append(f'<meta name="googlebot" content="{other.get("googlebot", "index, follow")}" />')
    tags.append(f'<meta name="bingbot" content="{other.get("bingbot", "noarchive")}" />')
    tags.append(f'<meta name="yahooContent" content="{other.get("yahooContent", "article")}" />')
    tags.append(f'<meta name="author" content="{other.get("author", "Clown World Team")}" />')
    tags.append(f'<meta name="revisit-after" content="{other.get("revisit-after", "7 days")}" />')
    tags.append(f'<meta name="rating" content="{other.get("rating", "General")}" />')
    tags.append(f'<meta name="distribution" content="{other.get("distribution", "global")}" />')
    if other.get("msvalidate.01"):
        tags.append(f'<meta name="msvalidate.01" content="{other["msvalidate.01"]}" />')
    if other.get("yandex-verification"):
        tags.append(f'<meta name="yandex-verification" content="{other["yandex-verification"]}" />')

    # Open Graph
    og = meta.get("og", {})
    canonical_fallback = meta.get("canonical", f"{base_url}{json_path}")
    tags.append(f'<meta property="og:title" content="{og.get("title", meta.get("title"))}" />')
    tags.append(f'<meta property="og:description" content="{og.get("description", meta.get("description"))}" />')
    tags.append(f'<meta property="og:url" content="{og.get("url", canonical_fallback)}" />')
    tags.append(
        '<meta property="og:image" content="{}" />'.format(
            meta.get("thumbnail_resized_link")
            or og.get("image")
            or meta.get("thumbnail_link")
            or meta.get("thumbnail")
        )
    )
    if og.get("image_alt"):
        tags.append(f'<meta property="og:image:alt" content="{og["image_alt"]}" />')
    tags.append(f'<meta property="og:image:width" content="{og.get("image_width", "1200")}" />')
    tags.append(f'<meta property="og:image:height" content="{og.get("image_height", "627")}" />')
    tags.append(f'<meta property="og:image:type" content="{og.get("image_type", "image/jpeg")}" />')
    tags.append(f'<meta property="og:type" content="{og.get("type", "article")}" />')
    tags.append(f'<meta property="og:site_name" content="{og.get("site_name")}" />')
    tags.append(f'<meta property="og:locale" content="{og.get("locale", "en_US")}" />')
    if og.get("fb_app_id"):
        tags.append(f'<meta property="fb:app_id" content="{og["fb_app_id"]}" />')
    if og.get("updated_time"):
        tags.append(f'<meta property="og:updated_time" content="{og["updated_time"]}" />')
    if og.get("article"):
        article = og["article"]
        if article.get("published_time"):
            tags.append(f'<meta property="article:published_time" content="{article["published_time"]}" />')
        if article.get("modified_time"):
            tags.append(f'<meta property="article:modified_time" content="{article["modified_time"]}" />')
        if article.get("section"):
            tags.append(f'<meta property="article:section" content="{article["section"]}" />')
        if article.get("tag"):
            for tag in article["tag"]:
                tags.append(f'<meta property="article:tag" content="{tag}" />')

    # Twitter Cards
    twitter = meta.get("twitter", {})
    tags.append(f'<meta name="twitter:card" content="{twitter.get("card", "summary_large_image")}" />')
    tags.append(f'<meta name="twitter:title" content="{twitter.get("title", meta.get("title"))}" />')
    tags.append(f'<meta name="twitter:description" content="{twitter.get("description", meta.get("description"))}" />')
    tags.append(f'<meta name="twitter:image" content="{twitter.get("image", meta.get("thumbnail"))}" />')
    if twitter.get("image_alt"):
        tags.append(f'<meta name="twitter:image:alt" content="{twitter["image_alt"]}" />')
    tags.append(f'<meta name="twitter:image:type" content="{twitter.get("image_type", "image/jpeg")}" />')
    tags.append(f'<meta name="twitter:site" content="{twitter.get("site", "@clownworld")}" />')
    if twitter.get("site:id"):
        tags.append(f'<meta name="twitter:site:id" content="{twitter["site:id"]}" />')
    tags.append(f'<meta name="twitter:creator" content="{twitter.get("creator", "@clownworld")}" />')
    if twitter.get("creator:id"):
        tags.append(f'<meta name="twitter:creator:id" content="{twitter["creator:id"]}" />')
    tags.append(f'<meta name="twitter:domain" content="{twitter.get("domain", "clownworld.biz")}" />')
    # 👇 new: explicit twitter:url using the same canonical/og.url
    tags.append(f'<meta name="twitter:url" content="{twitter.get("url", canonical_fallback)}" />')

    # Other
    tags.append(f'<meta name="viewport" content="{other.get("viewport", "width=device-width, initial-scale=1")}" />')
    tags.append(f'<meta name="application-name" content="{other.get("application-name")}" />')
    tags.append(f'<meta name="theme-color" content="{other.get("theme_color", "#FFFFFF")}" />')
    tags.append(f'<meta name="color-scheme" content="{other.get("color_scheme", "light")}" />')
    if other.get("charset"):
        tags.append(f'<meta charset="{other["charset"]}" />')
    if other.get("content_type"):
        tags.append(f'<meta http-equiv="content-type" content="{other["content_type"]}" />')
    if other.get("manifest"):
        tags.append(f'<link rel="manifest" href="{other["manifest"]}" />')

    # Single canonical tag – this is now per-video, not hardcoded root
    tags.append(f'<link rel="canonical" href="{meta.get("canonical", canonical_fallback)}" />')

    return "\n".join(tags)


# ─────────────────────────────────────────────────────────────
# JSON save helper for React consumption
# ─────────────────────────────────────────────────────────────

def save_meta_json(meta: Dict[str, Any], output_dir: str, slug: str) -> str:
    """
    Save meta JSON into a predictable location React can fetch.
    Example path: /var/www/sites/clownworld/json_pages/<slug>.json
    Returns the absolute path to the JSON file.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"{slug}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return str(out_path)
