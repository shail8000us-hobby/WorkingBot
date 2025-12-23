#!/bin/bash

# Easy Guide Viewer Script
# Makes reading documentation super easy!

cd /Users/shailendrasinghrajawat/Projects/WorkingBot

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${BLUE}📚 ═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}   GRIDBOT DOCUMENTATION VIEWER${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""
echo "Which guide do you want to read?"
echo ""
echo "  1) START_HERE.md (Simplest guide)"
echo "  2) LAUNCHAGENT_BEGINNER_GUIDE.md (Complete beginner guide)"
echo "  3) LAUNCHAGENT_QUICK_REFERENCE.md (Quick reference)"
echo "  4) List all .md files"
echo "  5) Read custom .md file"
echo "  6) Exit"
echo ""
echo -n "Enter your choice (1-6): "
read choice

case $choice in
    1)
        echo ""
        echo -e "${GREEN}📖 Opening START_HERE.md...${NC}"
        echo ""
        echo "Choose how to view:"
        echo "  a) In Cursor"
        echo "  b) In default text editor"
        echo "  c) In Terminal (with scrolling)"
        echo "  d) Just display here"
        echo ""
        echo -n "Your choice (a/b/c/d): "
        read view_choice
        
        case $view_choice in
            a) open -a "Cursor" START_HERE.md ;;
            b) open START_HERE.md ;;
            c) less START_HERE.md ;;
            d) cat START_HERE.md ;;
            *) echo "Invalid choice" ;;
        esac
        ;;
    
    2)
        echo ""
        echo -e "${GREEN}📖 Opening LAUNCHAGENT_BEGINNER_GUIDE.md...${NC}"
        echo ""
        echo "Choose how to view:"
        echo "  a) In Cursor"
        echo "  b) In default text editor"
        echo "  c) In Terminal (with scrolling)"
        echo ""
        echo -n "Your choice (a/b/c): "
        read view_choice
        
        case $view_choice in
            a) open -a "Cursor" LAUNCHAGENT_BEGINNER_GUIDE.md ;;
            b) open LAUNCHAGENT_BEGINNER_GUIDE.md ;;
            c) less LAUNCHAGENT_BEGINNER_GUIDE.md ;;
            *) echo "Invalid choice" ;;
        esac
        ;;
    
    3)
        echo ""
        echo -e "${GREEN}📖 Opening LAUNCHAGENT_QUICK_REFERENCE...${NC}"
        echo ""
        echo "Choose format:"
        echo "  a) Markdown (.md) in Cursor"
        echo "  b) HTML in browser (formatted)"
        echo "  c) Markdown in Terminal"
        echo ""
        echo -n "Your choice (a/b/c): "
        read view_choice
        
        case $view_choice in
            a) open -a "Cursor" LAUNCHAGENT_QUICK_REFERENCE.md ;;
            b) open -a Safari LAUNCHAGENT_QUICK_REFERENCE.html ;;
            c) less LAUNCHAGENT_QUICK_REFERENCE.md ;;
            *) echo "Invalid choice" ;;
        esac
        ;;
    
    4)
        echo ""
        echo -e "${BLUE}📚 All .md files in this directory:${NC}"
        echo ""
        ls -1 *.md | nl
        echo ""
        echo "Use option 5 to read any of these files"
        ;;
    
    5)
        echo ""
        echo -n "Enter the filename (e.g., README.md): "
        read filename
        
        if [ -f "$filename" ]; then
            echo ""
            echo "Choose how to view:"
            echo "  a) In Cursor"
            echo "  b) In default text editor"
            echo "  c) In Terminal (with scrolling)"
            echo "  d) Just display here"
            echo ""
            echo -n "Your choice (a/b/c/d): "
            read view_choice
            
            case $view_choice in
                a) open -a "Cursor" "$filename" ;;
                b) open "$filename" ;;
                c) less "$filename" ;;
                d) cat "$filename" ;;
                *) echo "Invalid choice" ;;
            esac
        else
            echo -e "${YELLOW}⚠️  File not found: $filename${NC}"
        fi
        ;;
    
    6)
        echo ""
        echo -e "${GREEN}👋 Goodbye!${NC}"
        exit 0
        ;;
    
    *)
        echo ""
        echo -e "${YELLOW}❌ Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

