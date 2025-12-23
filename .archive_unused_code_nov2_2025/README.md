# Archived Unused Code Files - November 2, 2025

This directory contains code files that are no longer actively used in production but kept for reference.

## Files Archived:

### 1. bot/strategy/gbot_ws.py (147KB)
- **Status**: DEPRECATED - Replaced by modular architecture
- **Replacement**: bot/strategy/gridbot.py + modules/
- **Reason**: Monolithic 3,492-line file refactored into clean modular system
- **References**: Still referenced in 2 legacy files (data_sources.py, verify_integrity.py)
- **Action Required**: Update references to use gridbot.py instead

### 2. webui/frontend/src/components/ConfigPanel_TabBased_Backup.js
- **Status**: BACKUP - Old tab-based UI design
- **Replacement**: ConfigPanel.js (accordion-based design)
- **Reason**: UI/UX redesign completed, tab-based version no longer needed

## Important Notes:

⚠️ **DO NOT DELETE** - These files are archived for reference only
⚠️ **DO NOT IMPORT** - Use modern replacements instead
⚠️ **UPDATE REFERENCES** - Fix any imports pointing to these files

## Migration Status:

✅ gridbot.py modular architecture: COMPLETE (96.7% test coverage)
✅ ConfigPanel accordion design: COMPLETE (production-ready)
❌ Legacy references: Need cleanup in 2 files

## Archive Date: November 2, 2025
## Archived By: AI Assistant (Wiring Audit & Cleanup)
