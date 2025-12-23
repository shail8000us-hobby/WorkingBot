# Mac Static IP Quick Reference
**Date:** November 7, 2025  
**Target IP:** 192.168.1.6  
**Purpose:** Stable Windows ↔ Mac connection

---

## 🚀 Quick Setup (One Command)

```bash
cd /Users/ssr/Projects/WorkingBot && ./MAC_STATIC_IP_SETUP.sh
```

---

## 📋 Manual Setup Commands

### 1. Check Current Configuration
```bash
networksetup -getinfo "Wi-Fi"
```

### 2. Set Static IP (192.168.1.6)
```bash
sudo networksetup -setmanual "Wi-Fi" 192.168.1.6 255.255.255.0 192.168.1.1
```

### 3. Set DNS Servers
```bash
sudo networksetup -setdnsservers "Wi-Fi" 8.8.8.8 8.8.4.4 192.168.1.1
```

### 4. Verify Configuration
```bash
networksetup -getinfo "Wi-Fi"
ifconfig | grep "inet " | grep -v 127.0.0.1
```

### 5. Test Windows Connectivity
```bash
ping -c 4 192.168.1.32
```

---

## 🔄 Revert to DHCP (If Needed)

```bash
sudo networksetup -setdhcp "Wi-Fi"
sudo networksetup -setdnsservers "Wi-Fi" Empty
```

---

## 📡 Network Map

| Device | IP Address | Type |
|--------|------------|------|
| **Mac (This Machine)** | `192.168.1.6` | STATIC |
| **Windows** | `192.168.1.32` | STATIC |
| **Router/Gateway** | `192.168.1.1` | Gateway |
| **Subnet Mask** | `255.255.255.0` | - |

---

## 🔧 Troubleshooting

### If IP doesn't change immediately:
```bash
# Option 1: Cycle Wi-Fi
sudo ifconfig en0 down
sleep 2
sudo ifconfig en0 up

# Option 2: Restart network service
sudo networksetup -setnetworkserviceenabled "Wi-Fi" off
sleep 2
sudo networksetup -setnetworkserviceenabled "Wi-Fi" on

# Option 3: Renew (for DHCP only)
sudo ipconfig set en0 DHCP
```

### Check current IP:
```bash
ifconfig en0 | grep "inet " | grep -v "127.0.0.1"
```

### Check routing:
```bash
netstat -rn | grep default
```

### Flush DNS cache:
```bash
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
```

---

## 📝 Notes

- ✅ Static IP persists across reboots
- ✅ No need to reconfigure after restart
- ✅ Stable connection for Windows SMB shares
- ✅ Consistent IP for SSH/network services

---

## 🔗 Windows ↔ Mac Connection

### Mount Windows from Mac:
```bash
mkdir -p /Users/ssr/Windows
mount -t smbfs //192.168.1.32/Users /Users/ssr/Windows
```

### SSH to Mac from Windows:
```powershell
ssh ssr@192.168.1.6
```

### Test connectivity:
```bash
# From Mac to Windows
ping 192.168.1.32

# Check if Windows port 445 (SMB) is open
nc -zv 192.168.1.32 445
```

---

## ⚠️ Important

1. **Before changing IP**: Make sure 192.168.1.6 is not used by another device
2. **Router settings**: Some routers may have DHCP reservation - check router admin panel
3. **Firewall**: Ensure macOS firewall allows incoming connections if needed

---

## 🎯 Quick Health Check

```bash
# Full network diagnostic
echo "Mac IP:" && ifconfig en0 | grep "inet " | awk '{print $2}'
echo "Gateway:" && netstat -rn | grep default | awk '{print $2}' | head -1
echo "DNS:" && scutil --dns | grep nameserver | head -3
echo "Windows ping:" && ping -c 2 192.168.1.32
```
