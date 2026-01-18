/**
 * Decision Flow Graph - SIMPLEST POSSIBLE VERSION
 * Pure JSX, no custom components, no recursion
 */

import React from 'react';
import { Box, Typography, Paper, Chip } from '@mui/material';

const DecisionFlowGraph = ({ flowData }) => {
  if (!flowData || !flowData.graph) {
    return <Typography>Loading...</Typography>;
  }

  const nodes = flowData.graph.nodes || [];
  const edges = flowData.graph.edges || [];
  const botState = flowData.bot_state || {};

  // Helper to find node
  const findNode = (id) => nodes.find((n) => n.id === id);

  return (
    <Box>
      {/* Stats */}
      <Box sx={{ display: 'flex', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
        <Chip label={`${nodes.length} Nodes`} size="small" />
        <Chip label={`${edges.length} Edges`} size="small" />
        {botState.volatility && botState.volatility.current_iv !== undefined && (
          <Chip
            label={`IV: ${botState.volatility.current_iv.toFixed(1)}% | RV: ${botState.volatility.current_rv.toFixed(1)}%`}
            sx={{ bgcolor: botState.volatility.is_safe ? '#4caf50' : '#f44336', color: '#fff' }}
            size="small"
          />
        )}
      </Box>

      {/* Flowchart */}
      <Paper sx={{ p: 2, bgcolor: '#0a0a0a', maxHeight: '75vh', overflow: 'auto' }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
          {/* Manually render each node to avoid recursion errors */}
          {nodes.map((node, idx) => {
            const label = node.data && node.data.label ? String(node.data.label) : 'No label';
            const type = node.type || 'unknown';
            const color =
              type === 'start'
                ? '#4caf50'
                : type === 'decision'
                  ? '#ff9800'
                  : type === 'action'
                    ? '#00bcd4'
                    : type === 'waiting'
                      ? '#ffeb3b'
                      : '#9c27b0';

            return (
              <Box key={idx} sx={{ width: '100%', maxWidth: 600, mb: 0.5 }}>
                <Paper
                  sx={{
                    p: 1,
                    bgcolor: color + '20',
                    border: `2px solid ${color}`,
                    borderRadius: '6px',
                    textAlign: 'center',
                  }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 1,
                      mb: 0.5,
                    }}
                  >
                    <Chip
                      label={type.toUpperCase()}
                      size="small"
                      sx={{ bgcolor: color, color: '#000', fontSize: '0.55rem', height: 18 }}
                    />
                    {node.realtime_data && (
                      <Chip
                        label="LIVE"
                        size="small"
                        sx={{ bgcolor: '#4caf50', color: '#fff', fontSize: '0.5rem', height: 16 }}
                      />
                    )}
                  </Box>

                  <Typography
                    sx={{
                      color: '#fff',
                      fontSize: '0.7rem',
                      lineHeight: 1.3,
                      whiteSpace: 'pre-line',
                    }}
                  >
                    {label}
                  </Typography>
                </Paper>

                {idx < nodes.length - 1 && (
                  <Typography
                    sx={{ color: '#90caf9', fontSize: '1rem', textAlign: 'center', my: 0.3 }}
                  >
                    ↓
                  </Typography>
                )}
              </Box>
            );
          })}
        </Box>

        {/* Legend */}
        <Box
          sx={{
            mt: 3,
            pt: 2,
            borderTop: '1px solid rgba(144, 202, 249, 0.2)',
            textAlign: 'center',
          }}
        >
          <Box sx={{ display: 'flex', gap: 1.5, justifyContent: 'center', flexWrap: 'wrap' }}>
            <Chip
              label="🟢 START"
              size="small"
              sx={{ bgcolor: '#2e7d32', color: '#fff', fontSize: '0.6rem', height: 20 }}
            />
            <Chip
              label="🟠 DECISION"
              size="small"
              sx={{ bgcolor: '#e65100', color: '#fff', fontSize: '0.6rem', height: 20 }}
            />
            <Chip
              label="🔵 ACTION"
              size="small"
              sx={{ bgcolor: '#006064', color: '#fff', fontSize: '0.6rem', height: 20 }}
            />
            <Chip
              label="🟡 WAITING"
              size="small"
              sx={{ bgcolor: '#424242', color: '#fff', fontSize: '0.6rem', height: 20 }}
            />
          </Box>
        </Box>
      </Paper>
    </Box>
  );
};

export default DecisionFlowGraph;
