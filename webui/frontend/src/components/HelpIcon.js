import React, { useState } from 'react';
import {
  IconButton,
  Popover,
  Box,
  Typography,
  Divider,
  useTheme,
  useMediaQuery,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
} from '@mui/material';
import { HelpOutline, Warning, CheckCircle, Info } from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
import helpContent from '../helpContent.json';

/**
 * HelpIcon Component
 *
 * Displays a ? icon next to any control. When clicked, shows a helpful popover/dialog
 * with detailed explanation of what the setting does, its impact, warnings, etc.
 *
 * @param {string} configKey - The configuration key (e.g., 'GUARDIAN_ENABLED')
 * @param {string} size - Icon size: 'small', 'medium', 'large'
 */
function HelpIcon({ configKey, size = 'small' }) {
  const [anchorEl, setAnchorEl] = useState(null);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const helpData = helpContent[configKey];

  // If no help content defined, don't show icon
  if (!helpData) {
    return null;
  }

  const handleClick = (event) => {
    event.stopPropagation();
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const open = Boolean(anchorEl);

  // Mobile: Use Dialog (modal)
  if (isMobile) {
    return (
      <>
        <IconButton
          size={size}
          onClick={handleClick}
          sx={{
            padding: '2px',
            marginLeft: '4px',
            color: 'primary.main',
            opacity: 0.7,
            '&:hover': {
              opacity: 1,
              backgroundColor: 'rgba(0, 230, 118, 0.1)',
            },
          }}
        >
          <HelpOutline fontSize={size} />
        </IconButton>

        <Dialog
          open={open}
          onClose={handleClose}
          maxWidth="sm"
          fullWidth
          PaperProps={{
            sx: {
              bgcolor: 'background.paper',
              backgroundImage:
                'linear-gradient(rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.05))',
            },
          }}
        >
          <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1, pb: 1 }}>
            <Info color="primary" />
            {helpData.title}
          </DialogTitle>
          <DialogContent>
            <Box sx={{ py: 1 }}>
              <Typography variant="body2" color="text.secondary" paragraph>
                {helpData.description}
              </Typography>

              <Divider sx={{ my: 2 }} />

              <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
                📋 What It Does:
              </Typography>
              <Typography variant="body2" paragraph>
                <ReactMarkdown>{helpData.whatItDoes}</ReactMarkdown>
              </Typography>

              {helpData.impact && (
                <>
                  <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
                    ⚡ Impact:
                  </Typography>
                  <Typography variant="body2" paragraph>
                    <ReactMarkdown>{helpData.impact}</ReactMarkdown>
                  </Typography>
                </>
              )}

              {helpData.warnings && (
                <Box sx={{ bgcolor: 'rgba(255, 152, 0, 0.1)', p: 2, borderRadius: 1, mb: 2 }}>
                  <Typography
                    variant="subtitle2"
                    sx={{
                      fontWeight: 'bold',
                      mb: 1,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      color: 'warning.main',
                    }}
                  >
                    <Warning /> Warnings:
                  </Typography>
                  <Typography variant="body2" color="warning.light">
                    <ReactMarkdown>{helpData.warnings}</ReactMarkdown>
                  </Typography>
                </Box>
              )}

              {helpData.dependencies && (
                <>
                  <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
                    🔗 Dependencies:
                  </Typography>
                  <Typography variant="body2" paragraph>
                    {helpData.dependencies}
                  </Typography>
                </>
              )}

              {helpData.recommended && (
                <Box sx={{ bgcolor: 'rgba(0, 230, 118, 0.1)', p: 2, borderRadius: 1 }}>
                  <Typography
                    variant="subtitle2"
                    sx={{
                      fontWeight: 'bold',
                      mb: 1,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      color: 'success.main',
                    }}
                  >
                    <CheckCircle /> Recommended:
                  </Typography>
                  <Typography variant="body2" color="success.light">
                    {helpData.recommended}
                  </Typography>
                </Box>
              )}
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleClose} variant="contained" autoFocus>
              Got It
            </Button>
          </DialogActions>
        </Dialog>
      </>
    );
  }

  // Desktop: Use Popover (tooltip-style)
  return (
    <>
      <IconButton
        size={size}
        onClick={handleClick}
        sx={{
          padding: '2px',
          marginLeft: '4px',
          color: 'primary.main',
          opacity: 0.7,
          '&:hover': {
            opacity: 1,
            backgroundColor: 'rgba(0, 230, 118, 0.1)',
          },
        }}
      >
        <HelpOutline fontSize={size} />
      </IconButton>

      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
        PaperProps={{
          sx: {
            maxWidth: 450,
            bgcolor: 'background.paper',
            backgroundImage:
              'linear-gradient(rgba(255, 255, 255, 0.09), rgba(255, 255, 255, 0.09))',
            border: '1px solid',
            borderColor: 'primary.main',
            borderRadius: 2,
            boxShadow: '0 8px 32px rgba(0, 230, 118, 0.15)',
          },
        }}
        elevation={8}
      >
        <Box sx={{ p: 2.5 }}>
          {/* Title */}
          <Typography
            variant="h6"
            sx={{ fontWeight: 'bold', mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}
          >
            <Info color="primary" fontSize="small" />
            {helpData.title}
          </Typography>

          <Typography variant="body2" color="text.secondary" paragraph>
            {helpData.description}
          </Typography>

          <Divider sx={{ my: 1.5 }} />

          {/* What It Does */}
          <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 0.5, fontSize: '0.85rem' }}>
            📋 What It Does:
          </Typography>
          <Typography variant="body2" sx={{ mb: 1.5, fontSize: '0.8rem' }}>
            <ReactMarkdown>{helpData.whatItDoes}</ReactMarkdown>
          </Typography>

          {/* Impact */}
          {helpData.impact && (
            <>
              <Typography
                variant="subtitle2"
                sx={{ fontWeight: 'bold', mb: 0.5, fontSize: '0.85rem' }}
              >
                ⚡ Impact:
              </Typography>
              <Typography variant="body2" sx={{ mb: 1.5, fontSize: '0.8rem' }}>
                <ReactMarkdown>{helpData.impact}</ReactMarkdown>
              </Typography>
            </>
          )}

          {/* Warnings */}
          {helpData.warnings && (
            <Box
              sx={{
                bgcolor: 'rgba(255, 152, 0, 0.1)',
                p: 1.5,
                borderRadius: 1,
                mb: 1.5,
                border: '1px solid rgba(255, 152, 0, 0.3)',
              }}
            >
              <Typography
                variant="subtitle2"
                sx={{
                  fontWeight: 'bold',
                  mb: 0.5,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  color: 'warning.main',
                  fontSize: '0.85rem',
                }}
              >
                <Warning fontSize="small" /> Warnings:
              </Typography>
              <Typography variant="body2" color="warning.light" sx={{ fontSize: '0.75rem' }}>
                <ReactMarkdown>{helpData.warnings}</ReactMarkdown>
              </Typography>
            </Box>
          )}

          {/* Dependencies */}
          {helpData.dependencies && (
            <>
              <Typography
                variant="subtitle2"
                sx={{ fontWeight: 'bold', mb: 0.5, fontSize: '0.85rem' }}
              >
                🔗 Dependencies:
              </Typography>
              <Typography variant="body2" sx={{ mb: 1.5, fontSize: '0.8rem' }}>
                {helpData.dependencies}
              </Typography>
            </>
          )}

          {/* Recommended */}
          {helpData.recommended && (
            <Box
              sx={{
                bgcolor: 'rgba(0, 230, 118, 0.1)',
                p: 1.5,
                borderRadius: 1,
                border: '1px solid rgba(0, 230, 118, 0.3)',
              }}
            >
              <Typography
                variant="subtitle2"
                sx={{
                  fontWeight: 'bold',
                  mb: 0.5,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  color: 'success.main',
                  fontSize: '0.85rem',
                }}
              >
                <CheckCircle fontSize="small" /> Recommended:
              </Typography>
              <Typography variant="body2" color="success.light" sx={{ fontSize: '0.75rem' }}>
                {helpData.recommended}
              </Typography>
            </Box>
          )}
        </Box>
      </Popover>
    </>
  );
}

export default HelpIcon;
