from time import time
import setuptools
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()
setuptools.setup(
    name='abstract_videos',
    version='0.0.0.261',
    author='putkoff',
    author_email='partners@abstractendeavors.com',
    description='A structured pipeline for transforming video content into **searchable, metadata-rich, and SEO-optimized assets**, combining ingestion, transcription, OCR, NLP enrichment, and persistent storage.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    install_requires=['abstract_utilities','requests','spacy','yt-dlp'],
    python_requires=">=3.6",
    entry_points={
        "console_scripts": [
            "abstract-video-dl=abstract_videos.pipeline.videoDownloader.simple_downloader:_main",
            "abstract-video-doctor=abstract_videos.pipeline.videoDownloader.simple_downloader:_print_doctor",
        ],
    },
    # Note: ffmpeg is an optional *system* dependency (not pip-installable).
    # It is required only for merging high-quality adaptive streams. Run
    # `abstract-video-doctor` to verify your environment.
    # Add this line to include wheel format in your distribution
    setup_requires=['wheel'],
)
