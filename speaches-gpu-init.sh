#!/bin/bash
set -e

echo "Checking for required GPU models..."

# Download TTS model for GPU (same ONNX model works with GPU)
if [ ! -d "/home/ubuntu/.cache/huggingface/hub/models--speaches-ai--Kokoro-82M-v1.0-ONNX" ]; then
    echo "Downloading TTS model: speaches-ai/Kokoro-82M-v1.0-ONNX"
    python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='speaches-ai/Kokoro-82M-v1.0-ONNX')"
    echo "TTS model downloaded successfully!"
else
    echo "TTS model already exists, skipping download"
fi

# Download STT model for GPU - using large-v3 for better accuracy with CUDA
if [ ! -d "/home/ubuntu/.cache/huggingface/hub/models--Systran--faster-whisper-base.en" ]; then
    echo "Downloading STT model: Systran/faster-whisper-base.en"
    python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='Systran/faster-whisper-base.en')"
    echo "STT model downloaded successfully!"
else
    echo "STT model already exists, skipping download"
fi

echo "All GPU models ready! Starting Speaches service..."

# Start the original Speaches service
exec uvicorn --factory speaches.main:create_app
