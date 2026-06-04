# Social / LinkedIn — Simple Video Downloader

A ready-to-post announcement for the `simple_downloader` feature in
`abstract_videos`. Copy/paste and adjust the call-to-action link as needed.

---

## LinkedIn post

**We kept hitting the same yt-dlp gotcha — so we fixed it once, properly.**

If you've ever scripted video downloads, you know the trap: you ask for "best
quality," the tool grabs separate video and audio streams to merge later... but
ffmpeg isn't installed, the merge silently fails, and you're left holding an
**audio-only file**. No error. Just a broken result you discover hours later.

So we built **Simple Video Downloader** into our `abstract_videos` pipeline — a
reliable, robust, *basic* downloader that works across ~1,800 platforms
(YouTube, Vimeo, TikTok, X, Instagram, direct links, and more).

What makes it boringly dependable:

🎯 **ffmpeg-aware by default** — detects your environment and picks a format that
actually contains both video and audio. No more silent audio-only downloads.
🔁 **Layered retries** — yt-dlp's internal retries plus an outer backoff loop for
flaky networks.
🛡️ **Returns, doesn't throw** — every call gives back a clean
`{success, filepath, info, error}` dict, so one bad URL never crashes your batch
job.
🩺 **A built-in doctor** — `abstract-video-doctor` tells you exactly what's
installed and what's missing, with copy-paste install hints.
🧩 **One call** — `download_video(url, output_dir)`. That's it.

Sometimes the most valuable engineering isn't a new capability — it's removing a
footgun that quietly wastes everyone's time.

Open source and part of the Abstract Intelligence Platform. 👇

\#Python #OpenSource #SoftwareEngineering #DeveloperTools #yt_dlp #DataEngineering

---

## Short description (one-liner)

> **Simple Video Downloader** — a reliable, robust, one-call video downloader for
> any platform. Built on yt-dlp with ffmpeg-aware format selection, automatic
> retries, and graceful error handling, so you get a real video file (not an
> audio-only surprise) from ~1,800 sites with a single function call.
