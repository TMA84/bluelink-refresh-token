#!/bin/bash
# Sync web.py from standalone/ to addon folders.
# Only edit standalone/web.py — this script copies it to the other locations.
cp standalone/web.py bluelink-token/web.py
cp standalone/web.py bluelink-token-dev/web.py
echo "✓ web.py synced to bluelink-token/ and bluelink-token-dev/"
