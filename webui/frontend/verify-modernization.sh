#!/bin/bash
# Verification script for Frontend V1 modernization

echo "🔍 Verifying Frontend V1 Modernization..."
echo ""

# Check if all key files exist
echo "📁 Checking files..."
files=(
    "src/setupTests.js"
    "src/utils/offlineStorage.js"
    "src/components/OfflineIndicator.js"
    "src/components/ui/Button.js"
    "src/components/ui/Card.js"
    "src/components/ui/Badge.js"
    "src/components/ui/Input.js"
    ".eslintrc.js"
    ".prettierrc"
    "README.md"
    "DESIGN_SYSTEM.md"
    "MODERNIZATION_SUMMARY.md"
)

missing=0
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file (missing)"
        ((missing++))
    fi
done

echo ""
echo "📦 Checking package.json scripts..."
scripts=("test:coverage" "lint" "format" "analyze")
for script in "${scripts[@]}"; do
    if grep -q "\"$script\"" package.json; then
        echo "  ✅ npm run $script"
    else
        echo "  ❌ npm run $script (missing)"
        ((missing++))
    fi
done

echo ""
echo "🎯 Summary:"
if [ $missing -eq 0 ]; then
    echo "  ✅ All modernization tasks verified!"
    echo "  ✅ Ready to test with: npm install && npm start"
else
    echo "  ⚠️  $missing items missing or incomplete"
fi

echo ""
echo "📊 Next Steps:"
echo "  1. npm install (if not done)"
echo "  2. npm test (run tests)"
echo "  3. npm run lint (check code)"
echo "  4. npm run build (create production build)"
echo "  5. Test on http://localhost:5555"
