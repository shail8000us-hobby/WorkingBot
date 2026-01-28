---
description: restart the backend and frontend services
---

1. Build the frontend
```bash
cd webui/frontend
npm run build
```

2. Restart the backend service
```bash
launchctl stop com.gridbot.webui
sleep 2
launchctl start com.gridbot.webui
```

3. Verify health
```bash
sleep 5
curl -s http://localhost:5555/api/zero-dte/health
```
