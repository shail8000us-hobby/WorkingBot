'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Settings, Search, Shield, TrendingUp, Activity } from 'lucide-react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

interface ConfigResponse {
  success: boolean
  config: Record<string, string>
  meta: Record<string, {
    has_value: boolean
    section: string
    source_key: string
    redacted: boolean
  }>
}

async function fetchConfig(): Promise<ConfigResponse> {
  // API URL - use the same logic as api.ts
  const API_URL = (typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
    : 'http://localhost:5557'
  ).trim();
  
  const res = await fetch(`${API_URL}/api/config`)
  if (!res.ok) throw new Error('Failed to fetch config')
  return res.json()
}

export function ConfigViewer() {
  const [searchTerm, setSearchTerm] = useState('')
  const { data, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: fetchConfig,
    refetchInterval: 30000,
  })

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Configuration
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-muted-foreground">Loading configuration...</div>
        </CardContent>
      </Card>
    )
  }

  if (!data?.success || !data.config) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Configuration
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-muted-foreground">Failed to load configuration</div>
        </CardContent>
      </Card>
    )
  }

  // Group config by section
  const sections: Record<string, Array<{ key: string; value: string; redacted: boolean }>> = {}
  
  Object.entries(data.config).forEach(([key, value]) => {
    const meta = data.meta?.[key]
    const section = meta?.section || 'Other'
    const redacted = meta?.redacted || false
    
    if (!sections[section]) {
      sections[section] = []
    }
    
    // Filter by search term
    if (searchTerm && !key.toLowerCase().includes(searchTerm.toLowerCase())) {
      return
    }
    
    sections[section].push({ key, value, redacted })
  })

  const sectionIcons: Record<string, any> = {
    'Grid Configuration': TrendingUp,
    'Risk Management': Shield,
    'Trading': Activity,
    'General': Settings,
  }

  // Critical config items to highlight
  const criticalKeys = [
    'TRADING_MODE',
    'GRIDBOT_SYMBOL',
    'GRIDBOT_LOWER',
    'GRIDBOT_UPPER',
    'GRIDBOT_STEP',
    'GUARDIAN_ENABLED',
    'GUARDIAN_MAX_ACCOUNT_LOSS_INR',
  ]

  return (
    <Card className="col-span-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              Configuration Viewer
            </CardTitle>
            <CardDescription>
              System configuration and parameters
            </CardDescription>
          </div>
          <Badge variant="outline">
            {Object.keys(data.config).length} settings
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search configuration..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9"
          />
        </div>

        {/* Critical Settings */}
        {!searchTerm && (
          <div className="space-y-2">
            <h3 className="text-sm font-medium text-muted-foreground">Critical Settings</h3>
            <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
              {criticalKeys.map((key) => {
                const value = data.config[key]
                const meta = data.meta?.[key]
                if (!value) return null
                return (
                  <div key={key} className="p-3 rounded-lg border bg-card">
                    <div className="text-xs text-muted-foreground">{key.replace(/_/g, ' ')}</div>
                    <div className="font-mono text-sm font-medium mt-1">
                      {meta?.redacted ? '***REDACTED***' : value}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Configuration Sections */}
        <Tabs defaultValue={Object.keys(sections)[0]} className="w-full">
          <TabsList className="flex-wrap h-auto">
            {Object.keys(sections).sort().map((section) => {
              const Icon = sectionIcons[section] || Settings
              return (
                <TabsTrigger key={section} value={section} className="gap-2">
                  <Icon className="h-4 w-4" />
                  {section}
                  <Badge variant="secondary" className="ml-1">
                    {sections[section].length}
                  </Badge>
                </TabsTrigger>
              )
            })}
          </TabsList>

          {Object.entries(sections).map(([section, items]) => (
            <TabsContent key={section} value={section} className="space-y-2 mt-4">
              <div className="grid gap-2 max-h-[500px] overflow-y-auto">
                {items.map(({ key, value, redacted }) => (
                  <div
                    key={key}
                    className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{key}</div>
                      <div className="text-xs text-muted-foreground">
                        {data.meta?.[key]?.source_key || key}
                      </div>
                    </div>
                    <div className="ml-4 text-sm font-mono text-right">
                      {redacted ? (
                        <Badge variant="secondary">REDACTED</Badge>
                      ) : (
                        <span className="break-all">{value}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </TabsContent>
          ))}
        </Tabs>
      </CardContent>
    </Card>
  )
}
