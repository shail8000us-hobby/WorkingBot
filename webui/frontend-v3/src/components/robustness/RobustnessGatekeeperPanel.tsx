'use client'

import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Shield, CheckCircle2, XCircle } from 'lucide-react'

interface GatekeeperStatus {
  success: boolean
  enabled: boolean
  stats: {
    checks: number
    blocks: number
    block_rate: number
    last_block_reason: string | null
  }
}

async function fetchGatekeeperStatus(): Promise<GatekeeperStatus> {
  const res = await fetch('http://localhost:5555/api/robustness/gatekeeper/status')
  if (!res.ok) throw new Error('Failed to fetch gatekeeper status')
  return res.json()
}

export function RobustnessGatekeeperPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ['gatekeeper-status'],
    queryFn: fetchGatekeeperStatus,
    refetchInterval: 5000,
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield className="h-5 w-5" />
          Safety Gatekeeper
        </CardTitle>
        <CardDescription>Pre-trade risk checks and validation</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="text-sm text-muted-foreground">Loading...</div>
        ) : !data?.success ? (
          <div className="text-sm text-muted-foreground">Failed to load data</div>
        ) : (
          <div className="space-y-4">
            {/* Status */}
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Status</span>
              {data.enabled ? (
                <Badge className="bg-green-500 flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  Active
                </Badge>
              ) : (
                <Badge variant="destructive" className="flex items-center gap-1">
                  <XCircle className="h-3 w-3" />
                  Disabled
                </Badge>
              )}
            </div>

            {/* Statistics */}
            <div className="grid grid-cols-2 gap-4 pt-2 border-t">
              <div>
                <div className="text-xs text-muted-foreground">Total Checks</div>
                <div className="text-2xl font-bold">{data.stats.checks.toLocaleString()}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Blocks</div>
                <div className="text-2xl font-bold text-red-500">{data.stats.blocks}</div>
              </div>
            </div>

            {/* Block Rate */}
            <div className="flex items-center justify-between pt-2 border-t">
              <span className="text-sm text-muted-foreground">Block Rate</span>
              <span className="text-sm font-medium">
                {(data.stats.block_rate * 100).toFixed(2)}%
              </span>
            </div>

            {/* Last Block Reason */}
            {data.stats.last_block_reason && (
              <div className="pt-2 border-t">
                <div className="text-xs text-muted-foreground mb-1">Last Block Reason</div>
                <div className="text-sm p-2 rounded-md bg-destructive/10 text-destructive">
                  {data.stats.last_block_reason}
                </div>
              </div>
            )}

            {/* All Clear */}
            {data.stats.blocks === 0 && (
              <div className="flex items-center gap-2 py-2 text-sm text-green-500">
                <CheckCircle2 className="h-4 w-4" />
                All checks passing - No blocks
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
