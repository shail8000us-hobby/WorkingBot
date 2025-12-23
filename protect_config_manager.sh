#!/bin/bash
echo '🔒 PROTECTED FILE: config_manager.py'
echo '⚠️  This file is protected. Enter your Mac password to modify:'
sudo chmod +w config_manager.py
echo '✅ File unlocked. Make your changes, then run:'
echo 'sudo chmod -w config_manager.py'
