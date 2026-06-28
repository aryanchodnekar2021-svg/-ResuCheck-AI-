#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Download NLP models and nltk datasets
python -m spacy download en_core_web_sm
python -m nltk.downloader stopwords
python -m nltk.downloader words
