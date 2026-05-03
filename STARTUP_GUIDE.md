# WebUI Backend Startup Guide

**Single Source of Truth for Starting the Backend**

## Quick Start

### Production (Default)
```bash
./start_webui.sh
```
✅ Use this for normal operations. Features:
- Loads environment variables automatically
- Runs in background (nohup)
- Logs to `logs/webui_backend.log`
- Single instance protection with PID file
- Auto-restart support with `./start_webui.sh restart`

### Development (Backend Only - Auto Reload)
```bash
cd webui/backend
./start_dev.sh
```
✅ Use this for development. Features:
- Auto-reloads on file changes
- Flask debug mode enabled
- Prints logs to console
- Exits on Ctrl+C

### Full Stack Development (Frontend + Backend)
```bash
cd webui
./start.sh
```
✅ Use this to develop frontend + backend together. Features:
- Starts backend in current directory
- Must be run from `webui/` directory
- Both frontend and backend built together

## Script Comparison

| Script | Purpose | When to Use | Features |
|--------|---------|------------|----------|
| `./start_webui.sh` | Production | Daily use, automated restarts | nohup, logging, PID file, restart support |
| `webui/backend/start_dev.sh` | Dev (Backend) | Debugging backend code | Auto-reload, Flask debug, console logs |
| `webui/start.sh` | Dev (Full Stack) | Frontend development | Frontend build + backend together |

## Common Commands

### Check Status
```bash
./start_webui.sh status
```

### Restart
```bash
./start_webui.sh restart
```

### Stop
```bash
./start_webui.sh stop
```

### View Logs
```bash
tail -f logs/webui_backend.log
```

## Troubleshooting

### "API credentials not found"
The backend needs `DELTA_API_KEY` and `DELTA_API_SECRET`. These are automatically loaded from:
1. `.env` (project root)
2. `secrets/api_keys.env`

### "Port 5555 already in use"
```bash
./start_webui.sh stop
# Wait a moment
./start_webui.sh start
```

### "Slow UI / API timeouts"
This indicates missing credentials. Check:
```bash
echo $DELTA_API_KEY  # Should print your API key
```

## Recommended Setup

**For Users:** Always use `./start_webui.sh`

**For Developers:** Use `webui/backend/start_dev.sh` when editing backend code

**For Frontend Devs:** Use `webui/start.sh` when editing frontend
