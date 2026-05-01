import React, { useEffect, useState } from 'react';
import { Snackbar, Alert, Typography, Box } from '@mui/material';
import { io } from 'socket.io-client';

const ShailendraToast = () => {
    const [open, setOpen] = useState(false);
    const [signal, setSignal] = useState(null);

    useEffect(() => {
        // Connect to Socket.IO running on 5555
        const origin = window.location.origin.includes('3000') 
            ? 'http://localhost:5555' 
            : window.location.origin;
            
        const socket = io(origin, {
            transports: ['polling'],
            upgrade: false,
            rememberUpgrade: false,
        });

        socket.on('shailendra_signal', (data) => {
            console.log("🔥 Shailendra Signal Received:", data);
            setSignal(data);
            setOpen(true);
        });

        return () => {
            socket.disconnect();
        };
    }, []);

    const handleClose = (event, reason) => {
        if (reason === 'clickaway') return;
        setOpen(false);
    };

    if (!signal) return null;

    // Define severity based on risk_level
    const severity = signal.risk_level === 'CRITICAL' ? 'error' 
                   : signal.risk_level === 'HIGH' ? 'warning' 
                   : 'info';

    return (
        <Snackbar 
            open={open} 
            autoHideDuration={15000} // Auto dismiss after 15 seconds
            onClose={handleClose}
            anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            sx={{ mt: 7, zIndex: 9999 }} // Ensures it sits over dashboards
        >
            <Alert 
                onClose={handleClose} 
                severity={severity}
                variant="filled"
                sx={{ 
                    width: '100%', 
                    boxShadow: 6,
                    fontSize: '1.1rem',
                    border: '1px solid rgba(255,255,255,0.2)',
                    display: 'flex',
                    alignItems: 'center'
                }}
            >
                <Box>
                    <Typography variant="subtitle2" sx={{ fontWeight: 'bold', letterSpacing: 1, textTransform: 'uppercase', opacity: 0.9 }}>
                        🧠 SECRETS OF SHAILENDRA
                    </Typography>
                    <Typography variant="body1" sx={{ fontWeight: 'bold', mt: 0.5 }}>
                        {signal.action}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 0.3, opacity: 0.9 }}>
                        {signal.description}
                    </Typography>
                </Box>
            </Alert>
        </Snackbar>
    );
};

export default ShailendraToast;
