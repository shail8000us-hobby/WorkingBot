import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Card,
  CardContent,
  Chip,
  LinearProgress,
  IconButton,
  Tooltip,
  Alert,
  TextField,
  Button,
  Tabs,
  Tab,
  CircularProgress,
  Divider
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  ShowChart,
  Security,
  Psychology,
  Lightbulb,
  Refresh,
  Chat,
  Assessment
} from '@mui/icons-material';
import api from '../utils/apiShim';

export default function InstitutionalAIPanel() {
  const [loading, setLoading] = useState(true);
  const [analysis, setAnalysis] = useState(null);
  const [currentTab, setCurrentTab] = useState(0);
  const [question, setQuestion] = useState('');
  const [aiResponse, setAiResponse] = useState(null);
  const [askingAI, setAskingAI] = useState(false);

  useEffect(() => {
    fetchAnalysis();
    const interval = setInterval(fetchAnalysis, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchAnalysis = async () => {
    try {
      console.log('🔄 Fetching AI analysis...');
      const response = await api.get('/api/institutional/comprehensive_analysis');
      console.log('📊 AI analysis response:', response.data);
      
      if (response.data.success && response.data.analysis) {
        console.log('✅ Setting analysis data');
        setAnalysis(response.data.analysis);
        setLoading(false);
      } else {
        console.warn('⚠️ Invalid response structure:', response.data);
        setLoading(false);
      }
    } catch (error) {
      console.error('❌ Error fetching AI analysis:', error);
      setLoading(false);
    }
  };

  const askAI = async () => {
    if (!question.trim()) return;
    
    setAskingAI(true);
    console.log('🤖 Asking AI:', question);
    
    try {
      const response = await api.post('/api/institutional/ask', { question });
      console.log('🤖 AI Response received:', response.data);
      
      if (response.data.success) {
        // The API returns the full response data, not nested under 'response'
        console.log('✅ Setting AI response:', response.data);
        setAiResponse(response.data);
      } else {
        // Show error message if request failed
        console.warn('⚠️ AI request failed:', response.data);
        setAiResponse({
          answer: response.data.answer || '❌ Failed to get AI response',
          success: false
        });
      }
    } catch (error) {
      console.error('❌ Error asking AI:', error);
      setAiResponse({
        answer: `❌ Error: ${error.message}\n\nPlease check your connection and try again.`,
        success: false
      });
    }
    setAskingAI(false);
  };

  const quickQuestions = [
    "How's my performance?",
    "What's my risk level?",
    "What's the market regime?",
    "Should I trade now?",
    "Show me bot status",
    "What should I do?",
    "Optimize my grid",
    "Am I at risk of liquidation?"
  ];

  if (loading) {
    console.log('🔄 AI Advisor is loading...');
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <CircularProgress />
        <Typography variant="body2" sx={{ ml: 2 }}>
          Loading AI analysis...
        </Typography>
      </Box>
    );
  }

  if (!analysis) {
    console.log('⚠️ No analysis data available');
    return (
      <Alert severity="warning">
        Unable to load AI analysis. Please ensure the backend is running.
      </Alert>
    );
  }

  console.log('✅ AI Advisor loaded with analysis:', analysis);

  return (
    <Box sx={{ width: '100%', py: 2 }}>
      {/* Header - Centered */}
      <Box sx={{ textAlign: 'center', mb: 2, position: 'relative', px: 1 }}>
        <Typography variant="h5" sx={{ fontWeight: 'bold', color: 'primary.main' }}>
          AI Advisor & Institutional Toolkit
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Continuous intelligence, incident analysis, and strategic guidance
        </Typography>
        <Tooltip title="Refresh Analysis">
          <IconButton 
            onClick={fetchAnalysis} 
            color="primary"
            sx={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)' }}
          >
            <Refresh />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Subheader - Centered */}
      <Box sx={{ textAlign: 'center', mb: 3, px: 1 }}>
        <Typography variant="h4" sx={{ fontWeight: 'bold', display: 'inline-flex', alignItems: 'center', gap: 1, justifyContent: 'center' }}>
          <Psychology color="primary" />
          Institutional AI Advisor
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          World-class analytics powered by institutional-grade algorithms
        </Typography>
      </Box>

      {/* Tabs - Spread evenly across full width */}
      <Tabs 
        value={currentTab} 
        onChange={(e, v) => setCurrentTab(v)} 
        sx={{ 
          mb: 3,
          '& .MuiTabs-flexContainer': {
            justifyContent: 'space-between'
          },
          '& .MuiTab-root': {
            flex: 1,
            maxWidth: 'none'
          }
        }}
        variant="fullWidth"
      >
        <Tab icon={<Assessment />} label="Overview" />
        <Tab icon={<ShowChart />} label="Performance" />
        <Tab icon={<Security />} label="Risk" />
        <Tab icon={<TrendingUp />} label="Market" />
        <Tab icon={<Lightbulb />} label="Recommendations" />
        <Tab icon={<Chat />} label="Ask AI" />
      </Tabs>

      {/* Tab Panels */}
      {currentTab === 0 && <OverviewTab analysis={analysis} />}
      {currentTab === 1 && <PerformanceTab analysis={analysis} />}
      {currentTab === 2 && <RiskTab analysis={analysis} />}
      {currentTab === 3 && <MarketTab analysis={analysis} />}
      {currentTab === 4 && <RecommendationsTab analysis={analysis} />}
      {currentTab === 5 && (
        <AskAITab
          question={question}
          setQuestion={setQuestion}
          askAI={askAI}
          aiResponse={aiResponse}
          askingAI={askingAI}
          quickQuestions={quickQuestions}
        />
      )}
    </Box>
  );
}

// Overview Tab
function OverviewTab({ analysis }) {
  const { performance, risk, insights, recommendations, alerts } = analysis;

  return (
    <Grid container spacing={1} sx={{ px: 1 }}>
      {/* Critical Alerts - Full Width */}
      {alerts && alerts.length > 0 && (
        <Grid item xs={12}>
          <Paper sx={{ p: 1, bgcolor: 'rgba(211, 47, 47, 0.1)', borderLeft: '4px solid #d32f2f' }}>
            <Typography variant="subtitle1" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
              🔴 Critical Alerts ({alerts.filter(a => a.severity === 'CRITICAL').length})
            </Typography>
            {alerts.filter(a => a.severity === 'CRITICAL').map((alert, idx) => (
              <Alert key={idx} severity="error" sx={{ mb: 1, py: 0.5 }}>
                <strong>{alert.title}</strong>: {alert.message}
              </Alert>
            ))}
          </Paper>
        </Grid>
      )}

      {/* Metric Cards - Spread evenly across full width */}
      <Grid item xs={6} sm={4} md={2}>
        <MetricCardWithTooltip
          title="Sharpe Ratio"
          value={performance.risk_adjusted_returns.sharpe_ratio}
          grade={analysis.performance_grades.sharpe}
          icon={<ShowChart />}
          color="primary"
          tooltip="Risk-adjusted return metric. Measures excess return per unit of total risk. Higher is better."
          benchmark=">2.0 Excellent | >1.0 Good | <0 Poor"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={2}>
        <MetricCardWithTooltip
          title="Win Rate"
          value={`${performance.win_loss_stats.win_rate.toFixed(1)}%`}
          grade={analysis.performance_grades.win_rate}
          icon={<TrendingUp />}
          color="success"
          tooltip="Percentage of profitable trades. Grid bots typically achieve 60-70% in ranging markets."
          benchmark=">65% Excellent | >55% Good"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={2}>
        <MetricCardWithTooltip
          title="Max Drawdown"
          value={`${Math.abs(performance.drawdown_analysis.max_drawdown.max_dd_pct).toFixed(1)}%`}
          grade={analysis.performance_grades.max_dd}
          icon={<TrendingDown />}
          color="error"
          tooltip="Largest peak-to-trough decline in equity. Lower is better. Keep under 20% for conservative trading."
          benchmark="<10% Excellent | <20% Good | >30% High Risk"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={2}>
        <MetricCardWithTooltip
          title="VaR (95%)"
          value={`₹${Math.abs(risk.value_at_risk.var_95_historical).toFixed(0)}`}
          grade={analysis.risk_grades.var}
          icon={<Security />}
          color="warning"
          tooltip="Value at Risk at 95% confidence. Maximum expected loss over a day in 95% of cases."
          benchmark="<2% of capital Excellent | <5% Good"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={2}>
        <MetricCardWithTooltip
          title="Profit Factor"
          value={performance.win_loss_stats.profit_factor}
          grade={analysis.performance_grades.profit_factor}
          icon={<TrendingUp />}
          color="success"
          tooltip="Ratio of gross profit to gross loss. Measures profitability efficiency."
          benchmark=">2.0 Excellent | >1.5 Good | <1.0 Losing"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={2}>
        <MetricCardWithTooltip
          title="Total Trades"
          value={performance.win_loss_stats.total_trades}
          subtitle={`${performance.win_loss_stats.wins}W/${performance.win_loss_stats.losses}L`}
          icon={<ShowChart />}
          tooltip="Total number of completed trades. More trades provide better statistical confidence."
          benchmark=">100 Good sample | >30 Acceptable"
          compact
        />
      </Grid>

      {/* Bottom Section - Insights & Recommendations side by side */}
      <Grid item xs={12} md={6}>
        <Paper sx={{ p: 1, height: '100%', bgcolor: 'rgba(255, 255, 255, 0.02)' }}>
          <Typography variant="subtitle1" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1, color: '#FFA726' }}>
            💡 Key Insights
          </Typography>
          {insights && insights.slice(0, 5).map((insight, idx) => (
            <Box key={idx} sx={{ mb: 1, pb: 1, borderBottom: idx < 4 ? '1px solid rgba(255,255,255,0.1)' : 'none' }}>
              <Chip
                label={insight.category}
                size="small"
                color={insight.severity === 'positive' ? 'success' : insight.severity === 'warning' ? 'warning' : 'error'}
                sx={{ mb: 0.75, height: 20, fontSize: '0.7rem' }}
              />
              <Typography variant="caption" sx={{ fontWeight: 'bold', mb: 0.5, display: 'block' }}>
                {insight.icon} {insight.title}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                {insight.message}
              </Typography>
            </Box>
          ))}
        </Paper>
      </Grid>

      <Grid item xs={12} md={6}>
        <Paper sx={{ p: 1, height: '100%', bgcolor: 'rgba(255, 255, 255, 0.02)' }}>
          <Typography variant="subtitle1" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1, color: '#66BB6A' }}>
            🎯 Top Recommendations
          </Typography>
          {recommendations && recommendations.slice(0, 3).map((rec, idx) => (
            <Box key={idx} sx={{ mb: 1, pb: 1, borderBottom: idx < 2 ? '1px solid rgba(255,255,255,0.1)' : 'none' }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.75 }}>
                <Typography variant="caption" sx={{ fontWeight: 'bold' }}>
                  {rec.title}
                </Typography>
                <Chip
                  label={rec.priority.toUpperCase()}
                  size="small"
                  color={rec.priority === 'critical' ? 'error' : rec.priority === 'high' ? 'warning' : 'info'}
                  sx={{ height: 20, fontSize: '0.65rem' }}
                />
              </Box>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem', mb: 0.5, display: 'block' }}>
                <strong>Action:</strong> {rec.action}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                <strong>Impact:</strong> {rec.expected_impact} <Chip label={`${rec.confidence}%`} size="small" sx={{ ml: 0.5, height: 16, fontSize: '0.65rem' }} />
              </Typography>
            </Box>
          ))}
        </Paper>
      </Grid>
    </Grid>
  );
}

// Performance Tab
function PerformanceTab({ analysis }) {
  const { performance, performance_grades } = analysis;
  const { risk_adjusted_returns, win_loss_stats, drawdown_analysis } = performance;

  return (
    <Grid container spacing={1} sx={{ px: 1 }}>
      {/* Section Header with Info */}
      <Grid item xs={12}>
        <Paper sx={{ p: 1, bgcolor: 'rgba(33, 150, 243, 0.05)', borderLeft: '4px solid #2196F3' }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
            📈 Risk-Adjusted Returns
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Metrics that measure returns relative to risk taken. Higher values indicate better risk-adjusted performance.
          </Typography>
        </Paper>
      </Grid>
      
      {/* 6 cards per row for better space utilization */}
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Sharpe Ratio"
          value={risk_adjusted_returns.sharpe_ratio}
          grade={performance_grades.sharpe}
          subtitle="Annualized"
          tooltip="Measures excess return per unit of risk. >2.0 is excellent, >1.0 is good, <0 means losing money relative to risk."
          benchmark=">2.0 Excellent"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Sortino Ratio"
          value={risk_adjusted_returns.sortino_ratio}
          subtitle="Downside Risk"
          tooltip="Like Sharpe but only penalizes downside volatility. Better for strategies with asymmetric returns."
          benchmark=">2.0 Excellent"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Calmar Ratio"
          value={risk_adjusted_returns.calmar_ratio}
          subtitle="Return/Max DD"
          tooltip="Annual return divided by maximum drawdown. Shows return relative to worst loss. >3.0 is excellent."
          benchmark=">3.0 Excellent"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Information Ratio"
          value={risk_adjusted_returns.information_ratio}
          subtitle="Active Return"
          tooltip="Excess return per unit of tracking error. Measures skill in generating alpha. >0.5 is good."
          benchmark=">0.5 Good"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Total Trades"
          value={performance.total_trades}
          subtitle="Completed"
          tooltip="Total number of completed trading cycles. More trades provide better statistical significance."
          benchmark=">100 Good"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Total PnL"
          value={`₹${performance.overall_performance.total_pnl.toFixed(0)}`}
          subtitle="Net Profit"
          tooltip="Total profit/loss from all trades. Cumulative earnings from the strategy."
          benchmark=">0 Profitable"
          compact
          color={performance.overall_performance.total_pnl >= 0 ? '#4CAF50' : '#F44336'}
        />
      </Grid>

      <Grid item xs={12}>
        <Divider sx={{ my: 1 }} />
        <Paper sx={{ p: 1, bgcolor: 'rgba(76, 175, 80, 0.05)', borderLeft: '4px solid #4CAF50' }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
            ⚖️ Win/Loss Statistics
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Core trading performance metrics. Win rate shows consistency, profit factor shows overall profitability.
          </Typography>
        </Paper>
      </Grid>
      
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Win Rate"
          value={`${win_loss_stats.win_rate.toFixed(1)}%`}
          grade={performance_grades.win_rate}
          subtitle={`${win_loss_stats.wins || 0}W/${win_loss_stats.losses || 0}L`}
          tooltip="Percentage of profitable trades. Grid bots typically aim for 60-70% win rate in ranging markets."
          benchmark=">65% Excellent"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Profit Factor"
          value={win_loss_stats.profit_factor > 100 ? '999+' : win_loss_stats.profit_factor}
          grade={performance_grades.profit_factor}
          subtitle="Gross P/L"
          tooltip="Total gains divided by total losses. >2.0 is excellent. Shows how much you make per rupee lost."
          benchmark=">2.0 Excellent"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Expectancy"
          value={`₹${win_loss_stats.expectancy.toFixed(0)}`}
          subtitle="Per Trade"
          tooltip="Average expected profit per trade. Positive value means profitable strategy over time."
          benchmark=">₹500 Good"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Risk/Reward"
          value={win_loss_stats.risk_reward_ratio.toFixed(2)}
          subtitle="Avg Win/Loss"
          tooltip="Average winning trade divided by average losing trade. >1.5 means wins are bigger than losses."
          benchmark=">2.0 Excellent"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Avg Win"
          value={`₹${win_loss_stats.avg_win.toFixed(0)}`}
          subtitle="Average"
          tooltip="Average profit from winning trades. Higher values mean each win is more valuable."
          benchmark=">₹1000 Good"
          compact
          color="#4CAF50"
        />
      </Grid>
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Avg Loss"
          value={`₹${Math.abs(win_loss_stats.avg_loss).toFixed(0)}`}
          subtitle="Average"
          tooltip="Average loss from losing trades. Lower is better. Should be smaller than average win."
          benchmark="<₹500 Good"
          compact
          color="#F44336"
        />
      </Grid>

      <Grid item xs={12}>
        <Divider sx={{ my: 1 }} />
        <Paper sx={{ p: 1, bgcolor: 'rgba(244, 67, 54, 0.05)', borderLeft: '4px solid #F44336' }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
            📉 Drawdown Analysis
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Measures peak-to-trough declines. Lower drawdowns mean smoother equity curve and better risk management.
          </Typography>
        </Paper>
      </Grid>
      
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Max Drawdown"
          value={`${Math.abs(drawdown_analysis.max_drawdown.max_dd_pct).toFixed(1)}%`}
          grade={performance_grades.max_dd}
          subtitle={`₹${Math.abs(drawdown_analysis.max_drawdown.max_dd).toFixed(0)}`}
          tooltip="Largest peak-to-trough decline. Shows worst-case scenario. Keep under 20% for conservative trading."
          benchmark="<10% Excellent"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Avg Drawdown"
          value={`${Math.abs(drawdown_analysis.avg_drawdown).toFixed(1)}%`}
          subtitle="Mean DD"
          tooltip="Average of all drawdown periods. Indicates typical volatility and consistency of returns."
          benchmark="<5% Excellent"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Current Drawdown"
          value={`${Math.abs(drawdown_analysis.current_drawdown).toFixed(1)}%`}
          subtitle="From Peak"
          tooltip="Current decline from the highest equity point. 0% means at all-time high. Shows if currently in drawdown."
          benchmark="0% At Peak"
          compact
        />
      </Grid>
    </Grid>
  );
}

// Risk Tab
function RiskTab({ analysis }) {
  const { risk, risk_grades } = analysis;
  const { value_at_risk, portfolio_risk, margin_leverage } = risk;

  return (
    <Grid container spacing={1}>
      {/* Value at Risk Section */}
      <Grid item xs={12}>
        <Paper sx={{ p: 1, bgcolor: 'rgba(211, 47, 47, 0.05)' }}>
          <Typography variant="subtitle1" color="error" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            📉 Value at Risk
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Maximum expected loss at different confidence levels
          </Typography>
        </Paper>
      </Grid>
      
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="VaR 95%"
          value={`₹${Math.abs(value_at_risk.var_95_historical).toFixed(0)}`}
          grade={risk_grades.var}
          subtitle="1-Day Loss"
          tooltip="Historical Value at Risk at 95% confidence. Maximum expected loss over 1 day in 95% of cases."
          benchmark="<2% of capital Excellent | <5% Good | >10% High Risk"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="VaR 99%"
          value={`₹${Math.abs(value_at_risk.var_99_historical).toFixed(0)}`}
          subtitle="Extreme Loss"
          tooltip="Value at Risk at 99% confidence. Expected loss in the worst 1% of cases."
          benchmark="<5% of capital Good | >10% Extreme Risk"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="CVaR 95%"
          value={`₹${Math.abs(value_at_risk.cvar_95).toFixed(0)}`}
          subtitle="Expected Shortfall"
          tooltip="Conditional VaR: Average loss when VaR threshold is breached. More conservative than VaR."
          benchmark="CVaR typically 1.5-2x VaR"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="MC VaR 95%"
          value={`₹${Math.abs(value_at_risk.var_95_monte_carlo).toFixed(0)}`}
          grade={risk_grades.var}
          subtitle="10k Simulations"
          tooltip="Monte Carlo simulated VaR using 10,000 random price paths. Forward-looking risk estimate."
          benchmark="Should align with Historical VaR ±20%"
          compact
        />
      </Grid>

      {/* Portfolio Risk Section */}
      <Grid item xs={12}>
        <Paper sx={{ p: 1, bgcolor: 'rgba(255, 152, 0, 0.05)' }}>
          <Typography variant="subtitle1" color="warning.main" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            ⚖️ Portfolio Risk
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Market correlation, volatility, and leverage metrics
          </Typography>
        </Paper>
      </Grid>
      
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Beta"
          value={portfolio_risk.beta}
          subtitle="Market Correlation"
          tooltip="Sensitivity to market movements. β=1: moves with market, β>1: more volatile, β<1: less volatile."
          benchmark="0.8-1.2 Normal | >1.5 High Risk"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Volatility"
          value={`${portfolio_risk.volatility.toFixed(1)}%`}
          grade={risk_grades.volatility}
          subtitle="Annualized"
          tooltip="Annualized price volatility. Higher values indicate more price swings and risk."
          benchmark="<30% Low | 30-60% Medium | >60% High"
          compact
        />
      </Grid>
      <Grid item xs={6} sm={4} md={3} lg={2}>
        <MetricCardWithTooltip
          title="Leverage"
          value={`${margin_leverage.leverage_ratio.toFixed(1)}x`}
          grade={risk_grades.leverage}
          subtitle="Position/Equity"
          tooltip="Total position size divided by account equity. Higher leverage = higher risk and potential returns."
          benchmark="<3x Conservative | 3-5x Moderate | >5x Aggressive"
          compact
        />
      </Grid>

      {/* Margin & Liquidation Section */}
      <Grid item xs={12}>
        <Paper sx={{ p: 1, bgcolor: 'rgba(244, 67, 54, 0.05)' }}>
          <Typography variant="subtitle1" color="error" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            🚨 Margin & Liquidation
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Monitor margin usage and liquidation risk
          </Typography>
        </Paper>
      </Grid>
      
      <Grid item xs={12} md={6}>
        <Paper sx={{ p: 1, height: '100%' }}>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
            Margin Utilization
          </Typography>
          <Typography variant="h4" sx={{ mb: 1 }}>
            {margin_leverage.margin_utilization.toFixed(1)}%
          </Typography>
          <LinearProgress
            variant="determinate"
            value={margin_leverage.margin_utilization}
            color={margin_leverage.margin_utilization > 70 ? 'error' : margin_leverage.margin_utilization > 50 ? 'warning' : 'success'}
            sx={{ height: 8, borderRadius: 4 }}
          />
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block', fontSize: '0.65rem' }}>
            Keep below 70% to avoid liquidation risk
          </Typography>
        </Paper>
      </Grid>
      <Grid item xs={12} md={6}>
        <Paper sx={{ p: 1, height: '100%' }}>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
            Liquidation Distance
          </Typography>
          <Typography variant="h4" sx={{ mb: 1 }}>
            {margin_leverage.liquidation_distance.toFixed(1)}%
          </Typography>
          <LinearProgress
            variant="determinate"
            value={Math.min(margin_leverage.liquidation_distance, 100)}
            color={margin_leverage.liquidation_distance < 30 ? 'error' : margin_leverage.liquidation_distance < 50 ? 'warning' : 'success'}
            sx={{ height: 8, borderRadius: 4 }}
          />
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block', fontSize: '0.65rem' }}>
            Distance to liquidation price - maintain above 50%
          </Typography>
        </Paper>
      </Grid>
    </Grid>
  );
}

// Market Tab
function MarketTab({ analysis }) {
  // Add null safety checks
  if (!analysis || !analysis.market) {
    return (
      <Alert severity="info">
        Market analysis data is not available yet. Please ensure the bot has sufficient trading history.
      </Alert>
    );
  }

  const { market } = analysis;
  const { regime, forecast } = market || {};

  if (!regime) {
    return (
      <Alert severity="info">
        Market regime data is not available yet. The AI needs more trading data to analyze market conditions.
      </Alert>
    );
  }

  const regimeColor = {
    'MEAN_REVERTING': 'success',
    'TRENDING': 'info',
    'HIGH_VOLATILITY': 'error',
    'LOW_LIQUIDITY': 'warning',
    'MIXED': 'default'
  };

  return (
    <Grid container spacing={1}>
      {/* Current Market Regime */}
      <Grid item xs={12} md={6}>
        <Paper sx={{ p: 1, height: '100%' }}>
          <Typography variant="subtitle1" sx={{ mb: 1 }}>📊 Current Market Regime</Typography>
          <Chip
            label={regime?.regime || 'Unknown'}
            color={regimeColor[regime?.regime] || 'default'}
            sx={{ fontSize: '1rem', py: 2, mb: 1, height: 'auto' }}
          />
          <Typography variant="body2" sx={{ mb: 1 }}>
            {regime?.description || 'No description available'}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Confidence: {regime?.confidence ? (regime.confidence * 100).toFixed(0) : '0'}%
          </Typography>
          <LinearProgress
            variant="determinate"
            value={regime?.confidence ? regime.confidence * 100 : 0}
            sx={{ mt: 0.5, height: 6, borderRadius: 3 }}
          />
        </Paper>
      </Grid>

      {/* Market Metrics */}
      <Grid item xs={12} md={6}>
        <Paper sx={{ p: 1, height: '100%' }}>
          <Typography variant="subtitle1" sx={{ mb: 1 }}>📈 Market Metrics</Typography>
          <Grid container spacing={1.5}>
            <Grid item xs={6}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>Momentum</Typography>
              <Typography variant="h6">{regime?.metrics?.momentum?.toFixed(2) || 'N/A'}</Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>Volatility</Typography>
              <Typography variant="h6">{regime?.metrics?.volatility?.toFixed(2) || 'N/A'}</Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>Mean Reversion</Typography>
              <Typography variant="h6">{regime?.metrics?.mean_reversion?.toFixed(2) || 'N/A'}</Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>Trend Strength</Typography>
              <Typography variant="h6">{regime?.metrics?.trend_strength?.toFixed(2) || 'N/A'}</Typography>
            </Grid>
          </Grid>
        </Paper>
      </Grid>

      {/* Strategy Recommendations */}
      <Grid item xs={12}>
        <Paper sx={{ p: 1 }}>
          <Typography variant="subtitle1" sx={{ mb: 1 }}>🎯 Strategy Recommendations</Typography>
          <Grid container spacing={1}>
            <Grid item xs={12} md={6}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>Strategy</Typography>
              <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
                {regime?.recommendations?.strategy || 'N/A'}
              </Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>Grid Adjustment</Typography>
              <Typography variant="body1">
                {regime?.recommendations?.grid_adjustment || 'N/A'}
              </Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>Expected Win Rate</Typography>
              <Typography variant="body1" sx={{ fontWeight: 'bold', color: 'success.main' }}>
                {regime?.recommendations?.expected_win_rate || 'N/A'}
              </Typography>
            </Grid>
          </Grid>
        </Paper>
      </Grid>

      {/* Price Forecast */}
      {forecast && (
        <Grid item xs={12}>
          <Paper sx={{ p: 1 }}>
            <Typography variant="subtitle1" sx={{ mb: 1 }}>🔮 Price Forecast</Typography>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>Direction</Typography>
                <Chip 
                  label={forecast.direction} 
                  size="small" 
                  color={forecast.direction === 'UP' ? 'success' : forecast.direction === 'DOWN' ? 'error' : 'default'} 
                  sx={{ mt: 0.5 }}
                />
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>Confidence</Typography>
                <Typography variant="h6" sx={{ mt: 0.5 }}>
                  {(forecast.confidence * 100).toFixed(0)}%
                </Typography>
              </Box>
            </Box>
          </Paper>
        </Grid>
      )}
    </Grid>
  );
}

// Recommendations Tab
function RecommendationsTab({ analysis }) {
  const { recommendations } = analysis;

  return (
    <Grid container spacing={1} sx={{ px: 1 }}>
      {recommendations && recommendations.map((rec, idx) => (
        <Grid item xs={12} key={idx}>
          <Paper sx={{ 
            p: 1, 
            borderLeft: `4px solid ${rec.priority === 'critical' ? '#d32f2f' : rec.priority === 'high' ? '#ed6c02' : '#0288d1'}`,
            bgcolor: rec.priority === 'critical' ? 'rgba(211, 47, 47, 0.05)' : 'rgba(255, 255, 255, 0.02)'
          }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="subtitle1">{rec.title}</Typography>
              <Chip
                label={rec.priority.toUpperCase()}
                color={rec.priority === 'critical' ? 'error' : rec.priority === 'high' ? 'warning' : 'info'}
                size="small"
                sx={{ height: 22, fontSize: '0.7rem' }}
              />
            </Box>
            <Typography variant="body2" sx={{ mb: 0.75 }}>
              <strong>Action:</strong> {rec.action}
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
              <strong>Reasoning:</strong> {rec.reasoning}
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
              <Chip 
                label={`Impact: ${rec.expected_impact}`} 
                variant="outlined" 
                size="small"
                sx={{ height: 24, fontSize: '0.7rem' }}
              />
              <Chip 
                label={`Confidence: ${rec.confidence}%`} 
                variant="outlined" 
                size="small"
                sx={{ height: 24, fontSize: '0.7rem' }}
              />
            </Box>
          </Paper>
        </Grid>
      ))}
    </Grid>
  );
}

// Ask AI Tab
function AskAITab({ question, setQuestion, askAI, aiResponse, askingAI, quickQuestions }) {
  return (
    <Grid container spacing={1}>
      <Grid item xs={12}>
        <Paper sx={{ p: 1.5 }}>
          <Typography variant="h6" sx={{ mb: 2 }}>Ask the AI Advisor</Typography>
          <TextField
            fullWidth
            multiline
            rows={3}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask me anything about your trading performance, risk, strategy..."
            variant="outlined"
            sx={{ mb: 2 }}
            onKeyPress={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                askAI();
              }
            }}
          />
          <Button
            variant="contained"
            onClick={askAI}
            disabled={askingAI || !question.trim()}
            startIcon={askingAI ? <CircularProgress size={20} /> : <Chat />}
          >
            {askingAI ? 'Thinking...' : 'Ask AI'}
          </Button>
        </Paper>
      </Grid>

      <Grid item xs={12}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Quick Questions:
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {quickQuestions.map((q, idx) => (
            <Chip
              key={idx}
              label={q}
              onClick={() => setQuestion(q)}
              variant="outlined"
              clickable
            />
          ))}
        </Box>
      </Grid>

      {/* Debug info */}
      <Grid item xs={12}>
        <Paper sx={{ p: 1, bgcolor: 'rgba(255, 255, 0, 0.1)', border: '1px solid rgba(255, 255, 0, 0.3)' }}>
          <Typography variant="caption" color="text.secondary">
            Debug: aiResponse = {aiResponse ? 'SET' : 'NULL'} | 
            Has answer: {aiResponse?.answer ? 'YES' : 'NO'} | 
            Answer length: {aiResponse?.answer?.length || 0}
          </Typography>
        </Paper>
      </Grid>

      {aiResponse && (
        <Grid item xs={12}>
          <Paper sx={{ p: 1.5, bgcolor: 'rgba(25, 118, 210, 0.05)', border: '1px solid rgba(25, 118, 210, 0.2)' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Psychology color="primary" />
                AI Response
              </Typography>
              <Box sx={{ display: 'flex', gap: 1 }}>
                {aiResponse.intent && (
                  <Chip 
                    label={aiResponse.intent.replace(/_/g, ' ').toUpperCase()} 
                    size="small" 
                    color="primary" 
                    variant="outlined"
                  />
                )}
                {aiResponse.confidence && (
                  <Chip 
                    label={`${(aiResponse.confidence * 100).toFixed(0)}% confidence`} 
                    size="small" 
                    color="success" 
                    variant="outlined"
                  />
                )}
              </Box>
            </Box>
            
            {/* Render answer with markdown-like formatting */}
            <Box sx={{ 
              '& h1, & h2, & h3': { mt: 2, mb: 1, fontWeight: 'bold' },
              '& ul, & ol': { pl: 3 },
              '& code': { 
                bgcolor: 'rgba(0,0,0,0.1)', 
                p: 0.5, 
                borderRadius: 1,
                fontFamily: 'monospace'
              },
              '& pre': {
                bgcolor: 'rgba(0,0,0,0.2)',
                p: 1,
                borderRadius: 1,
                overflow: 'auto',
                fontFamily: 'monospace'
              }
            }}>
              {aiResponse?.answer ? aiResponse.answer.split('\n').map((line, idx) => {
                // Bold text with **
                if (line.includes('**')) {
                  const parts = line.split('**');
                  return (
                    <Typography key={idx} variant="body1" sx={{ mb: 0.5 }}>
                      {parts.map((part, i) => 
                        i % 2 === 1 ? <strong key={i}>{part}</strong> : part
                      )}
                    </Typography>
                  );
                }
                // Bullet points
                if (line.trim().startsWith('-')) {
                  return (
                    <Typography key={idx} variant="body2" sx={{ ml: 2, mb: 0.5 }}>
                      • {line.trim().substring(1).trim()}
                    </Typography>
                  );
                }
                // Code blocks
                if (line.trim().startsWith('```')) {
                  return null; // Handle in next iteration
                }
                // Regular text
                return (
                  <Typography key={idx} variant="body1" sx={{ mb: line.trim() ? 0.5 : 1 }}>
                    {line || '\u00A0'}
                  </Typography>
                );
              }) : (
                <Typography variant="body1" color="text.secondary">
                  No response available
                </Typography>
              )}
            </Box>
            
            {/* Action buttons for actionable responses */}
            {aiResponse.actionable && (
              <Box sx={{ mt: 3, pt: 2, borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  💡 Quick Actions:
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  {aiResponse.data?.command === 'start_bot' && (
                    <Button variant="contained" color="success" size="small">
                      Start Bot
                    </Button>
                  )}
                  {aiResponse.data?.command === 'stop_bot' && (
                    <Button variant="contained" color="error" size="small">
                      Stop Bot
                    </Button>
                  )}
                  {aiResponse.data?.command === 'close_positions' && (
                    <Button variant="contained" color="warning" size="small">
                      Close All Positions
                    </Button>
                  )}
                  <Button variant="outlined" size="small" onClick={() => setQuestion('')}>
                    Ask Another Question
                  </Button>
                </Box>
              </Box>
            )}
            
            {/* Metadata */}
            <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid rgba(255,255,255,0.05)' }}>
              <Typography variant="caption" color="text.secondary">
                {aiResponse.timestamp && `Answered at ${new Date(aiResponse.timestamp).toLocaleTimeString()}`}
              </Typography>
            </Box>
          </Paper>
        </Grid>
      )}
    </Grid>
  );
}

// Reusable Metric Card
function MetricCard({ title, value, grade, subtitle, icon, color }) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        {icon && (
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            {React.cloneElement(icon, { color: color || 'primary' })}
            {grade && <Typography variant="h5">{grade}</Typography>}
          </Box>
        )}
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {title}
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
          {value}
        </Typography>
        {subtitle && (
          <Typography variant="caption" color="text.secondary">
            {subtitle}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}

// Enhanced Metric Card with Tooltip and Benchmark
function MetricCardWithTooltip({ title, value, grade, subtitle, tooltip, benchmark, icon, color, compact }) {
  return (
    <Card sx={{ height: '100%', position: 'relative' }}>
      <CardContent sx={{ p: compact ? 2.5 : 3, '&:last-child': { pb: compact ? 2.5 : 3 } }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: compact ? 1 : 1.5 }}>
          <Tooltip 
            title={
              <Box>
                <Typography variant="body2" sx={{ mb: 1, fontWeight: 'bold' }}>
                  {title}
                </Typography>
                <Typography variant="body2" sx={{ mb: 1 }}>
                  {tooltip}
                </Typography>
                {benchmark && (
                  <Typography variant="caption" sx={{ fontStyle: 'italic', opacity: 0.8 }}>
                    Benchmark: {benchmark}
                  </Typography>
                )}
              </Box>
            }
            arrow
            placement="top"
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, cursor: 'help' }}>
              <Typography variant={compact ? 'body2' : 'body2'} color="text.secondary" sx={{ m: 0, fontSize: compact ? '0.8rem' : '0.875rem' }}>
                {title}
              </Typography>
              <Typography variant="caption" sx={{ opacity: 0.5, fontSize: compact ? '0.65rem' : '0.7rem' }}>
                ⓘ
              </Typography>
            </Box>
          </Tooltip>
          {grade && (
            <Typography variant={compact ? 'h5' : 'h5'} sx={{ lineHeight: 1 }}>
              {grade}
            </Typography>
          )}
        </Box>
        
        <Typography 
          variant={compact ? 'h4' : 'h3'} 
          sx={{ 
            fontWeight: 'bold', 
            mb: compact ? 0.5 : 0.5,
            color: color || 'inherit',
            wordBreak: 'break-word'
          }}
        >
          {value}
        </Typography>
        
        {subtitle && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: compact ? '0.7rem' : '0.75rem' }}>
            {subtitle}
          </Typography>
        )}
        
        {benchmark && !compact && (
          <Box sx={{ mt: 1, pt: 1, borderTop: '1px solid rgba(255,255,255,0.05)' }}>
            <Typography variant="caption" sx={{ fontSize: '0.65rem', opacity: 0.6 }}>
              {benchmark.split('|')[0].trim()}
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
