# Guardian Bot Auto-Start (macOS)

This directory contains the configuration files for automatically starting the Guardian Bot on macOS using `launchd`.

## Files

- `com.gridbot.guardian.plist` - Launch daemon configuration
- `install_guardian_autostart.sh` - Installation script
- `uninstall_guardian_autostart.sh` - Uninstallation script

## Installation

1. **Edit the plist file** (if needed):
   ```bash
   nano com.gridbot.guardian.plist
   ```
   
   Update these paths if they're different:
   - `WorkingDirectory` - Path to your WorkingBot directory
   - `StandardOutPath` - Path to log file
   - `StandardErrorPath` - Path to error log file
   - `UserName` - Your macOS username

2. **Install auto-start**:
   ```bash
   ./install_guardian_autostart.sh
   ```

3. **Verify installation**:
   ```bash
   launchctl list | grep guardian
   ```

## Uninstallation

```bash
./uninstall_guardian_autostart.sh
```

## Manual Control

- **Start**: `launchctl start com.gridbot.guardian`
- **Stop**: `launchctl stop com.gridbot.guardian`
- **Status**: `launchctl list | grep guardian`

## Logs

- **Guardian log**: `bot/logs/guardian.log`
- **Error log**: `bot/logs/guardian_error.log`

## Troubleshooting

If Guardian doesn't start:

1. Check logs:
   ```bash
   tail -f bot/logs/guardian_error.log
   ```

2. Check plist syntax:
   ```bash
   plutil -lint ~/Library/LaunchAgents/com.gridbot.guardian.plist
   ```

3. Reload service:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.gridbot.guardian.plist
   launchctl load ~/Library/LaunchAgents/com.gridbot.guardian.plist
   ```

## Notes

- Guardian will automatically restart if it crashes
- Guardian starts 10 seconds after system boot
- Guardian runs as your user (not root)
- Guardian requires network connection (waits for network-online)

