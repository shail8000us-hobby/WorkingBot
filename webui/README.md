# GridBot Pro - Web UI Control Panel

A professional web-based control panel for managing and monitoring your GridBot.

## ✨ Features

### 🎛️ Real-Time Configuration Management
- Edit all `grid_config.env` parameters through a beautiful web interface
- **Two-way synchronization**: Changes in UI update the file, changes in file update the UI
- Organized sections: Grid Parameters, Risk Management, Safety, Telegram, etc.
- Live validation and safety warnings

### 🚀 Bot Control
- **Start/Stop** bot with one click
- Real-time bot status monitoring
- Process management (PID tracking)
- Graceful shutdown handling

### 📊 Live Monitoring
- Current bot status (Running/Stopped)
- Open positions and pending orders
- Grid configuration visualization
- Safety limits dashboard

### 📝 Live Logs
- Real-time log streaming
- Color-coded log levels (INFO, WARNING, ERROR)
- Auto-scrolling
- Download logs feature

### 🔒 Safety Features
- Safety warnings for critical settings
- Risk management limits display
- Execution safety controls
- Configuration validation

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+** (for backend)
- **Node.js 16+** (for frontend)
- **npm** (comes with Node.js)

### Installation

```bash
cd webui
./install.sh
```

This will:
1. Install Python backend dependencies
2. Install Node.js frontend dependencies
3. Build the React frontend
4. Make start/stop scripts executable

### Starting the Web UI

```bash
./start.sh
```

Then open your browser to: **http://localhost:5000**

### Stopping the Web UI

```bash
./stop.sh
```

Or press **Ctrl+C** in the terminal where it's running.

## 📖 Usage

### Configuration Tab

1. Navigate to the **Configuration** tab
2. Expand the sections you want to edit
3. Modify values as needed
4. Click **Save Configuration**
5. Changes are instantly written to `grid_config.env`

### Monitoring Tab

- View current grid configuration
- Monitor bot state (positions, orders)
- Check safety limits
- Real-time status updates

### Logs Tab

- View live logs from the bot
- Auto-scrolling to latest entries
- Color-coded by log level
- Download logs for analysis

### Bot Control

- **Start Button**: Starts the GridBot
- **Stop Button**: Gracefully stops the GridBot
- **Status Indicator**: Shows if bot is running/stopped
- **Refresh Button**: Manually refresh data

## 🔄 Two-Way Synchronization

### UI → File
When you change a setting in the web UI:
1. Click "Save Configuration"
2. Backend updates `grid_config.env`
3. All connected clients are notified
4. Bot can reload config on next restart

### File → UI
When you manually edit `grid_config.env`:
1. File watcher detects the change
2. Backend reloads the configuration
3. All connected clients receive updates
4. UI refreshes automatically

**Both directions work in real-time!**

## 🏗️ Architecture

```
webui/
├── backend/           # Flask + SocketIO server
│   ├── app.py        # Main backend application
│   └── requirements.txt
├── frontend/         # React application
│   ├── src/
│   │   ├── App.js   # Main app component
│   │   ├── components/
│   │   │   ├── BotStatus.js
│   │   │   ├── ConfigPanel.js
│   │   │   ├── LogsPanel.js
│   │   │   └── MonitoringPanel.js
│   │   └── index.js
│   ├── package.json
│   └── build/       # Production build (after npm run build)
├── install.sh       # Installation script
├── start.sh         # Start web UI
└── stop.sh          # Stop web UI
```

## 🔧 Technical Details

### Backend (Flask)
- **Flask**: Web framework
- **Flask-SocketIO**: WebSocket support for real-time updates
- **Watchdog**: File system monitoring for `grid_config.env`
- **Python-dotenv**: Configuration file parsing

### Frontend (React)
- **React 18**: UI framework
- **Material-UI (MUI)**: Beautiful component library
- **Socket.IO Client**: Real-time communication
- **Axios**: HTTP requests

### Communication Flow

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Browser   │◄───────►│   Backend   │◄───────►│ grid_config │
│  (React UI) │ WebSocket│  (Flask)    │  Watch  │    .env     │
└─────────────┘         └─────────────┘         └─────────────┘
                              │
                              ▼
                        ┌─────────────┐
                        │   GridBot   │
                        │  (Process)  │
                        └─────────────┘
```

## 🎨 UI Screenshots

### Dashboard
- Modern dark theme
- Real-time status indicators
- Organized configuration sections

### Configuration Panel
- Grouped settings by category
- Inline validation
- Safety warnings
- Unsaved changes indicator

### Monitoring Panel
- Grid configuration overview
- Current state metrics
- Safety limits dashboard

### Logs Panel
- Live streaming logs
- Color-coded entries
- Auto-scrolling
- Download capability

## 🔐 Security Notes

1. **Local Network Only**: By default, the server binds to `0.0.0.0:5000`, accessible on your local network
2. **No Authentication**: Currently no login required (intended for local use)
3. **API Access**: All API endpoints are unprotected
4. **For Production**: Add authentication, HTTPS, and firewall rules

## 🐛 Troubleshooting

### Port 5000 already in use
```bash
# Find and kill the process using port 5000
lsof -ti:5000 | xargs kill -9
```

### Backend won't start
```bash
# Reinstall dependencies
cd backend
pip3 install -r requirements.txt
```

### Frontend build fails
```bash
# Clear cache and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

### Bot won't start from UI
- Check if bot is already running: `ps aux | grep bot/run.py`
- Verify bot script path in `backend/app.py`
- Check bot logs in `bot/logs/bot.log`

### Config changes not syncing
- Check file permissions on `grid_config.env`
- Verify file watcher is running (check backend logs)
- Refresh the browser (hard refresh: Ctrl+Shift+R)

## 📝 Development

### Running in Development Mode

**Backend:**
```bash
cd webui/backend
python3 app.py
```

**Frontend:**
```bash
cd webui/frontend
npm start
```

Frontend dev server runs on `http://localhost:3000` and proxies API calls to backend on `http://localhost:5000`.

### Building for Production

```bash
cd webui/frontend
npm run build
```

The backend serves the production build from `frontend/build/`.

## 🔄 Updates

To update the Web UI:

1. Pull latest changes
2. Reinstall dependencies:
   ```bash
   cd webui
   ./install.sh
   ```
3. Restart the UI:
   ```bash
   ./stop.sh
   ./start.sh
   ```

## 📞 Support

- Check `USERMANUAL.md` in the root directory
- Review `grid_config.env` comments for parameter descriptions
- Check bot logs in `bot/logs/bot.log`

## ✅ Features Checklist

- [x] Real-time configuration editing
- [x] Two-way file synchronization
- [x] Bot start/stop controls
- [x] Live status monitoring
- [x] Real-time log streaming
- [x] Safety warnings and validation
- [x] Material-UI design
- [x] WebSocket communication
- [x] File watcher integration
- [x] Responsive layout
- [x] Color-coded logs
- [x] Configuration sections
- [x] Download logs
- [ ] Authentication (future)
- [ ] Multi-user support (future)
- [ ] Historical charts (future)
- [ ] Trade history view (future)

## 🎯 Roadmap

Future enhancements:
- User authentication
- Trade history visualization
- Performance charts
- P&L tracking
- Multi-bot support
- Mobile responsive improvements
- Dark/light theme toggle
- Configuration presets

---

**Made with ❤️ for GridBot Pro**

