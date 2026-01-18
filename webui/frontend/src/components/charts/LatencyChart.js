import {
  Line,
  LineChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;
  const [{ value }] = payload;
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/95 px-4 py-3 text-xs shadow-lg backdrop-blur">
      <div className="font-semibold text-slate-300">{label}</div>
      <div className="mt-2 text-sky-300">Latency: {Number(value).toFixed(0)} ms</div>
    </div>
  );
};

function LatencyChart({ data = [] }) {
  return (
    <div className="h-52 sm:h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.15)" />
          <XAxis
            dataKey="time"
            stroke="#475569"
            tick={{ fill: '#94a3b8', fontSize: 12 }}
            minTickGap={16}
          />
          <YAxis
            stroke="#475569"
            tick={{ fill: '#94a3b8', fontSize: 12 }}
            tickFormatter={(value) => `${value.toFixed(0)} ms`}
            width={70}
          />
          <Tooltip content={<CustomTooltip />} />
          <Line
            type="monotone"
            dataKey="latency"
            stroke="#38bdf8"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default LatencyChart;
