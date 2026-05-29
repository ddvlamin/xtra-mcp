#!/bin/bash
set -e

# Configuration
REPO_OWNER="ddvlamin"
REPO_NAME="dev-config"
BRANCH="${BRANCH:-main}"

echo "=========================================================="
echo "Downloading Dotfiles and Skills from $REPO_OWNER/$REPO_NAME"
echo "=========================================================="

# Create temporary directory for download
TEMP_DIR=$(mktemp -d)
TARBALL_URL="https://github.com/$REPO_OWNER/$REPO_NAME/archive/refs/heads/$BRANCH.tar.gz"

# Clean up temp directory automatically on exit or error
trap 'rm -rf "$TEMP_DIR"' EXIT

echo "-> Downloading repository archive from GitHub ($BRANCH)..."
if ! curl -sSL "$TARBALL_URL" -o "$TEMP_DIR/archive.tar.gz"; then
    echo "ERROR: Failed to download archive from $TARBALL_URL"
    exit 1
fi

# --- FIX APPLIED HERE ---
# Forces Git Bash to accept the symlinks as shortcut files
export MSYS="winsymlinks:lnk"

echo "-> Extracting archive..."
mkdir -p "$TEMP_DIR/extracted"
tar -xzf "$TEMP_DIR/archive.tar.gz" -C "$TEMP_DIR/extracted" --strip-components=1

# Folders to copy
FOLDERS_TO_COPY=(".ai-dotfiles" ".skills")

# Loop through and deploy each folder
for folder in "${FOLDERS_TO_COPY[@]}"; do
    echo "-> Deploying $folder..."
    if [ -d "$TEMP_DIR/extracted/$folder" ]; then
        rm -rf "$folder"
        cp -r "$TEMP_DIR/extracted/$folder" ./
        echo "   [OK] $folder folder updated."
    else
        echo "   [WARNING] $folder folder not found in source repository."
    fi
done

echo "=========================================================="
echo "Sync Complete!"
echo "=========================================================="
