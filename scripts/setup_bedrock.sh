#!/bin/bash

# Amazon Bedrock CLI Setup Script
# This script configures your environment to use Claude Opus 4.6 via Amazon Bedrock

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_KEY="${1:-}"

echo "🚀 Amazon Bedrock Claude CLI Setup"
echo "===================================="
echo ""

# Check if API key is provided
if [ -z "$API_KEY" ]; then
    echo "❌ Error: API key required"
    echo ""
    echo "Usage: bash setup_bedrock.sh 'YOUR_API_KEY'"
    echo ""
    echo "Example:"
    echo "  bash setup_bedrock.sh 'ABSKQmVkcm9ja0FQSUtleS1ibXMwLWF0LTAzMjE1NTk4Mjg1NDpwTkozeUNzMHI0Qk1lN0xNd0xBY1BPNzRhUzltTlJ2Nm1wYnZ3VzZxd2JyVjZZTVl5Wko1ZWRiSFJGaz0='"
    exit 1
fi

echo "✓ Setting up Bedrock CLI..."
echo ""

# 1. Check Python installation
echo "1️⃣  Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "   ✓ Python $PYTHON_VERSION found"
echo ""

# 2. Install boto3
echo "2️⃣  Installing/checking boto3..."
python3 -m pip install boto3 -q 2>/dev/null || echo "   ℹ️  boto3 installation may require additional setup"
echo "   ✓ boto3 ready"
echo ""

# 3. Create .bedrock_env file
echo "3️⃣  Creating credentials file..."
ENV_FILE="$SCRIPT_DIR/.bedrock_env"
cat > "$ENV_FILE" << EOF
# Amazon Bedrock Credentials
# DO NOT COMMIT THIS FILE TO GIT
export AWS_BEARER_TOKEN_BEDROCK='$API_KEY'
export AWS_REGION='us-east-1'

# If you have AWS credentials
# export AWS_ACCESS_KEY_ID='your_access_key'
# export AWS_SECRET_ACCESS_KEY='your_secret_key'
# export AWS_SESSION_TOKEN='your_session_token' # if using temporary credentials
EOF
chmod 600 "$ENV_FILE"
echo "   ✓ Credentials file created: $ENV_FILE"
echo ""

# 4. Update shell config
echo "4️⃣  Setting up shell aliases..."
SHELL_CONFIG=""
if [ -f ~/.zshrc ]; then
    SHELL_CONFIG=~/.zshrc
elif [ -f ~/.bashrc ]; then
    SHELL_CONFIG=~/.bashrc
fi

if [ -n "$SHELL_CONFIG" ]; then
    # Check if alias already exists
    if ! grep -q "alias amazon=" "$SHELL_CONFIG"; then
        cat >> "$SHELL_CONFIG" << EOF

# Amazon Bedrock CLI Alias
source '$ENV_FILE'
alias amazon='python3 $SCRIPT_DIR/bedrock_cli.py'
EOF
        echo "   ✓ Alias added to $SHELL_CONFIG"
    else
        echo "   ℹ️  Alias already exists in $SHELL_CONFIG"
    fi
else
    echo "   ⚠️  Could not find shell config (.zshrc or .bashrc)"
fi
echo ""

# 5. Final instructions
echo "5️⃣  Setup complete!"
echo ""
echo "🎯 Next Steps:"
echo "   1. Reload your shell:"
echo "      source $SHELL_CONFIG"
echo ""
echo "   2. Test the CLI:"
echo "      amazon"
echo ""
echo "   3. Try a command:"
echo "      You: Hello, what is 2+2?"
echo ""
echo "✨ You can now use 'amazon' command anywhere in your terminal!"
echo ""
echo "📝 Configuration file: $ENV_FILE"
echo "   Keep this file secure and do not commit to version control"
echo ""
