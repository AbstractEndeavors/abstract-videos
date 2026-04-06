from ..imports import *
from urllib.parse import urljoin
import json


def fs_path_to_url(path: str | None, base_url: str='https://clownworld.biz) -> str | None:
    """
    Convert a filesystem-style path (/var/www/..., /media/..., /...) to a public URL.
    Tunable to your nginx layout; this version assumes /var/www/* is web root.
    """
    if not path:
        return None

    # Already a URL? leave it alone
    if path.startswith("http://") or path.startswith("https://"):
        return path

    base_url = base_url.rstrip("/")
    # Map /var/www/<stuff> → https://domain/<stuff>
    if path.startswith("/var/www/media/DATA"):
        rel = path[len("/var/www//media/DATA"):]
        return f"{base_url}/{rel.lstrip('/')}"
    # Map /var/www/<stuff> → https://domain/<stuff>
    if path.startswith("/mnt/24T/media/DATA"):
        rel = path[len("/mnt/24T/media/DATA"):]
        return f"{base_url}/{rel.lstrip('/')}"

    # Site-root relative path (/media/..., /imgs/..., etc.)
    if path.startswith("/"):
        return f"{base_url}{path}"

    # Fallback – join relative against base
    return urljoin(base_url + "/", path)

def build_meta_from_video_result(result: dict,
                                 base_url: str = "https://clownworld.biz") -> dict:
    """
    Normalize your video pipeline result into the `meta` structure used by generate_meta_tags.
    """

    seo_data = (result.get("seodata") or {}).get("seo_data") or {}
    meta_data = result.get("metadata") or {}
    info_block = result.get("info") or {}

    # Video ID
    video_id = info_block.get("video_id") or (info_block.get("info") or {}).get("video_id")

    # Canonical URL
    canonical_raw = seo_data.get("canonical_url")
    if canonical_raw:
        # canonical_url in your data is "clownworld.biz" (no scheme / path)
        if not canonical_raw.startswith(("http://", "https://")):
            canonical = f"https://{canonical_raw.rstrip('/')}"
    else:
        canonical = base_url

    # If you want per-video canonicals like /?video_id=..., wire it here:
    if video_id:
        canonical = f"{canonical.rstrip('/')}/?video_id={video_id}"

    # Title / description
    seo_title = seo_data.get("seo_title") or meta_data.get("title") \
        or (video_id and f"{video_id} - Clown World") \
        or "Clown World"

    seo_description = seo_data.get("seo_description") or meta_data.get("summary")

    # Fallback to first chunk of Whisper text if summary missing
    if not seo_description and result.get("whisper", {}).get("text"):
        whisper_text = result["whisper"]["text"].strip()
        if whisper_text:
            seo_description = whisper_text[:300] + ("..." if len(whisper_text) > 300 else "")

    # Keywords
    tags_from_seo = seo_data.get("seo_tags") or []
    tags_from_meta = meta_data.get("keywords") or []
    keywords_list: list[str] = []
    for k in tags_from_seo + tags_from_meta:
        if k and k not in keywords_list:
            keywords_list.append(k)
    keywords_str = ", ".join(keywords_list)

    # Thumbnail
    thumb_obj = seo_data.get("thumbnail") or {}
    thumb_path = thumb_obj.get("file_path")

    if not thumb_path:
        # fall back to first thumbnail path in the list
        thumbs_paths = ((result.get("thumbnails") or {}).get("paths") or [])
        thumb_path = thumbs_paths[0] if thumbs_paths else None

    thumb_url = fs_path_to_url(thumb_path, base_url) if thumb_path else None

    # Video path / URL
    schema_markup = seo_data.get("schema_markup") or {}
    video_fs_path = (
        schema_markup.get("contentUrl")
        or (info_block.get("schema_paths") or {}).get("video_path")
        or info_block.get("video_path")
    )
    video_url = fs_path_to_url(video_fs_path, base_url) if video_fs_path else None

    # Social meta (og:* and twitter:*)
    social = seo_data.get("social_metadata") or {}

    og = {
        "title": social.get("og:title") or seo_title,
        "description": social.get("og:description") or seo_description,
        "url": canonical,
        "image": fs_path_to_url(social.get("og:image"), base_url)
                 if social.get("og:image") else thumb_url,
        "image_alt": thumb_obj.get("alt_text"),
        "image_width": "1200",
        "image_height": "627",
        "image_type": "image/jpeg",
        "type": "video.other",
        "site_name": "Clown World",
        "locale": "en_US",
        "video": fs_path_to_url(social.get("og:video"), base_url)
                 if social.get("og:video") else video_url,
    }

    # Strip empty keys so generate_meta_tags' conditionals behave nicely
    og = {k: v for k, v in og.items() if v}

    twitter = {
        "card": social.get("twitter:card", "player"),
        "title": social.get("twitter:title") or seo_title,
        "description": social.get("twitter:description") or seo_description,
        "image": fs_path_to_url(social.get("twitter:image"), base_url)
                 if social.get("twitter:image") else thumb_url,
        "site": "@clownworld",
        "creator": "@clownworld",
        "domain": base_url.replace("https://", "").replace("http://", ""),
        # optional: if you later have a dedicated player URL, set it here:
        # "player": f"{base_url.rstrip('/')}/player/{video_id}" if video_id else None,
    }
    twitter = {k: v for k, v in twitter.items() if v}

    # "Other" generic tags
    uploader = (seo_data.get("uploader") or {}).get("name") or "Clown World Team"
    category = seo_data.get("category") or meta_data.get("category") or "General"

    other = {
        "robots": "index, follow",
        "googlebot": "index, follow",
        "bingbot": "noarchive",
        "yahooContent": "article",
        "author": uploader,
        "revisit-after": "7 days",
        "rating": category,
        "distribution": "global",
        "viewport": "width=device-width, initial-scale=1",
        "application-name": "Clown World",
        "theme_color": "#000000",
        "color_scheme": "light dark",
        "charset": "utf-8",
        "content_type": "text/html; charset=utf-8",
    }

    # Final meta dict in your existing shape
    meta = {
        "title": seo_title,
        "description": seo_description,
        "description_html": None,
        "keywords": keywords_str,
        "thumbnail": thumb_url,
        "thumbnail_resized_link": thumb_url,  # so your existing logic finds it
        "canonical": canonical,
        "variants": [canonical],
        "og": og,
        "twitter": twitter,
        "other": other,
        "schema_markup": schema_markup,
    }
    return meta

def generate_meta_tags(meta, base_url=None, json_path=None, **kwargs):
    base_url = base_url or (meta.get('variants') or [None])[0] or ""
    tags = []
    json_path = (json_path or "").split('json_pages/')[-1]

    # ---------------- Base tags ----------------
    title = meta.get("title") or "clownworld.biz"
    description = (
        meta.get("description_html")
        or meta.get("description")
        or "Explore content from clownworld.biz."
    )
    keywords = meta.get("keywords", "")

    tags.append(f"<title>{title}</title>")
    tags.append(f'<meta name="description" content="{description}" />')
    tags.append(f'<meta name="keywords" content="{keywords}" />')

    # Favicon
    favicon = (
        meta.get("thumbnail_resized_link")
        or (meta.get("og", {}).get("image") if meta.get("og") else None)
        or meta.get("thumbnail_link")
        or meta.get("thumbnail_resized")
        or meta.get("thumbnail")
        or "/imgs/favicon.ico"
    )
    if favicon and base_url:
        favicon = fs_path_to_url(favicon, base_url)
    tags.append(f'<link rel="icon" href="{favicon}" type="image/x-icon" />')

    # ---------------- Universal crawler tags ----------------
    other = meta.get("other", {}) or {}
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

    # ---------------- Open Graph ----------------
    og = meta.get("og", {}) or {}

    og_title = og.get("title", title)
    og_description = og.get("description", description)

    # URL: prefer explicit og:url, then canonical, then base_url + json_path
    og_url = og.get("url") or meta.get("canonical") or (
        f"{base_url.rstrip('/')}{json_path}" if base_url else None
    )
    if og_url and base_url:
        og_url = fs_path_to_url(og_url, base_url)

    og_image = (
        meta.get("thumbnail_resized_link")
        or og.get("image")
        or meta.get("thumbnail_link")
        or meta.get("thumbnail_resized")
        or meta.get("thumbnail")
    )
    if og_image and base_url:
        og_image = fs_path_to_url(og_image, base_url)

    tags.append(f'<meta property="og:title" content="{og_title}" />')
    tags.append(f'<meta property="og:description" content="{og_description}" />')
    if og_url:
        tags.append(f'<meta property="og:url" content="{og_url}" />')
    if og_image:
        tags.append(f'<meta property="og:image" content="{og_image}" />')

    if og.get("image_alt"):
        tags.append(f'<meta property="og:image:alt" content="{og["image_alt"]}" />')
    tags.append(f'<meta property="og:image:width" content="{og.get("image_width", "1200")}" />')
    tags.append(f'<meta property="og:image:height" content="{og.get("image_height", "627")}" />')
    tags.append(f'<meta property="og:image:type" content="{og.get("image_type", "image/jpeg")}" />')
    tags.append(f'<meta property="og:type" content="{og.get("type", "article")}" />')
    if og.get("site_name"):
        tags.append(f'<meta property="og:site_name" content="{og["site_name"]}" />')
    tags.append(f'<meta property="og:locale" content="{og.get("locale", "en_US")}" />')

    # Video-specific OG tags
    if og.get("video"):
        og_video = fs_path_to_url(og["video"], base_url) if base_url else og["video"]
        tags.append(f'<meta property="og:video" content="{og_video}" />')
        if og.get("video_type"):
            tags.append(f'<meta property="og:video:type" content="{og["video_type"]}" />')
        if og.get("video_width"):
            tags.append(f'<meta property="og:video:width" content="{og["video_width"]}" />')
        if og.get("video_height"):
            tags.append(f'<meta property="og:video:height" content="{og["video_height"]}" />')

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

    # ---------------- Twitter Cards ----------------
    twitter = meta.get("twitter", {}) or {}
    tags.append(f'<meta name="twitter:card" content="{twitter.get("card", "summary_large_image")}" />')
    tags.append(f'<meta name="twitter:title" content="{twitter.get("title", title)}" />')
    tags.append(f'<meta name="twitter:description" content="{twitter.get("description", description)}" />')

    tw_image = twitter.get("image") or meta.get("thumbnail") or og_image
    if tw_image and base_url:
        tw_image = fs_path_to_url(tw_image, base_url)
    if tw_image:
        tags.append(f'<meta name="twitter:image" content="{tw_image}" />')

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

    # Optional: player tags if you eventually add them
    if twitter.get("player"):
        tags.append(f'<meta name="twitter:player" content="{twitter["player"]}" />')
    if twitter.get("player:width"):
        tags.append(f'<meta name="twitter:player:width" content="{twitter["player:width"]}" />')
    if twitter.get("player:height"):
        tags.append(f'<meta name="twitter:player:height" content="{twitter["player:height"]}" />')

    # ---------------- Other tags ----------------
    tags.append(f'<meta name="viewport" content="{other.get("viewport", "width=device-width, initial-scale=1")}" />')
    if other.get("application-name"):
        tags.append(f'<meta name="application-name" content="{other["application-name"]}" />')
    tags.append(f'<meta name="theme-color" content="{other.get("theme_color", "#FFFFFF")}" />')
    tags.append(f'<meta name="color-scheme" content="{other.get("color_scheme", "light")}" />')
    if other.get("charset"):
        tags.append(f'<meta charset="{other["charset"]}" />')
    if other.get("content_type"):
        tags.append(f'<meta http-equiv="content-type" content="{other["content_type"]}" />')
    if other.get("manifest"):
        tags.append(f'<link rel="manifest" href="{other["manifest"]}" />')

    canonical = meta.get("canonical") or og_url
    if canonical and base_url:
        canonical = fs_path_to_url(canonical, base_url)
    if canonical:
        tags.append(f'<link rel="canonical" href="{canonical}" />')

    # ---------------- JSON-LD Schema.org (VideoObject) ----------------
    schema_markup = meta.get("schema_markup")
    if schema_markup:
        sm = dict(schema_markup)  # shallow copy
        # normalize contentUrl & thumbnailUrl to public URLs
        for k in ("contentUrl", "thumbnailUrl"):
            if sm.get(k) and base_url:
                sm[k] = fs_path_to_url(sm[k], base_url)
        tags.append(
            '<script type="application/ld+json">'
            + json.dumps(sm, ensure_ascii=False)
            + "</script>"
        )

    return "\n".join(tags)
def build_seo_meta_from_result(result: dict, base_domain: str = "https://clownworld.biz") -> dict:
    """
    Take the huge result blob you pasted and normalize it into a clean SEO meta JSON
    that React can easily consume.
    """
    # Core references
    video_id = result["info"]["info"]["video_id"]
    seo_data = (result.get("seodata") or {}).get("seo_data") or {}
    metadata = result.get("metadata") or {}
    info = result.get("info") or {}

    # Canonical path for this video on your site
    # tweak this to match your real route: e.g. /video/<id> or /watch/<id>
    page_path = f"/video/{video_id}"
    canonical_url = f"{base_domain}{page_path}"

    # Thumbnail
    thumb = (seo_data.get("thumbnail") or {})
    thumb_path = thumb.get("file_path") or (seo_data.get("social_metadata") or {}).get("og:image")

    # OG / Twitter pulled from seo_data.social_metadata
    social = seo_data.get("social_metadata") or {}

    og = {
        "title": social.get("og:title") or seo_data.get("seo_title") or metadata.get("title"),
        "description": social.get("og:description") or seo_data.get("seo_description") or metadata.get("summary"),
        "url": canonical_url,
        "image": social.get("og:image") or thumb_path,
        "video": social.get("og:video") or (seo_data.get("schema_markup") or {}).get("contentUrl"),
        "site_name": "Clown World",
        "locale": "en_US",
        "type": "video.other",
    }

    twitter = {
        "card": social.get("twitter:card", "player"),
        "title": social.get("twitter:title") or og["title"],
        "description": social.get("twitter:description") or og["description"],
        "image": social.get("twitter:image") or og["image"],
        "site": "@clownworld",
        "creator": "@clownworld",
        "domain": "clownworld.biz",
    }

    schema_markup = seo_data.get("schema_markup") or {}
    # Ensure schema has canonical URL
    if schema_markup:
        schema_markup = {
            **schema_markup,
            "url": canonical_url,
            "embedUrl": schema_markup.get("embedUrl") or canonical_url,
        }

    other = {
        "robots": "index, follow",
        "googlebot": "index, follow",
        "bingbot": "noarchive",
        "yahooContent": "article",
        "author": (seo_data.get("uploader") or {}).get("name", "Clown World"),
        "revisit-after": "7 days",
        "rating": seo_data.get("category", "General"),
        "distribution": "global",
        "viewport": "width=device-width, initial-scale=1",
        "theme_color": "#000000",
        "color_scheme": "dark light",
    }

    seo_meta = {
        "video_id": video_id,
        "slug": video_id,  # you can swap for a human slug later
        "path": page_path,
        "canonical": canonical_url,
        "title": seo_data.get("seo_title") or metadata.get("title"),
        "description": seo_data.get("seo_description") or metadata.get("summary"),
        "keywords": seo_data.get("seo_tags") or metadata.get("keywords") or [],
        "duration_seconds": seo_data.get("duration_seconds"),
        "thumbnail": {
            "src": thumb_path,
            "alt": thumb.get("alt_text", video_id),
        },
        "og": og,
        "twitter": twitter,
        "schema": schema_markup,
        "other": other,
    }
    return seo_meta

def generate_meta_tags_from_result(result: dict,
                                   base_url: str = "https://clownworld.biz",
                                   json_path: str | None = None,
                                   **kwargs) -> str:
    meta = build_meta_from_video_result(result, base_url=base_url)
    return generate_meta_tags(meta, base_url=base_url, json_path=json_path, **kwargs)
