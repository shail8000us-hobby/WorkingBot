# GridBot Pro - Backtest Web UI

**Dedicated Web Interface for Backtesting**  
**Port:** 5556 (Separate from Live Trading UI on 5555)

---

## 🚀 Quick Start

### 1. Install Frontend Dependencies (First Time Only)

```bash
cd backtest_ui/frontend
npm install
```

### 2. Start the Backtest UI

```bash
cd backtest_ui
./start_backtest_ui.sh
```

The script will:
- Build the frontend if not already built
- Start the backend server on port 5556
- Open http://localhost:5556 in your browser

### 3. Access the UI

Open your browser to: **http://localhost:5556**

---

## 📊 Features

### ✅ Configuration Panel
- Date range picker (start/end dates)
- Symbol selector
- Timeframe selection (1m, 5m, 15m, 1h)
- Grid parameter overrides
- Advanced settings:
  - Maker/Taker fee toggle
  - Funding mode (off/simple)
  - Same-bar priority (TP first/BUY first)
  - Testnet data toggle

### ✅ Results Dashboard
- Key metrics cards:
  - Net PnL
  - Win Rate
  - Profit Factor
  - Max Drawdown
- Detailed metrics table
- Equity curve visualization (placeholder)
- Export functionality

### ✅ History Browser
- List of all past backtests
- Sortable table with key metrics
- Quick view of any historical backtest
- Date, symbol, period, PnL, win rate

### 🚧 Parameter Optimizer (Coming in v1.1)
- Grid STEP sweep
- MAX_OPEN sweep
- Heatmap visualization
- Best parameter recommendation

---

## 🏗️ Architecture

### Backend (Flask + SocketIO)
- **File:** `backtest_ui/backend/app.py`
- **Port:** 5556
- **Features:**
  - REST API for backtest management
  - WebSocket for real-time progress updates
  - Integration with backtest engine
  - History management

### Frontend (React + Material-UI)
- **Directory:** `backtest_ui/frontend/`
- **Framework:** React 18
- **UI Library:** Material-UI v5
- **Charts:** Chart.js + react-chartjs-2
- **Date Picker:** @mui/x-date-pickers

---

## 📡 API Endpoints

### Health Check
```
GET /api/health
```

### Configuration
```
GET /api/config
```
Returns current grid configuration from `grid_config.env`.

### Run Backtest
```
POST /api/backtest/run
Body: {
  "symbol": "BTC/USD:USD",
  "timeframe": "1m",
  "start": "2025-08-01",
  "end": "2025-09-01",
  "assume_maker": true,
  "funding_mode": "off",
  "same_bar_priority": "tp_first",
  "is_testnet": false
}
```

### Backtest Status
```
GET /api/backtest/<backtest_id>/status
```

### Backtest Result
```
GET /api/backtest/<backtest_id>/result
```

### History
```
GET /api/backtest/history
```

### Historical Backtest Details
```
GET /api/backtest/history/<backtest_dir>
```

### Cache Stats
```
GET /api/cache/stats
```

### Clear Cache
```
POST /api/cache/clear
Body: {"days_old": 30}
```

---

## 🔌 WebSocket Events

### Client → Server
- `connect`: Client connects
- `disconnect`: Client disconnects

### Server → Client
- `connected`: Connection established
- `backtest_status`: Real-time backtest updates
  ```json
  {
    "backtest_id": "BT0001",
    "status": "running|completed|failed",
    "progress": 75,
    "result": {...}
  }
  ```

---

## 📁 File Structure

```
backtest_ui/
├── backend/
│   └── app.py                    # Flask backend (port 5556)
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── App.js                # Main app component
│   │   ├── index.js              # React entry point
│   │   └── components/
│   │       ├── ConfigurationPanel.js
│   │       ├── ResultsPanel.js
│   │       ├── HistoryPanel.js
│   │       └── OptimizerPanel.js
│   ├── package.json
│   └── build/                    # Production build (after npm run build)
├── start_backtest_ui.sh          # Startup script
└── README.md                     # This file
```

---

## 🛠️ Development

### Run Frontend in Development Mode

```bash
cd backtest_ui/frontend
npm start
```

This starts the React dev server on port 3000 with hot reload.

### Run Backend Separately

```bash
cd backtest_ui/backend
python3 app.py
```

Backend runs on port 5556.

### Build Frontend for Production

```bash
cd backtest_ui/frontend
npm run build
```

Creates optimized production bundle in `frontend/build/`.

---

## 🐛 Troubleshooting

### Issue: "Frontend not built"

**Solution:**
```bash
cd backtest_ui/frontend
npm install
npm run build
```

### Issue: "Port 5556 already in use"

**Solution:**
```bash
# Find and kill process using port 5556
lsof -ti:5556 | xargs kill -9

# Or change port in backend/app.py (line ~500)
```

### Issue: "Cannot connect to backend"

**Solution:**
1. Check backend is running: `curl http://localhost:5556/api/health`
2. Check firewall settings
3. Restart backend: `cd backtest_ui/backend && python3 app.py`

### Issue: "WebSocket connection failed"

**Solution:**
1. Ensure backend is running with SocketIO
2. Check browser console for errors
3. Try hard refresh (Ctrl+Shift+R)

---

## 🔄 Integration with Main Bot

### Separation of Concerns

- **Live Trading UI**: Port 5555 (`webui/`)
- **Backtest UI**: Port 5556 (`backtest_ui/`)

Both UIs are **completely independent**:
- Separate codebases
- Separate ports
- No shared state
- Can run simultaneously

### Data Flow

```
Backtest UI (5556)
    ↓
Backend API
    ↓
Backtest Engine (backtest/)
    ↓
SimExchange
    ↓
Results (reports/backtests/)
```

---

## 📊 Usage Example

### 1. Configure Backtest

1. Open http://localhost:5556
2. Go to "New Backtest" tab
3. Set date range (e.g., Aug 1 - Sep 1, 2025)
4. Choose symbol (BTC/USD:USD)
5. Select timeframe (1m)
6. Toggle advanced settings if needed
7. Click "Run Backtest"

### 2. Monitor Progress

- Real-time status updates via WebSocket
- Progress indicator shows completion
- Automatically switches to Results tab when done

### 3. View Results

- Key metrics displayed in cards
- Detailed metrics table
- Export CSV files for further analysis

### 4. Browse History

- Go to "History" tab
- See all past backtests
- Click "View" to load any historical result

---

## 🎨 UI Screenshots

### Configuration Panel
- Clean, intuitive form
- Date pickers with calendar
- Advanced settings collapsible
- Real-time validation

### Results Dashboard
- Professional metric cards
- Color-coded PnL (green/red)
- Comprehensive statistics
- Export functionality

### History Browser
- Sortable table
- Quick comparison
- One-click result loading

---

## 🚀 Future Enhancements (v1.1)

### Parameter Optimizer
- [ ] Grid STEP sweep (50, 100, 200, 500)
- [ ] MAX_OPEN sweep (5, 10, 15, 20)
- [ ] Heatmap visualization
- [ ] Best parameter recommendation
- [ ] Multi-dimensional optimization

### Advanced Charting
- [ ] Interactive equity curve (Plotly/Recharts)
- [ ] Drawdown visualization
- [ ] Trade distribution histogram
- [ ] Win/loss timeline

### Comparison Tools
- [ ] Side-by-side backtest comparison
- [ ] Overlay multiple equity curves
- [ ] Metric diff table

### Export & Reporting
- [ ] PDF report generation
- [ ] Email results
- [ ] Scheduled backtests
- [ ] Slack/Telegram notifications

---

## 📚 Related Documentation

- **Backtest CLI Guide**: `../BACKTESTING_GUIDE.md`
- **Backtest Implementation**: `../BACKTEST_IMPLEMENTATION_SUMMARY.md`
- **Main Bot Manual**: `../USERMANUAL.md`

---

## ✅ System Requirements

- **Python**: 3.8+
- **Node.js**: 14+ (for frontend build)
- **npm**: 6+
- **Browser**: Chrome, Firefox, Safari, Edge (latest versions)

---

## 📝 Notes

- **Port 5556** is dedicated for backtesting UI
- **Port 5555** is for live trading bot UI
- Both can run simultaneously without conflict
- Backtest results are saved to `reports/backtests/`
- Frontend must be built before first use
- Backend auto-serves built frontend

---

**Happy Backtesting!** 🚀

For support, see main project README or BACKTESTING_GUIDE.md.

