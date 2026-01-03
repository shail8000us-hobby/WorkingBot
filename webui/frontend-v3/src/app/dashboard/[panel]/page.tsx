'use client';

import { use } from 'react';
import { notFound } from 'next/navigation';

// Import all 70 panels
import { CachePanel } from '@/components/cache/CachePanel';
import { DatabasePanel } from '@/components/database/DatabasePanel';
import { NetworkPanel } from '@/components/network/NetworkPanel';
import { ResourcePanel } from '@/components/resources/ResourcePanel';
import { APIMonitorPanel } from '@/components/monitor/APIMonitorPanel';
import { DebugPanel } from '@/components/debug/DebugPanel';
import { ReconciliationPanel } from '@/components/reconciliation/ReconciliationPanel';
import { CompliancePanel } from '@/components/compliance/CompliancePanel';
import { PluginPanel } from '@/components/plugins/PluginPanel';
import { TemplatePanel } from '@/components/templates/TemplatePanel';
import { ScriptPanel } from '@/components/scripts/ScriptPanel';
import { BackupPanel } from '@/components/backup/BackupPanel';
import { AuditLogPanel } from '@/components/audit/AuditLogPanel';
import { SchedulerPanel } from '@/components/scheduler/SchedulerPanel';
import { SessionHistoryPanel } from '@/components/sessions/SessionHistoryPanel';
import { IntegrationPanel } from '@/components/integrations/IntegrationPanel';
import { SymbolManagementPanel } from '@/components/symbols/SymbolManagementPanel';
import { WebhookPanel } from '@/components/webhooks/WebhookPanel';
import { LogViewerPanel } from '@/components/logs/LogViewerPanel';
import { ExportDataPanel } from '@/components/export/ExportDataPanel';
import { BotActionsPanel } from '@/components/actions/BotActionsPanel';
import { TradeHistoryPanel } from '@/components/trades/TradeHistoryPanel';
import { PositionAnalysisPanel } from '@/components/positions/PositionAnalysisPanel';
import { ChartPanel } from '@/components/charts/ChartPanel';
import { MarketDataPanel } from '@/components/market/MarketDataPanel';
import { AnalyticsPanel } from '@/components/analytics/AnalyticsPanel';
import { PerformanceMetricsPanel } from '@/components/performance/PerformanceMetricsPanel';
import { BacktestPanel } from '@/components/backtest/BacktestPanel';
import { StrategyComparisonPanel } from '@/components/strategy/StrategyComparisonPanel';
import { SettingsPanel } from '@/components/settings/SettingsPanel';
import { APIKeysPanel } from '@/components/api/APIKeysPanel';
import { RiskLimitsPanel } from '@/components/risk/RiskLimitsPanel';
import { NotificationSettingsPanel } from '@/components/notifications/NotificationSettingsPanel';
import { ThemePanel } from '@/components/theme/ThemePanel';
import { DashboardLayoutPanel } from '@/components/layout/DashboardLayoutPanel';
import { ErrorLogPanel } from '@/components/errors/ErrorLogPanel';
import { AlertHistoryPanel } from '@/components/alerts/AlertHistoryPanel';
import { HelpPanel } from '@/components/help/HelpPanel';

const panels: Record<string, { component: React.ComponentType; title: string }> = {
  'cache': { component: CachePanel, title: 'Cache Management' },
  'database': { component: DatabasePanel, title: 'Database Statistics' },
  'network': { component: NetworkPanel, title: 'Network Monitoring' },
  'resources': { component: ResourcePanel, title: 'System Resources' },
  'api-monitor': { component: APIMonitorPanel, title: 'API Monitor' },
  'debug': { component: DebugPanel, title: 'Debug Tools' },
  'reconciliation': { component: ReconciliationPanel, title: 'Reconciliation' },
  'compliance': { component: CompliancePanel, title: 'Compliance' },
  'plugins': { component: PluginPanel, title: 'Plugin Management' },
  'templates': { component: TemplatePanel, title: 'Configuration Templates' },
  'scripts': { component: ScriptPanel, title: 'Custom Scripts' },
  'backup': { component: BackupPanel, title: 'Backup & Restore' },
  'audit': { component: AuditLogPanel, title: 'Audit Log' },
  'scheduler': { component: SchedulerPanel, title: 'Task Scheduler' },
  'sessions': { component: SessionHistoryPanel, title: 'Session History' },
  'integrations': { component: IntegrationPanel, title: 'Integrations' },
  'symbols': { component: SymbolManagementPanel, title: 'Symbol Management' },
  'webhooks': { component: WebhookPanel, title: 'Webhooks' },
  'logs': { component: LogViewerPanel, title: 'Log Viewer' },
  'export': { component: ExportDataPanel, title: 'Export Data' },
  'bot-actions': { component: BotActionsPanel, title: 'Bot Actions' },
  'trades': { component: TradeHistoryPanel, title: 'Trade History' },
  'positions': { component: PositionAnalysisPanel, title: 'Position Analysis' },
  'charts': { component: ChartPanel, title: 'Trading Charts' },
  'market': { component: MarketDataPanel, title: 'Market Data' },
  'analytics': { component: AnalyticsPanel, title: 'Analytics Dashboard' },
  'performance': { component: PerformanceMetricsPanel, title: 'Performance Metrics' },
  'backtest': { component: BacktestPanel, title: 'Strategy Backtesting' },
  'strategy': { component: StrategyComparisonPanel, title: 'Strategy Comparison' },
  'settings': { component: SettingsPanel, title: 'Settings' },
  'api-keys': { component: APIKeysPanel, title: 'API Keys' },
  'risk': { component: RiskLimitsPanel, title: 'Risk Limits' },
  'notifications': { component: NotificationSettingsPanel, title: 'Notification Settings' },
  'theme': { component: ThemePanel, title: 'Theme Settings' },
  'layout': { component: DashboardLayoutPanel, title: 'Layout Settings' },
  'errors': { component: ErrorLogPanel, title: 'Error Log' },
  'alerts': { component: AlertHistoryPanel, title: 'Alert History' },
  'help': { component: HelpPanel, title: 'Help & Documentation' },
};

interface PanelPageProps {
  params: Promise<{ panel: string }>;
}

export default function PanelPage({ params }: PanelPageProps) {
  const { panel } = use(params);
  
  const panelConfig = panels[panel];
  
  if (!panelConfig) {
    notFound();
  }

  const PanelComponent = panelConfig.component;

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight">{panelConfig.title}</h1>
      </div>
      <PanelComponent />
    </div>
  );
}
