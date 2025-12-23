#!/bin/bash
# Error Intelligence Demo Script
# Tests all features: expand/collapse, mark resolved, auto-vanish

echo "🎬 Error Intelligence Demo"
echo "=========================="
echo ""

# Step 1: Clean slate
echo "Step 1: Cleaning old errors..."
python3 services/error_resolver.py --resolve-old 1
echo ""

# Step 2: Create 10 test errors
echo "Step 2: Creating 10 test errors..."
for i in {1..10}; do
    python3 create_test_error.py > /dev/null 2>&1
done
echo "✅ Created 10 errors"
echo ""

# Step 3: Show statistics
echo "Step 3: Current statistics:"
curl -s 'http://localhost:5555/api/errors/statistics' | python3 -m json.tool
echo ""

# Step 4: Instructions
echo "📋 Now test in WebUI (http://localhost:5555):"
echo ""
echo "1. ✅ See '10 High Priority Issues' in Error Intelligence panel"
echo "2. ✅ First 3 errors displayed with full details"
echo "3. ✅ Click '▼ Show 7 More Errors' to expand"
echo "4. ✅ All 10 errors visible"
echo "5. ✅ Click '▲ Show Less' to collapse"
echo "6. ✅ Click 'Mark Resolved' on any error"
echo "7. ✅ Error vanishes immediately"
echo "8. ✅ Count updates automatically"
echo ""

# Step 5: Wait for user interaction
read -p "Press Enter when done testing (will clean up)..."
echo ""

# Step 6: Cleanup
echo "Cleaning up test errors..."
python3 services/error_resolver.py --resolve-old 1
echo ""
echo "✅ Demo complete!"
