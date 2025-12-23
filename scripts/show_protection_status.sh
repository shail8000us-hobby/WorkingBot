#!/bin/bash

# Script to show protection status of production-locked files
# Quick health check of the protection system

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

REGISTRY=".locked_files_registry.json"

# Check if registry exists
if [ ! -f "$REGISTRY" ]; then
    echo -e "${RED}❌ Registry not found: $REGISTRY${NC}"
    echo "   Protection system may not be initialized"
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${RED}❌ Error: 'jq' command not found${NC}"
    echo "   Install with: brew install jq"
    exit 1
fi

# Header
echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}${BOLD}           🔒 PRODUCTION-LOCKED FILES STATUS 🔒${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
echo ""

# Registry info
VERSION=$(jq -r '.version' "$REGISTRY")
LAST_UPDATED=$(jq -r '.last_updated' "$REGISTRY")
echo -e "${BOLD}Registry Information:${NC}"
echo -e "  Version:      ${GREEN}$VERSION${NC}"
echo -e "  Last Updated: ${CYAN}$LAST_UPDATED${NC}"
echo ""

# Protection status
echo -e "${BOLD}Protection Status:${NC}"

PROTECTION_ENABLED=$(jq -r '.protection_enabled' "$REGISTRY")
if [ "$PROTECTION_ENABLED" = "true" ]; then
    echo -e "  Enabled:      ${GREEN}✅ YES${NC}"
else
    echo -e "  Enabled:      ${RED}❌ NO${NC}"
fi

REQUIRE_APPROVAL=$(jq -r '.require_approval' "$REGISTRY")
if [ "$REQUIRE_APPROVAL" = "true" ]; then
    echo -e "  Approval Req: ${GREEN}✅ YES${NC}"
else
    echo -e "  Approval Req: ${YELLOW}⚠️  NO${NC}"
fi

REQUIRE_PASSWORD=$(jq -r '.require_password' "$REGISTRY")
if [ "$REQUIRE_PASSWORD" = "true" ]; then
    echo -e "  Password Req: ${GREEN}✅ YES${NC}"
else
    echo -e "  Password Req: ${YELLOW}⚠️  NO${NC}"
fi

INTEGRITY_CHECK=$(jq -r '.integrity_check_on_startup' "$REGISTRY")
if [ "$INTEGRITY_CHECK" = "true" ]; then
    echo -e "  Integrity:    ${GREEN}✅ ENABLED${NC}"
else
    echo -e "  Integrity:    ${YELLOW}⚠️  DISABLED${NC}"
fi

echo ""

# Git protection
echo -e "${BOLD}Git Protection:${NC}"
BRANCH=$(jq -r '.git_protection.protected_branch' "$REGISTRY")
TAG=$(jq -r '.git_protection.tag' "$REGISTRY")
echo -e "  Branch:       ${BLUE}$BRANCH${NC}"
echo -e "  Tag:          ${BLUE}$TAG${NC}"

# Check if we're on the protected branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
if [ "$CURRENT_BRANCH" = "$BRANCH" ]; then
    echo -e "  Current:      ${GREEN}✅ On protected branch${NC}"
else
    echo -e "  Current:      ${YELLOW}⚠️  On branch: $CURRENT_BRANCH${NC}"
fi

# Check if pre-commit hook exists
if [ -x ".git/hooks/pre-commit" ]; then
    echo -e "  Pre-commit:   ${GREEN}✅ INSTALLED${NC}"
else
    echo -e "  Pre-commit:   ${RED}❌ NOT FOUND${NC}"
fi

echo ""

# Locked files
echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}Locked Files:${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
echo ""

jq -r '.locked_files[] | "\(.path)|\(.status)|\(.version)|\(.risk_level)|\(.sha256)"' "$REGISTRY" | while IFS='|' read -r path status version risk sha256; do
    echo -e "${BOLD}🔒 $path${NC}"
    echo -e "   Status:      $status"
    echo -e "   Version:     $version"
    echo -e "   Risk:        ${RED}$risk${NC}"
    
    # Check if file exists
    if [ -f "$path" ]; then
        echo -e "   File:        ${GREEN}✅ EXISTS${NC}"
        
        # Check permissions
        PERMS=$(ls -l "$path" | awk '{print $1}')
        if [[ "$PERMS" =~ ^-r--r--r-- ]]; then
            echo -e "   Permissions: ${GREEN}✅ READ-ONLY (444)${NC}"
        else
            echo -e "   Permissions: ${YELLOW}⚠️  $PERMS (not read-only)${NC}"
        fi
        
        # Verify checksum
        if [ "$sha256" != "TO_BE_GENERATED" ] && [ -n "$sha256" ]; then
            ACTUAL_HASH=$(shasum -a 256 "$path" | awk '{print $1}')
            if [ "$ACTUAL_HASH" = "$sha256" ]; then
                echo -e "   Integrity:   ${GREEN}✅ VERIFIED${NC}"
            else
                echo -e "   Integrity:   ${RED}❌ FAILED${NC}"
                echo -e "   Expected:    ${sha256:0:32}..."
                echo -e "   Actual:      ${ACTUAL_HASH:0:32}..."
            fi
        else
            echo -e "   Integrity:   ${YELLOW}⚠️  NO CHECKSUM${NC}"
        fi
        
        # Check if file has color tag (macOS)
        if command -v osascript &> /dev/null; then
            TAG_INDEX=$(osascript -e "tell application \"Finder\"" \
                                 -e "set theFile to POSIX file \"$(pwd)/$path\" as alias" \
                                 -e "return label index of theFile" \
                                 -e "end tell" 2>/dev/null)
            if [ "$TAG_INDEX" = "6" ]; then
                echo -e "   Finder Tag:  ${RED}🔴 RED (LOCKED)${NC}"
            else
                echo -e "   Finder Tag:  ${YELLOW}⚠️  NOT TAGGED${NC}"
            fi
        fi
    else
        echo -e "   File:        ${RED}❌ NOT FOUND${NC}"
    fi
    
    # Get critical features
    echo -e "   ${BOLD}Critical Features:${NC}"
    jq -r --arg path "$path" '.locked_files[] | select(.path == $path) | .critical_features[]' "$REGISTRY" | while read -r feature; do
        echo -e "     ${YELLOW}•${NC} $feature"
    done
    
    echo ""
done

# Protection layers
echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}Active Protection Layers:${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
echo ""

jq -r '.protection_layers[]' "$REGISTRY" | while read -r layer; do
    echo -e "  ${GREEN}✅${NC} $layer"
done

echo ""

# Checksums directory
echo -e "${BOLD}Checksum Files:${NC}"
if [ -d ".checksums" ]; then
    CHECKSUM_COUNT=$(ls -1 .checksums/*.sha256 2>/dev/null | wc -l | tr -d ' ')
    echo -e "  Directory:    ${GREEN}✅ EXISTS${NC}"
    echo -e "  Files:        ${CYAN}$CHECKSUM_COUNT checksum(s)${NC}"
    ls -1 .checksums/*.sha256 2>/dev/null | while read -r file; do
        echo -e "    ${BLUE}•${NC} $(basename $file)"
    done
else
    echo -e "  Directory:    ${RED}❌ NOT FOUND${NC}"
fi

echo ""

# Audit log
echo -e "${BOLD}Audit Log:${NC}"
AUDIT_LOG=$(jq -r '.audit_log' "$REGISTRY")
if [ -f "$AUDIT_LOG" ]; then
    LOG_COUNT=$(wc -l < "$AUDIT_LOG" | tr -d ' ')
    echo -e "  File:         ${GREEN}✅ $AUDIT_LOG${NC}"
    echo -e "  Entries:      ${CYAN}$LOG_COUNT event(s)${NC}"
    
    # Show last 3 entries
    if [ "$LOG_COUNT" -gt 0 ]; then
        echo -e "  ${BOLD}Recent Events:${NC}"
        tail -3 "$AUDIT_LOG" | jq -r '"    \(.timestamp) | \(.user) | \(.action)"' 2>/dev/null || echo "    (Unable to parse log)"
    fi
else
    echo -e "  File:         ${YELLOW}⚠️  NOT FOUND (no events yet)${NC}"
fi

echo ""

# System summary
echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}Protection System Health:${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
echo ""

# Count health indicators
HEALTH_SCORE=0
MAX_SCORE=8

# Check registry exists
[ -f "$REGISTRY" ] && ((HEALTH_SCORE++))

# Check protection enabled
[ "$PROTECTION_ENABLED" = "true" ] && ((HEALTH_SCORE++))

# Check pre-commit hook
[ -x ".git/hooks/pre-commit" ] && ((HEALTH_SCORE++))

# Check integrity verification script
[ -f "bot/verify_integrity.py" ] && ((HEALTH_SCORE++))

# Check checksums directory
[ -d ".checksums" ] && ((HEALTH_SCORE++))

# Check all locked files exist
ALL_FILES_EXIST=true
jq -r '.locked_files[].path' "$REGISTRY" | while read -r path; do
    if [ ! -f "$path" ]; then
        ALL_FILES_EXIST=false
        break
    fi
done
[ "$ALL_FILES_EXIST" = "true" ] && ((HEALTH_SCORE++))

# Check git tag exists
git rev-parse "$TAG" &>/dev/null && ((HEALTH_SCORE++))

# Check on protected branch or tag
[ "$CURRENT_BRANCH" = "$BRANCH" ] || git rev-parse "$TAG" &>/dev/null && ((HEALTH_SCORE++))

# Calculate percentage
HEALTH_PCT=$((HEALTH_SCORE * 100 / MAX_SCORE))

if [ $HEALTH_PCT -ge 90 ]; then
    HEALTH_COLOR="${GREEN}"
    HEALTH_STATUS="EXCELLENT"
elif [ $HEALTH_PCT -ge 70 ]; then
    HEALTH_COLOR="${CYAN}"
    HEALTH_STATUS="GOOD"
elif [ $HEALTH_PCT -ge 50 ]; then
    HEALTH_COLOR="${YELLOW}"
    HEALTH_STATUS="FAIR"
else
    HEALTH_COLOR="${RED}"
    HEALTH_STATUS="POOR"
fi

echo -e "  Health Score: ${HEALTH_COLOR}${BOLD}$HEALTH_SCORE/$MAX_SCORE ($HEALTH_PCT%) - $HEALTH_STATUS${NC}"
echo ""

if [ $HEALTH_PCT -lt 100 ]; then
    echo -e "${YELLOW}Recommendations:${NC}"
    
    [ ! -x ".git/hooks/pre-commit" ] && echo "  • Install pre-commit hook"
    [ ! -d ".checksums" ] && echo "  • Create checksums directory"
    [ ! -f "bot/verify_integrity.py" ] && echo "  • Add integrity verification script"
    ! git rev-parse "$TAG" &>/dev/null && echo "  • Create git tag: $TAG"
    
    echo ""
fi

echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
echo ""

# Quick commands
echo -e "${BOLD}Quick Commands:${NC}"
echo -e "  Test integrity:     ${BLUE}python -m bot.verify_integrity${NC}"
echo -e "  Generate checksums: ${BLUE}python -m bot.verify_integrity --generate${NC}"
echo -e "  View audit log:     ${BLUE}cat $AUDIT_LOG | jq${NC}"
echo -e "  Revert to stable:   ${BLUE}git checkout $TAG${NC}"
echo ""

