# 🔐 Tailscale VPN Setup - Always-On Configuration

## ✅ Setup Complete!

Your macOS machine now has a **bulletproof Tailscale VPN** that:
- ✅ Stays connected through sleep, reboots, network changes
- ✅ Auto-starts at system boot
- ✅ Auto-reconnects via watchdog (every 60 seconds)
- ✅ Survives crashes with KeepAlive
- ✅ MagicDNS enabled for stable hostnames
- ✅ Firewall configured

---

## 🚀 Quick Start

### View Connection Info
```bash
./show_info.sh
```

### Run Tests
```bash
./test_tailscale.sh
```

### View Full Guide
```bash
cat TAILSCALE_SETUP_GUIDE.md
```

---

## 📡 Your Access Information

**IPv4**: `100.107.230.67`  
**MagicDNS**: `mymac.tail289dc3.ts.net`

### Remote SSH
```bash
ssh shailendrasinghrajawat@mymac.tail289dc3.ts.net
```

### Remote Web Access
```bash
# Backend
http://mymac.tail289dc3.ts.net:5555

# Frontend
http://mymac.tail289dc3.ts.net:3000
```

---

## 📁 Files in This Directory

| File | Purpose |
|------|---------|
| `show_info.sh` | **Quick reference card** - connection info & commands |
| `test_tailscale.sh` | **Test suite** - verify all functionality |
| `TAILSCALE_SETUP_GUIDE.md` | **Complete guide** - troubleshooting, advanced config |
| `tailscale_watchdog.sh` | **Watchdog script** - monitors and auto-reconnects |
| `install_system_daemon.sh` | Daemon installer (already ran) |
| `com.tailscale.tailscaled.plist` | Daemon config template |
| `com.tailscale.watchdog.plist` | Watchdog config |

---

## 🛠️ Essential Commands

```bash
# Check status
tailscale status

# View daemon logs
tail -f /opt/homebrew/var/log/tailscaled.log

# View watchdog logs
tail -f /opt/homebrew/var/log/tailscale_watchdog.log

# Restart daemon
sudo launchctl kickstart -k system/com.tailscale.tailscaled

# Restart watchdog
launchctl kickstart -k gui/$(id -u)/com.tailscale.watchdog

# Show connection info
./show_info.sh

# Run tests
./test_tailscale.sh
```

---

## 🧪 Testing

### Automatic Tests
```bash
./test_tailscale.sh
```

### Manual Tests

#### Test Network Resilience
```bash
# Turn off Wi-Fi
networksetup -setairportpower en0 off

# Wait 10 seconds
sleep 10

# Turn on Wi-Fi
networksetup -setairportpower en0 on

# Check status (should auto-reconnect)
tailscale status
```

#### Test Remote Access (from another device)
```bash
# SSH
ssh shailendrasinghrajawat@mymac.tail289dc3.ts.net

# HTTP
curl http://mymac.tail289dc3.ts.net:5555/api/bots/status
```

---

## 🔧 Troubleshooting

### Connection Lost
```bash
# Check daemon
ps aux | grep tailscaled

# Restart if needed
sudo launchctl kickstart -k system/com.tailscale.tailscaled

# Force reconnect
tailscale up --ssh --accept-dns --accept-routes
```

### View Logs
```bash
# Daemon logs
tail -50 /opt/homebrew/var/log/tailscaled.log

# Error logs
tail -50 /opt/homebrew/var/log/tailscaled.error.log

# Watchdog logs
tail -50 /opt/homebrew/var/log/tailscale_watchdog.log
```

### Watchdog Not Running
```bash
# Check status
launchctl list | grep watchdog

# Reload if needed
launchctl unload ~/Library/LaunchAgents/com.tailscale.watchdog.plist
launchctl load ~/Library/LaunchAgents/com.tailscale.watchdog.plist
```

---

## 📚 Architecture

### System Components

1. **System Daemon** (`/Library/LaunchDaemons/com.tailscale.tailscaled.plist`)
   - Runs as root at system boot
   - KeepAlive enabled (auto-restart on crash)
   - NetworkState monitoring

2. **User Watchdog** (`~/Library/LaunchAgents/com.tailscale.watchdog.plist`)
   - Runs every 60 seconds
   - Monitors connection health
   - Auto-restarts daemon if needed
   - Detects network changes

3. **Configuration**
   - SSH enabled
   - MagicDNS enabled
   - DNS acceptance enabled
   - Route acceptance enabled

---

## 🔐 Security

- All traffic encrypted via WireGuard
- Only accessible from devices in your tailnet
- SSH uses Tailscale authentication
- No ports exposed to public internet
- Firewall allows only Tailscale traffic

---

## 📱 Multi-Device Access

Once other devices join your tailnet, you can:

**From iPhone/iPad (with Tailscale app):**
- Open Safari
- Go to `http://mymac.tail289dc3.ts.net:3000`

**From another Mac/PC:**
```bash
ssh shailendrasinghrajawat@mymac.tail289dc3.ts.net
```

**From anywhere on the tailnet:**
```bash
curl http://100.107.230.67:5555/api/bots/status
```

---

## 💡 Tips

1. **Bookmark these URLs** on other devices:
   - `http://mymac.tail289dc3.ts.net:5555` (Backend)
   - `http://mymac.tail289dc3.ts.net:3000` (Frontend)

2. **Add SSH config** on remote machines:
   ```bash
   # ~/.ssh/config
   Host mybot
       HostName mymac.tail289dc3.ts.net
       User shailendrasinghrajawat
   
   # Then just: ssh mybot
   ```

3. **Monitor in real-time**:
   ```bash
   watch -n 5 tailscale status
   ```

4. **Check watchdog health**:
   ```bash
   tail -f /opt/homebrew/var/log/tailscale_watchdog.log
   ```

---

## ✅ Verification Checklist

- [x] Daemon running at system boot
- [x] KeepAlive configured
- [x] Watchdog monitoring every 60s
- [x] Network change detection
- [x] MagicDNS enabled
- [x] Firewall configured
- [x] SSH access enabled
- [x] Remote access tested
- [x] Logs configured

---

## 🎉 Success!

Your Tailscale VPN is now **bulletproof** and ready for production use!

**Quick Reference**: Run `./show_info.sh` anytime to see connection details.

**Need Help?** Check `TAILSCALE_SETUP_GUIDE.md` for comprehensive documentation.

---

**Version**: 1.0.0  
**Date**: October 23, 2025  
**Status**: ✅ Production Ready
