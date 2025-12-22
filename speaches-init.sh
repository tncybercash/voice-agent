#!/bin/bash
set -e

echo "Checking for required models..."

# Download TTS model if not exists
if [ ! -d "/home/ubuntu/.cache/huggingface/hub/models--speaches-ai--Kokoro-82M-v1.0-ONNX" ]; then
    echo "Downloading TTS model: speaches-ai/Kokoro-82M-v1.0-ONNX"
    python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='speaches-ai/Kokoro-82M-v1.0-ONNX')"
    echo "TTS model downloaded successfully!"
else
    echo "TTS model already exists, skipping download"
fi

# Download STT model if not exists  
if [ ! -d "/home/ubuntu/.cache/huggingface/hub/models--Systran--faster-whisper-small.en" ]; then
    echo "Downloading STT model: Systran/faster-whisper-small.en (this may take 2-3 minutes)"
    python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='Systran/faster-whisper-small.en')"
    echo "STT model downloaded successfully!"
else
    echo "STT model already exists, skipping download"
fi

echo "All models ready! Starting Speaches service..."

# Start the original Speaches service
exec uvicorn --factory speaches.main:create_app
