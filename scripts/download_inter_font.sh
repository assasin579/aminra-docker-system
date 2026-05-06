#!/usr/bin/env bash
# Download Inter font (subset Latin + Vietnamese) into templates_html/_shared/fonts/
#
# Source: https://rsms.me/inter/font-files/
# License: SIL Open Font License v1.1
#
# Run from repo root: bash scripts/download_inter_font.sh
set -euo pipefail

DEST="${PWD}/backend/templates_html/_shared/fonts"
mkdir -p "$DEST"

# Inter v4.x web fonts (subset already includes Latin Extended + Vietnamese)
BASE_URL="https://rsms.me/inter/font-files"

declare -A WEIGHTS=(
  ["Regular"]="Inter-Regular.woff2"
  ["Medium"]="Inter-Medium.woff2"
  ["SemiBold"]="Inter-SemiBold.woff2"
  ["Bold"]="Inter-Bold.woff2"
  ["Black"]="Inter-Black.woff2"
  ["Italic"]="Inter-Italic.woff2"
)

echo "Downloading Inter weights to $DEST"
for weight in "${!WEIGHTS[@]}"; do
  filename="${WEIGHTS[$weight]}"
  if [[ -f "$DEST/$filename" ]]; then
    echo "  [skip] $filename already exists"
    continue
  fi
  echo "  [get]  $filename"
  curl -sSL --fail \
    "$BASE_URL/$filename" \
    -o "$DEST/$filename"
done

echo
echo "Done. Verify with:"
echo "  ls -lh $DEST/*.woff2"
