#!/bin/bash
# Script to fix API URLs from 5557 to 5555 and use centralized API client

cd webui/frontend-v3/src/components

# Find all files with localhost:5557
files=$(grep -r "localhost:5557" --include="*.tsx" --include="*.ts" -l .)

echo "Found $(echo "$files" | wc -l) files with localhost:5557"
echo "Files to update:"
echo "$files"

# Note: Manual review needed - some may need to use api.ts client instead
