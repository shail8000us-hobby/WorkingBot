'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Shield, Activity, AlertTriangle, CheckCircle2, Clock } from 'lucide-react'
import { useGuardianStatus } from '@/hooks'

export function GuardianDashboard() {
  const { data, isLoading } = useGuardianStatus()

  const isRunning = data?.running || data?.active || false

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield className="h-5 w-5" />
          Guardian Bot
        </CardTitle>
        <CardDescription>Autonomous safety monitoring system</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="text-sm text-muted-foreground">Loading...</div>
        ) : !data ? (
          <div className="text-sm text-muted-foreground">Guardian offline</div>
        ) : (
          <div className="space-y-4">
            {/* Status */}
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Status</span>
              {isRunning ? (
                <Badge className="bg-green-500 flex items-center gap-1">
                  <Activity className="h-3 w-3" />
                  Active
                </Badge>
              ) : (
                <Badge variant="outline" className="flex items-center gap-1">
                  <AlertTriangle className="h-3 w-3" />
                  Inactive
                </Badge>
              )}
            </div>

            {/* Check Statistics */}
            {data.checks && (
              <div className="grid grid-cols-2 gap-4 pt-2 border-t">
                <div>
                  <div className="text-xs text-muted-foreground">Checks Performed</div>
                  <div className="text-2xl font-bold text-blue-500 flex items-center gap-2">
                    <Activity className="h-5 w-5" />
                    {Object.keys(data.checks).length}
                  </div>
                </div>
                {data.blockers && data.blockers.length > 0 && (
                  <div>
                    <div className="text-xs text-muted-foreground">Active Blockers</div>
                    <div className="text-2xl font-bold text-red-500 flex items-center gap-2">
                      <AlertTriangle className="h-5 w-5" />
                      {data.blockers.length}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Last Check Time */}
            {data.lastCheck && (
              <div className="flex items-center justify-between pt-2 border-t">
                <span className="text-sm text-muted-foreground flex items-center gap-1">
                  <Clock className="h-4 w-4" />
                  Last Check
                </span>
                <span className="text-sm font-medium">
                  {new Date(data.lastCheck * 1000).toLocaleTimeString()}
                </span>
              </div>
            )}

            {/* Reason/Blockers */}
            {data.reason && (
              <div className="pt-2 border-t">
                <div className="text-xs text-muted-foreground mb-1">Status Reason</div>
                <div className="text-sm">{data.reason}</div>
              </div>
            )}
            
            {data.blockers && data.blockers.length > 0 && (
              <div className="pt-2 border-t">
                <div className="text-xs text-muted-foreground mb-2">Active Blockers</div>
                <div className="space-y-1">
                  {data.blockers.map((blocker: { name: string; reason: string }, idx: number) => (
                    <div key={idx} className="text-sm p-2 bg-red-500/10 border border-red-500/20 rounded">
                      <div className="font-medium text-red-500">{blocker.name}</div>
                      <div className="text-xs text-muted-foreground">{blocker.reason}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Guardian Features */}
            <div className="pt-2 border-t">
              <div className="text-xs text-muted-foreground mb-2">Monitoring</div>
              <div className="space-y-1 text-sm">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                  <span>Position Risk Management</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                  <span>Capital Protection</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                  <span>Market Anomaly Detection</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                  <span>Emergency Shutdown</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}