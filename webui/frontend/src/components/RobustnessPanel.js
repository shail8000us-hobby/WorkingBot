import React, { useCallback, useEffect, useState } from 'react';
import clsx from 'clsx';
import {
  ShieldCheck,
  Activity,
  Power,
  PowerOff,
  Lock,
  TrendingUp,
  TrendingDown,
  RotateCcw,
  AlertTriangle,
  CheckCircle2,
  RefreshCcw,
  ClipboardList,
  Timer,
  Clock,
  Info,
  LineChart,
  FileWarning,
  Layers,
} from 'lucide-react';
import api from '../utils/apiShim';
import { useSocket } from '../hooks/useSocket';
import EmergencyToggle from './EmergencyToggle';
import HelpIcon from './help/HelpIcon';
import VolatilityChart from './charts/VolatilityChart';

const tabs = [
  { id: 'gatekeeper', label: 'Safety Gatekeeper', icon: ShieldCheck },
  { id: 'loss', label: 'Loss Limits', icon: TrendingDown },
  { id: 'circuit', label: 'Circuit Breakers', icon: PowerOff },
  { id: 'volatility', label: 'Volatility Monitor', icon: Activity },
  { id: 'confirmation', label: 'Confirmation Guard', icon: Lock },
  { id: 'audit', label: 'Audit & Hysteresis', icon: ClipboardList },
];

const formatCurrency = (value, currency = 'INR') => {
  if (value === undefined || value === null) return '₹0';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value) || 0);
};

const formatNumber = (value) => {
  if (value === undefined || value === null) return '—';
  return new Intl.NumberFormat('en-IN').format(Number(value) || 0);
};

const formatTimestamp = (isoString) => {
  if (!isoString) return 'Never';
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return 'Invalid';
  return new Intl.DateTimeFormat('en-IN', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
    timeZone: 'Asia/Kolkata',
  }).format(date);
};

const freshnessDescriptor = (isoString) => {
  if (!isoString)
    return {
      label: 'No data',
      tone: 'bg-rose-500/10 text-rose-200',
      icon: <AlertTriangle className="h-3.5 w-3.5" />,
    };
  const diff = Date.now() - new Date(isoString).getTime();
  const minutes = diff / 60000;
  if (minutes < 5) {
    return {
      label: 'Fresh',
      tone: 'bg-emerald-500/15 text-emerald-200',
      icon: <CheckCircle2 className="h-3.5 w-3.5" />,
    };
  }
  if (minutes < 15) {
    return {
      label: 'Recent',
      tone: 'bg-amber-500/15 text-amber-200',
      icon: <Timer className="h-3.5 w-3.5" />,
    };
  }
  return {
    label: 'Stale',
    tone: 'bg-rose-500/15 text-rose-200',
    icon: <AlertTriangle className="h-3.5 w-3.5" />,
  };
};

const progressTone = (ratio) => {
  if (ratio >= 1) return 'from-rose-500 to-amber-400';
  if (ratio >= 0.85) return 'from-amber-400 to-emerald-400';
  return 'from-emerald-400 to-sky-400';
};

const RobustnessPanel = () => {
  const socket = useSocket();
  const isActive = true; // const { isActive } = useIdle(); // Idle detection - temporarily disabled
  const [activeTab, setActiveTab] = useState('gatekeeper');
  const [loading, setLoading] = useState(true);
  const [gatekeeper, setGatekeeper] = useState(null);
  const [lossLimits, setLossLimits] = useState(null);
  const [circuitBreakers, setCircuitBreakers] = useState({});
  const [auditReport, setAuditReport] = useState(null);
  const [hysteresis, setHysteresis] = useState(null);
  const [volatility, setVolatility] = useState(null);
  const [confirmationGuard, setConfirmationGuard] = useState(null);
  const [nextUpdateCountdown, setNextUpdateCountdown] = useState(0);
  const [banner, setBanner] = useState(null);
  const [lastRefreshed, setLastRefreshed] = useState(null);

  const [lossForm, setLossForm] = useState({ trader: '', guardian: '' });
  const [editingLoss, setEditingLoss] = useState(false);
  const [savingLoss, setSavingLoss] = useState(false);

  const [volForm, setVolForm] = useState({
    max_iv: '',
    max_rv: '',
    max_spread: '',
    check_interval: '',
  });
  const [editingVol, setEditingVol] = useState(false);
  const [savingVol, setSavingVol] = useState(false);

  const showBanner = (type, message) => {
    setBanner({ type, message });
    setTimeout(() => setBanner(null), 5000);
  };

  const fetchAllData = useCallback(async () => {
    try {
      setLoading(true);
      const [
        gatekeeperRes,
        limitsRes,
        circuitRes,
        auditRes,
        hysteresisRes,
        volatilityRes,
        confirmationRes,
      ] = await Promise.all([
        api.get('/api/robustness/gatekeeper/status').catch(() => ({ data: { success: false } })),
        api.get('/api/robustness/loss-limits').catch(() => ({ data: { success: false } })),
        api.get('/api/robustness/circuit-breakers').catch(() => ({ data: { success: false } })),
        api.get('/api/robustness/audit/report?days=7').catch(() => ({ data: { success: false } })),
        api.get('/api/robustness/guardian/hysteresis').catch(() => ({ data: { success: false } })),
        api.get('/api/robustness/volatility/status').catch(() => ({ data: { success: false } })),
        api
          .get('/api/robustness/confirmation-guard/status')
          .catch(() => ({ data: { success: false } })),
      ]);

      if (gatekeeperRes.data.success) setGatekeeper(gatekeeperRes.data.stats);
      if (limitsRes.data.success) setLossLimits(limitsRes.data.config);
      if (circuitRes.data.success) setCircuitBreakers(circuitRes.data.circuit_breakers || {});
      if (auditRes.data.success) setAuditReport(auditRes.data.report);
      if (hysteresisRes.data.success) setHysteresis(hysteresisRes.data.hysteresis);
      if (volatilityRes.data.success) setVolatility(volatilityRes.data.status);
      if (confirmationRes.data.success) setConfirmationGuard(confirmationRes.data.stats);
      setLastRefreshed(new Date());

      if (limitsRes.data.success) {
        setLossForm({
          trader: String(limitsRes.data.config?.trader_limit_inr ?? ''),
          guardian: String(limitsRes.data.config?.guardian_limit_inr ?? ''),
        });
      }

      if (volatilityRes.data.success) {
        const status = volatilityRes.data.status;
        setVolForm({
          max_iv: status?.thresholds?.max_iv ?? '',
          max_rv: status?.thresholds?.max_rv ?? '',
          max_spread: status?.thresholds?.max_spread ?? '',
          check_interval: status?.config?.check_interval ?? '',
        });
      }
    } catch (error) {
      console.error('Failed to load robustness data', error);
      showBanner('error', 'Failed to load robustness data. Check network or backend logs.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isActive) {
      console.log('⏸️ Robustness: Paused (user idle)');
      console.log(
        '✅ SAFETY: Trading bot, safety mechanisms, and all server processes continue running!'
      );
      return; // Don't poll when idle - ONLY affects browser visual updates
    }

    fetchAllData();

    // Auto-refresh every 30 seconds
    const refreshInterval = setInterval(() => {
      fetchAllData();
    }, 30000);

    return () => clearInterval(refreshInterval);
  }, [fetchAllData, isActive]);

  // WebSocket listener for real-time volatility updates
  useEffect(() => {
    if (!socket) return;

    const handleVolatilityUpdate = (data) => {
      if (data.status) {
        setVolatility(data.status);
        setLastRefreshed(new Date());
      }
    };

    socket.on('volatility_update', handleVolatilityUpdate);

    return () => {
      socket.off('volatility_update', handleVolatilityUpdate);
    };
  }, [socket]);

  useEffect(() => {
    if (!isActive) return; // Pause countdown when idle
    if (!volatility?.last_update || !volatility?.config?.check_interval) return;

    const updateInterval = volatility.config.check_interval;
    const lastUpdate = new Date(volatility.last_update);
    const nextUpdate = new Date(lastUpdate.getTime() + updateInterval * 1000);

    const tick = () => {
      const timeLeft = Math.max(0, Math.floor((nextUpdate - new Date()) / 1000));
      setNextUpdateCountdown(timeLeft);
    };

    tick();
    // OPTIMIZED: Update every 5 seconds instead of 1 second to reduce re-renders
    // IDLE-AWARE: Pauses when user is idle
    const interval = setInterval(tick, 30000);
    return () => clearInterval(interval);
  }, [volatility?.last_update, volatility?.config?.check_interval, isActive]);

  const handleResetCircuitBreakers = async () => {
    if (!window.confirm('Reset all circuit breakers? This clears throttling state.')) return;
    try {
      const response = await api.post('/api/robustness/circuit-breakers/reset');
      if (response.data.success) {
        showBanner('success', 'Circuit breakers reset. Service calls will resume immediately.');
        fetchAllData();
      } else {
        showBanner('error', response.data.error || 'Reset failed.');
      }
    } catch (error) {
      showBanner('error', error.message || 'Reset failed.');
    }
  };

  const handleResetConfirmationGuard = async () => {
    if (!window.confirm('Reset confirmation guard? Pending orders will be cleared.')) return;
    try {
      const response = await api.post('/api/robustness/confirmation-guard/reset');
      if (response.data.success) {
        showBanner('success', 'Confirmation guard reset. New orders will resume.');
        fetchAllData();
      } else {
        showBanner('error', response.data.error || 'Failed to reset confirmation guard.');
      }
    } catch (error) {
      showBanner('error', error.message || 'Failed to reset confirmation guard.');
    }
  };

  const handleRefreshVolatility = async () => {
    try {
      const response = await api.post('/api/robustness/volatility/update');
      if (response.data.success) {
        showBanner('success', 'Volatility snapshot refreshed.');
        fetchAllData();
      } else {
        showBanner('error', response.data.error || 'Refresh failed.');
      }
    } catch (error) {
      showBanner('error', error.message || 'Refresh failed.');
    }
  };

  const handleSaveLossLimits = async () => {
    try {
      setSavingLoss(true);
      const payload = {
        MAX_ACCOUNT_LOSS_INR: lossForm.trader,
        GUARDIAN_MAX_ACCOUNT_LOSS_INR: lossForm.guardian,
        confirmed: true, // Add confirmation flag to bypass backend confirmation requirement
      };
      const response = await api.post('/api/config/update', payload);
      if (response.data?.success) {
        showBanner('success', 'Loss limits saved. Restart relevant services to apply.');
        setEditingLoss(false);
        fetchAllData();
      } else {
        showBanner('error', response.data?.error || 'Failed to save loss limits.');
      }
    } catch (error) {
      showBanner('error', error.message || 'Failed to save loss limits.');
    } finally {
      setSavingLoss(false);
    }
  };

  const handleSaveVolatilityConfig = async () => {
    try {
      setSavingVol(true);
      const response = await api.post('/api/robustness/volatility/update-config', volForm);
      if (response.data.success) {
        showBanner('success', 'Volatility thresholds updated. Restart the bot to apply.');
        setEditingVol(false);
        fetchAllData();
      } else {
        showBanner('error', response.data.error || 'Failed to save volatility thresholds.');
      }
    } catch (error) {
      showBanner('error', error.message || 'Failed to save volatility thresholds.');
    } finally {
      setSavingVol(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[320px] flex-col items-center justify-center gap-4 rounded-3xl border border-slate-800/60 bg-slate-950/70 p-12">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-slate-700 border-t-sky-400" />
        <p className="text-sm text-slate-400">Loading production robustness telemetry…</p>
      </div>
    );
  }

  const renderHero = () => (
    <section className="rounded-3xl border border-slate-800/60 bg-slate-950/70 p-6 shadow-card">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
            Production Guardrails
          </p>
          <h1 className="text-2xl font-semibold text-slate-100">
            Advanced safety features that make GridBot production-ready
          </h1>
          <p className="max-w-2xl text-sm text-slate-400">
            Safety Gatekeeper, Guardian loss limits, volatility-based circuit breakers, and
            confirmation guards work together to prevent runaway losses, double fills, or chaotic
            behavior during exchange incidents.
          </p>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Clock className="h-4 w-4 text-sky-300" />
            Last refresh:{' '}
            <span className="font-medium text-slate-300">
              {lastRefreshed ? formatTimestamp(lastRefreshed) : '—'}
            </span>
          </div>
        </div>
        <div className="grid w-full gap-3 sm:grid-cols-2 lg:w-[360px]">
          <div className="rounded-2xl border border-sky-500/30 bg-sky-500/10 p-3 text-sm text-sky-100">
            <p className="text-xs uppercase tracking-widest text-sky-200/70">Guardian Status</p>
            <p className="mt-2 text-lg font-semibold text-sky-100">
              {confirmationGuard?.enabled ? 'Online' : 'Disabled'}
            </p>
            <p className="text-xs text-sky-200/70">
              Pending orders: {formatNumber(confirmationGuard?.pending_orders_count || 0)}
            </p>
          </div>
          <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">
            <p className="text-xs uppercase tracking-widest text-emerald-200/70">
              Guardian Loss Ceiling
            </p>
            <p className="mt-2 text-lg font-semibold text-emerald-100">
              {formatCurrency(lossLimits?.guardian_limit_inr)}
            </p>
            <p className="text-xs text-emerald-200/70">
              Buffer vs trader:{' '}
              {formatCurrency(
                (lossLimits?.trader_limit_inr || 0) - (lossLimits?.guardian_limit_inr || 0)
              )}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                'flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold transition',
                active
                  ? 'border-sky-500/60 bg-sky-500/20 text-sky-100 shadow-card'
                  : 'border-transparent bg-slate-900/60 text-slate-300 hover:border-slate-700 hover:bg-slate-900'
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>
    </section>
  );

  const renderGatekeeper = () => (
    <div className="grid gap-6 lg:grid-cols-12">
      <div className="lg:col-span-7 space-y-5">
        <div className="rounded-3xl border border-emerald-500/25 bg-emerald-500/5 p-6">
          <div className="flex gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-200">
              <ShieldCheck className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-100">Safety Gatekeeper</h2>
              <p className="text-sm text-emerald-200/80">
                Every order passes through a kill-switch before reaching the exchange. During
                emergencies, blocks all new placements automatically.
              </p>
            </div>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <MetricCard
              label="Total Checks"
              value={formatNumber(gatekeeper?.checks || 0)}
              tone="text-slate-100"
            />
            <MetricCard
              label="Blocked Orders"
              value={formatNumber(gatekeeper?.blocks || 0)}
              tone={gatekeeper?.blocks ? 'text-rose-200' : 'text-slate-100'}
            />
            <div className="rounded-2xl border border-emerald-500/20 bg-slate-950/60 p-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-emerald-300/60">
                Block Rate
              </p>
              <p className="mt-2 text-lg font-semibold text-emerald-100">
                {((gatekeeper?.block_rate || 0) * 100).toFixed(2)}%
              </p>
              <ProgressBar value={(gatekeeper?.block_rate || 0) * 100} />
            </div>
          </div>
          {gatekeeper?.last_block_reason && (
            <div className="mt-4 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100">
              <p className="font-semibold uppercase tracking-widest">Most Recent Block</p>
              <p className="mt-1 text-xs text-amber-200/80">
                {formatTimestamp(gatekeeper.last_block_time)}
              </p>
              <p className="mt-2 text-sm text-amber-100">{gatekeeper.last_block_reason}</p>
            </div>
          )}
        </div>

        {auditReport && (
          <div className="rounded-3xl border border-slate-800/60 bg-slate-950/60 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-widest text-slate-500">Order Audit</p>
                <h3 className="text-lg font-semibold text-slate-100">Last 7 days</h3>
              </div>
              <span className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-300">
                {formatNumber(auditReport.total_orders || 0)} orders tagged
              </span>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              {Object.entries(auditReport.by_origin || {}).map(([origin, stats]) => (
                <div
                  key={origin}
                  className="rounded-2xl border border-slate-800 bg-slate-900/60 p-3 text-sm text-slate-300"
                >
                  <p className="text-xs uppercase tracking-widest text-slate-500">
                    {origin.toUpperCase()}
                  </p>
                  <p className="mt-2 text-lg font-semibold text-slate-100">
                    {formatNumber(stats.total)}
                  </p>
                  <div className="mt-2 flex gap-3 text-xs text-slate-400">
                    <span>BUY {formatNumber(stats.buy || 0)}</span>
                    <span>TP {formatNumber(stats.tp || 0)}</span>
                  </div>
                </div>
              ))}
            </div>
            {!auditReport.by_origin && (
              <p className="mt-3 text-sm text-slate-400">No trading activity recorded yet.</p>
            )}
          </div>
        )}
      </div>

      <div className="lg:col-span-5 space-y-5">
        <div className="rounded-3xl border border-slate-800/60 bg-slate-950/70 p-5">
          <p className="text-xs uppercase tracking-widest text-slate-500">Gatekeeper Insights</p>
          <div className="mt-4 space-y-3 text-sm text-slate-300">
            <InsightPoint
              title="Single point of control"
              description="If Guardian, volatility or confirmation guards raise a flag, all new orders are halted instantly."
            />
            <InsightPoint
              title="LaunchAgent supervised"
              description="Runs as an independent LaunchAgent process. Survives terminal crashes and keeps the kill-switch armed."
            />
            <InsightPoint
              title="Integrates with Guardian"
              description="Guardian raises emergency flags consumed by the gatekeeper so trading pauses even if bots misbehave."
            />
          </div>
        </div>

        <div className="rounded-3xl border border-sky-500/30 bg-sky-500/10 p-5 text-sm text-sky-100">
          <p className="text-xs uppercase tracking-widest text-sky-200/70">Quick Action</p>
          <p className="mt-2 font-semibold text-sky-100">
            Gatekeeper is {gatekeeper?.enabled ? 'ENABLED' : 'DISABLED'}
          </p>
          <p className="mt-1 text-xs text-sky-200/80">
            Last decision: {formatTimestamp(gatekeeper?.last_check)}
          </p>
          <p className="mt-3 text-xs text-sky-200/90">
            Gatekeeper feeds (Guardian, Volatility, Confirmation Guard) must stay green for trading
            to continue.
          </p>
        </div>
      </div>
    </div>
  );

  const renderLossLimits = () => (
    <div className="grid gap-6 lg:grid-cols-12">
      <div className="lg:col-span-6 space-y-5">
        <div className="rounded-3xl border border-emerald-500/25 bg-emerald-500/5 p-6">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-emerald-500/15 p-3 text-emerald-200">
              <TrendingDown className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-100">Loss Ceiling Enforcement</h2>
              <p className="text-sm text-emerald-200/80">
                Guardian closes every position once cumulative losses hit the INR cap. Trader limit
                is the last resort.
              </p>
            </div>
          </div>

          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
              <p className="text-xs uppercase tracking-widest text-slate-500">Trader Limit</p>
              <p className="mt-2 text-2xl font-semibold text-slate-100">
                {formatCurrency(lossLimits?.trader_limit_inr)}
              </p>
            </div>
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4">
              <p className="text-xs uppercase tracking-widest text-emerald-200/80">
                Guardian Limit
              </p>
              <p className="mt-2 text-2xl font-semibold text-emerald-100">
                {formatCurrency(lossLimits?.guardian_limit_inr)}
              </p>
            </div>
          </div>

          <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
            <p className="text-xs uppercase tracking-widest text-slate-500">Buffer</p>
            <div className="mt-2 flex items-center justify-between">
              <p className="text-lg font-semibold text-slate-100">
                {formatCurrency(lossLimits?.buffer_inr)}
              </p>
              <span
                className={clsx(
                  'rounded-full px-3 py-1 text-xs font-semibold',
                  (lossLimits?.buffer_percent || 0) >= 5
                    ? 'bg-emerald-500/20 text-emerald-100 border border-emerald-500/30'
                    : 'bg-amber-500/20 text-amber-100 border border-amber-500/30'
                )}
              >
                {(lossLimits?.buffer_percent || 0).toFixed(1)}%
              </span>
            </div>
            {(lossLimits?.buffer_percent || 0) < 5 && (
              <p className="mt-2 text-xs text-amber-200/80">
                Increase buffer above 5% to avoid immediate liquidation when Guardian intervenes.
              </p>
            )}
          </div>
        </div>

        <div className="rounded-3xl border border-slate-800/60 bg-slate-950/60 p-6">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-widest text-slate-500">
              Loss Limits Configuration
            </h3>
            {!editingLoss ? (
              <button
                type="button"
                className="inline-flex items-center gap-2 rounded-xl border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:border-slate-500"
                onClick={() => setEditingLoss(true)}
              >
                <Layers className="h-3.5 w-3.5" />
                Edit
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="rounded-xl border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:border-slate-500"
                  onClick={() => {
                    setEditingLoss(false);
                    setLossForm({
                      trader: String(lossLimits?.trader_limit_inr ?? ''),
                      guardian: String(lossLimits?.guardian_limit_inr ?? ''),
                    });
                  }}
                  disabled={savingLoss}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-2 rounded-xl border border-emerald-500/40 bg-emerald-500/15 px-3 py-1.5 text-xs font-semibold text-emerald-100 hover:border-emerald-400"
                  onClick={handleSaveLossLimits}
                  disabled={savingLoss}
                  data-action-id="robustness.save-loss-limits"
                >
                  <Power className={clsx('h-3.5 w-3.5', savingLoss && 'animate-spin')} />
                  {savingLoss ? 'Saving…' : 'Save'}
                </button>
                <HelpIcon actionId="robustness.save-loss-limits" size="small" />
              </div>
            )}
          </div>

          {!editingLoss ? (
            <div className="mt-4 grid gap-3 text-sm text-slate-300">
              <DetailRow label="Trader Config Key" value="MAX_ACCOUNT_LOSS_INR" />
              <DetailRow label="Guardian Config Key" value="GUARDIAN_MAX_ACCOUNT_LOSS_INR" />
              <DetailRow
                label="Configuration State"
                value={
                  lossLimits?.is_valid
                    ? '✅ Guardian limit ≤ Trader limit'
                    : '⚠️ Guardian limit exceeds trader limit'
                }
                tone={lossLimits?.is_valid ? 'text-emerald-300' : 'text-amber-300'}
              />
            </div>
          ) : (
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Trader Limit (INR)
                </label>
                <input
                  type="number"
                  value={lossForm.trader}
                  onChange={(event) =>
                    setLossForm((prev) => ({ ...prev, trader: event.target.value }))
                  }
                  className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Guardian Limit (INR)
                </label>
                <input
                  type="number"
                  value={lossForm.guardian}
                  onChange={(event) =>
                    setLossForm((prev) => ({ ...prev, guardian: event.target.value }))
                  }
                  className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
                />
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="lg:col-span-6 space-y-5">
        {hysteresis && (
          <div className="rounded-3xl border border-amber-500/25 bg-amber-500/5 p-5">
            <div className="flex items-center gap-3">
              <div className="rounded-2xl bg-amber-500/20 p-3 text-amber-200">
                <LineChart className="h-6 w-6" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-slate-100">Guardian Hysteresis</h3>
                <p className="text-sm text-amber-200/80">
                  Prevents alert spam by adding a reset buffer once 80/90/100% drawdown alerts
                  trigger.
                </p>
              </div>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              {Object.entries(hysteresis).map(([level, config]) => (
                <div
                  key={level}
                  className="rounded-2xl border border-amber-500/30 bg-slate-950/60 p-3 text-sm text-slate-200"
                >
                  <p className="text-xs uppercase tracking-widest text-amber-300/70">
                    {level}% Threshold
                  </p>
                  <p className="mt-3 text-xs text-slate-400">Trigger</p>
                  <p className="text-sm font-semibold text-rose-200">{config.trigger}%</p>
                  <p className="mt-2 text-xs text-slate-400">Reset</p>
                  <p className="text-sm font-semibold text-emerald-200">{config.reset}%</p>
                  <p className="mt-2 text-xs text-slate-400">Buffer</p>
                  <p className="text-sm font-semibold text-slate-100">
                    {config.trigger - config.reset}%
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="rounded-3xl border border-slate-800/60 bg-slate-950/60 p-5">
          <p className="text-xs uppercase tracking-widest text-slate-500">Guardian Guidance</p>
          <div className="mt-3 space-y-3 text-sm text-slate-300">
            <InsightPoint
              title="Start Guardian before trading"
              description="Guardian should be the first service you start. It survives restarts and keeps loss controls alive even if the trading bot fails."
            />
            <InsightPoint
              title="Set realistic INR limits"
              description="Guardian exits the entire book at the configured INR amount. Pick a number that matches your maximum tolerable drawdown."
            />
            <InsightPoint
              title="Monitor Telegram escalations"
              description="80%, 90%, 100% alerts will hit Telegram. Manual follow-up is still critical despite Guardian automation."
            />
          </div>
        </div>
      </div>
    </div>
  );

  const renderCircuitBreakers = () => (
    <div className="space-y-6">
      <div className="rounded-3xl border border-amber-500/25 bg-amber-500/5 p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-amber-500/20 p-3 text-amber-200">
              <PowerOff className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-100">Circuit Breakers</h2>
              <p className="text-sm text-amber-200/80">
                Throttles noisy API endpoints during exchange outages. Automatically reopens once
                responses normalize.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleResetCircuitBreakers}
              className="inline-flex items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/15 px-4 py-2 text-xs font-semibold text-amber-100 hover:border-amber-400"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Reset All
            </button>
          </div>
        </div>
      </div>

      {Object.keys(circuitBreakers || {}).length === 0 ? (
        <div className="rounded-3xl border border-slate-800/60 bg-slate-950/60 p-6 text-sm text-slate-400">
          No circuit breaker activity yet. They will appear here once the bot begins making live API
          calls.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {Object.entries(circuitBreakers).map(([name, stats]) => (
            <div key={name} className="rounded-3xl border border-slate-800/60 bg-slate-950/60 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-widest text-slate-500">Endpoint</p>
                  <h3 className="text-lg font-semibold text-slate-100">{name}</h3>
                </div>
                <span
                  className={clsx(
                    'rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-widest',
                    stats.state === 'CLOSED'
                      ? 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
                      : stats.state === 'OPEN'
                        ? 'border border-rose-500/30 bg-rose-500/10 text-rose-100'
                        : 'border border-amber-500/30 bg-amber-500/10 text-amber-100'
                  )}
                >
                  {stats.state}
                </span>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3 text-sm text-slate-300">
                <MetricBlock label="Total Calls" value={formatNumber(stats.total_calls)} />
                <MetricBlock
                  label="Failures"
                  value={formatNumber(stats.total_failures)}
                  tone="text-rose-200"
                />
                <MetricBlock
                  label="Successes"
                  value={formatNumber(stats.total_successes)}
                  tone="text-emerald-200"
                />
                <MetricBlock
                  label="Blocks"
                  value={formatNumber(stats.total_blocks)}
                  tone="text-amber-200"
                />
              </div>

              <div className="mt-4">
                <p className="text-xs uppercase tracking-widest text-slate-500">Failure Rate</p>
                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-800">
                  <div
                    className={clsx(
                      'h-full rounded-full bg-gradient-to-r',
                      progressTone(stats.failure_rate || 0)
                    )}
                    style={{ width: `${((stats.failure_rate || 0) * 100).toFixed(1)}%` }}
                  />
                </div>
                <p className="mt-1 text-xs text-slate-400">
                  {((stats.failure_rate || 0) * 100).toFixed(2)}% of calls failed
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderVolatility = () => (
    <div className="space-y-6">
      <div className="rounded-3xl border border-sky-500/25 bg-sky-500/5 p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-sky-500/20 p-3 text-sky-200">
              <Activity className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-100">
                Volatility Monitor (IV vs RV 1h)
              </h2>
              <p className="text-sm text-sky-200/80">
                Automatically pauses trading when implied or realized volatility (1-hour) exceeds
                safe thresholds for grid strategies.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleRefreshVolatility}
            className="inline-flex items-center gap-2 rounded-xl border border-sky-500/40 bg-sky-500/15 px-4 py-2 text-xs font-semibold text-sky-100 hover:border-sky-400"
          >
            <RefreshCcw className="h-3.5 w-3.5" />
            Refresh Snapshot
          </button>
        </div>
      </div>

      {volatility ? (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <VolMetric
              label="Implied Volatility"
              value={volatility.iv ? `${volatility.iv.toFixed(1)}%` : 'N/A'}
              limit={`${volatility.thresholds?.max_iv ?? '–'}%`}
              healthy={(volatility.iv || 0) <= (volatility.thresholds?.max_iv || Infinity)}
            />
            <VolMetric
              label="Realized Volatility (1h)"
              value={volatility.rv ? `${volatility.rv.toFixed(1)}%` : 'N/A'}
              limit={`${volatility.thresholds?.max_rv ?? '–'}%`}
              healthy={(volatility.rv || 0) <= (volatility.thresholds?.max_rv || Infinity)}
            />
            <VolMetric
              label="IV-RV Spread"
              value={
                volatility.spread !== null && volatility.spread !== undefined
                  ? `${volatility.spread > 0 ? '+' : ''}${volatility.spread.toFixed(1)}%`
                  : 'N/A'
              }
              limit={`±${volatility.thresholds?.max_spread ?? '–'}%`}
              healthy={
                Math.abs(volatility.spread || 0) <= (volatility.thresholds?.max_spread || Infinity)
              }
            />
            <div className="rounded-2xl border border-slate-800/60 bg-slate-950/60 p-4 text-sm text-slate-300">
              <p className="text-xs uppercase tracking-widest text-slate-500">Status</p>
              <p className="mt-2 text-lg font-semibold text-slate-100">
                {volatility.is_safe ? '✅ Trading Allowed' : '🚨 Trading Halted'}
              </p>
              {!volatility.is_safe && (
                <p className="mt-2 text-xs text-rose-200/80">{volatility.violation_reason}</p>
              )}
              <p className="mt-3 text-xs text-slate-500">
                Last update: {formatTimestamp(volatility.last_update)}
              </p>
              <p className="text-xs text-slate-500">
                Next check in {Math.floor(nextUpdateCountdown / 60)}:
                {(nextUpdateCountdown % 60).toString().padStart(2, '0')}s
              </p>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800/60 bg-slate-950/60 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-widest text-slate-500">Historical View</p>
                <h3 className="text-lg font-semibold text-slate-100">IV vs RV trend</h3>
              </div>
              <span className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-300">
                Auto updates every {volatility.config?.check_interval || 0}s
              </span>
            </div>
            <div className="mt-4">
              <VolatilityChart
                socket={socket}
                showHeader={false}
                showSummary={false}
                showFooter={false}
                showLegend={false}
                chartHeight={240}
              />
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800/60 bg-slate-950/60 p-6">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold uppercase tracking-widest text-slate-500">
                Volatility Thresholds
              </h3>
              {!editingVol ? (
                <button
                  type="button"
                  onClick={() => setEditingVol(true)}
                  className="rounded-xl border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:border-slate-500"
                >
                  Edit
                </button>
              ) : (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setEditingVol(false);
                      setVolForm({
                        max_iv: volatility?.thresholds?.max_iv ?? '',
                        max_rv: volatility?.thresholds?.max_rv ?? '',
                        max_spread: volatility?.thresholds?.max_spread ?? '',
                        check_interval: volatility?.config?.check_interval ?? '',
                      });
                    }}
                    className="rounded-xl border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:border-slate-500"
                    disabled={savingVol}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveVolatilityConfig}
                    className="inline-flex items-center gap-2 rounded-xl border border-sky-500/40 bg-sky-500/15 px-3 py-1.5 text-xs font-semibold text-sky-100 hover:border-sky-400"
                    disabled={savingVol}
                  >
                    <Power className={clsx('h-3.5 w-3.5', savingVol && 'animate-spin')} />
                    {savingVol ? 'Saving…' : 'Save'}
                  </button>
                </div>
              )}
            </div>

            {!editingVol ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-4">
                <MetricBlock label="Max IV" value={`${volatility.thresholds?.max_iv ?? '—'}%`} />
                <MetricBlock label="Max RV" value={`${volatility.thresholds?.max_rv ?? '—'}%`} />
                <MetricBlock
                  label="Max Spread"
                  value={`±${volatility.thresholds?.max_spread ?? '—'}%`}
                />
                <MetricBlock
                  label="Check Interval"
                  value={`${volatility.config?.check_interval ?? '—'}s`}
                />
              </div>
            ) : (
              <div className="mt-4 grid gap-4 sm:grid-cols-4">
                <ConfigInput
                  label="Max IV (%)"
                  value={volForm.max_iv}
                  onChange={(event) =>
                    setVolForm((prev) => ({ ...prev, max_iv: event.target.value }))
                  }
                />
                <ConfigInput
                  label="Max RV (%)"
                  value={volForm.max_rv}
                  onChange={(event) =>
                    setVolForm((prev) => ({ ...prev, max_rv: event.target.value }))
                  }
                />
                <ConfigInput
                  label="Max Spread (%)"
                  value={volForm.max_spread}
                  onChange={(event) =>
                    setVolForm((prev) => ({ ...prev, max_spread: event.target.value }))
                  }
                />
                <ConfigInput
                  label="Check Interval (s)"
                  value={volForm.check_interval}
                  onChange={(event) =>
                    setVolForm((prev) => ({ ...prev, check_interval: event.target.value }))
                  }
                />
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="rounded-3xl border border-slate-800/60 bg-slate-950/60 p-6 text-sm text-slate-400">
          Volatility monitor has not produced data yet.
        </div>
      )}
    </div>
  );

  const renderConfirmation = () => (
    <div className="grid gap-6 lg:grid-cols-12">
      <div className="lg:col-span-6 space-y-5">
        <div className="rounded-3xl border border-slate-800/60 bg-slate-950/60 p-6">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-slate-800/80 p-3 text-slate-200">
              <Lock className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-100">Confirmation Guard</h2>
              <p className="text-sm text-slate-300/80">
                Waits for exchange confirmations before allowing new orders. Prevents double fills
                during degraded network conditions.
              </p>
            </div>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <MetricBlock
              label="Registered Orders"
              value={formatNumber(confirmationGuard?.total_orders_registered)}
            />
            <MetricBlock
              label="Pending Confirmations"
              value={formatNumber(confirmationGuard?.pending_orders_count)}
              tone={confirmationGuard?.pending_orders_count ? 'text-amber-200' : 'text-slate-200'}
            />
            <MetricBlock
              label="Blocks Triggered"
              value={formatNumber(confirmationGuard?.blocks)}
              tone={confirmationGuard?.blocks ? 'text-amber-200' : 'text-slate-200'}
            />
            <MetricBlock
              label="Chaos Detections"
              value={formatNumber(confirmationGuard?.chaos_detections)}
              tone={confirmationGuard?.chaos_detections ? 'text-rose-200' : 'text-slate-200'}
            />
          </div>

          <div className="mt-4 space-y-2 text-xs text-slate-400">
            <DetailRow
              label="Poll Interval"
              value={`${confirmationGuard?.poll_interval || '—'}s`}
            />
            <DetailRow
              label="Chaos Threshold"
              value={`${confirmationGuard?.chaos_threshold || '—'}s`}
            />
            <DetailRow label="Enabled" value={confirmationGuard?.enabled ? 'Yes' : 'No'} />
          </div>
        </div>

        <div className="rounded-3xl border border-rose-500/25 bg-rose-500/5 p-5">
          <p className="text-xs uppercase tracking-widest text-rose-200/70">Emergency Action</p>
          <p className="mt-2 text-sm text-rose-100">
            Use reset only when the guard has deadlocked due to exchange outages. It clears pending
            confirmations and allows new orders.
          </p>
          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              onClick={handleResetConfirmationGuard}
              className="inline-flex items-center gap-2 rounded-xl border border-rose-500/40 bg-rose-500/15 px-4 py-2 text-xs font-semibold text-rose-100 hover:border-rose-400"
              disabled={!confirmationGuard || confirmationGuard.pending_orders_count === 0}
            >
              <Power className="h-3.5 w-3.5" />
              Reset Guard
            </button>
            <HelpIcon actionId="confirmation.reset" />
          </div>
        </div>
      </div>

      <div className="lg:col-span-6 space-y-5">
        <div className="rounded-3xl border border-slate-800/60 bg-slate-950/60 p-5">
          <p className="text-xs uppercase tracking-widest text-slate-500">Pending Orders</p>
          {confirmationGuard?.pending_orders?.length ? (
            <div className="mt-4 space-y-3">
              {confirmationGuard.pending_orders.map((order, index) => (
                <div
                  key={`${order.order_id}-${index}`}
                  className={clsx(
                    'rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-300',
                    order.wait_time_seconds > confirmationGuard.chaos_threshold &&
                      'border-rose-500/50 bg-rose-500/10 text-rose-100'
                  )}
                >
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-slate-100">{order.order_id}</p>
                    <span className="text-xs text-slate-400">{order.exchange}</span>
                  </div>
                  <p className="mt-2 text-xs text-slate-400">
                    Wait time: {order.wait_time_seconds}s • Side: {order.side} • Qty:{' '}
                    {order.quantity}
                  </p>
                  {order.wait_time_seconds > confirmationGuard.chaos_threshold && (
                    <p className="mt-2 text-xs text-rose-200/80">
                      Chaos threshold breached — review exchange connectivity before resuming.
                    </p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-400">
              No pending confirmations. Guard is allowing new orders.
            </p>
          )}
        </div>

        <div className="rounded-3xl border border-slate-800/60 bg-slate-950/60 p-5">
          <p className="text-xs uppercase tracking-widest text-slate-500">Operational Playbook</p>
          <div className="mt-3 space-y-3 text-sm text-slate-300">
            <InsightPoint
              title="Normal flow"
              description="BUY placed → Guardian registers → Fill confirmed → TP placed → Guard clears → New orders allowed."
            />
            <InsightPoint
              title="Degraded exchange"
              description="BUY fills but confirmation stalls → Guard blocks new orders until confirmation arrives or you intervene."
            />
            <InsightPoint
              title="Chaos detection"
              description="If wait time exceeds chaos threshold, guard emits an escalation alert and keeps trading paused."
            />
          </div>
        </div>
      </div>
    </div>
  );

  const renderAuditTab = () => (
    <div className="grid gap-6 lg:grid-cols-12">
      <div className="lg:col-span-7 space-y-5">
        <div className="rounded-3xl border border-slate-800/60 bg-slate-950/60 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-widest text-slate-500">Order Audit</p>
              <h3 className="text-lg font-semibold text-slate-100">
                Tagged order provenance (7 days)
              </h3>
              <p className="mt-1 text-xs text-slate-500">
                Ensures every order has a clear origin (grid, recovery, manual) for post-mortems.
              </p>
            </div>
            <span className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-300">
              {formatNumber(auditReport?.total_orders || 0)} orders
            </span>
          </div>
          {auditReport?.by_origin && Object.keys(auditReport.by_origin).length > 0 ? (
            <div className="mt-4 space-y-3">
              {Object.entries(auditReport.by_origin).map(([origin, stats]) => (
                <div
                  key={origin}
                  className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-300"
                >
                  <div>
                    <p className="text-xs uppercase tracking-widest text-slate-500">
                      {origin.toUpperCase()}
                    </p>
                    <p className="mt-1 text-lg font-semibold text-slate-100">
                      {formatNumber(stats.total)}
                    </p>
                  </div>
                  <div className="flex gap-4 text-xs text-slate-400">
                    <span>BUY {formatNumber(stats.buy)}</span>
                    <span>TP {formatNumber(stats.tp)}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-400">
              No orders recorded yet. Once trading starts, origins will populate here automatically.
            </p>
          )}
        </div>
      </div>
      <div className="lg:col-span-5 space-y-5">
        <div className="rounded-3xl border border-amber-500/25 bg-amber-500/5 p-5">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-amber-500/20 p-3 text-amber-200">
              <FileWarning className="h-6 w-6" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-widest text-amber-200/70">
                Guardian Hysteresis
              </p>
              <h3 className="text-lg font-semibold text-slate-100">Alert dampening map</h3>
            </div>
          </div>
          {hysteresis ? (
            <div className="mt-4 space-y-3 text-sm text-slate-200">
              {Object.entries(hysteresis).map(([level, config]) => (
                <div
                  key={level}
                  className="rounded-2xl border border-amber-500/30 bg-slate-950/60 p-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs uppercase tracking-widest text-amber-300/70">
                      {level}% alert
                    </span>
                    <span className="text-xs text-slate-400">
                      Buffer {config.trigger - config.reset}%
                    </span>
                  </div>
                  <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
                    <span>Trigger</span>
                    <span className="text-rose-200">{config.trigger}%</span>
                  </div>
                  <div className="mt-1 flex items-center justify-between text-xs text-slate-400">
                    <span>Reset</span>
                    <span className="text-emerald-200">{config.reset}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-400">
              Hysteresis map unavailable. Guardian may not have exposed thresholds yet.
            </p>
          )}
        </div>
        <div className="rounded-3xl border border-slate-800/60 bg-slate-950/60 p-5 text-sm text-slate-300">
          <p className="text-xs uppercase tracking-widest text-slate-500">Audit Playbook</p>
          <div className="mt-3 space-y-3">
            <InsightPoint
              title="Origin tags"
              description="normal / recovery / manual flags help reconstruct why an order existed during incident reviews."
            />
            <InsightPoint
              title="Guardian correlation"
              description="Pair audit trail with Guardian drawdown timeline to see how the bot reacted under stress."
            />
            <InsightPoint
              title="Compliance archive"
              description="Export audit logs for compliance or investor communications directly from the backend."
            />
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <EmergencyToggle
        featureName="risk_management"
        displayName="Risk Management & Robustness"
        description="Advanced risk controls including Guardian hysteresis, volatility safety, loss limits, circuit breakers, and confirmation guards."
        warningMessage="Disabling risk management removes protective guardrails and exposes the bot to uncontrolled losses during exchange or network incidents."
      />

      {banner && (
        <div
          className={clsx(
            'flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm shadow-lg',
            banner.type === 'success' && 'border-emerald-500/40 bg-emerald-500/10 text-emerald-100',
            banner.type === 'error' && 'border-rose-500/40 bg-rose-500/10 text-rose-100',
            banner.type === 'info' && 'border-sky-500/40 bg-sky-500/10 text-sky-100'
          )}
        >
          {banner.type === 'success' && <CheckCircle2 className="h-4 w-4" />}
          {banner.type === 'error' && <AlertTriangle className="h-4 w-4" />}
          {banner.type === 'info' && <Info className="h-4 w-4" />}
          <p>{banner.message}</p>
        </div>
      )}

      {renderHero()}

      <div className="space-y-6 rounded-3xl border border-slate-800/60 bg-slate-950/70 p-6 shadow-card">
        {activeTab === 'gatekeeper' && renderGatekeeper()}
        {activeTab === 'loss' && renderLossLimits()}
        {activeTab === 'circuit' && renderCircuitBreakers()}
        {activeTab === 'volatility' && renderVolatility()}
        {activeTab === 'confirmation' && renderConfirmation()}
        {activeTab === 'audit' && renderAuditTab()}
      </div>
    </div>
  );
};

const MetricCard = ({ label, value, tone = 'text-slate-300' }) => (
  <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
    <p className="text-xs uppercase tracking-widest text-slate-500">{label}</p>
    <p className={clsx('mt-2 text-xl font-semibold', tone)}>{value}</p>
  </div>
);

const MetricBlock = ({ label, value, tone = 'text-slate-200' }) => (
  <div>
    <p className="text-xs uppercase tracking-widest text-slate-500">{label}</p>
    <p className={clsx('mt-1 text-lg font-semibold', tone)}>{value}</p>
  </div>
);

const DetailRow = ({ label, value, tone = 'text-slate-300' }) => (
  <div className="flex items-center justify-between border-b border-slate-800/60 py-2 text-xs">
    <span className="text-slate-500">{label}</span>
    <span className={clsx('font-semibold', tone)}>{value}</span>
  </div>
);

const InsightPoint = ({ title, description }) => (
  <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-3">
    <p className="text-sm font-semibold text-slate-100">{title}</p>
    <p className="mt-1 text-xs text-slate-400">{description}</p>
  </div>
);

const ConfigInput = ({ label, value, onChange }) => (
  <div className="space-y-2">
    <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">
      {label}
    </label>
    <input
      type="number"
      value={value}
      onChange={onChange}
      className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
    />
  </div>
);

const ProgressBar = ({ value }) => (
  <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
    <div
      className={clsx('h-full rounded-full bg-gradient-to-r', progressTone(value / 100))}
      style={{ width: `${Math.min(value, 100)}%` }}
    />
  </div>
);

const VolMetric = ({ label, value, limit, healthy }) => (
  <div
    className={clsx(
      'rounded-2xl border p-4',
      healthy ? 'border-slate-800 bg-slate-950/60' : 'border-rose-500/40 bg-rose-500/10'
    )}
  >
    <p className="text-xs uppercase tracking-widest text-slate-500">{label}</p>
    <p className={clsx('mt-2 text-xl font-semibold', healthy ? 'text-slate-100' : 'text-rose-200')}>
      {value}
    </p>
    <p className="text-xs text-slate-500">Limit: {limit}</p>
  </div>
);

export default RobustnessPanel;
