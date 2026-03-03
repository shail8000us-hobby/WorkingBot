/**
 * SSR Algo Dashboard V2
 * 
 * Professional cryptocurrency options trading dashboard with:
 * - Dark theme with gradient background (slate-950 to slate-900)
 * - Single-column, full-width layout with max-width of 1600px
 * - All sections stacked vertically with consistent spacing
 * 
 * Components (Top to Bottom):
 * 1. Max Loss Alert Banner
 * 2. SSR Algo Configuration
 * 3. Position Legs
 * 4. Payoff Diagram
 * 5. Order History Tabs
 * 
 * Part of SSR Algo V2 Dashboard
 * Created: February 3, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Butterfly } from 'lucide-react';
import MaxLossAlertBanner from './MaxLossAlertBanner';
import SSRAlgoConfigV2 from './SSRAlgoConfigV2';
import PositionLegsTableV2 from './PositionLegsTableV2';
import PayoffDiagramV2 from './PayoffDiagramV2';
import OrderHistoryTabs from './OrderHistoryTabs';
import ssrAlgoService from '../ssrAlgoService';

// Calculate total legs from session positions
const calculateTotalLegs = (session) => {
  if (!session?.positions?.length) return 0;
  // Each position group has 6 legs (ATM CE, ATM PE, OTM CE Buy, OTM PE Buy, Far OTM CE, Far OTM PE)
  // Multiplied by rounds_executed for that group
  return session.positions.reduce((total, posGroup) => {
    const roundsExecuted = posGroup.rounds_executed || 1;
    return total + (6 * roundsExecuted);
  }, 0);
};

const SSRAlgoDashboardV2 = () => {
  // State
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedSession, setSelectedSession] = useState(null);
  const [selectedPayoff, setSelectedPayoff] = useState(null);
  const [selectedMonitorStatus, setSelectedMonitorStatus] = useState(null);
  const [healthStatus, setHealthStatus] = useState(null);
  
  // Fetch sessions
  const fetchSessions = useCallback(async () => {
    try {
      const result = await ssrAlgoService.getSessions(false);
      if (result.success) {
        setSessions(result.sessions || []);
      } else {
        setError(result.error);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Health check
  const checkHealth = useCallback(async () => {
    try {
      const result = await ssrAlgoService.healthCheck();
      setHealthStatus(result.success ? 'healthy' : 'error');
    } catch (err) {
      setHealthStatus('error');
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchSessions();
    checkHealth();
    
    // Auto-refresh every 10 seconds
    const interval = setInterval(() => {
      fetchSessions();
    }, 10000);
    
    return () => clearInterval(interval);
  }, [fetchSessions, checkHealth]);

  // Auto-select session for display - prioritize MONITORING
  useEffect(() => {
    if (sessions.length === 0) return;
    if (selectedSession) return; // Don't override manual selection
    
    const monitoringSession = sessions.find(s => s.status === 'MONITORING');
    const activeSession = sessions.find(s => 
      ['IDLE', 'SELECTING_STRIKES', 'EXECUTING_AUTO_LOOP', 'MONITORING', 'PAUSED'].includes(s.status)
    );
    const mostRecentSession = sessions[0];
    
    const sessionToSelect = monitoringSession || activeSession || mostRecentSession;
    if (sessionToSelect) {
      handleSelectSession(sessionToSelect);
    }
  }, [sessions, selectedSession]);

  // Auto-refresh payoff for selected session
  useEffect(() => {
    if (!selectedSession || selectedSession.status !== 'MONITORING') return;
    
    const payoffInterval = setInterval(async () => {
      try {
        const result = await ssrAlgoService.getSessionPayoff(selectedSession.session_id);
        if (result.success) {
          setSelectedPayoff(result);
        }
      } catch (err) {
        console.error('Failed to refresh payoff:', err);
      }
    }, 30000);
    
    return () => clearInterval(payoffInterval);
  }, [selectedSession]);

  // Auto-refresh monitor status every 5 seconds
  useEffect(() => {
    if (!selectedSession) return;
    
    const monitorInterval = setInterval(async () => {
      try {
        const result = await ssrAlgoService.getMonitorStatus(selectedSession.session_id);
        if (result.success) {
          setSelectedMonitorStatus(result.monitor);
        }
      } catch (err) {
        // Silent fail
      }
    }, 5000);
    
    return () => clearInterval(monitorInterval);
  }, [selectedSession]);

  // Filter sessions
  const activeSessions = sessions.filter(s => 
    ['IDLE', 'SELECTING_STRIKES', 'EXECUTING_AUTO_LOOP', 'MONITORING', 'PAUSED'].includes(s.status)
  );
  const historicalSessions = sessions.filter(s => s.status === 'STOPPED');

  // Handlers
  const handleSessionCreated = (session) => {
    setSessions(prev => [session, ...prev]);
    handleSelectSession(session);
  };

  const handleSelectSession = async (session) => {
    setSelectedSession(session);
    try {
      const payoffResult = await ssrAlgoService.getSessionPayoff(session.session_id);
      if (payoffResult.success) {
        setSelectedPayoff(payoffResult);
      }
      const monitorResult = await ssrAlgoService.getMonitorStatus(session.session_id);
      if (monitorResult.success) {
        setSelectedMonitorStatus(monitorResult.monitor);
      }
    } catch (err) {
      console.error('Failed to fetch session data:', err);
    }
  };

  const handleClearHistory = async () => {
    if (historicalSessions.length === 0) return;
    
    for (const session of historicalSessions) {
      try {
        await ssrAlgoService.deleteSession(session.session_id);
      } catch (err) {
        console.error('Failed to delete session:', session.session_id, err);
      }
    }
    fetchSessions();
  };

  // Calculate banner props from monitor status
  const getBannerProps = () => {
    const dwellStatus = selectedMonitorStatus?.dwell_status || {};
    const inMaxLossZone = dwellStatus.current_zone !== null;
    
    // Calculate active time
    let activeTime = null;
    if (selectedSession?.started_at) {
      const start = new Date(selectedSession.started_at);
      const now = new Date();
      const mins = Math.floor((now - start) / 60000);
      if (mins < 60) {
        activeTime = `${mins}m`;
      } else {
        activeTime = `${Math.floor(mins / 60)}h ${mins % 60}m`;
      }
    }

    return {
      underlying: selectedSession?.underlying || 'BTC',
      currentPrice: selectedMonitorStatus?.last_price || selectedPayoff?.spot_price || 0,
      atmStrike: selectedPayoff?.atm_strike || selectedSession?.positions?.[0]?.atm_strike || 0,
      triggerZones: {
        upper: selectedPayoff?.max_loss_points?.upper_trigger || 0,
        lower: selectedPayoff?.max_loss_points?.lower_trigger || 0,
      },
      currentRound: selectedSession?.rounds_completed || 0,
      totalRounds: selectedSession?.config?.auto_loop_rounds || selectedSession?.auto_loop_rounds || 2,
      openLegs: calculateTotalLegs(selectedSession),
      activeTime,
      inMaxLossZone,
      zoneTimeMinutes: dwellStatus.time_in_zone_minutes || 0,
      triggerThresholdMinutes: dwellStatus.dwell_threshold_minutes || 10,
      zoneSide: dwellStatus.current_zone,
    };
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 to-slate-900">
      <div className="w-full px-4 py-4 space-y-6">
        
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-3xl">🦋</span>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-purple-400 bg-clip-text text-transparent">
              SSR ALGO
            </h1>
            <span className={`
              px-2 py-0.5 rounded-lg text-xs font-medium
              ${healthStatus === 'healthy' 
                ? 'bg-green-500/20 text-green-400' 
                : 'bg-red-500/20 text-red-400'
              }
            `}>
              {healthStatus === 'healthy' ? '● Connected' : '○ Disconnected'}
            </span>
          </div>
          <p className="text-sm text-slate-500">
            Automated Modified Iron Butterfly with Protective Wings
          </p>
        </div>

        {/* 1. Max Loss Alert Banner - Show when session selected */}
        {selectedSession && (
          <MaxLossAlertBanner {...getBannerProps()} />
        )}

        {/* 2. SSR Algo Configuration */}
        <SSRAlgoConfigV2 
          onSessionCreated={handleSessionCreated}
        />

        {/* 3. Position Legs - Show when session has positions */}
        {selectedSession && selectedSession.positions?.length > 0 && (
          <PositionLegsTableV2 
            positions={selectedSession.positions}
            totalLegs={calculateTotalLegs(selectedSession)}
          />
        )}

        {/* 4. Payoff Diagram */}
        <PayoffDiagramV2
          payoffCurve={selectedPayoff?.payoff_curve || []}
          spotPrice={selectedPayoff?.spot_price || 0}
          currentPrice={selectedMonitorStatus?.last_price || selectedPayoff?.spot_price || 0}
          maxLossPoints={selectedPayoff?.max_loss_points || {}}
          breakevens={selectedPayoff?.breakevens || []}
          netPremium={selectedPayoff?.net_premium || 0}
          positionCount={calculateTotalLegs(selectedSession)}
          strategyId={selectedSession?.session_id || ''}
          loading={loading && !selectedPayoff}
        />

        {/* 5. Order History Tabs */}
        <OrderHistoryTabs
          pendingSessions={activeSessions}
          historySessions={historicalSessions}
          onViewDetails={handleSelectSession}
          onClearHistory={handleClearHistory}
          loading={loading}
        />

        {/* Error Display */}
        {error && (
          <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400">
            <p className="text-sm">{error}</p>
            <button 
              onClick={() => setError(null)}
              className="mt-2 text-xs underline hover:no-underline"
            >
              Dismiss
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default SSRAlgoDashboardV2;
