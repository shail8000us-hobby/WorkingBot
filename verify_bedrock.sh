#!/bin/bash

# Bedrock CLI Verification Script
# Checks if everything is set up correctly

echo "🔍 Bedrock CLI Verification Checklist"
echo "====================================="
echo ""

SCRIPT_DIR="/Users/ssr/Projects/WorkingBot"
ERRORS=0

# 1. Check files exist
echo "1. Checking files..."
if [ -f "$SCRIPT_DIR/bedrock_cli.py" ]; then
    echo "   ✓ bedrock_cli.py exists"
else
    echo "   ✗ bedrock_cli.py NOT FOUND"
    ((ERRORS++))
fi

if [ -f "$SCRIPT_DIR/.bedrock_env" ]; then
    echo "   ✓ .bedrock_env exists"
else
    echo "   ✗ .bedrock_env NOT FOUND"
    ((ERRORS++))
fi

if [ -f "$SCRIPT_DIR/setup_bedrock.sh" ]; then
    echo "   ✓ setup_bedrock.sh exists"
else
    echo "   ✗ setup_bedrock.sh NOT FOUND"
    ((ERRORS++))
fi
echo ""

# 2. Check permissions
echo "2. Checking permissions..."
if [ -x "$SCRIPT_DIR/bedrock_cli.py" ]; then
    echo "   ✓ bedrock_cli.py is executable"
else
    echo "   ⚠️  bedrock_cli.py is not executable (fixing...)"
    chmod +x "$SCRIPT_DIR/bedrock_cli.py"
    echo "   ✓ Fixed!"
fi

PERMS=$(stat -f %OLp "$SCRIPT_DIR/.bedrock_env" 2>/dev/null || echo "000")
if [[ "$PERMS" == *"600"* ]] || [[ "$PERMS" == *"400"* ]]; then
    echo "   ✓ .bedrock_env has secure permissions ($PERMS)"
else
    echo "   ⚠️  .bedrock_env permissions may not be secure ($PERMS)"
fi
echo ""

# 3. Check Python
echo "3. Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo "   ✓ $PYTHON_VERSION"
else
    echo "   ✗ Python 3 not found"
    ((ERRORS++))
fi
echo ""

# 4. Check boto3
echo "4. Checking boto3..."
if python3 -c "import boto3" 2>/dev/null; then
    BOTO_VERSION=$(python3 -c "import boto3; print(boto3.__version__)" 2>/dev/null)
    echo "   ✓ boto3 $BOTO_VERSION installed"
else
    echo "   ✗ boto3 NOT installed"
    echo "   → Fix: pip3 install boto3"
    ((ERRORS++))
fi
echo ""

# 5. Check API Key
echo "5. Checking API key..."
source "$SCRIPT_DIR/.bedrock_env" 2>/dev/null
if [ -n "$AWS_BEARER_TOKEN_BEDROCK" ]; then
    KEY_SHORT="${AWS_BEARER_TOKEN_BEDROCK:0:10}...${AWS_BEARER_TOKEN_BEDROCK: -10}"
    echo "   ✓ API key loaded ($KEY_SHORT)"
else
    echo "   ✗ API key not found"
    ((ERRORS++))
fi
echo ""

# 6. Check shell alias
echo "6. Checking shell alias..."
if grep -q "alias amazon=" ~/.zshrc 2>/dev/null; then
    ALIAS_CMD=$(grep "alias amazon=" ~/.zshrc | tail -1 | cut -d= -f2-)
    echo "   ✓ amazon alias configured"
else
    echo "   ⚠️  Amazon alias not in ~/.zshrc"
    echo "   → Try: source ~/.zshrc"
fi
echo ""

# 7. Check directories
echo "7. Checking configuration directories..."
CONFIG_DIR="$SCRIPT_DIR/.bedrock_config"
if [ -d "$CONFIG_DIR" ] || mkdir -p "$CONFIG_DIR" 2>/dev/null; then
    echo "   ✓ .bedrock_config directory ready"
else
    echo "   ✗ Cannot create .bedrock_config directory"
    ((ERRORS++))
fi

SESSIONS_DIR="$CONFIG_DIR/sessions"
if [ -d "$SESSIONS_DIR" ] || mkdir -p "$SESSIONS_DIR" 2>/dev/null; then
    echo "   ✓ sessions directory ready"
else
    echo "   ✗ Cannot create sessions directory"
    ((ERRORS++))
fi
echo ""

# 8. Summary
echo "═══════════════════════════════════════════"
if [ $ERRORS -eq 0 ]; then
    echo "✅ Everything looks good!"
    echo ""
    echo "🚀 Next steps:"
    echo "   1. Reload shell: source ~/.zshrc"
    echo "   2. Start CLI: amazon"
    echo "   3. Type your question!"
    echo ""
else
    echo "❌ Found $ERRORS issue(s)"
    echo ""
    echo "📝 Common fixes:"
    echo "   • Install boto3: pip3 install boto3"
    echo "   • Reload shell: source ~/.zshrc"
    echo "   • Check API key: echo \$AWS_BEARER_TOKEN_BEDROCK"
    echo ""
fi
echo ""

# Detailed test option
echo "═══════════════════════════════════════════"
echo ""
read -p "Run detailed test? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Testing Python import..."
    python3 << 'EOF'
import sys
try:
    import boto3
    print(f"  ✓ boto3 module imported successfully")
    print(f"  ✓ Python version: {sys.version.split()[0]}")
except ImportError as e:
    print(f"  ✗ Error: {e}")
    sys.exit(1)
EOF
    
    echo ""
    echo "Testing bedrock_cli.py syntax..."
    if python3 -m py_compile "$SCRIPT_DIR/bedrock_cli.py" 2>/dev/null; then
        echo "  ✓ bedrock_cli.py syntax is valid"
    else
        echo "  ✗ Syntax error in bedrock_cli.py"
    fi
fi

echo ""
echo "✨ Verification complete!"
