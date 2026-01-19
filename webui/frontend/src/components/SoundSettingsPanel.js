/**
 * Sound Settings Panel
 * 
 * Independent component for managing sound preferences
 * NO trading logic - pure UI for sound configuration
 */

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Switch,
  Slider,
  FormControl,
  Select,
  MenuItem,
  Divider,
  IconButton,
  Paper,
  Grid,
} from '@mui/material';
import {
  VolumeUp as VolumeIcon,
  VolumeOff as VolumeOffIcon,
  PlayArrow as PlayIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import soundManager from '../utils/soundManager';

const SoundSettingsPanel = ({ open, onClose }) => {
  const [enabled, setEnabled] = useState(soundManager.isEnabled());
  const [volume, setVolume] = useState(soundManager.volume * 100);
  const [soundTypes, setSoundTypes] = useState({
    buy: soundManager.getSoundType('buy'),
    sell: soundManager.getSoundType('sell'),
    close: soundManager.getSoundType('close'),
    profit: soundManager.getSoundType('profit'),
    loss: soundManager.getSoundType('loss'),
  });
  
  // Initialize with all sound options
  const availableSounds = [
    // Generated sounds
    { value: 'chime', label: '🔔 Chime', description: 'Soft C major chord', category: 'Generated' },
    { value: 'success', label: '✨ Success', description: 'Uplifting ascending tone', category: 'Generated' },
    { value: 'gentle', label: '🎵 Gentle', description: 'Subtle single tone', category: 'Generated' },
    { value: 'alert', label: '⚡ Alert', description: 'Attention grabbing', category: 'Generated' },
    // macOS system sounds
    { value: 'basso', label: '🍎 Basso', description: 'macOS system sound', category: 'System' },
    { value: 'blow', label: '🍎 Blow', description: 'macOS system sound', category: 'System' },
    { value: 'bottle', label: '🍎 Bottle', description: 'macOS system sound', category: 'System' },
    { value: 'frog', label: '🍎 Frog', description: 'macOS system sound', category: 'System' },
    { value: 'funk', label: '🍎 Funk', description: 'macOS system sound', category: 'System' },
    { value: 'glass', label: '🍎 Glass', description: 'macOS system sound', category: 'System' },
    { value: 'hero', label: '🍎 Hero', description: 'macOS system sound', category: 'System' },
    { value: 'morse', label: '🍎 Morse', description: 'macOS system sound', category: 'System' },
    { value: 'ping', label: '🍎 Ping', description: 'macOS system sound', category: 'System' },
    { value: 'pop', label: '🍎 Pop', description: 'macOS system sound', category: 'System' },
    { value: 'purr', label: '🍎 Purr', description: 'macOS system sound', category: 'System' },
    { value: 'sosumi', label: '🍎 Sosumi', description: 'macOS system sound', category: 'System' },
    { value: 'submarine', label: '🍎 Submarine', description: 'macOS system sound', category: 'System' },
    { value: 'tink', label: '🍎 Tink', description: 'macOS system sound', category: 'System' },
  ];

  const actionTypes = [
    { key: 'buy', label: 'Buy Orders', icon: '🟢', description: 'Played when buy order fills' },
    { key: 'sell', label: 'Sell Orders', icon: '🔴', description: 'Played when sell order fills' },
    { key: 'close', label: 'Close Position', icon: '🔵', description: 'Played when position closes' },
    { key: 'profit', label: 'Profit Exit', icon: '💚', description: 'Played on profitable close' },
    { key: 'loss', label: 'Loss Exit', icon: '💔', description: 'Played on loss close' },
  ];

  const handleEnabledToggle = (event) => {
    const newEnabled = event.target.checked;
    setEnabled(newEnabled);
    soundManager.setEnabled(newEnabled);
  };

  const handleVolumeChange = (event, newValue) => {
    setVolume(newValue);
    soundManager.setVolume(newValue / 100);
  };

  const handleSoundTypeChange = (action, newSound) => {
    const newTypes = { ...soundTypes, [action]: newSound };
    setSoundTypes(newTypes);
    soundManager.setSoundType(action, newSound);
  };

  const handlePreviewSound = (soundType) => {
    soundManager.previewSound(soundType);
  };

  const handleTestAll = () => {
    // Play a sequence of all configured sounds
    Object.entries(soundTypes).forEach(([action, sound], index) => {
      setTimeout(() => {
        soundManager.previewSound(sound);
      }, index * 400);
    });
  };

  return (
    <Dialog 
      open={open} 
      onClose={onClose} 
      maxWidth="md" 
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: 'background.paper',
          backgroundImage: 'linear-gradient(rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.05))',
        }
      }}
    >
      <DialogTitle sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        pb: 1
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <VolumeIcon color="primary" />
          <Typography variant="h6">Sound Settings</Typography>
        </Box>
        <IconButton onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent>
        {/* Master Enable/Disable */}
        <Paper sx={{ p: 2, mb: 2, bgcolor: 'action.hover' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Box>
              <Typography variant="subtitle1" fontWeight="bold">
                Enable Sound Notifications
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Play sounds when trades execute
              </Typography>
            </Box>
            <Switch
              checked={enabled}
              onChange={handleEnabledToggle}
              color="primary"
              size="large"
            />
          </Box>
        </Paper>

        {/* Volume Control */}
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle1" gutterBottom fontWeight="bold">
            Volume
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {volume === 0 ? <VolumeOffIcon /> : <VolumeIcon />}
            <Slider
              value={volume}
              onChange={handleVolumeChange}
              min={0}
              max={100}
              disabled={!enabled}
              valueLabelDisplay="auto"
              valueLabelFormat={(value) => `${value}%`}
              sx={{ flex: 1 }}
            />
            <Typography variant="body2" sx={{ minWidth: 45, textAlign: 'right' }}>
              {volume}%
            </Typography>
          </Box>
        </Paper>

        {/* Sound Type Selection */}
        <Paper sx={{ p: 2, mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="subtitle1" fontWeight="bold">
              Sound for Each Action
            </Typography>
            <Button 
              size="small" 
              variant="outlined" 
              onClick={handleTestAll}
              disabled={!enabled}
              startIcon={<PlayIcon />}
            >
              Test All
            </Button>
          </Box>

          <Grid container spacing={2}>
            {actionTypes.map((action) => (
              <Grid item xs={12} key={action.key}>
                <Box 
                  sx={{ 
                    p: 1.5, 
                    bgcolor: 'background.default', 
                    borderRadius: 1,
                    border: '1px solid',
                    borderColor: 'divider'
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <Typography variant="body1">
                      {action.icon} <strong>{action.label}</strong>
                    </Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                    {action.description}
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <FormControl fullWidth size="small" disabled={!enabled}>
                      <Select
                        value={soundTypes[action.key]}
                        onChange={(e) => handleSoundTypeChange(action.key, e.target.value)}
                        sx={{ bgcolor: 'background.paper' }}
                      >
                        {availableSounds.map((sound) => (
                          <MenuItem key={sound.value} value={sound.value}>
                            <Box>
                              <Typography variant="body2">{sound.label}</Typography>
                              <Typography variant="caption" color="text.secondary">
                                {sound.description}
                              </Typography>
                            </Box>
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                    <IconButton
                      size="small"
                      onClick={() => handlePreviewSound(soundTypes[action.key])}
                      disabled={!enabled}
                      sx={{ 
                        bgcolor: 'primary.main', 
                        color: 'white',
                        '&:hover': { bgcolor: 'primary.dark' },
                        '&:disabled': { bgcolor: 'action.disabledBackground' }
                      }}
                    >
                      <PlayIcon fontSize="small" />
                    </IconButton>
                  </Box>
                </Box>
              </Grid>
            ))}
          </Grid>
        </Paper>

        {/* Available Sounds Preview */}
        <Paper sx={{ p: 2, bgcolor: 'info.dark', backgroundImage: 'none' }}>
          <Typography variant="caption" color="info.contrastText">
            💡 <strong>Tip:</strong> Click the play button next to each action to preview the sound.
            Includes {availableSounds.filter(s => s.category === 'Generated').length} generated sounds + {availableSounds.filter(s => s.category === 'System').length} macOS system sounds.
            All settings save automatically.
          </Typography>
        </Paper>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} variant="contained" color="primary">
          Done
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SoundSettingsPanel;
