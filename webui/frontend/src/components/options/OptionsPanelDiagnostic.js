/**
 * DIAGNOSTIC VERSION - Find exact source of Invariant error
 */
import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  CircularProgress,
  Alert,
} from '@mui/material';
import api from '../../utils/apiShim';

const OptionsPanelDiagnostic = () => {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [diagnosticStep, setDiagnosticStep] = useState('Starting...');

  useEffect(() => {
    const fetchData = async () => {
      try {
        setDiagnosticStep('Fetching positions from API...');
        const { data } = await api.get('/api/options/positions');
        
        setDiagnosticStep('API call successful');
        
        if (data?.success) {
          const rawPositions = data.positions || [];
          setDiagnosticStep(`Received ${rawPositions.length} positions`);
          
          // Check for duplicates
          const symbols = rawPositions.map(p => p.product_symbol);
          const duplicates = symbols.filter((item, index) => symbols.indexOf(item) !== index);
          if (duplicates.length > 0) {
            setError(`Found duplicate symbols: ${duplicates.join(', ')}`);
          }
          
          setPositions(rawPositions);
          setDiagnosticStep('Data loaded successfully');
        } else {
          setError(data?.error || 'Failed to fetch positions');
        }
      } catch (err) {
        setError(`API Error: ${err.message}`);
        setDiagnosticStep('Error occurred');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <CircularProgress />
        <Typography sx={{ mt: 2 }}>{diagnosticStep}</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="h5" sx={{ mb: 2 }}>
        🔍 Options Panel Diagnostic Mode
      </Typography>
      
      <Alert severity="info" sx={{ mb: 2 }}>
        <strong>Diagnostic Step:</strong> {diagnosticStep}
      </Alert>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Paper sx={{ mb: 2, p: 2 }}>
        <Typography variant="subtitle1">Data Status:</Typography>
        <Typography>Total Positions: {positions.length}</Typography>
        <Typography>Unique Symbols: {new Set(positions.map(p => p.product_symbol)).size}</Typography>
        <Typography>Has Duplicates: {positions.length !== new Set(positions.map(p => p.product_symbol)).size ? 'YES ⚠️' : 'NO ✅'}</Typography>
      </Paper>

      {/* MINIMAL TABLE - NO DND, NO TOOLTIPS, NO COMPLEX COMPONENTS */}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Symbol</TableCell>
              <TableCell align="right">Size</TableCell>
              <TableCell align="right">Entry Price</TableCell>
              <TableCell align="right">Mark Price</TableCell>
              <TableCell align="right">PnL</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {positions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  No positions found
                </TableCell>
              </TableRow>
            ) : (
              positions.map((pos, index) => (
                <TableRow key={pos.product_symbol || `pos-${index}`}>
                  <TableCell>{pos.product_symbol || 'N/A'}</TableCell>
                  <TableCell align="right">{pos.size || 0}</TableCell>
                  <TableCell align="right">{pos.entry_price?.toFixed(4) || 'N/A'}</TableCell>
                  <TableCell align="right">{pos.mark_price?.toFixed(4) || 'N/A'}</TableCell>
                  <TableCell align="right">{pos.unrealized_pnl?.toFixed(2) || '0.00'}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Alert severity="success" sx={{ mt: 2 }}>
        ✅ If you see this message without errors, the basic table works fine.
        The issue is in the advanced features (DnD, Tooltips, or complex components).
      </Alert>
    </Box>
  );
};

export default OptionsPanelDiagnostic;
