'use client'

import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { AlertTriangle, CheckCircle2, Shield } from 'lucide-react'

interface ErrorStats {
  success: boolean
  statistics: {
    total: number
    by_status: {
      open: number
      acknowledged: number
      resolved: number
    }
    by_severity: {
      critical: number
      high: number
      medium: number
      low: number
    }
  }
}

async function fetchErrorStats(): Promise<ErrorStats> {
  const res = await fetch('http://localhost:5555/api/errors/statistics')
  if (!res.ok) throw new Error('Failed to fetch error statistics')
  return res.json()
}

export function ErrorIntelligencePanel() {
  const { data, isLoading } = useQuery({
    queryKey: ['error-stats'],
    queryFn: fetchErrorStats,
    refetchInterval: 15000,
  })

  const stats = data?.statistics

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5" />
          Error Intelligence
        </CardTitle>
        <CardDescription>System error tracking and statistics</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="text-sm text-muted-foreground">Loading...</div>
        ) : !stats ? (
          <div className="text-sm text-muted-foreground">No data available</div>
        ) : (
          <div className="space-y-4">
            {/* Total Errors */}
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Total Errors</span>
              <span className="text-2xl font-bold">{stats.total}</span>
            </div>

            {/* By Status */}
            {stats.total > 0 && (
              <div className="space-y-2 pt-2 border-t">
                <div className="text-xs font-medium text-muted-foreground">By Status</div>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Open</span>
                    <Badge variant="destructive">{stats.by_status.open}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Ack</span>
                    <Badge variant="outline">{stats.by_status.acknowledged}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Resolved</span>
                    <Badge className="bg-green-500">{stats.by_status.resolved}</Badge>
                  </div>
                </div>
              </div>
            )}

            {/* By Severity */}
            {stats.total > 0 && (
              <div className="space-y-2 pt-2 border-t">
                <div className="text-xs font-medium text-muted-foreground">By Severity</div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Critical</span>
                    <Badge variant="destructive">{stats.by_severity.critical}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">High</span>
                    <Badge className="bg-orange-500">{stats.by_severity.high}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Medium</span>
                    <Badge className="bg-yellow-500">{stats.by_severity.medium}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Low</span>
                    <Badge variant="outline">{stats.by_severity.low}</Badge>
                  </div>
                </div>
              </div>
            )}

            {/* All Clear */}
            {stats.total === 0 && (
              <div className="flex items-center gap-2 py-4 text-sm text-green-500">
                <CheckCircle2 className="h-4 w-4" />
                No errors detected - System healthy
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
