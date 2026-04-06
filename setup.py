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
    install_requires=['abstract_utilities','requests','spacy'],
    python_requires=">=3.6",
    # Add this line to include wheel format in your distribution
    setup_requires=['wheel'],
)
