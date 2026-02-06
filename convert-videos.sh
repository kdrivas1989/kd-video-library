#!/bin/bash
# Video Converter - Converts MKV, AVI, MTS files to MP4
# Usage: ./convert-videos.sh [folder_path]
# If no folder specified, uses current directory

FOLDER="${1:-.}"

echo "========================================"
echo "  Video Converter (MKV/AVI/MTS -> MP4)"
echo "========================================"
echo "Folder: $FOLDER"
echo ""

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "ERROR: ffmpeg is not installed."
    echo "Install with: brew install ffmpeg"
    exit 1
fi

# Find all files to convert
count=0
converted=0
failed=0

# Use find with -print0 and while read to handle special characters
while IFS= read -r -d '' file; do
    count=$((count + 1))

    filename=$(basename "$file")
    dirname=$(dirname "$file")
    name="${filename%.*}"
    output="$dirname/$name.mp4"

    # Skip if output already exists
    if [ -f "$output" ]; then
        echo "SKIP: $name.mp4 already exists"
        continue
    fi

    echo "----------------------------------------"
    echo "Converting ($count): $filename"
    echo "       To: $name.mp4"
    echo ""

    if ffmpeg -i "$file" -c:v libx264 -preset fast -crf 23 -c:a aac -b:a 128k -movflags +faststart "$output" -y -loglevel warning -stats 2>&1; then
        echo ""
        echo "SUCCESS: $name.mp4"
        converted=$((converted + 1))
    else
        echo ""
        echo "FAILED: $filename"
        failed=$((failed + 1))
    fi
    echo ""
done < <(find "$FOLDER" -maxdepth 1 -type f \( -iname "*.mkv" -o -iname "*.avi" -o -iname "*.mts" -o -iname "*.m2ts" \) -print0 2>/dev/null)

if [ $count -eq 0 ]; then
    echo "No MKV, AVI, or MTS files found in $FOLDER"
    exit 0
fi

echo "========================================"
echo "Complete! Converted: $converted, Failed: $failed, Skipped: $((count - converted - failed))"
echo "========================================"
