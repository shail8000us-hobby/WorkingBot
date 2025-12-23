import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload || !payload.length) return null;
  const datum = payload[0].payload;
  const { timestamp, pnl } = datum;
  
  const formatTimestamp = (ts) => {
    if (!ts) return '';
    const date = new Date(ts);
    return new Intl.DateTimeFormat('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      day: '2-digit',
      month: 'short',
      hour12: false
    }).format(date);
  };
  
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/95 px-4 py-3 text-xs shadow-lg backdrop-blur">
      <div className="font-semibold text-slate-300">{formatTimestamp(timestamp)}</div>
      <div className="mt-2 text-emerald-300">
        Unrealized PnL: ₹{Number(pnl).toFixed(2)}
      </div>
    </div>
  );
};

// Format tick labels as HH:MM
const formatXAxisTime = (timestamp) => {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return '';
  
  return new Intl.DateTimeFormat('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).format(date);
};

const getDataDomain = (data) => {
  if (!data || data.length === 0) {
    const now = Date.now();
    return [now - (24 * 60 * 60 * 1000), now];
  }
  
  const timestamps = data.map(d => d.timestamp).filter(t => t);
  if (timestamps.length === 0) {
    const now = Date.now();
    return [now - (24 * 60 * 60 * 1000), now];
  }
  
  const minTime = Math.min(...timestamps);
  const maxTime = Math.max(...timestamps);
  
  const padding = (maxTime - minTime) * 0.05 || (60 * 60 * 1000);
  
  return [minTime - padding, maxTime + padding];
};

const generateTicksFromData = (data) => {
  if (!data || data.length === 0) return [];
  
  const domain = getDataDomain(data);
  const [startTime, endTime] = domain;
  const range = endTime - startTime;
  
  const hourInMs = 60 * 60 * 1000;
  const numTicks = Math.min(Math.ceil(range / hourInMs), 24);
  
  const ticks = [];
  for (let i = 0; i <= numTicks; i++) {
    ticks.push(startTime + (i * range / numTicks));
  }
  
  return ticks;
};

function PnLChart({ data = [] }) {
  if (!data || data.length === 0) {
    return (
      <div className="h-52 sm:h-64 flex items-center justify-center">
        <div className="text-center text-slate-500 px-4">
          <div className="text-sm font-medium">No historical PnL data</div>
          <div className="text-xs mt-2 max-w-md">
            Guardian bot collects PnL data every 10 seconds.
            Chart displays the last 24 hours of data.
          </div>
          <div className="text-xs mt-2 text-amber-500/80">
            ⚠️ Guardian may not be running. Check Guardian status above.
          </div>
        </div>
      </div>
    );
  }

  const domain = getDataDomain(data);
  const ticks = generateTicksFromData(data);

  return (
    <div className="h-52 sm:h-64">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#22c55e" stopOpacity={0.45} />
              <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.15)" />
          <XAxis
            dataKey="timestamp"
            type="number"
            domain={domain}
            stroke="#475569"
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            tickFormatter={formatXAxisTime}
            ticks={ticks}
            minTickGap={50}
            height={40}
          />
          <YAxis
            stroke="#475569"
            tick={{ fill: '#94a3b8', fontSize: 12 }}
            tickFormatter={(value) => value.toFixed(0)}
            width={70}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="pnl"
            stroke="#22c55e"
            strokeWidth={2}
            fill="url(#pnlGradient)"
            name="Unrealized PnL"
            activeDot={{ r: 4 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export default PnLChart;
