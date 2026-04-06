# src/pipeline.py
from .imports import *
class VideoPipeline:
    def __init__(self, video_url=None, video_path=None, force_refresh=False, whisper_model=None,videos_root=None,documents_root=None):
        self.video_url = video_url
        self.video_path = video_path
        self.config = StorageConfig.from_env(videos_root=videos_root,documents_root=documents_root)
        self.videos_root = self.config.videos_root
        self.documents_root = self.config.documents_root
        self.force_refresh = force_refresh
        self.whisper_model = get_whisper_model(whisper_model or "small")

        if self.video_path and not self.video_url:
            self.video_id = generate_video_id(video_path)
        else:
            self.video_url = get_corrected_url(self.video_url)
            self.video_id = get_video_id(self.video_url)

        
##        self.registry = infoRegistry(config=self.config)
##
##        self.info = self.registry.get_video_info(
##            url=video_url,
##            video_id=self.video_id,
##            video_path=self.video_path,
##            force_refresh=force_refresh
##        ) or {}
##        self.video_info = self.info.get('info') or {}

    # ── internal plumbing ──────────────────────────────────────────────────

    def _record(self) -> dict:
        """Fresh DB fetch. Use sparingly — one call per public method."""
        return get_video_record(self.video_id) or {}

    def _get_or_compute(self, field: str, compute_fn):
        record = self._record()
        if record.get(field):
            return record[field]
        result = compute_fn()
        upsert_video(self.video_id, **{field: result})
        return result

    def _file_exists(self, key: str) -> tuple[str | None, bool]:
        path = self.video_info.get(key)
        exists = bool(path and os.path.isfile(path))
        logger.info(f"{key} = {path!r} ({'exists' if exists else 'missing'})")
        return path, exists

    # ── ensure helpers (idempotent, guarded) ──────────────────────────────

    def ensure_video(self) -> str | None:
        """Download only if video file is missing. Returns video_path."""
        video_path, exists = self._file_exists('video_path')
        if exists:
            return video_path
        VideoDownloader(url=self.video_url, download_video=True)
        # re-read after download so video_info stays fresh
        record = self._record()
        self.video_info = record.get('info') or self.video_info
        video_path, _ = self._file_exists('video_path')
        return video_path

    def ensure_audio(self) -> tuple[str | None, str | None]:
        """Extract audio only if audio file is missing. Returns (audio_path, fmt)."""
        audio_path, exists = self._file_exists('audio_path')
        if audio_path:
            fmt = audio_path.rsplit('.', 1)[-1]
            if exists:
                return audio_path, fmt
        video_path = self.ensure_video()
        if not video_path:
            logger.error("ensure_audio: no video_path, cannot extract audio")
            return None, None
        audio_path = self.video_info.get('audio_path')
        fmt = audio_path.rsplit('.', 1)[-1] if audio_path else 'wav'
        os.system(f"ffmpeg -y -i {video_path} -vn -acodec pcm_s16le -ar 16000 -ac 1 {audio_path}")
        upsert_video(self.video_id, audio_path=audio_path, audio_format=fmt)
        return audio_path, fmt

    # ── compute fns (pure, no guard logic) ────────────────────────────────

    def _compute_whisper(self):
        audio_path, _ = self.ensure_audio()
        return self.whisper_model.transcribe(audio_path)

    def _compute_captions(self):
        whisper = self.get_whisper()
        return [
            {"start": seg["start"], "end": seg["end"], "text": seg["text"]}
            for seg in whisper.get("segments", [])
        ]

    def _compute_metadata(self):
        whisper = self.get_whisper()
        captions = self.get_captions()
        text_blob = " ".join([whisper.get("text", "")] + [c["text"] for c in captions])
        title = (
            self.info.get('title')
            or self.video_info.get('title')
            or text_blob[:50]
            or "Untitled"
        )
        summary = summarize(text=text_blob)
        keywords = (self.info.get('keywords') or self.video_info.get('keywords') or [])
        tags = (self.info.get('tags') or self.video_info.get('tags') or [])
        extracted = refine_keywords(text=text_blob) or []
        
        keywords = (keywords + tags + make_list(extracted.meta_keywords))[:10]
        return {
            "title": title,
            "summary": summary,
            "category": choose_category(keywords),
            "keywords": keywords,
        }

    def _compute_thumbnails(self):
        video_path = self.ensure_video()
        thumbnails_dir = self.video_info.get("thumbnails_directory")
        return get_thumbnails(self.video_id, video_path, thumbnails_dir)

    def _compute_seodata(self):
        whisper_result = self.get_whisper()
        captions = self.get_captions()
        thumbnails = self.get_thumbnails()
        metadata = self.get_metadata()

        video_path = self.ensure_video()
        audio_path, _ = self.ensure_audio()
        thumbnails_dir = self.video_info.get("thumbnails_directory")

        return get_seo_data(
            video_path=video_path,
            filename=self.video_id,
            title=metadata.get('title'),
            summary=metadata.get('summary'),
            description=metadata.get('description', metadata.get('summary')),
            keywords=metadata.get('keywords'),
            thumbnails_dir=thumbnails_dir,
            thumbnail_paths=thumbnails.get('paths'),
            whisper_result=whisper_result,
            audio_path=audio_path,
            domain='thedailydialectics.com'
        )

    def _compute_aggregated(self):
        record = self._record()
        directory = (record.get('info') or {}).get('directory')
        return aggregate_from_base_dir(directory=directory)

    # ── public API ────────────────────────────────────────────────────────

    def get_whisper(self):
        return self._get_or_compute("whisper", self._compute_whisper)

    def get_captions(self):
        return self._get_or_compute("captions", self._compute_captions)

    def get_metadata(self):
        return self._get_or_compute("metadata", self._compute_metadata)

    def get_thumbnails(self):
        return self._get_or_compute("thumbnails", self._compute_thumbnails)

    def get_seodata(self):
        return self._get_or_compute("seodata", self._compute_seodata)

    def get_aggregated_data(self):
        return self._get_or_compute("aggregated", self._compute_aggregated)

    def get_info(self):
        return get_video_record(self.video_id, hide_audio=True) or {}

    def get_all(self):
        return {
            "info": self.get_info(),
            "whisper": self.get_whisper(),
            "captions": self.get_captions(),
            "metadata": self.get_metadata(),
            "thumbnails": self.get_thumbnails(),
            "seodata": self.get_seodata(),
            "aggregated": self.get_aggregated_data(),
        }
