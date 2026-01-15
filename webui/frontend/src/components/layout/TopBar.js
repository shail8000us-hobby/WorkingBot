import { RefreshCw, Activity, Bot, Gauge, SignalHigh, SignalLow, Sun, Moon, Shield, TrendingUp } from 'lucide-react';
import { motion } from 'framer-motion';
import clsx from 'clsx';
import { useState, useEffect } from 'react';
import SymbolSelector from '../SymbolSelector';
import { useInstance } from '../../context/InstanceContext';

const qualityIconMap = {
  excellent: SignalHigh,
  good: SignalHigh,
  fair: Gauge,
  poor: SignalLow,
  disconnected: SignalLow,
  failed: SignalLow,
  offline: SignalLow,
  unknown: Gauge
};

const StatusSection = ({ title, icon: Icon, children, color = "border-slate-700/50" }) => (
  <motion.div
    layout
    className={clsx(
      'flex items-center gap-2 rounded-lg border bg-slate-800/40 px-3 py-2',
      color
    )}
    initial={{ opacity: 0, y: -8 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ type: 'spring', stiffness: 320, damping: 24 }}
  >
    <Icon className="h-4 w-4 text-slate-400" strokeWidth={2} />
    <div className="flex items-center gap-3">
      <span className="text-xs font-medium text-slate-400 uppercase tracking-wide">{title}</span>
      <div className="flex items-center gap-2">
        {children}
      </div>
    </div>
  </motion.div>
);

const Badge = ({ label, value, color }) => (
  <div className="flex items-center gap-1.5">
    <span className="text-xs text-slate-500">{label}:</span>
    <span className={clsx("text-xs font-semibold", color)}>{value}</span>
  </div>
);

function TopBar({
  mode = 'dark',
  onToggleTheme,
  onRefresh,
  onEnsureFresh,
  metrics = {},
  isMobile = false,
  warnings = [],
  processStatus = {}
}) {
  const {
    running = false,
    latency = null,
    latencyQuality = 'unknown',
    unrealizedPnl = 0,
    lastUpdated = null
  } = metrics;
  
  const {
    guardianPid = null,
    tradingBotPid = null,
    healthBotPid = null
  } = processStatus;

  // Live prices state
  const [btcPrice, setBtcPrice] = useState(null);
  const [ethPrice, setEthPrice] = useState(null);
  const [priceLoading, setPriceLoading] = useState(true);

  // Fetch live prices on mount and every 10 seconds
  useEffect(() => {
    const fetchPrices = async () => {
      try {
        const [btcRes, ethRes] = await Promise.all([
          fetch('/api/market/spot-price?symbol=BTC'),
          fetch('/api/market/spot-price?symbol=ETH')
        ]);
        
        if (btcRes.ok) {
          const btcData = await btcRes.json();
          setBtcPrice(btcData.price);
        }
        
        if (ethRes.ok) {
          const ethData = await ethRes.json();
          setEthPrice(ethData.price);
        }
        
        setPriceLoading(false);
      } catch (error) {
        console.error('Failed to fetch live prices:', error);
        setPriceLoading(false);
      }
    };

    fetchPrices();
    const interval = setInterval(fetchPrices, 10000); // Update every 10 seconds

    return () => clearInterval(interval);
  }, []);

  const connectionIcon = qualityIconMap[latencyQuality] || qualityIconMap.unknown;
  const latencyDisplay = latency !== null ? `${latency} ms` : '–';
  const pnlColor = unrealizedPnl >= 0 ? 'text-emerald-300' : 'text-rose-300';
  const pnlPrefix = unrealizedPnl >= 0 ? '+' : '';

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'Never';
    try {
      return new Intl.DateTimeFormat('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      }).format(new Date(timestamp));
    } catch (err) {
      return 'Recently';
    }
  };

  return (
    <header
      className="fixed inset-x-0 top-0 z-40 border-b border-slate-800/80 bg-slate-900/90 backdrop-blur supports-[backdrop-filter]:bg-slate-900/70"
      style={{
        paddingTop: `calc(env(safe-area-inset-top) + ${isMobile ? '0.5rem' : '0.75rem'})`,
        paddingBottom: isMobile ? '0.5rem' : '0.75rem'
      }}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
        {/* Left: Brand */}
        <motion.div
          className="flex items-center gap-2 rounded-lg bg-slate-800/50 px-3 py-1.5"
          layout
        >
          <motion.div
            className={clsx(
              'grid h-8 w-8 place-items-center rounded border',
              running ? 'border-emerald-400/50 bg-emerald-500/10' : 'border-rose-400/40 bg-rose-500/10'
            )}
            animate={{ scale: [1, 1.05, 1] }}
            transition={{ repeat: Infinity, duration: 4, ease: 'easeInOut' }}
          >
            <Bot className={clsx('h-4 w-4', running ? 'text-emerald-400' : 'text-rose-400')} />
          </motion.div>
          <div>
            <p className="text-[9px] font-medium uppercase tracking-wider text-slate-400">
              SSR BOT
            </p>
            <p className="text-xs font-semibold text-slate-100">
              {running ? 'Online' : 'Standby'}
            </p>
          </div>
        </motion.div>

        {/* Center: System Status & Symbol Selector */}
        <div className="flex items-center gap-3">
          {/* Live Prices */}
          <StatusSection 
            title="Market" 
            icon={Activity}
            color="border-blue-500/30"
          >
            <Badge 
              label="BTC" 
              value={priceLoading ? '...' : btcPrice ? `$${btcPrice.toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '–'}
              color="text-orange-300"
            />
            <Badge 
              label="ETH" 
              value={priceLoading ? '...' : ethPrice ? `$${ethPrice.toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '–'}
              color="text-indigo-300"
            />
          </StatusSection>
          
          {/* Symbol Selector (v5.0 Multi-Symbol) */}
          <SymbolSelector onSymbolChange={(symbol) => {
            console.log('Symbol changed to:', symbol);
            // Trigger soft data refresh for new symbol (NOT hard page reload)
            if (onEnsureFresh) onEnsureFresh();
          }} />
          
          {/* Process Status */}
          <StatusSection 
            title="System" 
            icon={Activity}
            color={running ? "border-emerald-500/30" : "border-slate-700/50"}
          >
            <Badge 
              label="Status" 
              value={running ? "Running" : "Stopped"} 
              color={running ? "text-emerald-300" : "text-rose-300"}
            />
            {guardianPid && <Badge label="Guardian" value={guardianPid} color="text-slate-300" />}
            {tradingBotPid && <Badge label="Bot" value={tradingBotPid} color="text-slate-300" />}
            {healthBotPid && <Badge label="Health" value={healthBotPid} color="text-slate-300" />}
          </StatusSection>

          {/* Trading Metrics */}
          <StatusSection 
            title="Trading" 
            icon={TrendingUp}
            color="border-amber-500/30"
          >
            <Badge 
              label="PnL" 
              value={`${unrealizedPnl >= 0 ? '+' : ''}${unrealizedPnl?.toFixed?.(2) ?? '0.00'}`}
              color={unrealizedPnl >= 0 ? 'text-emerald-300' : 'text-rose-300'}
            />
          </StatusSection>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2">
          <div className="text-[10px] text-slate-500">
            <span className="font-medium text-slate-400">Synced:</span>{' '}
            {formatTimestamp(lastUpdated)}
          </div>
          <button
            type="button"
            onClick={onEnsureFresh}
            className="group flex items-center gap-1.5 rounded-lg border border-sky-500/40 bg-sky-500/10 px-2.5 py-1.5 text-xs font-semibold text-sky-200 transition hover:border-sky-400 hover:bg-sky-500/20"
          >
            <RefreshCw className="h-3.5 w-3.5 transition group-hover:rotate-180" />
            Sync
          </button>
          <button
            type="button"
            onClick={onRefresh}
            className="rounded-lg border border-slate-700 bg-slate-800/70 px-2.5 py-1.5 text-xs font-semibold text-slate-200 transition hover:border-slate-600 hover:bg-slate-700"
          >
            Reload
          </button>
          <button
            type="button"
            onClick={onToggleTheme}
            aria-label="Toggle theme"
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-700 bg-slate-800 text-slate-200 transition hover:border-slate-500"
          >
            {mode === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </header>
  );
}

export default TopBar;
