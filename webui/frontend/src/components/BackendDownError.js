import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Alert,
  Card,
  CardContent,
  Divider,
  Chip,
  IconButton,
  Tooltip,
  Snackbar,
  CircularProgress,
} from '@mui/material';
import {
  ErrorOutline as ErrorIcon,
  Refresh as RefreshIcon,
  Terminal as TerminalIcon,
  ContentCopy as ContentCopyIcon,
  CheckCircle as CheckCircleIcon,
  PowerSettingsNew as PowerIcon,
  Cancel as CancelIcon,
} from '@mui/icons-material';

const BackendDownError = ({ onRetry }) => {
  const [copiedCommand, setCopiedCommand] = useState('');
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [isChecking, setIsChecking] = useState(false);

  const handleCopyCommand = (command, name) => {
    navigator.clipboard.writeText(command);
    setCopiedCommand(name);
    setSnackbarOpen(true);
    setTimeout(() => setCopiedCommand(''), 2000);
  };

  const handleRetry = async () => {
    setIsChecking(true);
    setTimeout(() => {
      setIsChecking(false);
      if (onRetry) onRetry();
    }, 2000);
  };

  useEffect(() => {
    // Auto-retry every 10 seconds
    const interval = setInterval(() => {
      if (onRetry) onRetry();
    }, 10000);

    return () => clearInterval(interval);
  }, [onRetry]);

  const commands = [
    {
      title: 'Start Backend (Enhanced)',
      description: 'Recommended: Start WebUI with production stability',
      command: 'launchctl start com.gridbot.webui.enhanced',
      icon: <PowerIcon />,
      color: '#4CAF50',
    },
    {
      title: 'Start Backend (Basic)',
      description: 'Start WebUI using basic LaunchAgent',
      command: 'launchctl start com.gridbot.webui',
      icon: <PowerIcon />,
      color: '#2196F3',
    },
    {
      title: 'Check Backend Status',
      description: 'Verify if the WebUI backend LaunchAgent is running',
      command: 'launchctl list | grep gridbot.webui',
      icon: <TerminalIcon />,
      color: '#2196F3',
    },
    {
      title: 'Restart Backend (Enhanced)',
      description: 'Restart the enhanced WebUI backend',
      command: 'launchctl restart com.gridbot.webui.enhanced',
      icon: <RefreshIcon />,
      color: '#FF9800',
    },
    {
      title: 'Check WebUI Health',
      description: 'Run quick status check (if installed)',
      command: 'cd ~/Projects/WorkingBot && ./check_webui_status.sh',
      icon: <TerminalIcon />,
      color: '#00E676',
    },
    {
      title: 'Manual Start (Fallback)',
      description: 'Manually start backend if LaunchAgent fails',
      command: 'cd ~/Projects/WorkingBot/webui/backend && python3 app.py &',
      icon: <TerminalIcon />,
      color: '#9C27B0',
    },
    {
      title: 'Check Port 5555',
      description: "See what's running on the WebUI port",
      command: 'lsof -i :5555',
      icon: <TerminalIcon />,
      color: '#F44336',
    },
  ];

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #0a0e27 0%, #1a1f3a 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 3,
      }}
    >
      <Box sx={{ maxWidth: 900, width: '100%' }}>
        {/* Error Header */}
        <Paper
          elevation={8}
          sx={{
            p: 4,
            mb: 3,
            background: 'linear-gradient(135deg, #d32f2f 0%, #c62828 100%)',
            color: 'white',
            textAlign: 'center',
          }}
        >
          <ErrorIcon sx={{ fontSize: 80, mb: 2, opacity: 0.9 }} />
          <Typography variant="h3" sx={{ fontWeight: 'bold', mb: 2 }}>
            Backend Connection Failed
          </Typography>
          <Typography variant="h6" sx={{ opacity: 0.9 }}>
            Cannot connect to WebUI backend at <code>localhost:5555</code>
          </Typography>
          <Typography variant="body2" sx={{ mt: 2, opacity: 0.8 }}>
            The backend server is not responding. Use the commands below to start it.
          </Typography>
        </Paper>

        {/* Alert Box */}
        <Alert
          severity="warning"
          sx={{
            mb: 3,
            fontSize: '1rem',
            '& .MuiAlert-icon': {
              fontSize: 28,
            },
          }}
        >
          <strong>Quick Fix:</strong> Run the first command below in your Mac Terminal to start the
          backend via LaunchAgent.
        </Alert>

        {/* Commands List */}
        <Paper elevation={4} sx={{ p: 3, mb: 3 }}>
          <Typography
            variant="h5"
            sx={{ mb: 2, fontWeight: 'bold', display: 'flex', alignItems: 'center' }}
          >
            <TerminalIcon sx={{ mr: 1 }} />
            Recovery Commands
          </Typography>
          <Divider sx={{ mb: 2 }} />

          {commands.map((cmd, index) => (
            <Card
              key={index}
              variant="outlined"
              sx={{
                mb: 2,
                transition: 'all 0.3s',
                '&:hover': {
                  boxShadow: 4,
                  borderColor: cmd.color,
                },
              }}
            >
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'flex-start', mb: 1 }}>
                  <Box sx={{ color: cmd.color, mr: 1.5, mt: 0.5 }}>{cmd.icon}</Box>
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 0.5 }}>
                      {cmd.title}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                      {cmd.description}
                    </Typography>
                    <Box
                      sx={{
                        bgcolor: '#0a0e27',
                        color: '#00e676',
                        p: 1.5,
                        borderRadius: 1,
                        fontFamily: 'monospace',
                        fontSize: '0.9rem',
                        overflow: 'auto',
                        border: '1px solid rgba(0, 230, 118, 0.2)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <code>{cmd.command}</code>
                      <Tooltip title="Copy to clipboard">
                        <IconButton
                          size="small"
                          onClick={() => handleCopyCommand(cmd.command, cmd.title)}
                          sx={{
                            color: copiedCommand === cmd.title ? '#4CAF50' : '#00e676',
                            ml: 1,
                          }}
                        >
                          {copiedCommand === cmd.title ? <CheckCircleIcon /> : <ContentCopyIcon />}
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          ))}
        </Paper>

        {/* Action Buttons */}
        <Paper elevation={4} sx={{ p: 3, textAlign: 'center' }}>
          <Typography variant="body1" sx={{ mb: 2 }}>
            After starting the backend, click the button below to retry the connection
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }}>
            <Button
              variant="contained"
              size="large"
              startIcon={
                isChecking ? <CircularProgress size={20} color="inherit" /> : <RefreshIcon />
              }
              onClick={handleRetry}
              disabled={isChecking}
              sx={{
                px: 4,
                py: 1.5,
                background: 'linear-gradient(135deg, #4CAF50 0%, #388E3C 100%)',
                '&:hover': {
                  background: 'linear-gradient(135deg, #388E3C 0%, #2E7D32 100%)',
                },
              }}
            >
              {isChecking ? 'Checking...' : 'Retry Connection'}
            </Button>
            <Button
              variant="outlined"
              size="large"
              startIcon={<CancelIcon />}
              onClick={() => window.close()}
              sx={{ px: 4, py: 1.5 }}
            >
              Close Window
            </Button>
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
            Auto-retry every 10 seconds...
          </Typography>
        </Paper>

        {/* Additional Info */}
        <Alert severity="info" sx={{ mt: 3 }}>
          <Typography variant="body2">
            <strong>Need more help?</strong> Once the backend is running, check the "Know Your Bot"
            section in the WebUI for a complete command reference.
          </Typography>
        </Alert>
      </Box>

      {/* Snackbar */}
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

export default BackendDownError;
