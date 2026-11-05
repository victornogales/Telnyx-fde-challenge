#!/usr/bin/env bash
set -euo pipefail

SRC="functions/_shared"
DESTINATIONS=(
  "functions/refill-webhook/function/shared"
  "functions/refill-mcp/function/shared"
)

for dest in "${DESTINATIONS[@]}"; do
  echo "Syncing $SRC → $dest"
  rm -rf "$dest"
  mkdir -p "$dest"
  cp -r "$SRC"/* "$dest/"
done

echo "Done."
