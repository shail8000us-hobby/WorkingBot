/**
 * ClosePositionDialog Component
 *
 * ARCH-2: Extracted from OptionsPanel.js monolith.
 * Confirmation dialog for closing a position.
 *
 * Created: February 26, 2026 (ARCH-2 refactor)
 */

import React from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Typography,
    Box,
    Button,
    Alert,
} from '@mui/material';

const formatPnl = (pnl) => {
    const numPnl = Number(pnl) || 0;
    const formatted = Math.abs(numPnl).toFixed(4);
    return numPnl >= 0 ? `+$${formatted}` : `-$${formatted}`;
};

function ClosePositionDialog({ open, position, onClose, onConfirm }) {
    return (
        <Dialog
            open={open}
            onClose={onClose}
            disableRestoreFocus
        >
            <DialogTitle>Close Position</DialogTitle>
            <DialogContent>
                <Typography>
                    Are you sure you want to close your position in{' '}
                    <strong>{position?.product_symbol}</strong>?
                </Typography>
                <Box sx={{ mt: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                        Size: {position?.size}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        Current PnL: {formatPnl(position?.unrealized_pnl || 0)}
                    </Typography>
                </Box>
                {!position?.is_liquid && (
                    <Alert severity="warning" sx={{ mt: 2 }}>
                        Warning: This position has a wide spread (
                        {(Number(position?.spread_pct) || 0).toFixed(1)}%). You may get
                        unfavorable fill prices.
                    </Alert>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Cancel</Button>
                <Button onClick={onConfirm} color="error" variant="contained">
                    Close Position
                </Button>
            </DialogActions>
        </Dialog>
    );
}

export default React.memo(ClosePositionDialog);
