import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Button,
  Box,
  Alert,
  Chip,
  CircularProgress,
  Divider,
  Paper
} from '@mui/material';
import {
  Terminal as TerminalIcon,
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon
} from '@mui/icons-material';
import api from '../utils/apiShim';

const TmuxPanel = () => {
  const [tmuxStatus, setTmuxStatus] = useState({
    tmux_installed: false,
    session: { exists: false }
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  const [messageType, setMessageType] = useState('info');
  const [botStarting, setBotStarting] = useState(false);

  const fetchTmuxStatus = async () => {
    try {
      const response = await api.get('/api/tmux/status');
      setTmuxStatus(response.data);
    } catch (error) {
      console.error('Error fetching tmux status:', error);
    }
  };

  useEffect(() => {
    fetchTmuxStatus();
    const interval = setInterval(fetchTmuxStatus, 5000); // Poll every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const handleStartTmux = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const response = await api.post('/api/tmux/start');
      if (response.data.success) {
        setMessage('✅ tmux session started! Open Terminal and run "tmux -S ~/.tmux-gridbot/default attach -t gridbot" to view the panes.');
        setMessageType('success');
        setTimeout(fetchTmuxStatus, 2000); // Refresh status after 2 seconds
      } else {
        // Show detailed error message from backend
        const errorMsg = response.data.message || response.data.error || 'Failed to start tmux.';
        setMessage(errorMsg);
        setMessageType('error');
      }
    } catch (error) {
      // Better error handling - show actual backend message
      const backendMessage = error.response?.data?.message;
      const errorDetail = error.response?.data?.error;
      const fallbackMessage = error.message;
      
      const displayMessage = backendMessage || errorDetail || fallbackMessage || 'Unknown error';
      
      setMessage(`❌ ${displayMessage}`);
      setMessageType('error');
      
      console.error('tmux start error:', error);
      console.error('Response data:', error.response?.data);
    } finally {
      setLoading(false);
    }
  };

  const handleStopTmux = async () => {
    if (!window.confirm('Stop all bots in tmux session? This will terminate Guardian, Monitor, and Trading Bot.')) {
      return;
    }

    setLoading(true);
    setMessage(null);
    try {
      const response = await api.post('/api/tmux/stop');
      if (response.data.success) {
        setMessage(response.data.message);
        setMessageType('success');
        setTimeout(fetchTmuxStatus, 1000);
      } else {
        setMessage(response.data.message);
        setMessageType('error');
      }
    } catch (error) {
      setMessage(`Error: ${error.response?.data?.message || error.message}`);
      setMessageType('error');
    } finally {
      setLoading(false);
    }
  };

  const handleStartBotOnly = async () => {
    setBotStarting(true);
    setMessage(null);
    try {
      const response = await api.post('/api/bot/start');
      if (response.data.success) {
        setMessage('✅ Bot start command acknowledged. Check status panels or tmux once it spins up.');
        setMessageType('success');
      } else {
        setMessage(response.data.message || 'Failed to start bot.');
        setMessageType('error');
      }
    } catch (error) {
      setMessage(`Error starting bot: ${error.response?.data?.message || error.message}`);
      setMessageType('error');
    } finally {
      setBotStarting(false);
    }
  };

  const sessionExists = tmuxStatus.session?.exists;
  const tmuxInstalled = tmuxStatus.tmux_installed;


  return (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" mb={2}>
          <TerminalIcon sx={{ mr: 1, fontSize: 28 }} />
          <Typography variant="h6">
            tmux Professional Setup
          </Typography>
        </Box>


        <Typography variant="body2" color="text.secondary" paragraph>
          Start all 3 bots (Guardian + Monitor + Trading) in a professional split-pane terminal view
        </Typography>


        {/* tmux Installation Status */}
        <Box mb={2}>
          <Chip
            icon={tmuxInstalled ? <CheckIcon /> : <ErrorIcon />}
            label={tmuxInstalled ? 'tmux Installed' : 'tmux Not Installed'}
            color={tmuxInstalled ? 'success' : 'error'}
            size="small"
          />
        </Box>

        {!tmuxInstalled && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2">
              <strong>tmux is not installed.</strong><br />
              Install it with:<br />
              • macOS: <code>brew install tmux</code><br />
              • Linux: <code>sudo apt install tmux</code>
            </Typography>
          </Alert>
        )}

        {/* Session Status */}
        {tmuxInstalled && (
          <Paper variant="outlined" sx={{ p: 2, mb: 2, bgcolor: 'background.default' }}>
            <Typography variant="subtitle2" gutterBottom>
              Session Status
            </Typography>
            <Box display="flex" alignItems="center" gap={1}>
              <Chip
                label={sessionExists ? 'Session Active' : 'No Session'}
                color={sessionExists ? 'success' : 'default'}
                size="small"
              />
              {sessionExists && (
                <Typography variant="caption" color="text.secondary">
                  Session: "gridbot"
                </Typography>
              )}
            </Box>

            {!sessionExists && (
              <Alert severity="info" sx={{ mt: 2 }}>
                When you start tmux, Guardian, Monitor, and Trading processes will launch inside a split-pane session automatically.
              </Alert>
            )}

            {sessionExists && (
              <Box mt={2}>
                <Alert severity="info" sx={{ fontSize: '0.875rem' }}>
                  <Typography variant="body2" gutterBottom>
                    <strong>📺 To view bots in terminal:</strong>
                  </Typography>
                  <Typography variant="caption" display="block" sx={{ mb: 1 }}>
                    1. Open a <strong>NEW terminal window</strong> (Terminal.app on macOS)<br/>
                    2. Copy and paste this command:
                  </Typography>
                  <Typography variant="body2" component="div" sx={{ fontFamily: 'monospace', fontSize: '0.8rem', bgcolor: '#000', color: '#0f0', p: 1, borderRadius: 1, mb: 1, cursor: 'pointer' }} onClick={() => navigator.clipboard.writeText('tmux -S ~/.tmux-gridbot/default attach -t gridbot')}>
                    tmux -S ~/.tmux-gridbot/default attach -t gridbot
                  </Typography>
                  <Typography variant="caption" display="block" sx={{ bgcolor: 'rgba(255, 152, 0, 0.15)', p: 1, borderRadius: 1, border: '1px solid rgba(255, 152, 0, 0.4)', mb: 1 }}>
                    💡 Click the command above to copy it to clipboard
                  </Typography>
                  <Typography variant="caption" display="block" sx={{ bgcolor: 'rgba(33, 150, 243, 0.1)', p: 1, borderRadius: 1, mb: 1, border: '1px solid rgba(33, 150, 243, 0.3)' }}>
                    ✅ You'll see 3 split panes with bot output
                  </Typography>
                  <Typography variant="caption" display="block" sx={{ bgcolor: 'rgba(255, 152, 0, 0.15)', p: 1, borderRadius: 1, border: '1px solid rgba(255, 152, 0, 0.4)' }}>
                    <strong>⌨️ To detach (ONLY works INSIDE tmux window):</strong><br/>
                    Step 1: Press <strong>Ctrl+B</strong> (then release)<br/>
                    Step 2: Press <strong>d</strong> key<br/>
                    <em>📝 This is a keyboard shortcut, NOT a command to type!</em><br/>
                    <strong>💡 OR just close the terminal - bots keep running!</strong>
                  </Typography>
                </Alert>
              </Box>
            )}
          </Paper>
        )}

        {/* Message Display */}
        {message && (
          <Alert severity={messageType} sx={{ mb: 2 }} onClose={() => setMessage(null)}>
            {message}
          </Alert>
        )}

        {/* Control Buttons */}
        <Box display="flex" gap={1} flexWrap="wrap">
          <Button
            variant="contained"
            color="success"
            startIcon={loading ? <CircularProgress size={20} /> : <PlayIcon />}
            onClick={handleStartTmux}
            disabled={loading || !tmuxInstalled || sessionExists}
            fullWidth={!sessionExists}
          >
            {sessionExists ? 'Session Already Running' : 'Start with tmux'}
          </Button>

          {!sessionExists && (
            <Button
              variant="outlined"
              color="primary"
              startIcon={botStarting ? <CircularProgress size={20} /> : <PlayIcon />}
              onClick={handleStartBotOnly}
              disabled={botStarting}
            >
              Start Bot Only
            </Button>
          )}

          {sessionExists && (
            <>
              <Button
                variant="outlined"
                color="error"
                startIcon={loading ? <CircularProgress size={20} /> : <StopIcon />}
                onClick={handleStopTmux}
                disabled={loading}
              >
                Stop Session
              </Button>

              <Button
                variant="outlined"
                startIcon={<RefreshIcon />}
                onClick={fetchTmuxStatus}
                disabled={loading}
              >
                Refresh
              </Button>
            </>
          )}
        </Box>

        {/* Info Section */}
        <Divider sx={{ my: 2 }} />
        <Box>
          <Typography variant="subtitle2" gutterBottom>
            What is tmux?
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            tmux is a terminal multiplexer that allows you to:
          </Typography>
          <Box component="ul" sx={{ pl: 2, mt: 0 }}>
            <Typography component="li" variant="body2" color="text.secondary">
              See all 3 bots in split panes (Guardian | Monitor | Trading)
            </Typography>
            <Typography component="li" variant="body2" color="text.secondary">
              Detach and reattach without stopping bots
            </Typography>
            <Typography component="li" variant="body2" color="text.secondary">
              Scroll through terminal history
            </Typography>
            <Typography component="li" variant="body2" color="text.secondary">
              Professional monitoring experience
            </Typography>
          </Box>
        </Box>

        {/* Layout Preview */}
        {sessionExists && (
          <Box mt={2}>
            <Typography variant="subtitle2" gutterBottom>
              Terminal Layout:
            </Typography>
            <Paper variant="outlined" sx={{ p: 1, bgcolor: '#1e1e1e', color: '#00ff00', fontFamily: 'monospace', fontSize: '0.7rem' }}>
              <pre style={{ margin: 0 }}>
{`┌─────────────┬──────────────┬──────────────┐
│   Guardian  │   Monitor    │  Trading Bot │
│      🛡️      │      💓       │      🤖      │
└─────────────┴──────────────┴──────────────┘`}
              </pre>
            </Paper>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default TmuxPanel;
