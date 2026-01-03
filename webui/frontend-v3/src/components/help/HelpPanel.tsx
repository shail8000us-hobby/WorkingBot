'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  HelpCircle,
  Search,
  Book,
  Settings,
  Shield,
  TrendingUp,
  Code,
  ExternalLink,
} from 'lucide-react';

interface HelpTopic {
  id: string;
  title: string;
  category: 'getting-started' | 'configuration' | 'trading' | 'safety' | 'api' | 'troubleshooting';
  content: string;
  keywords: string[];
}

const helpTopics: HelpTopic[] = [
  {
    id: 'bot-overview',
    title: 'Bot Overview',
    category: 'getting-started',
    content: 'The GridBot automates trading using a grid strategy. It places buy and sell orders at predefined price levels to profit from market volatility.',
    keywords: ['bot', 'overview', 'introduction', 'basics'],
  },
  {
    id: 'grid-configuration',
    title: 'Grid Configuration',
    category: 'configuration',
    content: 'Configure grid parameters including upper/lower bounds, step size, and lot size. The grid mode can be arithmetic or geometric.',
    keywords: ['grid', 'configuration', 'settings', 'parameters'],
  },
  {
    id: 'safety-settings',
    title: 'Safety Settings',
    category: 'safety',
    content: 'Safety features include max account loss, auto margin top-up, and stop loss limits. These protect your account from excessive losses.',
    keywords: ['safety', 'risk', 'protection', 'stop-loss'],
  },
  {
    id: 'position-monitoring',
    title: 'Position Monitoring',
    category: 'trading',
    content: 'Monitor open positions, track PnL, and manage position sizes. The dashboard shows real-time position status and profit/loss.',
    keywords: ['position', 'monitoring', 'pnl', 'profit', 'loss'],
  },
  {
    id: 'api-keys',
    title: 'API Key Setup',
    category: 'api',
    content: 'Add exchange API keys with read and trade permissions. Keys are stored securely and used for placing orders and fetching account data.',
    keywords: ['api', 'keys', 'exchange', 'authentication'],
  },
  {
    id: 'bot-not-trading',
    title: 'Bot Not Trading',
    category: 'troubleshooting',
    content: 'If bot is not placing orders, check: 1) Bot is running, 2) API keys are valid, 3) Exchange connection is active, 4) Grid parameters are correct.',
    keywords: ['troubleshooting', 'not trading', 'orders', 'problems'],
  },
  {
    id: 'margin-management',
    title: 'Margin Management',
    category: 'trading',
    content: 'Monitor margin usage and available balance. Enable auto margin top-up to prevent liquidation. Set margin warnings at appropriate levels.',
    keywords: ['margin', 'leverage', 'balance', 'liquidation'],
  },
  {
    id: 'error-logs',
    title: 'Understanding Error Logs',
    category: 'troubleshooting',
    content: 'Error logs show system issues, API errors, and trading problems. Check error severity and take action for critical errors.',
    keywords: ['errors', 'logs', 'debugging', 'issues'],
  },
  {
    id: 'webhooks',
    title: 'Webhook Configuration',
    category: 'api',
    content: 'Configure webhooks to receive real-time notifications about trades, orders, and system events. Supports Telegram, Discord, and custom endpoints.',
    keywords: ['webhooks', 'notifications', 'alerts', 'telegram'],
  },
  {
    id: 'performance-metrics',
    title: 'Performance Metrics',
    category: 'trading',
    content: 'Track win rate, profit factor, Sharpe ratio, and other performance metrics. Use analytics to optimize your trading strategy.',
    keywords: ['performance', 'metrics', 'analytics', 'statistics'],
  },
];

const categories = [
  { id: 'all', label: 'All Topics', icon: Book },
  { id: 'getting-started', label: 'Getting Started', icon: HelpCircle },
  { id: 'configuration', label: 'Configuration', icon: Settings },
  { id: 'trading', label: 'Trading', icon: TrendingUp },
  { id: 'safety', label: 'Safety', icon: Shield },
  { id: 'api', label: 'API', icon: Code },
  { id: 'troubleshooting', label: 'Troubleshooting', icon: HelpCircle },
];

export function HelpPanel() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);

  const filteredTopics = helpTopics.filter((topic) => {
    const matchesCategory = selectedCategory === 'all' || topic.category === selectedCategory;
    const matchesSearch =
      searchQuery === '' ||
      topic.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      topic.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
      topic.keywords.some((keyword) =>
        keyword.toLowerCase().includes(searchQuery.toLowerCase())
      );
    return matchesCategory && matchesSearch;
  });

  const selected = helpTopics.find((t) => t.id === selectedTopic);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <HelpCircle className="h-5 w-5" />
          Help & Documentation
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search help topics..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Categories */}
        <div className="flex items-center gap-2 flex-wrap">
          {categories.map((category) => {
            const Icon = category.icon;
            return (
              <Badge
                key={category.id}
                variant={selectedCategory === category.id ? 'default' : 'outline'}
                className="cursor-pointer"
                onClick={() => setSelectedCategory(category.id)}
              >
                <Icon className="h-3 w-3 mr-1" />
                {category.label}
              </Badge>
            );
          })}
        </div>

        {/* Content */}
        <div className="grid grid-cols-2 gap-4">
          {/* Topics List */}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold mb-2">
              Topics ({filteredTopics.length})
            </h3>
            <ScrollArea className="h-[400px] pr-4">
              <div className="space-y-2">
                {filteredTopics.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <HelpCircle className="h-12 w-12 mx-auto mb-3 opacity-20" />
                    <p>No topics found</p>
                  </div>
                ) : (
                  filteredTopics.map((topic) => (
                    <Card
                      key={topic.id}
                      className={`p-3 cursor-pointer transition-colors hover:bg-muted/50 ${
                        selectedTopic === topic.id ? 'border-primary bg-muted/30' : ''
                      }`}
                      onClick={() => setSelectedTopic(topic.id)}
                    >
                      <div className="flex items-start justify-between mb-1">
                        <h4 className="font-semibold text-sm">{topic.title}</h4>
                        <Badge variant="outline" className="text-xs">
                          {topic.category.replace('-', ' ')}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-2">
                        {topic.content}
                      </p>
                    </Card>
                  ))
                )}
              </div>
            </ScrollArea>
          </div>

          {/* Topic Detail */}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold mb-2">Details</h3>
            {selected ? (
              <Card className="p-4">
                <div className="mb-4">
                  <div className="flex items-start justify-between mb-2">
                    <h2 className="text-lg font-bold">{selected.title}</h2>
                    <Badge variant="secondary">
                      {selected.category.replace('-', ' ')}
                    </Badge>
                  </div>
                  <ScrollArea className="h-[350px]">
                    <p className="text-sm leading-relaxed mb-4">{selected.content}</p>
                    <div className="space-y-2 text-sm">
                      <h3 className="font-semibold">Keywords:</h3>
                      <div className="flex flex-wrap gap-2">
                        {selected.keywords.map((keyword, idx) => (
                          <Badge key={idx} variant="outline" className="text-xs">
                            {keyword}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </ScrollArea>
                </div>
              </Card>
            ) : (
              <Card className="p-8 text-center">
                <Book className="h-12 w-12 mx-auto mb-3 opacity-20" />
                <p className="text-sm text-muted-foreground">
                  Select a topic to view details
                </p>
              </Card>
            )}
          </div>
        </div>

        {/* Quick Links */}
        <div className="mt-6 p-4 border-t">
          <h3 className="text-sm font-semibold mb-3">Quick Links</h3>
          <div className="grid grid-cols-2 gap-3">
            <a
              href="https://docs.example.com"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-primary hover:underline"
            >
              <ExternalLink className="h-4 w-4" />
              Full Documentation
            </a>
            <a
              href="https://github.com/example/gridbot"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-primary hover:underline"
            >
              <ExternalLink className="h-4 w-4" />
              GitHub Repository
            </a>
            <a
              href="https://discord.gg/example"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-primary hover:underline"
            >
              <ExternalLink className="h-4 w-4" />
              Discord Community
            </a>
            <a
              href="https://t.me/example"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-primary hover:underline"
            >
              <ExternalLink className="h-4 w-4" />
              Telegram Support
            </a>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
