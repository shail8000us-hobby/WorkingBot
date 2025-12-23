# Guardian Bot Auto-Start (Linux/systemd)

This directory contains the configuration files for automatically starting the Guardian Bot on Linux systems using `systemd`.

## Files

- `gridbot-guardian.service` - Systemd service unit file

## Installation

1. **Edit the service file**:
   ```bash
   nano gridbot-guardian.service
   ```
   
   Update these values:
   - `User=YOUR_USERNAME_HERE` - Your Linux username
   - `Group=YOUR_GROUP_HERE` - Your Linux group (usually same as username)
   - `WorkingDirectory=/path/to/WorkingBot` - Full path to WorkingBot directory
   - `StandardOutput` and `StandardError` paths
   - `ReadWritePaths` paths

2. **Copy to systemd directory**:
   ```bash
   sudo cp gridbot-guardian.service /etc/systemd/system/
   ```

3. **Reload systemd**:
   ```bash
   sudo systemctl daemon-reload
   ```

4. **Enable auto-start**:
   ```bash
   sudo systemctl enable gridbot-guardian.service
   ```

5. **Start the service**:
   ```bash
   sudo systemctl start gridbot-guardian.service
   ```

6. **Verify status**:
   ```bash
   sudo systemctl status gridbot-guardian.service
   ```

## Uninstallation

1. **Stop the service**:
   ```bash
   sudo systemctl stop gridbot-guardian.service
   ```

2. **Disable auto-start**:
   ```bash
   sudo systemctl disable gridbot-guardian.service
   ```

3. **Remove service file**:
   ```bash
   sudo rm /etc/systemd/system/gridbot-guardian.service
   ```

4. **Reload systemd**:
   ```bash
   sudo systemctl daemon-reload
   ```

## Manual Control

- **Start**: `sudo systemctl start gridbot-guardian`
- **Stop**: `sudo systemctl stop gridbot-guardian`
- **Restart**: `sudo systemctl restart gridbot-guardian`
- **Status**: `sudo systemctl status gridbot-guardian`
- **Logs**: `sudo journalctl -u gridbot-guardian -f`

## Logs

Guardian logs are written to:
- **Guardian log**: `bot/logs/guardian.log`
- **Error log**: `bot/logs/guardian_error.log`

You can also view logs via systemd:
```bash
sudo journalctl -u gridbot-guardian -n 50 -f
```

## Troubleshooting

If Guardian doesn't start:

1. Check service status:
   ```bash
   sudo systemctl status gridbot-guardian.service
   ```

2. Check systemd logs:
   ```bash
   sudo journalctl -u gridbot-guardian -n 100
   ```

3. Check Guardian error log:
   ```bash
   tail -f bot/logs/guardian_error.log
   ```

4. Validate service file:
   ```bash
   systemd-analyze verify /etc/systemd/system/gridbot-guardian.service
   ```

## Notes

- Guardian will automatically restart if it crashes
- Guardian starts after network is online
- Guardian runs as your user (not root)
- Service is hardened with security options (PrivateTmp, NoNewPrivileges, etc.)

