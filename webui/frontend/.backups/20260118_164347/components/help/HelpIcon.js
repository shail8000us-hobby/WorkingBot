import React, { useState, useEffect } from 'react';
import {
  IconButton,
  Popover,
  Box,
  Typography,
  Divider,
  Chip,
  List,
  ListItem,
  ListItemText,
  Collapse,
  Alert,
  CircularProgress,
  Tooltip
} from '@mui/material';
import {
  HelpOutline,
  Warning,
  Info,
  Code,
  Settings,
  ExpandMore,
  ExpandLess,
  ErrorOutline
} from '@mui/icons-material';
import api from '../../utils/apiShim';

/**
 * HelpIcon Component
 * 
 * Universal help system that displays contextual help for any UI control.
 * Auto-fetches help metadata from the backend registry.
 * 
 * Usage:
 *   <HelpIcon actionId="bot.start" />
 *   <HelpIcon actionId="guardian.start" placement="bottom" />
 * 
 * Props:
 *   - actionId: The action identifier (e.g., "bot.start", "config.update")
 *   - placement: Popover placement (default: "right")
 *   - size: Icon size ("small", "medium", "large")
 *   - color: Icon color
 */
export default function HelpIcon({ 
  actionId, 
  placement = 'right',
  size = 'small',
  color = 'primary'
}) {
  const [anchorEl, setAnchorEl] = useState(null);
  const [helpData, setHelpData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedSections, setExpandedSections] = useState({
    effects: true,
    config: false,
    risks: false,
    code: false
  });

  const open = Boolean(anchorEl);

  // Fetch help data when popover opens
  useEffect(() => {
    if (open && !helpData && !loading) {
      fetchHelpData();
    }
  }, [open]);

  const fetchHelpData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await api.get('/api/help/registry');
      
      if (!response.data.success) {
        throw new Error(response.data.message || 'Failed to load help registry');
      }
      
      // Find the action in the registry
      const action = response.data.actions.find(a => a.action_id === actionId);
      
      if (!action) {
        setError(`No help documentation found for action: ${actionId}`);
        // Create inferred help data
        setHelpData({
          action_id: actionId,
          title: actionId.replace(/\./g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
          summary: '📝 Documentation missing for this action',
          effects: ['Action details not yet documented'],
          risks: [],
          related_config: [],
          api: {},
          code_refs: [],
          inferred: true
        });
      } else {
        setHelpData(action);
      }
    } catch (err) {
      console.error('Failed to fetch help data:', err);
      setError(err.message);
      // Create minimal fallback
      setHelpData({
        action_id: actionId,
        title: actionId.replace(/\./g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        summary: 'Help system unavailable',
        effects: ['Unable to load help documentation'],
        risks: [],
        related_config: [],
        inferred: true
      });
    } finally {
      setLoading(false);
    }
  };

  const handleClick = (event) => {
    event.stopPropagation();
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const isDangerous = () => {
    if (!helpData) return false;
    
    const dangerKeywords = ['delete', 'kill', 'emergency', 'force', 'destroy', 'live'];
    const actionLower = helpData.action_id.toLowerCase();
    
    return dangerKeywords.some(keyword => actionLower.includes(keyword)) ||
           (helpData.risks && helpData.risks.length > 0);
  };

  return (
    <>
      <Tooltip title={`Help: ${actionId}`} arrow>
        <IconButton
          size={size}
          color={color}
          onClick={handleClick}
          sx={{
            ml: 0.5,
            opacity: 0.7,
            '&:hover': { opacity: 1 }
          }}
          data-help-trigger={actionId}
        >
          <HelpOutline fontSize={size} />
        </IconButton>
      </Tooltip>

      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: placement.includes('bottom') ? 'bottom' : 'top',
          horizontal: placement.includes('left') ? 'left' : 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
        PaperProps={{
          sx: {
            maxWidth: 500,
            minWidth: 350,
            maxHeight: '80vh',
            overflow: 'auto'
          }
        }}
      >
        <Box sx={{ p: 2 }}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
              <CircularProgress size={24} />
            </Box>
          ) : helpData ? (
            <>
              {/* Header */}
              <Box sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  {isDangerous() && <Warning color="error" />}
                  <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                    {helpData.title}
                  </Typography>
                </Box>
                
                {helpData.inferred && (
                  <Chip
                    label="Auto-generated"
                    size="small"
                    color="warning"
                    icon={<Info />}
                    sx={{ mb: 1 }}
                  />
                )}
                
                <Typography variant="body2" color="text.secondary">
                  {helpData.summary}
                </Typography>
                
                {helpData.api && helpData.api.path && (
                  <Chip
                    label={`${helpData.api.method} ${helpData.api.path}`}
                    size="small"
                    variant="outlined"
                    sx={{ mt: 1 }}
                  />
                )}
              </Box>

              <Divider sx={{ my: 2 }} />

              {/* What it does */}
              {helpData.effects && helpData.effects.length > 0 && (
                <Box sx={{ mb: 2 }}>
                  <Box 
                    sx={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'space-between',
                      cursor: 'pointer',
                      mb: 1
                    }}
                    onClick={() => toggleSection('effects')}
                  >
                    <Typography variant="subtitle2" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Info fontSize="small" color="primary" />
                      What it does
                    </Typography>
                    {expandedSections.effects ? <ExpandLess /> : <ExpandMore />}
                  </Box>
                  
                  <Collapse in={expandedSections.effects}>
                    <List dense>
                      {helpData.effects.slice(0, 5).map((effect, idx) => (
                        <ListItem key={idx} sx={{ pl: 0 }}>
                          <ListItemText 
                            primary={`• ${effect}`}
                            primaryTypographyProps={{ variant: 'body2' }}
                          />
                        </ListItem>
                      ))}
                    </List>
                  </Collapse>
                </Box>
              )}

              {/* Related Configuration */}
              {helpData.related_config && helpData.related_config.length > 0 && (
                <Box sx={{ mb: 2 }}>
                  <Box 
                    sx={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'space-between',
                      cursor: 'pointer',
                      mb: 1
                    }}
                    onClick={() => toggleSection('config')}
                  >
                    <Typography variant="subtitle2" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Settings fontSize="small" color="action" />
                      Related Config ({helpData.related_config.length})
                    </Typography>
                    {expandedSections.config ? <ExpandLess /> : <ExpandMore />}
                  </Box>
                  
                  <Collapse in={expandedSections.config}>
                    <List dense>
                      {helpData.related_config.map((config, idx) => (
                        <ListItem key={idx} sx={{ pl: 0, flexDirection: 'column', alignItems: 'flex-start' }}>
                          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 'bold' }}>
                            {config.key}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            = {config.value}
                          </Typography>
                        </ListItem>
                      ))}
                    </List>
                  </Collapse>
                </Box>
              )}

              {/* Risks & Warnings */}
              {helpData.risks && helpData.risks.length > 0 && (
                <Box sx={{ mb: 2 }}>
                  <Box 
                    sx={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'space-between',
                      cursor: 'pointer',
                      mb: 1
                    }}
                    onClick={() => toggleSection('risks')}
                  >
                    <Typography variant="subtitle2" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Warning fontSize="small" color="error" />
                      Risks & Warnings
                    </Typography>
                    {expandedSections.risks ? <ExpandLess /> : <ExpandMore />}
                  </Box>
                  
                  <Collapse in={expandedSections.risks}>
                    {helpData.risks.map((risk, idx) => (
                      <Alert key={idx} severity="warning" sx={{ mb: 1 }} icon={<ErrorOutline />}>
                        <Typography variant="body2">{risk}</Typography>
                      </Alert>
                    ))}
                  </Collapse>
                </Box>
              )}

              {/* Code References */}
              {helpData.code_refs && helpData.code_refs.length > 0 && (
                <Box sx={{ mb: 1 }}>
                  <Box 
                    sx={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'space-between',
                      cursor: 'pointer',
                      mb: 1
                    }}
                    onClick={() => toggleSection('code')}
                  >
                    <Typography variant="subtitle2" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Code fontSize="small" />
                      Code References
                    </Typography>
                    {expandedSections.code ? <ExpandLess /> : <ExpandMore />}
                  </Box>
                  
                  <Collapse in={expandedSections.code}>
                    <List dense>
                      {helpData.code_refs.map((ref, idx) => (
                        <ListItem key={idx} sx={{ pl: 0 }}>
                          <ListItemText 
                            primary={ref}
                            primaryTypographyProps={{ 
                              variant: 'caption', 
                              sx: { fontFamily: 'monospace', fontSize: '0.7rem' }
                            }}
                          />
                        </ListItem>
                      ))}
                    </List>
                  </Collapse>
                </Box>
              )}

              {/* Last Updated */}
              {helpData.last_updated && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2, fontStyle: 'italic' }}>
                  Last updated: {new Date(helpData.last_updated).toLocaleString()}
                </Typography>
              )}

              {/* Error Message */}
              {error && !helpData.inferred && (
                <Alert severity="warning" sx={{ mt: 2 }}>
                  {error}
                </Alert>
              )}
            </>
          ) : (
            <Alert severity="error">
              Failed to load help information
            </Alert>
          )}
        </Box>
      </Popover>
    </>
  );
}
