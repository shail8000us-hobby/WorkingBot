# V3 Frontend Deployment Guide

**Application:** GridBot WebUI v3  
**Port:** 3003  
**Framework:** Next.js 16

---

## 🚀 Quick Deploy

### 1. Build the Application

```bash
cd webui/frontend-v3
npm run build
```

### 2. Start Production Server

```bash
npm start
```

The application will be available at: **http://localhost:3003**

---

## 📦 Production Deployment Options

### Option 1: Direct Start (Development/Testing)

```bash
cd webui/frontend-v3
npm run build
npm start
```

### Option 2: PM2 Process Manager (Recommended for Production)

```bash
cd webui/frontend-v3
npm run build
pm2 start npm --name "frontend-v3" -- start
pm2 save
pm2 startup  # Follow instructions for auto-start on boot
```

### Option 3: Systemd Service (Linux)

Create `/etc/systemd/system/frontend-v3.service`:

```ini
[Unit]
Description=GridBot WebUI v3
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/WorkingBot/webui/frontend-v3
ExecStart=/usr/bin/npm start
Restart=always
Environment=NODE_ENV=production
Environment=NEXT_PUBLIC_API_URL=http://localhost:5555

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable frontend-v3
sudo systemctl start frontend-v3
```

---

## ⚙️ Environment Variables

### Required
- `NEXT_PUBLIC_API_URL` - Backend API URL (default: `http://localhost:5555`)

### Optional
- `PORT` - Server port (default: 3000, but app runs on 3003 via package.json)
- `NODE_ENV` - Set to `production` for production builds

### Example .env.production

```env
NEXT_PUBLIC_API_URL=http://localhost:5555
NODE_ENV=production
```

---

## 🔍 Verification

After deployment, verify:

1. **Application is running:**
   ```bash
   curl http://localhost:3003
   ```

2. **API connectivity:**
   - Ensure backend is running on port 5555
   - Check browser console for API connection errors

3. **All routes are accessible:**
   - Dashboard: http://localhost:3003/
   - Portfolio: http://localhost:3003/portfolio
   - Guardian: http://localhost:3003/guardian
   - Health: http://localhost:3003/health
   - And all other routes...

---

## 📝 Pre-Deployment Checklist

- [x] ✅ All components migrated
- [x] ✅ TypeScript compilation passes
- [x] ✅ All API URLs fixed (5557 → 5555)
- [x] ✅ All pages created
- [x] ✅ Build completes successfully
- [ ] Backend API running on port 5555
- [ ] Environment variables configured
- [ ] Port 3003 available
- [ ] Process manager configured (if using PM2/systemd)

---

## 🛠️ Troubleshooting

### Build Fails
- Check Node.js version (requires Node 18+)
- Run `npm install` to ensure dependencies are installed
- Check for TypeScript errors: `npm run typecheck`

### Port Already in Use
- Change port in `package.json` scripts or use environment variable
- Kill existing process: `lsof -ti:3003 | xargs kill`

### API Connection Issues
- Verify backend is running: `curl http://localhost:5555/api/health`
- Check `NEXT_PUBLIC_API_URL` environment variable
- Check browser console for CORS errors

### PM2 Issues
- Check logs: `pm2 logs frontend-v3`
- Restart: `pm2 restart frontend-v3`
- Check status: `pm2 status`

---

## 📊 Deployment Status

**Current Status:** ✅ Ready for Deployment

- ✅ Build script: Configured
- ✅ Production start: Configured  
- ✅ All components: Migrated
- ✅ TypeScript: Passing
- ✅ API Integration: Complete

---

**Ready to deploy!** 🚀

