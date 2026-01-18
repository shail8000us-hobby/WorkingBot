/**
 * Bot Brain Analyzer - Main Component
 *
 * Single Responsibility: Orchestrate brain analysis sub-components.
 *
 * Auto-refreshes every 5 seconds - NO manual intervention needed.
 *
 * Sub-components:
 * - DecisionFlowGraph: Visual flowchart
 * - SequenceTimeline: Action sequences
 * - BrainModulesList: Discovered modules
 */

import React, { useState, useEffect } from 'react';
import { Box, Paper, Typography, Alert, CircularProgress, Tabs, Tab, Chip } from '@mui/material';
import DecisionFlowGraph from './DecisionFlowGraph';
import SequenceTimeline from './SequenceTimeline';
import BrainModulesList from './BrainModulesList';
import RealTimePredictions from './RealTimePredictions';
import ComprehensiveDashboard from './ComprehensiveDashboard';
import RobustSimulator from './RobustSimulator';
import InteractiveSimulator from './InteractiveSimulator';
import SimpleTradingSimulator from './SimpleTradingSimulator';

const BotBrainAnalyzer = () => {
  const [flowData, setFlowData] = useState(null);
  const [changes, setChanges] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState(0);

  const fetchBrainData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Call brain analyzer API (same port as main WebUI)
      const [flowResponse, changesResponse] = await Promise.all([
        fetch('/api/brain/flowchart'),
        fetch('/api/brain/changes'),
      ]);

      const flowData = await flowResponse.json();
      const changesData = await changesResponse.json();

      if (flowData.success) {
        setFlowData(flowData);
      } else {
        setError(flowData.error || 'Failed to load brain data');
      }

      if (changesData.success) {
        setChanges(changesData.changes);
      }
    } catch (err) {
      console.error('Error fetching brain data:', err);
      setError('Failed to connect to brain analyzer API');
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh every 5 seconds
  useEffect(() => {
    fetchBrainData();
    const interval = setInterval(fetchBrainData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
  };

  if (loading && !flowData) {
    return (
      <Paper
        sx={{
          p: 3,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '400px',
        }}
      >
        <CircularProgress />
        <Typography variant="h6" sx={{ ml: 2 }}>
          Reading Bot Brain...
        </Typography>
      </Paper>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        {error}
      </Alert>
    );
  }

  return (
    <Box sx={{ mt: 2 }}>
      <Paper elevation={2} sx={{ p: 3, borderRadius: '12px' }}>
        <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold', mb: 2 }}>
          🧠 Bot Brain Analyzer
        </Typography>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="body2" color="text.secondary">
            Real-time analysis of bot's decision-making logic • Auto-refreshes every 5 seconds
          </Typography>
          {changes && (changes.files_changed?.length > 0 || changes.new_files?.length > 0) && (
            <Chip
              label={`⚠️ ${changes.files_changed.length + changes.new_files.length} File(s) Changed`}
              color="warning"
              size="small"
              sx={{ fontWeight: 'bold' }}
            />
          )}
        </Box>

        <Tabs value={activeTab} onChange={handleTabChange} sx={{ mb: 3 }}>
          <Tab label="📊 Simple Trading Simulator" />
          <Tab label="🧠 Live Brain Monitor" />
          <Tab label="🎮 Interactive Simulator" />
          <Tab label="🚀 User-Friendly Simulator" />
          <Tab label="🔮 Real-Time Predictions" />
          <Tab label="📊 Decision Flow Graph" />
          <Tab label="📋 Action Sequences" />
          <Tab label="🧩 Brain Modules" />
        </Tabs>

        {activeTab === 0 && <SimpleTradingSimulator />}
        {activeTab === 1 && <ComprehensiveDashboard />}
        {activeTab === 2 && <RobustSimulator />}
        {activeTab === 3 && <InteractiveSimulator />}
        {activeTab === 4 && <RealTimePredictions />}
        {activeTab === 5 && <DecisionFlowGraph flowData={flowData} />}
        {activeTab === 6 && <SequenceTimeline flowData={flowData} />}
        {activeTab === 7 && <BrainModulesList flowData={flowData} />}
      </Paper>
    </Box>
  );
};

export default BotBrainAnalyzer;
