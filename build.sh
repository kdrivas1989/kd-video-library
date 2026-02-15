#!/usr/bin/env bash
# Build script for Render - installs ffmpeg static binary

set -e

# Install Python dependencies
pip install -r requirements.txt

# Download and install static ffmpeg binary
FFMPEG_DIR="/opt/render/project/src/bin"
mkdir -p "$FFMPEG_DIR"

if [ ! -f "$FFMPEG_DIR/ffmpeg" ]; then
    echo "Downloading ffmpeg static binary..."
    cd "$FFMPEG_DIR"
    curl -L --retry 3 https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz | tar xJ --strip-components=1
    chmod +x ffmpeg ffprobe
else
    echo "ffmpeg already installed, skipping download"
fi

# Verify installation
if "$FFMPEG_DIR/ffmpeg" -version > /dev/null 2>&1; then
    echo "ffmpeg installed and working at $FFMPEG_DIR/ffmpeg"
else
    echo "ERROR: ffmpeg installation failed!" >&2
    # Try apt-get as fallback on Render
    if command -v apt-get > /dev/null 2>&1; then
        echo "Trying apt-get install as fallback..."
        apt-get update && apt-get install -y ffmpeg
    fi
fi
