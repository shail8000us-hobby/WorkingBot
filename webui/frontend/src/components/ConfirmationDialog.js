import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  Box,
  Typography,
  Alert,
  Checkbox,
  FormControlLabel
} from '@mui/material';
import { Warning, Error as ErrorIcon, Info } from '@mui/icons-material';

/**
 * Reusable Confirmation Dialog Component
 * Provides consistent confirmation dialogs for critical actions
 */
const ConfirmationDialog = ({
  open,
  onClose,
  onConfirm,
  title,
  message,
  severity = 'warning', // 'warning', 'error', 'info'
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  requireConfirmation = false,
  confirmationText = '',
  loading = false,
  children
}) => {
  const [confirmed, setConfirmed] = useState(false);

  const handleConfirm = () => {
    if (requireConfirmation && !confirmed) {
      return;
    }
    onConfirm();
  };

  const handleClose = () => {
    setConfirmed(false);
    onClose();
  };

  const getIcon = () => {
    switch (severity) {
      case 'error':
        return <ErrorIcon sx={{ fontSize: 48, color: 'error.main' }} />;
      case 'warning':
        return <Warning sx={{ fontSize: 48, color: 'warning.main' }} />;
      case 'info':
      default:
        return <Info sx={{ fontSize: 48, color: 'info.main' }} />;
    }
  };

  const getColor = () => {
    switch (severity) {
      case 'error':
        return 'error';
      case 'warning':
        return 'warning';
      case 'info':
      default:
        return 'primary';
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderTop: '4px solid',
          borderColor: `${getColor()}.main`
        }
      }}
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {getIcon()}
          <Typography variant="h6">{title}</Typography>
        </Box>
      </DialogTitle>
      
      <DialogContent>
        <DialogContentText sx={{ mb: 2 }}>
          {message}
        </DialogContentText>

        {children}

        {requireConfirmation && (
          <Box sx={{ mt: 2 }}>
            <Alert severity={severity} sx={{ mb: 2 }}>
              This action requires confirmation
            </Alert>
            <FormControlLabel
              control={
                <Checkbox
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                  color={getColor()}
                />
              }
              label={confirmationText || "I understand the consequences of this action"}
            />
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ p: 2, pt: 0 }}>
        <Button 
          onClick={handleClose} 
          color="inherit"
          disabled={loading}
        >
          {cancelText}
        </Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          color={getColor()}
          disabled={loading || (requireConfirmation && !confirmed)}
          autoFocus
        >
          {loading ? 'Processing...' : confirmText}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ConfirmationDialog;
