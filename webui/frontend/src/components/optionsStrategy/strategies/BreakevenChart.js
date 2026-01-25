import React from 'react';
import { Paper, Box, Typography, Chip } from '@mui/material';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const BreakevenChart = ({ data }) => {
  if (!data || !data.prices || !data.pnl) {
    return (
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>P&L at Expiry</Typography>
        <Typography variant="body2" color="text.secondary">
          No data available
        </Typography>
      </Paper>
    );
  }

  // Sample every nth point to keep chart readable
  const sampleRate = Math.max(1, Math.floor(data.prices.length / 50));
  const sampledPrices = data.prices.filter((_, i) => i % sampleRate === 0);
  const sampledPnl = data.pnl.filter((_, i) => i % sampleRate === 0);

  const chartData = {
    labels: sampledPrices.map(p => `$${Math.round(p).toLocaleString()}`),
    datasets: [
      {
        label: 'P&L at Expiry',
        data: sampledPnl,
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: (context) => {
          const ctx = context.chart.ctx;
          const gradient = ctx.createLinearGradient(0, 0, 0, 400);
          gradient.addColorStop(0, 'rgba(75, 192, 192, 0.4)');
          gradient.addColorStop(0.5, 'rgba(255, 255, 255, 0.1)');
          gradient.addColorStop(1, 'rgba(255, 99, 132, 0.4)');
          return gradient;
        },
        fill: true,
        tension: 0.4
      },
      {
        label: 'Breakeven',
        data: sampledPrices.map(() => 0),
        borderColor: 'rgba(255, 255, 255, 0.5)',
        borderDash: [5, 5],
        borderWidth: 1,
        pointRadius: 0,
        fill: false
      }
    ]
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'top'
      },
      title: {
        display: false
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            const label = context.dataset.label || '';
            const value = context.parsed.y;
            return `${label}: $${value.toFixed(2)}`;
          }
        }
      }
    },
    scales: {
      y: {
        grid: {
          color: 'rgba(255, 255, 255, 0.1)'
        },
        ticks: {
          callback: (value) => `$${value.toFixed(0)}`
        }
      },
      x: {
        grid: {
          color: 'rgba(255, 255, 255, 0.05)'
        },
        ticks: {
          maxTicksLimit: 8
        }
      }
    }
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">P&L at Expiry</Typography>
        {data.breakeven_points && data.breakeven_points.length > 0 && (
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Chip 
              label={`Lower BE: $${Math.round(data.breakeven_points[0]).toLocaleString()}`}
              size="small"
              color="info"
            />
            {data.breakeven_points[1] && (
              <Chip 
                label={`Upper BE: $${Math.round(data.breakeven_points[1]).toLocaleString()}`}
                size="small"
                color="info"
              />
            )}
          </Box>
        )}
      </Box>

      <Box sx={{ height: 300 }}>
        <Line data={chartData} options={options} />
      </Box>

      {/* Summary Stats */}
      {data.strike && (
        <Box sx={{ mt: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Box>
            <Typography variant="caption" color="text.secondary">Strike</Typography>
            <Typography variant="body2" fontWeight="bold">
              ${data.strike.toLocaleString()}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Total Premium</Typography>
            <Typography variant="body2" fontWeight="bold">
              ${data.total_premium?.toFixed(2)}
            </Typography>
          </Box>
          {data.breakeven_points && data.breakeven_points.length >= 2 && (
            <Box>
              <Typography variant="caption" color="text.secondary">Profit Range</Typography>
              <Typography variant="body2" fontWeight="bold">
                ${Math.round(data.breakeven_points[1] - data.breakeven_points[0]).toLocaleString()}
              </Typography>
            </Box>
          )}
        </Box>
      )}
    </Paper>
  );
};

export default BreakevenChart;
