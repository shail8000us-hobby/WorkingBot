#!/bin/bash
# Documentation Cleanup Script
# Created: October 30, 2025
# Purpose: Delete redundant .md files, keep only consolidated docs

echo "🗑️  WorkingBot Documentation Cleanup"
echo "======================================"
echo ""

# Files to KEEP (critical documentation)
KEEP_FILES=(
    "README.md"
    "START_HERE.md"
    "USER_MANUAL.md"
    "BOT_STRUCTURE.md"
    "AI_CONTEXT.md"
    "AI_CONTEXT.md.old"
    "AI_CONTEXT.md.bak"
    "CHANGELOG.md"
    "LICENSE.md"
)

# Directories to SKIP (don't delete .md files here)
SKIP_DIRS=(
    ".doc_backup_*"
    "webui/frontend/node_modules"
    "webui/frontend/build"
    ".git"
    "venv"
    "__pycache__"
)

# Count files
echo "📊 Counting markdown files..."
TOTAL_MD=$(find . -name "*.md" -type f ! -path "./.doc_backup*" ! -path "./webui/frontend/node_modules/*" ! -path "./.git/*" | wc -l)
echo "Total .md files found: $TOTAL_MD"
echo ""

# Build exclusion pattern for find
EXCLUDE_PATTERN=""
for dir in "${SKIP_DIRS[@]}"; do
    EXCLUDE_PATTERN="$EXCLUDE_PATTERN ! -path './$dir/*'"
done

echo "📝 Files that will be KEPT:"
echo "-------------------------"
for file in "${KEEP_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    fi
done
echo ""

echo "🔍 Analyzing files to delete..."
echo ""

# Create deletion list
DELETION_LIST=$(mktemp)
DELETE_COUNT=0

# Find all .md files
find . -name "*.md" -type f \
    ! -path "./.doc_backup*" \
    ! -path "./webui/frontend/node_modules/*" \
    ! -path "./.git/*" > "$DELETION_LIST"

# Filter out files to keep
for keep_file in "${KEEP_FILES[@]}"; do
    sed -i.bak "/$keep_file$/d" "$DELETION_LIST"
done

# Count files to delete
DELETE_COUNT=$(wc -l < "$DELETION_LIST")

echo "📊 Summary:"
echo "  Total files: $TOTAL_MD"
echo "  Files to keep: ${#KEEP_FILES[@]}"
echo "  Files to delete: $DELETE_COUNT"
echo ""

# Show sample of files to delete
echo "📄 Sample files to be deleted (first 20):"
echo "----------------------------------------"
head -20 "$DELETION_LIST"
if [ $DELETE_COUNT -gt 20 ]; then
    echo "  ... and $(($DELETE_COUNT - 20)) more files"
fi
echo ""

# Confirmation
read -p "⚠️  Delete $DELETE_COUNT files? (yes/NO): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo ""
    echo "❌ Deletion cancelled. No files were deleted."
    echo ""
    echo "💡 Tip: Files are backed up in .doc_backup_20251030_132749/"
    rm "$DELETION_LIST"
    rm "${DELETION_LIST}.bak" 2>/dev/null
    exit 0
fi

echo ""
echo "🗑️  Deleting $DELETE_COUNT files..."

# Delete files
DELETED=0
while IFS= read -r file; do
    if [ -f "$file" ]; then
        rm "$file"
        DELETED=$((DELETED + 1))
        if [ $((DELETED % 100)) -eq 0 ]; then
            echo "  Deleted $DELETED files..."
        fi
    fi
done < "$DELETION_LIST"

echo ""
echo "✅ Deletion complete!"
echo ""
echo "📊 Final Summary:"
echo "  Files deleted: $DELETED"
echo "  Files kept: ${#KEEP_FILES[@]}"
echo "  Backup location: .doc_backup_20251030_132749/"
echo ""

# Count remaining .md files
REMAINING=$(find . -name "*.md" -type f ! -path "./.doc_backup*" ! -path "./webui/frontend/node_modules/*" ! -path "./.git/*" | wc -l)
echo "  Remaining .md files: $REMAINING"
echo ""

echo "🎉 Documentation cleanup complete!"
echo ""
echo "📚 Core Documentation:"
for file in "${KEEP_FILES[@]}"; do
    if [ -f "$file" ] && [[ ! "$file" =~ \.old$ ]] && [[ ! "$file" =~ \.bak$ ]]; then
        SIZE=$(du -h "$file" | cut -f1)
        echo "  - $file ($SIZE)"
    fi
done
echo ""

echo "💾 Backup available at: .doc_backup_20251030_132749/"
echo ""

# Cleanup temp files
rm "$DELETION_LIST"
rm "${DELETION_LIST}.bak" 2>/dev/null

echo "✨ All done! Your documentation is now clean and organized."
