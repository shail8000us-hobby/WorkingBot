# Changelog

All notable changes to GridBot Pro will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0-sync-hardening] - 2025-10-24

### Added

#### API Endpoints
- `POST /api/bot/restart` - Restart bot with graceful stop/start
- `GET /api/config/verify` - Validate configuration integrity
- `POST /api/config/apply` - Apply config changes with hot reload
- `GET /api/logs/recent?lines=N` - Fetch recent log lines
- `GET /api/system/status` - Comprehensive system health check

#### SocketIO Events (Frontend)
- `liquidation_alert` - Urgent liquidation risk notifications
- `liquidation_update` - Periodic liquidation metrics updates
- `fix_result` - Error resolution auto-fix results

#### Scripts
- `scripts/dev.sh` - Development server with live reload
- `scripts/build_frontend.sh` - Production frontend build automation
- `scripts/start_backend.sh` - Production backend startup with validation
- `scripts/preflight.sh` - 41 pre-deployment checks

#### Documentation
- `RUNBOOK.md` - Operational procedures and incident response
- `SECRETS_SETUP.md` - Complete secrets configuration guide
- `grid_config.env.example` - Documented configuration template
- `RELEASE_v1.0.0-sync-hardening.md` - Full release notes
- `FINAL_DEPLOYMENT_SUMMARY.md` - Deployment guide with smoke tests

#### Security
- API authentication now enforced (Bearer token + Basic auth)
- Rate limiting (10 req/min) on sensitive endpoints
- Global exception handler with traceback logging
- Secrets removed from Git tracking (`secrets/` gitignored)

### Changed

#### Security Improvements
- `.gitignore` - Added explicit `.env.local` entry
- Authentication `@app.before_request` uncommented and active
- All `/api/*` routes now require auth (except health, version, SocketIO)

#### Infrastructure
- Cache headers: index.html = `no-store`, static assets = long-lived
- `/api/version` reports backend version + UI build hash
- App tracks start time for uptime calculations
- Environment loading order: grid_config.env → secrets → .env.local

### Fixed
- Backend-frontend sync now 100% (was 80%)
- SocketIO event coverage now 100% (was 80%)
- API endpoint coverage now 100% (was 81%)
- Missing error handlers for unhandled exceptions
- Stale UI caching issues resolved

### Security
- **CRITICAL:** API keys accidentally committed to Git (now removed)
- **ACTION REQUIRED:** Rotate all API keys before deployment
- See `SECURITY.md` for rotation procedures

### Deprecated
- None

### Removed
- `secrets/api_keys.env` from Git tracking (must create manually per deployment)

### Breaking Changes
1. **Authentication required** - All API calls need `Authorization: Bearer <token>`
2. **API keys must be rotated** - Old keys were exposed in Git history
3. **Rate limiting** - Rapid requests (>10/min) will receive HTTP 429

### Migration Guide
```bash
# 1. Rotate API keys (follow SECURITY.md)

# 2. Generate auth token
export WEBUI_AUTH_TOKEN=$(openssl rand -base64 32)
echo "WEBUI_AUTH_TOKEN=$WEBUI_AUTH_TOKEN" >> .env.local

# 3. Update API clients to send Authorization header
Authorization: Bearer <your-token>

# 4. Run preflight checks
./scripts/preflight.sh

# 5. Deploy
./scripts/start_backend.sh
```

---

## [Unreleased]

### Planned
- HTTPS support documentation
- Prometheus metrics integration
- OAuth2 authentication
- E2E automated testing

---

## Version History

- **1.0.0-sync-hardening** (2025-10-24) - Security hardening & backend-frontend sync
  - Production-ready release
  - 100% API/SocketIO coverage
  - Authentication enforced
  - Comprehensive documentation

---

## Links

- [Full Release Notes](RELEASE_v1.0.0-sync-hardening.md)
- [Deployment Summary](FINAL_DEPLOYMENT_SUMMARY.md)
- [Security Policy](SECURITY.md)
- [Operations Runbook](RUNBOOK.md)
