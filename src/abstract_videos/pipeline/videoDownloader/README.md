# Simple Video Downloader

A reliable, robust, and *basic* video downloader for **any platform** — built on
[`yt-dlp`](https://github.com/yt-dlp/yt-dlp) with sane defaults so you don't have
to think about formats, merging, or retries.

Part of the [`abstract_videos`](../../../../../README.md) media pipeline, but
fully self-contained: the only hard dependency is `yt-dlp` (plus optional
`ffmpeg` for best quality).

---

## Why

`yt-dlp` is powerful but low-level. A "just download this video" call still
requires you to reason about format selection, adaptive vs. progressive
streams, ffmpeg merging, filename sanitization, and error handling. Get the
format string wrong without ffmpeg installed and you silently end up with an
**audio-only file**.

`simple_downloader` wraps all of that into one safe call that:

- works across **~1,800 sites** `yt-dlp` supports (YouTube, Vimeo, TikTok,
  Twitter/X, Instagram, Reddit, Facebook, direct `.mp4`/`.m3u8` links, …),
- **never silently gives you audio-only** — it detects whether `ffmpeg` is
  available and picks a compatible format accordingly,
- **never throws on a normal failure** — it returns a result dict you can
  branch on,
- retries transient failures automatically.

---

## Install

```bash
pip install abstract_videos          # installs yt-dlp automatically
```

`ffmpeg` is an optional **system** dependency (not pip-installable). It is only
needed to merge the highest-quality adaptive streams. Without it you still get
video — just capped at whatever single progressive stream the site offers.

```bash
# Debian/Ubuntu
sudo apt install ffmpeg
# macOS
brew install ffmpeg
# Windows
winget install Gyan.FFmpeg
```

### Check your environment

```bash
abstract-video-doctor
```

```
abstract_videos downloader — environment check
------------------------------------------------
[ok] yt-dlp 2024.xx.xx installed
[ok] ffmpeg + ffprobe found
------------------------------------------------
Status: READY (full quality available)
```

---

## Quick start

### Python

```python
from abstract_videos.pipeline.videoDownloader import simple_download_video

result = simple_download_video(
    "https://youtu.be/dQw4w9WgXcQ",
    output_dir="downloads",
)

if result["success"]:
    print("Saved to:", result["filepath"])
else:
    print("Failed:", result["error"])
```

Every call returns the same shape:

```python
{
    "success": bool,        # did it download?
    "url":     str,         # the input URL
    "filepath": str | None, # where the file landed on disk
    "info":    dict | None, # yt-dlp metadata (title, id, duration, …)
    "error":   str | None,  # reason on failure
}
```

### Command line

```bash
# Download one or more URLs
abstract-video-dl "https://youtu.be/dQw4w9WgXcQ" -o downloads

# Audio only (mp3 when ffmpeg is present)
abstract-video-dl URL --audio

# Cap the resolution (handy on metered connections)
abstract-video-dl URL -q 720

# Just inspect metadata, don't download
abstract-video-dl URL --info

# Verbose progress
abstract-video-dl URL --verbose
```

You can also run it as a module:

```bash
python -m abstract_videos.pipeline.videoDownloader.simple_downloader URL -o downloads
```

---

## API reference

### `download_video(url, output_dir=".", **opts) -> dict`

Download a single URL. Exported from the package as `simple_download_video`.

| Argument         | Default  | Description                                                        |
| ---------------- | -------- | ------------------------------------------------------------------ |
| `url`            | —        | The video URL (any `yt-dlp`-supported site).                       |
| `output_dir`     | `"."`    | Destination directory (created if missing).                        |
| `filename`       | `None`   | Custom output filename. Defaults to `"<title> [<id>].<ext>"`.      |
| `audio_only`     | `False`  | Extract audio (mp3 when `ffmpeg` is available).                    |
| `quality`        | `"best"` | `"best"`, `"worst"`, or a max height like `720`.                   |
| `retries`        | `3`      | Retry attempts with exponential backoff.                          |
| `cookies`        | `None`   | Path to a `cookies.txt` file **or** a browser name (e.g. `chrome`).|
| `user_agent`     | `None`   | Override the HTTP User-Agent.                                      |
| `quiet`          | `True`   | Suppress `yt-dlp` progress/output.                                 |
| `ydl_opts`       | `None`   | Escape hatch: extra raw `yt-dlp` options (merged last).            |
| `raise_on_error` | `False`  | If `True`, raise `DownloadError` instead of returning it.          |

### `download_videos(urls, output_dir=".", **opts) -> list[dict]`

Download many URLs. Failures are isolated — one bad URL never stops the rest.
Returns one result dict per URL.

### `get_video_info(url, **opts) -> dict`

Fetch `yt-dlp` metadata **without downloading**. Exported as
`simple_get_video_info`.

### `check_dependencies() -> dict`

Report `yt-dlp` / `ffmpeg` status with install hints. Backs the
`abstract-video-doctor` command.

### `SimpleVideoDownloader(...)`

The reusable class behind the functions — construct once, call `.download()`,
`.info()`, etc. multiple times.

```python
from abstract_videos.pipeline.videoDownloader import SimpleVideoDownloader

dl = SimpleVideoDownloader(output_dir="downloads", quality=720, retries=5)
for url in urls:
    print(dl.download(url)["filepath"])
```

---

## How it stays reliable

- **ffmpeg-aware format selection.** With `ffmpeg`, it requests
  `bestvideo*+bestaudio` and merges to mp4. Without it, it falls back to a single
  progressive stream that already contains **both** video and audio — and warns
  you — so you never get a broken audio-only file.
- **Layered retries.** `yt-dlp`'s own fragment/extractor retries *plus* an outer
  retry loop with exponential backoff (1s, 2s, 4s …) for whole-extraction
  failures.
- **Result, not exception.** Normal failures come back as
  `{"success": False, "error": ...}` so batch jobs and pipelines don't crash.
- **Safe filenames.** ASCII-safe, cross-OS filenames by default.
- **Resumable.** Partially downloaded files continue instead of restarting.

---

## Notes

- This module intentionally avoids playlists (`noplaylist=True`) — it is a
  *video* downloader. Pass `ydl_opts={"noplaylist": False}` if you need them.
- For sites requiring login, pass `cookies="chrome"` (or another browser) or a
  `cookies.txt` path.
- Only download content you have the right to download. Respect each platform's
  Terms of Service and applicable copyright law.
