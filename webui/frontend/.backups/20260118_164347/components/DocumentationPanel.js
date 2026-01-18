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

const DocumentationPanel = () => {
  const [copiedCommand, setCopiedCommand] = useState('');
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Command categories with actual Mac terminal commands
  const commandCategories = [
    {
      title: '� Bot Management',
      icon: <PlayArrowIcon />,
      color: '#4CAF50',
      commands: [
        {
          name: 'Start Trading Bot (Live)',
          description: 'Start the live trading bot with real money',
          command: 'cd ~/Projects/WorkingBot && python3 bot/run.py',
          icon: <PlayArrowIcon />,
          tags: ['start', 'live', 'trading'],
        },
        {
          name: 'Start Trading Bot (Demo)',
          description: 'Start bot in demo mode with paper trading',
          command: 'cd ~/Projects/WorkingBot && python3 bot/run.py demo',
          icon: <PlayArrowIcon />,
          tags: ['start', 'demo', 'paper'],
        },
        {
          name: 'Stop Trading Bot',
          description: 'Gracefully stop the trading bot (SIGTERM)',
          command: 'pkill -TERM -f "python.*bot/run"',
          icon: <StopIcon />,
          tags: ['stop', 'kill'],
        },
        {
          name: 'Emergency Kill All',
          description: 'Force kill all bot processes immediately',
          command: 'cd ~/Projects/WorkingBot && python3 bot/emergency_kill.py',
          icon: <StopIcon />,
          tags: ['emergency', 'kill', 'stop'],
        },
        {
          name: 'Restart Trading Bot',
          description: 'Stop and restart the trading bot',
          command: 'pkill -TERM -f "python.*bot/run" && sleep 5 && cd ~/Projects/WorkingBot && python3 bot/run.py &',
          icon: <RefreshIcon />,
          tags: ['restart'],
        },
      ],
    },
    {
      title: '�️ Guardian & Monitors',
      icon: <SecurityIcon />,
      color: '#F44336',
      commands: [
        {
          name: 'Start Guardian Bot',
          description: 'Start the capital protection guardian',
          command: 'cd ~/Projects/WorkingBot && python3 -u bot/guardian/guardian_bot.py | tee -a logs/guardian.log &',
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
      ],
    },
    {
      title: '� Monitoring & Logs',
      icon: <ViewListIcon />,
      color: '#FF9800',
      commands: [
        {
          name: 'View Trading Bot Logs',
          description: 'Tail the trading bot logs in real-time',
          command: 'tail -f ~/Projects/WorkingBot/bot/logs/bot.log',
          icon: <ViewListIcon />,
          tags: ['logs', 'trading', 'tail'],
        },
        {
          name: 'View Guardian Logs',
          description: 'Tail the guardian bot logs',
          command: 'tail -f ~/Projects/WorkingBot/bot/logs/guardian.log',
          icon: <ViewListIcon />,
          tags: ['logs', 'guardian', 'tail'],
        },
        {
          name: 'View WebUI Logs',
          description: 'View WebUI backend logs',
          command: 'tail -f ~/Projects/WorkingBot/webui/backend/webui.log',
          icon: <ViewListIcon />,
          tags: ['logs', 'webui', 'tail'],
        },
        {
          name: 'Check All Bot Processes',
          description: 'List all running bot-related processes',
          command: 'ps aux | grep -E "python.*(bot|guardian|webui)" | grep -v grep',
          icon: <MonitorHeartIcon />,
          tags: ['status', 'processes', 'monitor'],
        },
        {
          name: 'Check Port Usage',
          description: 'See what\'s running on WebUI port 5555',
          command: 'lsof -i :5555',
          icon: <MonitorHeartIcon />,
          tags: ['network', 'port', 'debug'],
        },
        {
          name: 'View System Resource Usage',
          description: 'Monitor CPU and memory usage of bot processes',
          command: 'ps aux | grep -E "python.*(bot|guardian|webui)" | grep -v grep | awk \'{print $2, $3"%", $4"%", $11}\'',
          icon: <MonitorHeartIcon />,
          tags: ['performance', 'resources'],
        },
      ],
    },
    {
      title: '🔧 Troubleshooting',
      icon: <BugReportIcon />,
      color: '#9C27B0',
      commands: [
        {
          name: 'Check Bot PID File',
          description: 'View the current bot process ID',
          command: 'cat ~/Projects/WorkingBot/reports/bot.pid 2>/dev/null || echo "No PID file found"',
          icon: <BugReportIcon />,
          tags: ['debug', 'pid'],
        },
        {
          name: 'Check Volatility Halt Status',
          description: 'See if bot is halted due to volatility',
          command: 'cat ~/Projects/WorkingBot/.volatility_halt.json 2>/dev/null | python3 -m json.tool',
          icon: <BugReportIcon />,
          tags: ['debug', 'volatility'],
        },
        {
          name: 'Test API Health',
          description: 'Check WebUI backend health endpoint',
          command: 'curl -s http://localhost:5555/api/health | python3 -m json.tool',
          icon: <BugReportIcon />,
          tags: ['debug', 'api', 'health'],
        },
        {
          name: 'Clean Lock Files',
          description: 'Remove stale lock files that prevent startup',
          command: 'rm -f ~/Projects/WorkingBot/.bot_instance.lock ~/Projects/WorkingBot/.bot.lock /tmp/webui_backend.lock',
          icon: <BugReportIcon />,
          tags: ['fix', 'lock', 'cleanup'],
        },
        {
          name: 'Check tmux Sessions',
          description: 'List all tmux sessions (including custom socket)',
          command: 'tmux -S ~/.tmux-gridbot/default list-sessions 2>&1 || echo "No tmux sessions"',
          icon: <BugReportIcon />,
          tags: ['tmux', 'debug'],
        },
        {
          name: 'Kill All tmux Sessions',
          description: 'Kill custom GridBot tmux sessions',
          command: 'tmux -S ~/.tmux-gridbot/default kill-server 2>&1',
          icon: <StopIcon />,
          tags: ['tmux', 'kill', 'cleanup'],
        },
        {
          name: 'Check LaunchAgents Status',
          description: 'View status of all GridBot LaunchAgents',
          command: 'launchctl list | grep gridbot',
          icon: <MonitorHeartIcon />,
          tags: ['launchd', 'status'],
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
  const filteredCategories = commandCategories.map(category => ({
    ...category,
    commands: category.commands.filter(cmd => {
      const searchLower = searchQuery.toLowerCase();
      return (
        cmd.name.toLowerCase().includes(searchLower) ||
        cmd.description.toLowerCase().includes(searchLower) ||
        cmd.command.toLowerCase().includes(searchLower) ||
        cmd.tags.some(tag => tag.includes(searchLower))
      );
    }),
  })).filter(category => category.commands.length > 0);

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
        <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold' }}>
          📚 KNOW YOUR BOT
        </Typography>
        <Typography variant="body1">
          Complete documentation for all features, setup guides, and best practices
        </Typography>
      </Paper>

      {/* Alert */}
      <Alert severity="info" sx={{ mb: 3 }}>
        <strong>Tip:</strong> Click "Open" to read documentation in a popup, or "Download" for offline reading.
      </Alert>

      {/* Documentation Categories */}
      {docCategories.map((category, categoryIndex) => (
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
              label={`${category.docs.length} docs`}
              size="small"
              sx={{ ml: 2 }}
              color="primary"
            />
          </Box>

          <Divider sx={{ mb: 2 }} />

          {/* Documents Grid */}
          <Grid container spacing={2}>
            {category.docs.map((doc, docIndex) => (
              <Grid item xs={12} md={6} key={docIndex}>
                <Card
                  variant="outlined"
                  sx={{
                    height: '100%',
                    transition: 'all 0.3s',
                    '&:hover': {
                      boxShadow: 4,
                      transform: 'translateY(-4px)',
                    },
                  }}
                >
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                      <Box sx={{ color: category.color, mr: 1 }}>
                        {doc.icon}
                      </Box>
                      <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                        {doc.name}
                      </Typography>
                    </Box>
                    <Typography variant="body2" color="text.secondary">
                      {doc.description}
                    </Typography>
                    <Typography
                      variant="caption"
                      color="text.disabled"
                      sx={{ mt: 1, display: 'block' }}
                    >
                      📄 {doc.file}
                    </Typography>
                  </CardContent>
                  <CardActions>
                    <Button
                      size="small"
                      startIcon={<OpenInNewIcon />}
                      onClick={() => handleOpenDoc(doc)}
                    >
                      Open
                    </Button>
                    <Button
                      size="small"
                      startIcon={<DescriptionIcon />}
                      onClick={() => handleDownloadDoc(doc.file)}
                    >
                      Download
                    </Button>
                  </CardActions>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Paper>
      ))}

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
          💡 <strong style={{ color: '#00e676' }}>Pro Tip:</strong> Read the User Manual and README first for a complete overview.
          Then explore specific guides based on your needs.
        </Typography>
      </Paper>

      {/* Documentation Viewer Dialog */}
      <Dialog
        open={openDialog}
        onClose={handleCloseDialog}
        maxWidth="lg"
        fullWidth
        PaperProps={{
          sx: {
            height: '90vh',
          },
        }}
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            {selectedDoc?.icon && (
              <Box sx={{ mr: 1, display: 'flex', alignItems: 'center' }}>
                {selectedDoc.icon}
              </Box>
            )}
            <Typography variant="h6">{selectedDoc?.name}</Typography>
          </Box>
          <IconButton onClick={handleCloseDialog}>
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent dividers>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
              <CircularProgress />
            </Box>
          ) : (
            <Box sx={{ 
              '& h1': { fontSize: '2rem', fontWeight: 'bold', mt: 3, mb: 2, color: 'text.primary' },
              '& h2': { fontSize: '1.5rem', fontWeight: 'bold', mt: 2, mb: 1, color: 'text.primary' },
              '& h3': { fontSize: '1.25rem', fontWeight: 'bold', mt: 2, mb: 1, color: 'text.primary' },
              '& p': { mb: 2, color: 'text.primary' },
              '& code': { 
                bgcolor: 'rgba(255, 255, 255, 0.1)',
                color: '#00e676',
                p: '2px 6px',
                borderRadius: 1,
                fontFamily: 'monospace',
                fontSize: '0.9em',
                border: '1px solid rgba(255, 255, 255, 0.2)',
              },
              '& pre': { 
                bgcolor: '#0a0e27',
                color: '#d4d4d4',
                p: 2, 
                borderRadius: 1,
                overflow: 'auto',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                '& code': {
                  bgcolor: 'transparent',
                  color: '#d4d4d4',
                  border: 'none',
                  p: 0,
                },
              },
              '& ul, & ol': { ml: 3, mb: 2, color: 'text.primary' },
              '& li': { mb: 1, color: 'text.primary' },
              '& blockquote': {
                borderLeft: '4px solid #00e676',
                pl: 2,
                ml: 0,
                fontStyle: 'italic',
                color: 'text.secondary',
                bgcolor: 'rgba(0, 230, 118, 0.05)',
                py: 1,
              },
              '& table': {
                width: '100%',
                borderCollapse: 'collapse',
                mb: 2,
              },
              '& th, & td': {
                border: '1px solid rgba(255, 255, 255, 0.2)',
                p: 1,
                color: 'text.primary',
              },
              '& th': {
                bgcolor: 'rgba(0, 230, 118, 0.1)',
                fontWeight: 'bold',
              },
              '& strong': {
                color: '#00e676',
                fontWeight: 'bold',
              },
              '& a': {
                color: '#00e676',
                textDecoration: 'none',
                '&:hover': {
                  textDecoration: 'underline',
                },
              },
            }}>
              <ReactMarkdown>{docContent}</ReactMarkdown>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => handleDownloadDoc(selectedDoc?.file)} startIcon={<DescriptionIcon />}>
            Download
          </Button>
          <Button onClick={handleCloseDialog} variant="contained">
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default DocumentationPanel;
