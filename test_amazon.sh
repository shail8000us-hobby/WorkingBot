#!/bin/bash

# Quick test of amazon CLI
# This script tests if the amazon command works

echo "Testing amazon CLI..."
echo ""

# Source the environment
source /Users/ssr/Projects/WorkingBot/.bedrock_env

# Test the CLI
python3 /Users/ssr/Projects/WorkingBot/bedrock_cli.py << 'EOF'
Hello, can you help me?
/exit
EOF
