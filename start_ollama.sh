#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# 🤖 Ollama AI Service Startup Script
# ═══════════════════════════════════════════════════════════════════════════
#
# This script manages the Ollama AI service for GridBot Pro's AI Advisor
#
# Usage:
#   ./start_ollama.sh           # Start Ollama service
#   ./start_ollama.sh status    # Check status
#   ./start_ollama.sh stop      # Stop service
#   ./start_ollama.sh restart   # Restart service
#
# ═══════════════════════════════════════════════════════════════════════════

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
OLLAMA_URL="http://localhost:11434"
REQUIRED_MODEL="llama3.1:8b"
STARTUP_TIMEOUT=30

# ═══════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════

print_header() {
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  🤖 ${PURPLE}Ollama AI Service Manager${NC}                                             ${CYAN}║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_step() {
    echo -e "${CYAN}▶ $1${NC}"
}

# ═══════════════════════════════════════════════════════════════════════════
# Check Functions
# ═══════════════════════════════════════════════════════════════════════════

check_ollama_installed() {
    print_step "Checking Ollama installation..."
    
    if command -v ollama &> /dev/null; then
        OLLAMA_VERSION=$(ollama --version 2>&1 | head -n 1)
        print_success "Ollama found: $OLLAMA_VERSION"
        return 0
    else
        print_error "Ollama is not installed!"
        echo ""
        print_info "Install Ollama from: https://ollama.ai"
        echo ""
        print_info "Quick install:"
        echo "  curl -fsSL https://ollama.ai/install.sh | sh"
        return 1
    fi
}

check_ollama_running() {
    if curl -s "$OLLAMA_URL/api/tags" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

get_ollama_status() {
    if check_ollama_running; then
        echo "running"
    else
        echo "stopped"
    fi
}

check_model_available() {
    print_step "Checking model availability..."
    
    if ! check_ollama_running; then
        print_warning "Ollama service is not running. Cannot check models."
        return 1
    fi
    
    # Get list of models
    MODELS=$(curl -s "$OLLAMA_URL/api/tags" 2>/dev/null | grep -o '"name":"[^"]*"' | cut -d'"' -f4 || echo "")
    
    if [ -z "$MODELS" ]; then
        print_warning "No models found!"
        return 1
    fi
    
    # Check if required model exists
    if echo "$MODELS" | grep -q "$REQUIRED_MODEL"; then
        print_success "Required model found: $REQUIRED_MODEL"
        
        # Get model size
        MODEL_SIZE=$(curl -s "$OLLAMA_URL/api/tags" 2>/dev/null | grep -A5 "$REQUIRED_MODEL" | grep '"size"' | grep -o '[0-9]*' | head -1)
        if [ -n "$MODEL_SIZE" ]; then
            SIZE_GB=$(echo "scale=1; $MODEL_SIZE / 1073741824" | bc 2>/dev/null || echo "?")
            print_info "Model size: ${SIZE_GB}GB"
        fi
        return 0
    else
        print_error "Required model not found: $REQUIRED_MODEL"
        print_info "Available models: $MODELS"
        echo ""
        print_info "Download model with: ollama pull $REQUIRED_MODEL"
        return 1
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# Service Management Functions
# ═══════════════════════════════════════════════════════════════════════════

start_ollama() {
    print_step "Starting Ollama service..."
    
    # Check if already running
    if check_ollama_running; then
        print_warning "Ollama is already running!"
        return 0
    fi
    
    # Start Ollama in background
    nohup ollama serve > /dev/null 2>&1 &
    OLLAMA_PID=$!
    
    print_info "Started Ollama (PID: $OLLAMA_PID)"
    print_step "Waiting for service to be ready..."
    
    # Wait for service to be ready
    local elapsed=0
    while [ $elapsed -lt $STARTUP_TIMEOUT ]; do
        if check_ollama_running; then
            print_success "Ollama service is ready!"
            return 0
        fi
        echo -n "."
        sleep 1
        elapsed=$((elapsed + 1))
    done
    
    echo ""
    print_error "Ollama service failed to start within ${STARTUP_TIMEOUT}s"
    return 1
}

stop_ollama() {
    print_step "Stopping Ollama service..."
    
    if ! check_ollama_running; then
        print_warning "Ollama is not running"
        return 0
    fi
    
    # Find and kill Ollama process
    pkill -f "ollama serve" 2>/dev/null || true
    
    # Wait for process to stop
    sleep 2
    
    if check_ollama_running; then
        print_error "Failed to stop Ollama service"
        return 1
    else
        print_success "Ollama service stopped"
        return 0
    fi
}

restart_ollama() {
    print_step "Restarting Ollama service..."
    stop_ollama
    sleep 2
    start_ollama
}

test_ollama_connection() {
    print_step "Testing Ollama connection..."
    
    if ! check_ollama_running; then
        print_error "Service is not running"
        return 1
    fi
    
    # Test with a simple prompt
    print_info "Sending test query..."
    
    RESPONSE=$(curl -s -X POST "$OLLAMA_URL/api/generate" \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"$REQUIRED_MODEL\",
            \"prompt\": \"Say 'OK' if you are working.\",
            \"stream\": false,
            \"options\": {
                \"num_predict\": 10
            }
        }" 2>/dev/null)
    
    if [ $? -eq 0 ] && [ -n "$RESPONSE" ]; then
        print_success "Connection test successful!"
        
        # Extract response text
        ANSWER=$(echo "$RESPONSE" | grep -o '"response":"[^"]*"' | cut -d'"' -f4 | head -c 50)
        if [ -n "$ANSWER" ]; then
            print_info "AI Response: $ANSWER"
        fi
        return 0
    else
        print_error "Connection test failed"
        return 1
    fi
}

show_status() {
    print_header
    
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}Status Summary${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Check installation
    if check_ollama_installed; then
        STATUS="✅"
    else
        STATUS="❌"
        echo ""
        return 1
    fi
    
    echo ""
    
    # Check service status
    print_step "Checking service status..."
    if check_ollama_running; then
        print_success "Service Status: RUNNING"
        SERVICE_STATUS="✅"
    else
        print_error "Service Status: STOPPED"
        SERVICE_STATUS="❌"
    fi
    
    echo ""
    
    # Check model
    if check_ollama_running; then
        check_model_available
        if [ $? -eq 0 ]; then
            MODEL_STATUS="✅"
        else
            MODEL_STATUS="❌"
        fi
    else
        print_warning "Cannot check models - service not running"
        MODEL_STATUS="⚠️"
    fi
    
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}Overall Status:${NC}"
    echo ""
    echo -e "  Ollama Installed:  $STATUS"
    echo -e "  Service Running:   $SERVICE_STATUS"
    echo -e "  Model Available:   $MODEL_STATUS"
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════${NC}"
}

# ═══════════════════════════════════════════════════════════════════════════
# Main Script
# ═══════════════════════════════════════════════════════════════════════════

main() {
    local command="${1:-start}"
    
    case "$command" in
        start)
            print_header
            
            # Check if Ollama is installed
            if ! check_ollama_installed; then
                exit 1
            fi
            
            echo ""
            
            # Start service
            if ! start_ollama; then
                exit 1
            fi
            
            echo ""
            
            # Check model
            if ! check_model_available; then
                print_warning "Service is running but model is not available"
                print_info "Download model: ollama pull $REQUIRED_MODEL"
                exit 1
            fi
            
            echo ""
            
            # Test connection
            if ! test_ollama_connection; then
                print_warning "Service is running but connection test failed"
                exit 1
            fi
            
            echo ""
            echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════${NC}"
            print_success "Ollama AI Service is ready!"
            echo ""
            print_info "API URL: $OLLAMA_URL"
            print_info "Model: $REQUIRED_MODEL"
            echo ""
            print_info "Next steps:"
            echo "  1. Keep this terminal open (or use nohup)"
            echo "  2. Restart WebUI backend to use AI Advisor"
            echo "  3. Test AI Advisor in WebUI (bottom-right corner)"
            echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════${NC}"
            ;;
        
        stop)
            print_header
            stop_ollama
            ;;
        
        restart)
            print_header
            restart_ollama
            ;;
        
        status)
            show_status
            ;;
        
        test)
            print_header
            check_ollama_installed || exit 1
            echo ""
            check_model_available || exit 1
            echo ""
            test_ollama_connection || exit 1
            ;;
        
        *)
            print_header
            print_error "Unknown command: $command"
            echo ""
            echo "Usage:"
            echo "  $0 [start|stop|restart|status|test]"
            echo ""
            echo "Commands:"
            echo "  start     - Start Ollama service (default)"
            echo "  stop      - Stop Ollama service"
            echo "  restart   - Restart Ollama service"
            echo "  status    - Show status summary"
            echo "  test      - Test connection"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
