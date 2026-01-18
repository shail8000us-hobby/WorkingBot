import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Divider,
  Chip,
  Grid,
  Card,
  CardContent,
  CardActions,
  Button,
  Alert,
  IconButton,
  Snackbar,
  Tooltip,
  TextField,
  InputAdornment,
} from '@mui/material';
import {
  Terminal as TerminalIcon,
  PlayArrow as PlayArrowIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  Build as BuildIcon,
  BugReport as BugReportIcon,
  Security as SecurityIcon,
  MonitorHeart as MonitorHeartIcon,
  ViewList as ViewListIcon,
  ContentCopy as ContentCopyIcon,
  CheckCircle as CheckCircleIcon,
  OpenInNew as OpenInNewIcon,
  Search as SearchIcon,
} from '@mui/icons-material';

const CommandKnowledgeBase = () => {
  const [copiedCommand, setCopiedCommand] = useState('');
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Command categories with actual Mac terminal commands
  const commandCategories = [
    {
      title: '🤖 PM2 Bot Management (Primary) - ASYNC BOT',
      icon: <PlayArrowIcon />,
      color: '#4CAF50',
      commands: [
        {
          name: 'Start Async Trading Bot via PM2',
          description:
            '🚀 Start the async trading bot (production-ready with WebSocket + Actor model)',
          command: 'cd ~/Projects/WorkingBot && pm2 start gridbot-live',
          icon: <PlayArrowIcon />,
          tags: ['bot', 'start', 'live', 'pm2', 'trading', 'async'],
        },
        {
          name: 'Stop Async Trading Bot via PM2',
          description: 'Stop the async bot gracefully (cancels pending orders, closes WebSocket)',
          command: 'pm2 stop gridbot-live',
          icon: <StopIcon />,
          tags: ['bot', 'stop', 'pm2', 'async'],
        },
        {
          name: 'Restart Async Trading Bot via PM2',
          description: 'Restart the async bot (useful after config changes)',
          command: 'pm2 restart gridbot-live',
          icon: <RefreshIcon />,
          tags: ['bot', 'restart', 'pm2', 'async'],
        },
        {
          name: 'View Bot Status',
          description: 'Check status of all PM2 processes (async bot, guardian, heartbeat)',
          command: 'pm2 status',
          icon: <ViewListIcon />,
          tags: ['bot', 'status', 'pm2', 'monitor', 'async'],
        },
        {
          name: 'View Async Bot Logs (Live)',
          description: 'Stream live logs from the async trading bot with human-readable narrative',
          command: 'pm2 logs gridbot-live --lines 50',
          icon: <ViewListIcon />,
          tags: ['bot', 'logs', 'pm2', 'monitoring', 'async'],
        },
        {
          name: 'View All Bot Logs',
          description: 'See logs from all PM2 processes (async bot + guardian + heartbeat)',
          command: 'pm2 logs --lines 30',
          icon: <ViewListIcon />,
          tags: ['bot', 'logs', 'pm2', 'all', 'async'],
        },
        {
          name: 'PM2 Real-Time Monitor',
          description: 'Interactive dashboard showing CPU, memory, and logs in real-time',
          command: 'pm2 monit',
          icon: <MonitorHeartIcon />,
          tags: ['bot', 'monitor', 'pm2', 'dashboard'],
        },
        {
          name: 'Save PM2 State',
          description: 'Save current PM2 processes (auto-restart on reboot)',
          command: 'pm2 save',
          icon: <SecurityIcon />,
          tags: ['pm2', 'save', 'persist'],
        },
        {
          name: 'Start All Components (Async)',
          description: 'Start async trading bot, guardian, and heartbeat',
          command: 'cd ~/Projects/WorkingBot && ./pm2_gridbot.sh start all',
          icon: <PlayArrowIcon />,
          tags: ['bot', 'start', 'all', 'pm2', 'async'],
        },
        {
          name: 'Stop All Bots',
          description: 'Stop all bots (async trading, guardian, heartbeat)',
          command: 'cd ~/Projects/WorkingBot && ./pm2_gridbot.sh stop all',
          icon: <StopIcon />,
          tags: ['bot', 'stop', 'all', 'pm2'],
        },
      ],
    },
    {
      title: '🚀 Direct Async Bot Commands (Backup)',
      icon: <TerminalIcon />,
      color: '#9E9E9E',
      commands: [
        {
          name: 'Start Async Bot (Direct)',
          description: '⚠️ Only use if PM2 is unavailable. Runs async bot with USE_ASYNC_BOT=true',
          command: 'cd ~/Projects/WorkingBot && USE_ASYNC_BOT=true python3 -m bot.run',
          icon: <PlayArrowIcon />,
          tags: ['start', 'live', 'trading', 'async', 'direct'],
        },
        {
          name: 'Start Async Bot (Demo Mode)',
          description: 'Start async bot in demo mode with paper trading',
          command:
            'cd ~/Projects/WorkingBot && TRADING_MODE=demo USE_ASYNC_BOT=true python3 bot/run.py',
          icon: <PlayArrowIcon />,
          tags: ['start', 'demo', 'paper', 'async'],
        },
        {
          name: 'Stop Async Bot',
          description: 'Gracefully stop the async trading bot (SIGTERM)',
          command: 'pkill -TERM -f "python.*bot/run"',
          icon: <StopIcon />,
          tags: ['stop', 'kill', 'async'],
        },
        {
          name: 'Emergency Kill All',
          description: 'Force kill all bot processes immediately',
          command: 'cd ~/Projects/WorkingBot && python3 bot/emergency_kill.py',
          icon: <StopIcon />,
          tags: ['emergency', 'kill', 'stop'],
        },
        {
          name: 'Restart Async Bot',
          description: 'Stop and restart the async trading bot',
          command:
            'pkill -TERM -f "python.*bot/run" && sleep 5 && cd ~/Projects/WorkingBot && USE_ASYNC_BOT=true python3 bot/run.py &',
          icon: <RefreshIcon />,
          tags: ['restart', 'async'],
        },
        {
          name: 'Clean Start Async Bot',
          description: '🧹 Clean all locks and start fresh async bot instance',
          command: 'cd ~/Projects/WorkingBot && ./clean_start_async.sh',
          icon: <PlayArrowIcon />,
          tags: ['start', 'clean', 'async', 'fresh'],
        },
      ],
    },
    {
      title: '🛡️ Guardian & Monitors',
      icon: <SecurityIcon />,
      color: '#F44336',
      commands: [
        {
          name: 'Start Guardian Bot',
          description: 'Start the capital protection guardian',
          command:
            'cd ~/Projects/WorkingBot && python3 -u bot/guardian/guardian_bot.py | tee -a logs/guardian.log &',
          icon: <SecurityIcon />,
          tags: ['guardian', 'start', 'protection'],
        },
        {
          name: 'Stop Guardian Bot',
          description: 'Stop the guardian bot',
          command: 'pkill -TERM -f "guardian_bot.py"',
          icon: <StopIcon />,
          tags: ['guardian', 'stop'],
        },
        {
          name: 'Check Guardian Status',
          description: 'View guardian health and status',
          command: 'cat ~/Projects/WorkingBot/.guardian_health | python3 -m json.tool',
          icon: <MonitorHeartIcon />,
          tags: ['guardian', 'status', 'health'],
        },
      ],
    },
    {
      title: '🖥️ WebUI Management',
      icon: <TerminalIcon />,
      color: '#2196F3',
      commands: [
        {
          name: 'Start WebUI (Enhanced)',
          description: 'Start WebUI with production stability (RECOMMENDED)',
          command: 'launchctl start com.gridbot.webui.enhanced',
          icon: <PlayArrowIcon />,
          tags: ['webui', 'backend', 'start', 'enhanced', 'production'],
        },
        {
          name: 'Start WebUI (Basic)',
          description: 'Start WebUI backend using basic LaunchAgent',
          command: 'launchctl start com.gridbot.webui',
          icon: <PlayArrowIcon />,
          tags: ['webui', 'backend', 'start', 'basic'],
        },
        {
          name: 'Stop WebUI (Enhanced)',
          description: 'Stop enhanced WebUI backend',
          command: 'launchctl stop com.gridbot.webui.enhanced',
          icon: <StopIcon />,
          tags: ['webui', 'backend', 'stop', 'enhanced'],
        },
        {
          name: 'Stop WebUI (Basic)',
          description: 'Stop basic WebUI backend',
          command: 'launchctl stop com.gridbot.webui',
          icon: <StopIcon />,
          tags: ['webui', 'backend', 'stop', 'basic'],
        },
        {
          name: 'Restart WebUI (Enhanced)',
          description: 'Restart enhanced WebUI LaunchAgent',
          command: 'launchctl restart com.gridbot.webui.enhanced',
          icon: <RefreshIcon />,
          tags: ['webui', 'restart', 'launchd', 'enhanced'],
        },
        {
          name: 'Build Frontend',
          description: 'Rebuild the React frontend',
          command: 'cd ~/Projects/WorkingBot/webui/frontend && npm run build',
          icon: <BuildIcon />,
          tags: ['webui', 'frontend', 'build'],
        },
        {
          name: 'Start Development Frontend',
          description: 'Start frontend in dev mode with hot reload',
          command: 'cd ~/Projects/WorkingBot/webui/frontend && npm start',
          icon: <PlayArrowIcon />,
          tags: ['webui', 'frontend', 'dev'],
        },
        {
          name: 'Check WebUI Status',
          description: 'Check all WebUI LaunchAgent services',
          command: 'launchctl list | grep gridbot.webui',
          icon: <ViewListIcon />,
          tags: ['webui', 'status', 'check'],
        },
      ],
    },
    {
      title: '🛡️ Production Stability',
      icon: <SecurityIcon />,
      color: '#00E676',
      commands: [
        {
          name: 'Install Production Stability',
          description: 'Install Guardian + Enhanced LaunchAgent (Mac Mini M4)',
          command: 'cd ~/Projects/WorkingBot && ./install_webui_production.sh',
          icon: <BuildIcon />,
          tags: ['install', 'production', 'guardian', 'stability', 'setup'],
        },
        {
          name: 'Check WebUI Status',
          description: 'Quick status check for WebUI health',
          command: 'cd ~/Projects/WorkingBot && ./check_webui_status.sh',
          icon: <MonitorHeartIcon />,
          tags: ['status', 'health', 'check', 'guardian'],
        },
        {
          name: 'Start Guardian',
          description: 'Start WebUI Guardian monitoring system',
          command: 'launchctl start com.gridbot.webui.guardian',
          icon: <PlayArrowIcon />,
          tags: ['guardian', 'start', 'monitoring'],
        },
        {
          name: 'Stop Guardian',
          description: 'Stop WebUI Guardian monitoring',
          command: 'launchctl stop com.gridbot.webui.guardian',
          icon: <StopIcon />,
          tags: ['guardian', 'stop'],
        },
        {
          name: 'Restart Guardian',
          description: 'Restart the Guardian monitoring system',
          command: 'launchctl restart com.gridbot.webui.guardian',
          icon: <RefreshIcon />,
          tags: ['guardian', 'restart'],
        },
        {
          name: 'View Guardian Logs',
          description: 'Monitor Guardian health check logs',
          command: 'tail -f ~/Projects/WorkingBot/logs/webui_guardian.log',
          icon: <ViewListIcon />,
          tags: ['guardian', 'logs', 'monitoring'],
        },
        {
          name: 'View Guardian Stats',
          description: 'Show Guardian statistics (uptime, restarts, health)',
          command: 'cat ~/Projects/WorkingBot/data/webui_guardian_stats.json',
          icon: <MonitorHeartIcon />,
          tags: ['guardian', 'stats', 'monitoring'],
        },
        {
          name: 'View WebUI Error Logs',
          description: 'Check WebUI backend error logs',
          command: 'tail -f ~/Projects/WorkingBot/logs/launchagent_webui_error.log',
          icon: <BugReportIcon />,
          tags: ['webui', 'logs', 'error', 'debug'],
        },
      ],
    },
    {
      title: '📊 Monitoring & Logs (Async Bot)',
      icon: <ViewListIcon />,
      color: '#FF9800',
      commands: [
        {
          name: 'Watch All Async Bot Logs (Multi-Pane)',
          description: 'Open tmux with async bot, guardian, and webui logs in split panes',
          command: 'cd ~/Projects/WorkingBot && ./watch_bot_logs.sh all',
          icon: <ViewListIcon />,
          tags: ['logs', 'tmux', 'all', 'monitoring', 'async'],
        },
        {
          name: 'Watch Async Bot Logs',
          description:
            'Stream live async trading bot logs with human-readable narrative (PM2-aware)',
          command: 'cd ~/Projects/WorkingBot && ./watch_bot_logs.sh main',
          icon: <ViewListIcon />,
          tags: ['logs', 'bot', 'pm2', 'live', 'async'],
        },
        {
          name: 'Watch Guardian Logs',
          description: 'Stream live guardian logs (PM2-aware)',
          command: 'cd ~/Projects/WorkingBot && ./watch_bot_logs.sh guardian',
          icon: <ViewListIcon />,
          tags: ['logs', 'guardian', 'pm2'],
        },
        {
          name: 'Watch Errors Only',
          description: 'Filter and show only ERROR and CRITICAL messages from all async bot logs',
          command: 'cd ~/Projects/WorkingBot && ./watch_bot_logs.sh errors',
          icon: <BugReportIcon />,
          tags: ['logs', 'errors', 'critical', 'debug', 'async'],
        },
        {
          name: 'View PM2 Logs (All)',
          description: 'Stream all PM2 process logs (async bot + guardian + heartbeat)',
          command: 'pm2 logs --lines 50',
          icon: <ViewListIcon />,
          tags: ['logs', 'pm2', 'all', 'async'],
        },
        {
          name: 'View PM2 Async Bot Logs',
          description: 'Stream only async trading bot PM2 logs with narrative mode',
          command: 'pm2 logs gridbot-live --lines 50',
          icon: <ViewListIcon />,
          tags: ['logs', 'pm2', 'bot', 'async'],
        },
        {
          name: 'View PM2 Guardian Logs',
          description: 'Stream only guardian PM2 logs',
          command: 'pm2 logs guardian-live --lines 50',
          icon: <ViewListIcon />,
          tags: ['logs', 'pm2', 'guardian'],
        },
        {
          name: 'View Async Bot File Logs',
          description: 'Tail async bot file-based logs (includes WebSocket events)',
          command: 'tail -f ~/Projects/WorkingBot/bot/logs/bot.log',
          icon: <ViewListIcon />,
          tags: ['logs', 'trading', 'tail', 'file', 'async'],
        },
        {
          name: 'View Guardian File Logs',
          description: 'Tail traditional file-based guardian logs',
          command: 'tail -f ~/Projects/WorkingBot/bot/logs/guardian.log',
          icon: <ViewListIcon />,
          tags: ['logs', 'guardian', 'tail', 'file'],
        },
        {
          name: 'View WebUI Backend Logs',
          description: 'View WebUI backend error logs',
          command: 'tail -f ~/Projects/WorkingBot/logs/launchagent_webui_error.log',
          icon: <ViewListIcon />,
          tags: ['logs', 'webui', 'tail', 'backend'],
        },
        {
          name: 'Check All Bot Processes',
          description: 'List all running async bot-related processes',
          command: 'ps aux | grep -E "python.*(bot|guardian|webui)" | grep -v grep',
          icon: <MonitorHeartIcon />,
          tags: ['status', 'processes', 'monitor', 'async'],
        },
        {
          name: 'Check WebSocket Connection',
          description: 'Check if async bot WebSocket is connected to Delta Exchange',
          command:
            'pm2 logs gridbot-live --lines 20 | grep -E "WebSocket|authenticated|subscribed"',
          icon: <MonitorHeartIcon />,
          tags: ['websocket', 'connection', 'async', 'debug'],
        },
        {
          name: 'Check Port Usage',
          description: "See what's running on WebUI port 5555",
          command: 'lsof -i :5555',
          icon: <MonitorHeartIcon />,
          tags: ['network', 'port', 'debug'],
        },
        {
          name: 'View System Resource Usage',
          description: 'Monitor CPU and memory usage of async bot processes',
          command:
            'ps aux | grep -E "python.*(bot|guardian|webui)" | grep -v grep | awk \'{print $2, $3"%", $4"%", $11}\'',
          icon: <MonitorHeartIcon />,
          tags: ['performance', 'resources', 'async'],
        },
      ],
    },
    {
      title: '🔧 Troubleshooting & Fixes (Async Bot)',
      icon: <BugReportIcon />,
      color: '#9C27B0',
      commands: [
        {
          name: 'Fix Async Bot Instance Lock',
          description: "🔥 FIX: Async bot won't start due to instance lock conflict",
          command: 'cd ~/Projects/WorkingBot && ./fix_bot_instance_lock.sh',
          icon: <BugReportIcon />,
          tags: ['fix', 'lock', 'instance', 'emergency', 'async'],
        },
        {
          name: 'Check Async Bot Status & Health',
          description: 'Comprehensive async bot status check (PM2 + WebSocket + locks)',
          command:
            'cd ~/Projects/WorkingBot && pm2 status && echo "---" && ps aux | grep -E "python.*bot" | grep -v grep',
          icon: <MonitorHeartIcon />,
          tags: ['debug', 'status', 'health', 'async'],
        },
        {
          name: 'Clean All Lock Files',
          description: 'Remove all stale lock files (async bot, webui, instance locks)',
          command:
            'cd ~/Projects/WorkingBot && rm -f .bot_instance_*.lock .bot.lock /tmp/webui_backend.lock && echo "✅ All locks removed"',
          icon: <BugReportIcon />,
          tags: ['fix', 'lock', 'cleanup', 'emergency', 'async'],
        },
        {
          name: 'Check WebSocket Health',
          description: 'Check if async bot WebSocket is authenticated and receiving data',
          command:
            'pm2 logs gridbot-live --lines 100 | grep -E "WebSocket authenticated|Subscriptions active|Price.*flowing|Connection stable"',
          icon: <BugReportIcon />,
          tags: ['debug', 'websocket', 'async', 'health'],
        },
        {
          name: 'Check Actor System Health',
          description: 'Verify async bot actor system (OrderManager, PositionTracker, etc.)',
          command:
            'pm2 logs gridbot-live --lines 100 | grep -E "Actor.*processing|actor.*active|OrderManager|PositionTracker"',
          icon: <BugReportIcon />,
          tags: ['debug', 'actors', 'async', 'health'],
        },
        {
          name: 'Check Volatility Halt Status',
          description: 'See if async bot is halted due to high volatility',
          command:
            'cat ~/Projects/WorkingBot/.volatility_halt.json 2>/dev/null | python3 -m json.tool || echo "No halt active"',
          icon: <BugReportIcon />,
          tags: ['debug', 'volatility', 'status', 'async'],
        },
        {
          name: 'Test Backend Health',
          description: 'Check if WebUI backend is responding',
          command: 'curl -s http://localhost:5555/api/health | python3 -m json.tool 2>&1',
          icon: <BugReportIcon />,
          tags: ['debug', 'api', 'health', 'webui'],
        },
        {
          name: 'Restart Backend & Frontend',
          description: 'Complete sync: restart backend and rebuild frontend',
          command: 'cd ~/Projects/WorkingBot && ./sync_backend_frontend.sh',
          icon: <RefreshIcon />,
          tags: ['fix', 'webui', 'sync', 'restart'],
        },
        {
          name: 'Check PM2 Restart Count',
          description: 'See if async bot is crash-looping (high restart count = problem)',
          command: 'pm2 status | grep -E "gridbot|guardian|heartbeat"',
          icon: <BugReportIcon />,
          tags: ['pm2', 'debug', 'monitor', 'restarts', 'async'],
        },
        {
          name: 'Reset PM2 Restart Counter',
          description: 'Reset restart counter to 0 (after fixing issues)',
          command: 'pm2 reset gridbot-live',
          icon: <RefreshIcon />,
          tags: ['pm2', 'reset', 'fix', 'async'],
        },
        {
          name: 'View Last 100 Async Bot Logs',
          description: 'Quick check of recent async bot activity',
          command: 'cd ~/Projects/WorkingBot && tail -100 bot/logs/bot.log',
          icon: <ViewListIcon />,
          tags: ['logs', 'debug', 'quick', 'async'],
        },
        {
          name: 'Check for Duplicate Async Bots',
          description: '⚠️ CRITICAL: Check if multiple async bot instances are running',
          command:
            'ps aux | grep -E "python.*bot.run" | grep -v grep || echo "✅ No duplicate bots"',
          icon: <SecurityIcon />,
          tags: ['debug', 'critical', 'duplicate', 'safety', 'async'],
        },
        {
          name: 'Emergency Stop All Bots',
          description: '🚨 EMERGENCY: Kill all async bot processes immediately',
          command: 'pkill -TERM -f "bot.run" && pkill -TERM -f "guardian" && pm2 stop all',
          icon: <StopIcon />,
          tags: ['emergency', 'stop', 'kill', 'critical', 'async'],
        },
        {
          name: 'View PM2 Error Logs',
          description: 'Check PM2 error logs for async bot crash details',
          command: 'cat ~/.pm2/logs/gridbot-live-error.log | tail -50',
          icon: <BugReportIcon />,
          tags: ['pm2', 'logs', 'errors', 'debug', 'async'],
        },
        {
          name: 'Check LaunchAgents Status',
          description: 'View status of all GridBot LaunchAgents',
          command: 'launchctl list | grep gridbot',
          icon: <MonitorHeartIcon />,
          tags: ['launchd', 'status'],
        },
        {
          name: 'Debug WebSocket Reconnections',
          description: 'Check for WebSocket disconnection/reconnection patterns',
          command:
            'pm2 logs gridbot-live --lines 200 | grep -E "disconnected|reconnecting|CONNECTION LOST|RECONNECTING NOW"',
          icon: <BugReportIcon />,
          tags: ['debug', 'websocket', 'reconnect', 'async'],
        },
      ],
    },
    {
      title: '⚙️ Configuration & Setup',
      icon: <BuildIcon />,
      color: '#00BCD4',
      commands: [
        {
          name: 'Edit Bot Configuration',
          description: 'Open bot config in default editor',
          command: 'nano ~/Projects/WorkingBot/grid_config.env',
          icon: <BuildIcon />,
          tags: ['config', 'edit'],
        },
        {
          name: 'View Current Configuration',
          description: 'Display current bot settings',
          command: 'cat ~/Projects/WorkingBot/grid_config.env | grep -v "^#" | grep -v "^$"',
          icon: <ViewListIcon />,
          tags: ['config', 'view'],
        },
        {
          name: 'Edit API Keys',
          description: 'Securely edit API credentials',
          command: 'nano ~/Projects/WorkingBot/secrets/api_keys.env',
          icon: <SecurityIcon />,
          tags: ['config', 'api', 'security'],
        },
        {
          name: 'Install/Update Dependencies',
          description: 'Install Python packages from requirements.txt',
          command: 'cd ~/Projects/WorkingBot && pip3 install -r requirements.txt',
          icon: <BuildIcon />,
          tags: ['setup', 'dependencies', 'install'],
        },
        {
          name: 'Install Frontend Dependencies',
          description: 'Install npm packages for React frontend',
          command: 'cd ~/Projects/WorkingBot/webui/frontend && npm install',
          icon: <BuildIcon />,
          tags: ['setup', 'frontend', 'npm'],
        },
      ],
    },
  ];

  const handleCopyCommand = (command, name) => {
    navigator.clipboard.writeText(command);
    setCopiedCommand(name);
    setSnackbarOpen(true);
    setTimeout(() => setCopiedCommand(''), 2000);
  };

  const handleOpenInTerminal = (command) => {
    // This creates a .command file that can be opened in Terminal.app
    const script = `#!/bin/bash\n${command}\nread -p "Press Enter to close..."\n`;
    const blob = new Blob([script], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'gridbot_command.command';
    a.click();
    URL.revokeObjectURL(url);
  };

  // Filter commands based on search
  const filteredCategories = commandCategories
    .map((category) => ({
      ...category,
      commands: category.commands.filter((cmd) => {
        const searchLower = searchQuery.toLowerCase();
        return (
          cmd.name.toLowerCase().includes(searchLower) ||
          cmd.description.toLowerCase().includes(searchLower) ||
          cmd.command.toLowerCase().includes(searchLower) ||
          cmd.tags.some((tag) => tag.includes(searchLower))
        );
      }),
    }))
    .filter((category) => category.commands.length > 0);

  const displayCategories = searchQuery ? filteredCategories : commandCategories;

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Paper
        elevation={3}
        sx={{
          p: 3,
          mb: 3,
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          color: 'white',
        }}
      >
        <Typography
          variant="h4"
          gutterBottom
          sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center' }}
        >
          <TerminalIcon sx={{ mr: 2, fontSize: 40 }} />
          KNOW YOUR BOT - ASYNC EDITION
        </Typography>
        <Typography variant="body1">
          Mac Terminal commands for the Async GridBot (WebSocket + Actor Model + Saga Pattern)
        </Typography>
        <Typography variant="body2" sx={{ mt: 1, opacity: 0.9 }}>
          🚀 Running production async bot with PM2 process management
        </Typography>
      </Paper>

      {/* Search */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <TextField
          fullWidth
          placeholder="Search async bot commands... (e.g., 'start', 'logs', 'websocket', 'actor', 'debug')"
          variant="outlined"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
        />
      </Paper>

      {/* Alert */}
      <Alert severity="info" sx={{ mb: 3 }}>
        <strong>Tip:</strong> Click "Copy" to copy command to clipboard, then paste in your Mac
        Terminal. All commands use zsh shell and are optimized for the async bot.
      </Alert>

      {/* Command Categories */}
      {displayCategories.map((category, categoryIndex) => (
        <Paper key={categoryIndex} elevation={2} sx={{ mb: 3, p: 3 }}>
          {/* Category Header */}
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Box
              sx={{
                bgcolor: category.color,
                color: 'white',
                p: 1,
                borderRadius: 1,
                mr: 2,
                display: 'flex',
                alignItems: 'center',
              }}
            >
              {category.icon}
            </Box>
            <Typography variant="h5" sx={{ fontWeight: 'bold' }}>
              {category.title}
            </Typography>
            <Chip
              label={`${category.commands.length} commands`}
              size="small"
              sx={{ ml: 2 }}
              color="primary"
            />
          </Box>

          <Divider sx={{ mb: 2 }} />

          {/* Commands Grid */}
          <Grid container spacing={2}>
            {category.commands.map((cmd, cmdIndex) => (
              <Grid item xs={12} key={cmdIndex}>
                <Card
                  variant="outlined"
                  sx={{
                    transition: 'all 0.3s',
                    '&:hover': {
                      boxShadow: 4,
                      transform: 'translateX(4px)',
                      borderColor: category.color,
                    },
                  }}
                >
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'flex-start', mb: 1 }}>
                      <Box sx={{ color: category.color, mr: 1, mt: 0.5 }}>{cmd.icon}</Box>
                      <Box sx={{ flexGrow: 1 }}>
                        <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 0.5 }}>
                          {cmd.name}
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                          {cmd.description}
                        </Typography>
                        <Box
                          sx={{
                            bgcolor: '#0a0e27',
                            color: '#00e676',
                            p: 1.5,
                            borderRadius: 1,
                            fontFamily: 'monospace',
                            fontSize: '0.85rem',
                            overflow: 'auto',
                            border: '1px solid rgba(0, 230, 118, 0.2)',
                          }}
                        >
                          {cmd.command}
                        </Box>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
                          {cmd.tags.map((tag, tagIndex) => (
                            <Chip
                              key={tagIndex}
                              label={tag}
                              size="small"
                              variant="outlined"
                              sx={{ fontSize: '0.7rem' }}
                            />
                          ))}
                        </Box>
                      </Box>
                    </Box>
                  </CardContent>
                  <CardActions>
                    <Tooltip title="Copy to clipboard">
                      <Button
                        size="small"
                        startIcon={
                          copiedCommand === cmd.name ? <CheckCircleIcon /> : <ContentCopyIcon />
                        }
                        onClick={() => handleCopyCommand(cmd.command, cmd.name)}
                        color={copiedCommand === cmd.name ? 'success' : 'primary'}
                      >
                        {copiedCommand === cmd.name ? 'Copied!' : 'Copy'}
                      </Button>
                    </Tooltip>
                    <Tooltip title="Download as .command file to open in Terminal">
                      <Button
                        size="small"
                        startIcon={<OpenInNewIcon />}
                        onClick={() => handleOpenInTerminal(cmd.command)}
                      >
                        Download
                      </Button>
                    </Tooltip>
                  </CardActions>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Paper>
      ))}

      {/* No Results */}
      {displayCategories.length === 0 && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <BugReportIcon sx={{ fontSize: 60, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            No commands found matching "{searchQuery}"
          </Typography>
          <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
            Try searching for: start, stop, logs, async, websocket, actor, guardian, debug, config
          </Typography>
        </Paper>
      )}

      {/* Footer */}
      <Paper
        elevation={1}
        sx={{
          p: 2,
          mt: 3,
          bgcolor: 'rgba(0, 230, 118, 0.05)',
          border: '1px solid rgba(0, 230, 118, 0.2)',
        }}
      >
        <Typography variant="body2" align="center" sx={{ color: 'rgba(255, 255, 255, 0.7)' }}>
          💡 <strong style={{ color: '#00e676' }}>Pro Tip:</strong> All commands are designed for
          macOS with zsh shell. Adjust paths if your WorkingBot folder is in a different location.
        </Typography>
      </Paper>

      {/* Snackbar for copy confirmation */}
      <Snackbar
        open={snackbarOpen}
        autoHideDuration={2000}
        onClose={() => setSnackbarOpen(false)}
        message="Command copied to clipboard!"
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      />
    </Box>
  );
};

export default CommandKnowledgeBase;
