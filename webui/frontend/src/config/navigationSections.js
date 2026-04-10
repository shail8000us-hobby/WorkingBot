/**
 * Navigation sections configuration for the WebUI sidebar.
 *
 * Extracted from App.js (Phase 2.3) to keep the main component lean.
 * Each section defines: id, label, icon, optional badge, description, and group.
 *
 * Usage:
 *   import { buildSections } from '../config/navigationSections';
 *   const sections = useMemo(() => buildSections({ pendingOrders }), [pendingOrders]);
 */

import {
  LayoutDashboard,
  Layers3,
  ShieldCheck,
  SlidersHorizontal,
  Zap,
  RadioTower,
  Terminal,
  BarChart3,
  Brain,
  Database,
  Table2,
  Workflow,
  Scale,
  Coins,
  Timer,
  ListChecks,
  CandlestickChart,
  Wallet,
  TrendingUp,
} from 'lucide-react';

/**
 * Build the sections array with dynamic badges and feature flags.
 *
 * @param {Object} opts
 * @param {number|null} opts.pendingOrders  - pending order count (badge)
 * @returns {Array} sections list consumed by Sidebar and MobileNav
 */
export function buildSections({ pendingOrders }) {
  return [
    // ── Grid Bot ──────────────────────────────────────────────
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: LayoutDashboard,
      badge: pendingOrders ?? undefined,
      description: 'Trading overview & telemetry',
      group: 'Grid Bot',
    },
    {
      id: 'config',
      label: 'Configuration',
      icon: SlidersHorizontal,
      description: 'Bot parameters and reconciliation tools',
      group: 'Grid Bot',
    },
    {
      id: 'risk',
      label: 'Risk & Safety',
      icon: ShieldCheck,
      description: 'Risk analytics and protection systems',
      group: 'Grid Bot',
    },
    // ── Options Trading ──────────────────────────────────────
    {
      id: 'options',
      label: '📈 Options',
      icon: CandlestickChart,
      description: 'Options trading - manage calls/puts positions',
      group: 'Options Trading',
    },
    {
      id: 'options_chain',
      label: '🔗 Options Chain',
      icon: Table2,
      description: 'Options chain - market data, IV, Greeks, strike selection',
      group: 'Options Trading',
    },
    {
      id: 'strategy_builder',
      label: '🏗️ Strategy Builder',
      icon: Workflow,
      description: 'Multi-leg options strategies - straddles, iron condors, spreads',
      group: 'Options Trading',
    },
    {
      id: 'mv_straddle',
      label: '📊 MV Straddle',
      icon: Scale,
      description: 'Market View Straddle - volatility-driven directional neutral strategy',
      group: 'Options Trading',
    },
    {
      id: 'portfolio_margin',
      label: '💼 Portfolio Margin',
      icon: Wallet,
      description: 'Portfolio margin monitoring — risk, IM/MM, WebSocket live data',
      group: 'Options Trading',
    },
    // ── Algorithms ───────────────────────────────────────────
    {
      id: 'mmm',
      label: '💰 MMM',
      icon: Coins,
      description: 'Money Mind & Method - BTC 0DTE options selling algorithm',
      group: 'Algorithms',
    },
    {
      id: 'mmmx',
      label: '📈 MMMX',
      icon: TrendingUp,
      description: 'MMMX — Options selling algorithm with hedging & circuit breakers',
      group: 'Algorithms',
    },
    {
      id: 'ic',
      label: '🦅 Iron Condor',
      icon: Layers3,
      description: 'Iron Condor - 4-leg defined-risk premium harvesting',
      group: 'Algorithms',
    },
    {
      id: 'patience',
      label: '🎯 Patience',
      icon: Timer,
      description: 'Scenario card engine — conditional entry, GCD lot execution, IV gating',
      group: 'Algorithms',
    },
    {
      id: 'ssr_algo',
      label: '🦋 SSR ALGO',
      icon: Zap,
      description: 'Modified Iron Butterfly - automated percentage-based strike selection',
      group: 'Algorithms',
    },
    {
      id: 'ssdh',
      label: '⚡ SSDH',
      icon: Layers3,
      description: 'Short Straddle Double Hedge - sell ATM straddle + buy OTM wing hedges',
      group: 'Algorithms',
    },
    {
      id: 'zero_dte',
      label: '⏱️ 0DTE Trading',
      icon: Timer,
      description: '0DTE options - autonomous strangle with premium balancing',
      group: 'Algorithms',
    },
    // ── Analytics ────────────────────────────────────────────
    {
      id: 'oi',
      label: '📊 OI Dashboard',
      icon: BarChart3,
      description: 'Open Interest aggregator — multi-exchange OI, spike alerts, PCR',
      group: 'Analytics',
    },
    // ── Signals & ML ─────────────────────────────────────────
    {
      id: 'tradingview',
      label: '📊 TradingView',
      icon: RadioTower,
      description: 'TradingView webhook signals - buy/sell alerts from Pine Script',
      group: 'Signals & ML',
    },
    {
      id: 'rsi',
      label: 'RSI',
      icon: BarChart3,
      description: 'RSI safety monitor - mode-specific thresholds with hysteresis',
      group: 'Signals & ML',
    },
    {
      id: 'ml_trading',
      label: 'ML',
      icon: Brain,
      description:
        'Machine Learning trading insights, style analysis, and autonomous decision engine',
      group: 'Signals & ML',
    },
    // ── System ───────────────────────────────────────────────
    {
      id: 'botmanagement',
      label: 'Bot Management',
      icon: Terminal,
      description: 'tmux control, process management, and emergency controls',
      group: 'System',
    },
    {
      id: 'todos',
      label: 'Todo List',
      icon: ListChecks,
      description: 'Track improvements and ideas for the trading bot',
      group: 'System',
    },
    // ── Labs ─────────────────────────────────────────────────
    {
      id: 'advanced_features',
      label: '🚀 Advanced',
      icon: Database,
      description: 'Advanced data collection - Delta Exchange OHLCV, live streaming, technical indicators',
      group: 'Labs',
    },
  ];
}
