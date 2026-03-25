# File Server — Port 8080

**Script:** `nocache_server.py` (project root)
**Port:** 8080
**Serves:** `/Users/ssr/Projects/WorkingBot/` (static files, no-cache headers)
**Start:** `python3 nocache_server.py &`
**Stop:** `kill $(lsof -ti:8080)`
**Restart:** `kill $(lsof -ti:8080); python3 nocache_server.py &`
**Check:** `lsof -ti:8080`
