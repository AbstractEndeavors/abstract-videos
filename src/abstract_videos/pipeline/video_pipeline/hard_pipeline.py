from .imports import *
class VideoTextPipeline:
    def __init__(self,
                 config = None,
                 video_path=None,
                 output_dir=None,
                 output_path=None,
                 new_filename=None,
                 info_data=None,
                 output_option=None,
                 info_path=None,
                 whisper_result_path=None,
                 reencode=None,
                 frame_interval=None,
                 remove_phrases=None,
                 model_size=None,
                 conversion= False,
                 audio_extraction= False,
                 frame_extraction= False,
                 ocr= False,
                 transcription= False,
                 text_processing= False,
                 seo_data= False,
                 is_optimized=None):
        self.config = config or StorageConfig.from_env()
        self.info = {}
        self.model_size = model_size or "medium"
        self.remove_phrases = remove_phrases or []
        self.reencode = if_none_get_default(reencode, default=False)
        self.video_path = video_path
        self.info["video_path"] = self.video_path
        self.video_id = generate_file_id(self.video_path)
        self.info["video_id"] = self.video_id
        
        # Set output_path, ensuring it’s unique
        self.output_path = get_path(self.video_path, output_dir=output_dir, output_path=output_path, new_filename=new_filename)
        if self.output_path == self.video_path:
            self.output_path = create_unique_filename(self.video_path)
        self.output_dir = os.path.dirname(self.output_path)
        self.info["info_dir"] = self.output_dir
        
        # Set output_option, defaulting to "copy"
        self.output_option = output_option or "copy"
        self.info["output_path"] = self.output_path
        
        self.info_path = info_path or os.path.join(self.output_dir, 'info.json')
        self.info["info_path"] = self.info_path
        self.whisper_result_path = whisper_result_path or os.path.join(self.output_dir, 'whisper_result.json')
        self.info["whisper_result_path"] = self.whisper_result_path
        self.thumbnails_directory = os.path.join(self.output_dir, 'thumbnails')
        self.info["thumbnails_directory"] = self.thumbnails_directory
        self.frame_interval = if_none_get_default(frame_interval, default=1)
        self.original_dir = os.path.dirname(self.video_path)
        self.audio_path = os.path.join(self.output_dir, 'audio.wav')
        self.info['audio_path'] = self.audio_path
        self.is_optimized = is_optimized or is_video_optimized(self.video_path)
        
        # Initialize info_data with processed_steps
        self.info_data = self.get_info(info_path=self.info_path, data=self.info)
        self.info_data.setdefault("processed_steps", {
            "conversion": conversion,
            "audio_extraction": audio_extraction,
            "frame_extraction": frame_extraction,
            "ocr": ocr,
            "transcription": transcription,
            "text_processing": text_processing,
            "seo_data": seo_data
        })
        self.info_data["is_optimized"] = is_optimized or self.info_data.get("is_optimized", self.is_optimized)
        # Save initial info_data
        safe_dump_to_file(data=self.info_data, file_path=self.info_path)

    def get_info(self, info_path=None, data=None):
        data = data or {}
        self.info_path = info_path or self.info_path
        if not os.path.isfile(self.info_path):
            safe_dump_to_file(data=data, file_path=self.info_path)
        else:
            og_data = safe_load_from_file(self.info_path)
            og_data = og_data or {}
            og_data.update(data)
            safe_dump_to_file(data=og_data, file_path=self.info_path)
        return safe_load_from_file(self.info_path)

    def needs_conversion(self):
        if self.info_data["processed_steps"]["conversion"]:
            return self.info_data.get("video_text") is None
        
        if not self.is_optimized:
            optimize_video_for_safari(
                input_file=self.video_path,
                output_option=self.output_option,
                output_path=self.output_path,
                reencode=self.reencode
            )
        elif os.path.isfile(self.output_path):
            input_hash = compute_file_hash(self.video_path, chunk_size=8192)
            output_hash = compute_file_hash(self.output_path, chunk_size=8192)
            if input_hash == output_hash:
                self.info_data["processed_steps"]["conversion"] = True
                safe_dump_to_file(data=self.info_data, file_path=self.info_path)
                return
            self.final_output = handle_output_option(self.video_path, self.output_path, self.output_option)
        else:
            self.final_output = handle_output_option(self.video_path, self.output_path, self.output_option)
        
        self.info_data["is_optimized"] = True
        self.info_data["processed_steps"]["conversion"] = True
        safe_dump_to_file(data=self.info_data, file_path=self.info_path)
        return self.info_data.get("video_text") is None

    def extract_audio(self):
        if self.info_data["processed_steps"]["audio_extraction"]:
            return
        extract_audio_from_video(video_path=self.video_path, audio_path=self.audio_path)
        self.info_data["processed_steps"]["audio_extraction"] = True
        safe_dump_to_file(data=self.info_data, file_path=self.info_path)

    def needs_transcription(self):
        if self.info_data["processed_steps"]["transcription"]:
            return safe_load_from_file(self.whisper_result_path)
        
        whisper_result = {}
        if not os.path.isfile(self.whisper_result_path):
            whisper_result = transcribe_with_whisper_local(audio_path=self.audio_path,model_size=self.model_size)
            safe_dump_to_file(data=whisper_result, file_path=self.whisper_result_path)
        whisper_result = get_create_json_data(file_path=self.whisper_result_path, data=whisper_result)
        if not whisper_result.get('text') or not whisper_result.get('segments'):
            whisper_result = transcribe_with_whisper_local(audio_path=self.audio_path,model_size=self.model_size)
            safe_dump_to_file(data=whisper_result, file_path=self.whisper_result_path)
        
        self.info_data["processed_steps"]["transcription"] = True
        safe_dump_to_file(data=self.info_data, file_path=self.info_path)
        return whisper_result

    def needs_text(self, whisper_text=None):
        if self.info_data["processed_steps"]["text_processing"]:
            return self.info_data
        
        info_data = self.info_data
        whisper_text = whisper_text or get_whisper_text_data(info_data=info_data)
        summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
        full_text = whisper_text or self.info_data.get('title') or os.path.basename(self.info_data.get('video_path'))
        if info_data.get('description') is None:
            desc_len = 1000 if len(full_text) >1000 else len(full_text)-1
            info_data['description'] = summarizer(full_text[:desc_len], max_length=100, min_length=30, do_sample=False)[0]['summary_text']
        if info_data.get('keywords') is None:
            keywords =  refine_keywords(full_text=full_text, top_n=5,info_data={})
            info_data.update(keywords)
        if info_data.get('summary') is None:
            info_data['summary'] = get_summary(full_text=full_text, max_words=200, max_length=100, min_length=50)
        
        self.info_data = info_data
        self.info_data["processed_steps"]["text_processing"] = True
        safe_dump_to_file(data=self.info_data, file_path=self.info_path)
        return self.info_data

    def extract_frames(self):
        if self.info_data["processed_steps"]["frame_extraction"]:
            return
        
        video_path = self.video_path
        directory = self.thumbnails_directory
        interval = self.frame_interval
        vid_id = self.video_id

        clip = VideoFileClip(video_path)
        duration = int(clip.duration)

        os.makedirs(directory, exist_ok=True)
        for t in range(0, duration, interval):
            frame_file = os.path.join(directory, f"{vid_id}_frame_{t}.jpg")
            if not os.path.isfile(frame_file):
                frame = clip.get_frame(t)
                import cv2, numpy as np
                cv2.imwrite(frame_file, cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR))
        
        self.info_data["processed_steps"]["frame_extraction"] = True
        safe_dump_to_file(data=self.info_data, file_path=self.info_path)

    def ocr_images(self, existing_texts=None):
        if self.info_data["processed_steps"]["ocr"]:
            return self.info_data.get("video_text")
        
        texts = extract_image_texts_from_directory(
            directory=self.thumbnails_directory,
            image_texts=existing_texts or [],
            remove_phrases=self.remove_phrases)
        
        self.info_data["video_text"] = texts
        self.info_data["processed_steps"]["ocr"] = True
        safe_dump_to_file(data=self.info_data, file_path=self.info_path)
        return texts

    def get_seo_data(self):
        if self.info_data["processed_steps"]["seo_data"]:
            return self.info_data
        
        self.info_data = get_seo_data(info_data=self.info_data, infos_dir=self.output_dir)
        self.info_data["processed_steps"]["seo_data"] = True
        safe_dump_to_file(data=self.info_data, file_path=self.info_path)
        return self.info_data

    def run(self):
        """Perform the full OCR pipeline and update info_data & JSON on disk."""
        # Step 1: Video conversion
        self.needs_conversion()
        
        # Step 2: Audio extraction
        self.extract_audio()
        
        # Step 3: Frame extraction
        self.extract_frames()
        
        # Step 4: OCR on frames
        self.ocr_images(existing_texts=self.info_data.get("video_text"))
        
        # Step 5: Transcription
        whisper_result = self.needs_transcription()
        
        # Step 6: Text processing (summary, keywords, description)
        self.needs_text(whisper_text=whisper_result.get('text'))
        
        # Step 7: SEO data
        self.get_seo_data()
        
        # Final save
        safe_dump_to_file(data=self.info_data, file_path=self.info["info_path"])
        return self.info_data
