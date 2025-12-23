/**
 * Sequence Timeline Component
 * 
 * Single Responsibility: Display DYNAMIC action sequences from bot state.
 * 
 * Shows the 3 scenarios (safe, unsafe, recovery) with REAL-TIME sequences.
 * Auto-refreshes every 5 seconds - fetches live data!
 */

import React, { useState, useEffect } from 'react';
import { Box, Typography, Paper, Chip, CircularProgress, Alert, Accordion, AccordionSummary, AccordionDetails } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

const SequenceTimeline = ({ flowData }) => {
  const [sequences, setSequences] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchSequences = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch('/api/brain/sequences');
      const data = await response.json();
      
      if (data.success) {
        setSequences(data);
      } else {
        setError(data.error || 'Failed to load sequences');
      }
    } catch (err) {
      console.error('Error fetching sequences:', err);
      setError('Failed to connect to brain analyzer API');
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh every 5 seconds
  useEffect(() => {
    fetchSequences();
    const interval = setInterval(fetchSequences, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !sequences) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
        <CircularProgress />
        <Typography variant="body1" sx={{ ml: 2 }}>
          Loading action sequences...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error">
        {error}
      </Alert>
    );
  }

  const scenarioData = sequences?.sequences || {};
  const safeScenario = scenarioData.scenario_1_safe || {};
  const unsafeScenario = scenarioData.scenario_2_unsafe || {};
  const recoveryScenario = scenarioData.scenario_3_recovery || {};

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
        <Chip label="🔄 Auto-refresh: 5s" color="success" size="small" />
        {sequences?.bot_state && (
          <Chip label={`Current Price: ₹${sequences.bot_state.current_price || 'N/A'}`} color="info" size="small" />
        )}
      </Box>

      {/* Scenario 1: Safe */}
      <Accordion defaultExpanded sx={{ mb: 2 }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
            {safeScenario.title || '✅ SCENARIO 1: IF VOLATILITY SAFE'}
          </Typography>
        </AccordionSummary>
        <AccordionDetails>
          {safeScenario.sequence && safeScenario.sequence.length > 0 ? (
            <Box>
              {safeScenario.sequence.map((action, idx) => {
                const actionType = action.action_type || `Step ${idx + 1}`;
                const description = action.description || (typeof action === 'string' ? action : JSON.stringify(action));
                const price = action.price;
                
                return (
                  <Paper key={idx} sx={{ p: 2, mb: 1, bgcolor: '#1a1a1a', borderLeft: '4px solid #4caf50' }}>
                    <Typography variant="body2" sx={{ fontWeight: 'bold', color: '#4caf50' }}>
                      {actionType}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {description}
                    </Typography>
                    {price && (
                      <Chip label={`₹${price}`} size="small" sx={{ mt: 1 }} />
                    )}
                  </Paper>
                );
              })}
            </Box>
          ) : (
            <Typography color="text.secondary">No sequence data available. Bot may be idle.</Typography>
          )}
        </AccordionDetails>
      </Accordion>

      {/* Scenario 2: Unsafe */}
      <Accordion sx={{ mb: 2 }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
            {unsafeScenario.title || '🛑 SCENARIO 2: IF VOLATILITY UNSAFE'}
          </Typography>
        </AccordionSummary>
        <AccordionDetails>
          {unsafeScenario.sequence && unsafeScenario.sequence.length > 0 ? (
            <Box>
              {unsafeScenario.sequence.map((action, idx) => {
                const actionType = action.action_type || `Step ${idx + 1}`;
                const description = action.description || (typeof action === 'string' ? action : JSON.stringify(action));
                
                return (
                  <Paper key={idx} sx={{ p: 2, mb: 1, bgcolor: '#1a1a1a', borderLeft: '4px solid #f44336' }}>
                    <Typography variant="body2" sx={{ fontWeight: 'bold', color: '#f44336' }}>
                      {actionType}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {description}
                    </Typography>
                  </Paper>
                );
              })}
            </Box>
          ) : (
            <Typography color="text.secondary">No sequence data available.</Typography>
          )}
        </AccordionDetails>
      </Accordion>

      {/* Scenario 3: Recovery */}
      <Accordion sx={{ mb: 2 }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
            {recoveryScenario.title || '💰 SCENARIO 3: IF GRIDS MISSED + RECOVERY'}
          </Typography>
        </AccordionSummary>
        <AccordionDetails>
          {recoveryScenario.sequence && recoveryScenario.sequence.length > 0 ? (
            <Box>
              {recoveryScenario.sequence.map((action, idx) => {
                const actionType = action.action_type || `Step ${idx + 1}`;
                const description = action.description || (typeof action === 'string' ? action : JSON.stringify(action));
                const price = action.price;
                
                return (
                  <Paper key={idx} sx={{ p: 2, mb: 1, bgcolor: '#1a1a1a', borderLeft: '4px solid #ff9800' }}>
                    <Typography variant="body2" sx={{ fontWeight: 'bold', color: '#ff9800' }}>
                      {actionType}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {description}
                    </Typography>
                    {price && (
                      <Chip label={`₹${price}`} size="small" sx={{ mt: 1 }} />
                    )}
                  </Paper>
                );
              })}
            </Box>
          ) : (
            <Typography color="text.secondary">No sequence data available.</Typography>
          )}
        </AccordionDetails>
      </Accordion>
    </Box>
  );
};

export default SequenceTimeline;

