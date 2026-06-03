"""
simple_downloader
=================

A reliable, robust, *basic* video downloader that works for any platform
``yt-dlp`` supports (YouTube, Vimeo, TikTok, Twitter/X, Instagram, Reddit,
Facebook, direct ``.mp4``/``.m3u8`` links, and ~1800 other sites).

Design goals
------------
* **Basic**     — one function, ``download_video(url)``. Sensible defaults.
* **Reliable**  — automatic retries, fragment retries, format fallbacks.
* **Robust**    — never raises on a normal failure; returns a result dict.
* **Standalone**— depends only on ``yt-dlp`` (and optionally ``ffmpeg`` for
                  merging). Imports lazily so this module can be imported even
                  when those tools are missing.

Usage
-----
    from abstract_videos.pipeline.videoDownloader.simple_downloader import download_video

    result = download_video("https://youtu.be/dQw4w9WgXc", output_dir="downloads")
    if result["success"]:
        print("Saved to", result["filepath"])
    else:
        print("Failed:", result["error"])

CLI
---
    python -m abstract_videos.pipeline.videoDownloader.simple_downloader URL [-o DIR] [--audio]
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, List, Optional

__all__ = [
    "download_video",
    "download_videos",
    "get_video_info",
    "check_dependencies",
    "SimpleVideoDownloader",
    "DownloadError",
]


class DownloadError(Exception):
    """Raised only when explicitly asked to (``raise_on_error=True``)."""


# --------------------------------------------------------------------------- #
# Dependency / environment checks
# --------------------------------------------------------------------------- #
def check_dependencies() -> Dict[str, Any]:
    """Inspect the runtime environment for the tools this downloader needs.

    Returns a report dict::

        {
            "ok": bool,                 # yt-dlp present (hard requirement)
            "full_quality": bool,       # yt-dlp AND ffmpeg present
            "yt_dlp": str | None,       # version or None
            "ffmpeg": bool,
            "ffprobe": bool,
            "messages": [str, ...],     # human-readable status lines
        }

    ``yt-dlp`` is required to download anything. ``ffmpeg`` is optional but
    needed to merge high-quality adaptive streams; without it the downloader
    falls back to lower-quality progressive streams.
    """
    import shutil

    report: Dict[str, Any] = {
        "ok": False,
        "full_quality": False,
        "yt_dlp": None,
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "ffprobe": bool(shutil.which("ffprobe")),
        "messages": [],
    }

    try:
        import yt_dlp
        report["yt_dlp"] = getattr(yt_dlp.version, "__version__", "unknown")
        report["ok"] = True
        report["messages"].append(f"[ok] yt-dlp {report['yt_dlp']} installed")
    except ImportError:
        report["messages"].append(
            "[MISSING] yt-dlp is required. Install it with: pip install yt-dlp"
        )

    if report["ffmpeg"] and report["ffprobe"]:
        report["full_quality"] = report["ok"]
        report["messages"].append("[ok] ffmpeg + ffprobe found")
    else:
        missing = ", ".join(
            n for n, present in (("ffmpeg", report["ffmpeg"]), ("ffprobe", report["ffprobe"]))
            if not present
        )
        report["messages"].append(
            f"[WARNING] {missing} not found on PATH. High-quality merging is "
            "disabled; downloads fall back to lower-quality progressive streams. "
            "Install ffmpeg:\n"
            "  Debian/Ubuntu : sudo apt install ffmpeg\n"
            "  macOS (brew)  : brew install ffmpeg\n"
            "  Windows       : winget install Gyan.FFmpeg"
        )

    return report


def _print_doctor() -> int:
    """Print the dependency report. Returns a process exit code."""
    report = check_dependencies()
    print("abstract_videos downloader — environment check")
    print("-" * 48)
    for line in report["messages"]:
        print(line)
    print("-" * 48)
    if report["ok"] and report["full_quality"]:
        print("Status: READY (full quality available)")
    elif report["ok"]:
        print("Status: USABLE (install ffmpeg for best quality)")
    else:
        print("Status: NOT READY (yt-dlp missing)")
    return 0 if report["ok"] else 1


# --------------------------------------------------------------------------- #
# ffmpeg detection
# --------------------------------------------------------------------------- #
def _has_ffmpeg() -> bool:
    """True only if BOTH ffmpeg and ffprobe are on PATH.

    yt-dlp needs ffmpeg to merge separate video+audio (adaptive) streams. When
    it is missing, requesting ``bestvideo+bestaudio`` leaves you with only one
    stream (commonly audio-only). Detecting this lets us fall back to a single
    progressive stream that already contains both tracks.
    """
    import shutil
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


# --------------------------------------------------------------------------- #
# Format selection
# --------------------------------------------------------------------------- #
def _default_format(
    audio_only: bool,
    quality: Optional[str],
    can_merge: bool = True,
) -> str:
    """Build a yt-dlp format string with graceful fallbacks.

    ``quality`` may be ``"best"`` (default), ``"worst"``, or a max height as a
    number/string like ``720`` to cap resolution on metered connections.

    ``can_merge`` indicates whether ffmpeg is available. When it is ``False`` we
    must pick a single *progressive* stream (video+audio in one file) because we
    cannot merge separate adaptive streams — otherwise the result is audio-only.
    """
    if audio_only:
        return "bestaudio/best"

    height = None
    if quality and str(quality).strip().lower() not in ("best", "worst", ""):
        digits = "".join(ch for ch in str(quality) if ch.isdigit())
        if digits:
            height = int(digits)

    if quality and str(quality).strip().lower() == "worst":
        if not can_merge:
            return "worst[vcodec!=none][acodec!=none]/worst"
        return "worstvideo+worstaudio/worst"

    if not can_merge:
        # No ffmpeg: only consider single files that already have BOTH streams.
        if height:
            return (
                f"best[height<={height}][vcodec!=none][acodec!=none][ext=mp4]/"
                f"best[height<={height}][vcodec!=none][acodec!=none]/"
                f"best[height<={height}]/best"
            )
        return "best[vcodec!=none][acodec!=none][ext=mp4]/best[vcodec!=none][acodec!=none]/best"

    if height:
        # cap height, but always keep a fallback to a single progressive stream
        return (
            f"bestvideo[height<={height}]+bestaudio/"
            f"best[height<={height}]/best"
        )

    # The most compatible "best" chain: prefer mp4, fall back to anything.
    return "bestvideo*+bestaudio/best"


def _build_ydl_opts(
    *,
    output_dir: str,
    outtmpl: str,
    audio_only: bool,
    quality: Optional[str],
    retries: int,
    cookies: Optional[str],
    user_agent: Optional[str],
    quiet: bool,
    extra: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    has_ffmpeg = _has_ffmpeg()
    if not has_ffmpeg and not audio_only and not quiet:
        print(
            "[simple_downloader] WARNING: ffmpeg/ffprobe not found on PATH. "
            "Falling back to a single progressive stream (lower max quality) so "
            "you still get video+audio. Install ffmpeg for best quality.",
            file=sys.stderr,
        )

    opts: Dict[str, Any] = {
        "outtmpl": outtmpl,
        "format": _default_format(audio_only, quality, can_merge=has_ffmpeg),
        "paths": {"home": output_dir},
        # --- reliability ---
        "retries": retries,
        "fragment_retries": retries,
        "file_access_retries": retries,
        "extractor_retries": retries,
        "concurrent_fragment_downloads": 4,
        "continuedl": True,            # resume partially downloaded files
        "socket_timeout": 30,
        # --- robustness ---
        "ignoreerrors": False,         # we handle errors ourselves
        "noplaylist": True,            # a "video downloader", not a playlist grabber
        "geo_bypass": True,
        "restrictfilenames": True,     # ASCII-safe filenames, no surprises
        "windowsfilenames": True,      # also safe on every OS
        "overwrites": False,
        # --- quietness ---
        "quiet": quiet,
        "no_warnings": quiet,
        "noprogress": quiet,
    }

    if audio_only:
        if has_ffmpeg:
            # Re-encode to mp3 only when ffmpeg is present; otherwise keep the
            # native audio container so the download still succeeds.
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
    elif has_ffmpeg:
        # Merge separate video+audio tracks into a single mp4 when ffmpeg exists.
        opts["merge_output_format"] = "mp4"

    if cookies:
        # Either a cookies.txt path or a "browser[:profile]" spec like "chrome".
        if os.path.isfile(cookies):
            opts["cookiefile"] = cookies
        else:
            opts["cookiesfrombrowser"] = (cookies,)

    if user_agent:
        opts.setdefault("http_headers", {})["User-Agent"] = user_agent

    if extra:
        opts.update(extra)

    return opts


def _resolved_filepath(ydl, info: Dict[str, Any], merged_to_mp4: bool) -> Optional[str]:
    """Best-effort resolution of the final file on disk."""
    try:
        path = ydl.prepare_filename(info)
    except Exception:
        path = None

    candidates: List[str] = []
    # yt-dlp records the real, post-processed paths here:
    for entry in info.get("requested_downloads") or []:
        if entry.get("filepath"):
            candidates.append(entry["filepath"])
    if path:
        if merged_to_mp4:
            root, _ = os.path.splitext(path)
            candidates.append(root + ".mp4")
        candidates.append(path)

    for cand in candidates:
        if cand and os.path.isfile(cand):
            return cand
    # Fall back to the first candidate even if we can't stat it.
    return candidates[0] if candidates else None


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
class SimpleVideoDownloader:
    """Thin, reusable wrapper around yt-dlp with robust defaults."""

    def __init__(
        self,
        output_dir: str = ".",
        *,
        audio_only: bool = False,
        quality: Optional[str] = "best",
        retries: int = 3,
        cookies: Optional[str] = None,
        user_agent: Optional[str] = None,
        quiet: bool = True,
        ydl_opts: Optional[Dict[str, Any]] = None,
    ):
        self.output_dir = output_dir
        self.audio_only = audio_only
        self.quality = quality
        self.retries = max(0, int(retries))
        self.cookies = cookies
        self.user_agent = user_agent
        self.quiet = quiet
        self.ydl_opts = ydl_opts or {}

    # -- helpers ----------------------------------------------------------- #
    @staticmethod
    def _require_yt_dlp():
        try:
            import yt_dlp  # noqa: F401
            return yt_dlp
        except ImportError as exc:  # pragma: no cover - depends on env
            raise DownloadError(
                "yt-dlp is not installed. Install it with: pip install yt-dlp"
            ) from exc

    # -- info only --------------------------------------------------------- #
    def info(self, url: str) -> Dict[str, Any]:
        """Return yt-dlp metadata for ``url`` without downloading."""
        yt_dlp = self._require_yt_dlp()
        opts = _build_ydl_opts(
            output_dir=self.output_dir,
            outtmpl="%(title).80s [%(id)s].%(ext)s",
            audio_only=self.audio_only,
            quality=self.quality,
            retries=self.retries,
            cookies=self.cookies,
            user_agent=self.user_agent,
            quiet=self.quiet,
            extra=self.ydl_opts,
        )
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return ydl.sanitize_info(info)

    # -- download ---------------------------------------------------------- #
    def download(
        self,
        url: str,
        *,
        filename: Optional[str] = None,
        raise_on_error: bool = False,
    ) -> Dict[str, Any]:
        """Download a single URL. Returns a result dict; never raises unless
        ``raise_on_error=True``."""
        result: Dict[str, Any] = {
            "success": False,
            "url": url,
            "filepath": None,
            "info": None,
            "error": None,
        }
        try:
            yt_dlp = self._require_yt_dlp()
        except DownloadError as exc:
            result["error"] = str(exc)
            if raise_on_error:
                raise
            return result

        os.makedirs(self.output_dir, exist_ok=True)

        if filename:
            base, ext = os.path.splitext(filename)
            outtmpl = base + (ext or ".%(ext)s")
        else:
            outtmpl = "%(title).80s [%(id)s].%(ext)s"

        opts = _build_ydl_opts(
            output_dir=self.output_dir,
            outtmpl=outtmpl,
            audio_only=self.audio_only,
            quality=self.quality,
            retries=self.retries,
            cookies=self.cookies,
            user_agent=self.user_agent,
            quiet=self.quiet,
            extra=self.ydl_opts,
        )

        last_exc: Optional[Exception] = None
        # An outer retry loop on top of yt-dlp's own internal retries, in case a
        # whole extraction attempt blows up (transient network / throttling).
        for attempt in range(self.retries + 1):
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if info is None:
                        raise DownloadError("yt-dlp returned no info (extraction failed)")
                    sanitized = ydl.sanitize_info(info)
                    path = _resolved_filepath(
                        ydl, info, merged_to_mp4=not self.audio_only
                    )
                result.update(success=True, info=sanitized, filepath=path)
                return result
            except Exception as exc:  # noqa: BLE001 - report, optionally retry
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(2 ** attempt)  # 1s, 2s, 4s ... backoff
                    continue

        result["error"] = f"{type(last_exc).__name__}: {last_exc}"
        if raise_on_error:
            raise DownloadError(result["error"]) from last_exc
        return result


# --------------------------------------------------------------------------- #
# Convenience functions
# --------------------------------------------------------------------------- #
def download_video(
    url: str,
    output_dir: str = ".",
    *,
    filename: Optional[str] = None,
    audio_only: bool = False,
    quality: Optional[str] = "best",
    retries: int = 3,
    cookies: Optional[str] = None,
    user_agent: Optional[str] = None,
    quiet: bool = True,
    ydl_opts: Optional[Dict[str, Any]] = None,
    raise_on_error: bool = False,
) -> Dict[str, Any]:
    """Download a single video from *any* supported platform.

    Returns a dict: ``{"success", "url", "filepath", "info", "error"}``.
    """
    return SimpleVideoDownloader(
        output_dir=output_dir,
        audio_only=audio_only,
        quality=quality,
        retries=retries,
        cookies=cookies,
        user_agent=user_agent,
        quiet=quiet,
        ydl_opts=ydl_opts,
    ).download(url, filename=filename, raise_on_error=raise_on_error)


def download_videos(
    urls: List[str],
    output_dir: str = ".",
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """Download many URLs; returns one result dict per URL. Failures are
    isolated — one bad URL never stops the rest."""
    dl = SimpleVideoDownloader(
        output_dir=output_dir,
        audio_only=kwargs.get("audio_only", False),
        quality=kwargs.get("quality", "best"),
        retries=kwargs.get("retries", 3),
        cookies=kwargs.get("cookies"),
        user_agent=kwargs.get("user_agent"),
        quiet=kwargs.get("quiet", True),
        ydl_opts=kwargs.get("ydl_opts"),
    )
    return [dl.download(u, filename=kwargs.get("filename")) for u in urls]


def get_video_info(url: str, **kwargs: Any) -> Dict[str, Any]:
    """Fetch metadata for ``url`` without downloading."""
    return SimpleVideoDownloader(
        output_dir=kwargs.get("output_dir", "."),
        quality=kwargs.get("quality", "best"),
        retries=kwargs.get("retries", 3),
        cookies=kwargs.get("cookies"),
        user_agent=kwargs.get("user_agent"),
        quiet=kwargs.get("quiet", True),
        ydl_opts=kwargs.get("ydl_opts"),
    ).info(url)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="simple_downloader",
        description="Reliable, basic video downloader for any platform (yt-dlp).",
    )
    parser.add_argument("urls", nargs="*", help="One or more video URLs.")
    parser.add_argument(
        "--doctor", action="store_true",
        help="Check that yt-dlp and ffmpeg are installed, then exit.",
    )
    parser.add_argument("-o", "--output-dir", default=".", help="Destination directory.")
    parser.add_argument("-f", "--filename", default=None, help="Output filename (single URL).")
    parser.add_argument("--audio", action="store_true", help="Download audio only (mp3).")
    parser.add_argument(
        "-q", "--quality", default="best",
        help="'best' (default), 'worst', or a max height like 720.",
    )
    parser.add_argument("--retries", type=int, default=3, help="Retry attempts.")
    parser.add_argument(
        "--cookies", default=None,
        help="Path to cookies.txt or a browser name (e.g. 'chrome').",
    )
    parser.add_argument("--info", action="store_true", help="Print metadata, do not download.")
    parser.add_argument("--verbose", action="store_true", help="Show yt-dlp progress/output.")
    args = parser.parse_args(argv)

    if args.doctor:
        return _print_doctor()

    if not args.urls:
        parser.error("at least one URL is required (or use --doctor)")

    if args.info:
        import json
        for url in args.urls:
            try:
                info = get_video_info(url, cookies=args.cookies, quiet=not args.verbose)
                print(json.dumps(
                    {k: info.get(k) for k in ("title", "id", "duration", "ext", "extractor")},
                    indent=2,
                ))
            except Exception as exc:  # noqa: BLE001
                print(f"[info-error] {url}: {exc}", file=sys.stderr)
        return 0

    results = download_videos(
        args.urls,
        output_dir=args.output_dir,
        filename=args.filename if len(args.urls) == 1 else None,
        audio_only=args.audio,
        quality=args.quality,
        retries=args.retries,
        cookies=args.cookies,
        quiet=not args.verbose,
    )

    failures = 0
    for res in results:
        if res["success"]:
            print(f"[ok] {res['url']} -> {res['filepath']}")
        else:
            failures += 1
            print(f"[fail] {res['url']}: {res['error']}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
