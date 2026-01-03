'use client'

import { useSystemHealth } from '@/hooks/useQueries'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Activity,
  Cpu,
  HardDrive,
  MemoryStick,
  Wifi,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
} from 'lucide-react'

export function HealthDashboard() {
  const { data: response, isLoading, error } = useSystemHealth();
  
  const health = response?.summary;
  const overallHealth = response?.overall_health;

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            System Health
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <div className="animate-pulse text-sm text-muted-foreground">
              Loading system health...
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            System Health
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-sm text-destructive">
            <AlertTriangle className="h-4 w-4" />
            Failed to load system health
          </div>
        </CardContent>
      </Card>
    )
  }

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'healthy':
      case 'ok':
      case 'connected':
        return 'bg-green-500/10 text-green-500 border-green-500/20'
      case 'warning':
      case 'degraded':
        return 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20'
      case 'error':
      case 'critical':
      case 'disconnected':
        return 'bg-red-500/10 text-red-500 border-red-500/20'
      default:
        return 'bg-muted text-muted-foreground'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'healthy':
      case 'ok':
      case 'connected':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />
      case 'warning':
      case 'degraded':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />
      case 'error':
      case 'critical':
      case 'disconnected':
        return <XCircle className="h-4 w-4 text-red-500" />
      default:
        return <Activity className="h-4 w-4 text-muted-foreground" />
    }
  }

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)

    if (days > 0) return `${days}d ${hours}h ${minutes}m`
    if (hours > 0) return `${hours}h ${minutes}m`
    return `${minutes}m`
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {/* Overall Status */}
      <Card className="md:col-span-2 lg:col-span-3">
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              System Health
            </div>
            {overallHealth && (
              <Badge className={getStatusColor(overallHealth)}>
                {overallHealth.toUpperCase()}
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {health?.system?.timestamp && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Clock className="h-4 w-4" />
              Last Updated: {new Date(health.system.timestamp).toLocaleString()}
            </div>
          )}
        </CardContent>
      </Card>

      {/* CPU Usage */}
      {health?.system?.cpu_percent !== undefined && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Cpu className="h-4 w-4" />
              CPU Usage
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-2xl font-bold">{health.system.cpu_percent.toFixed(1)}%</span>
                {getStatusIcon(
                  health.system.cpu_percent > 80 ? 'warning' : health.system.cpu_percent > 95 ? 'critical' : 'ok'
                )}
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all ${
                    health.system.cpu_percent > 80
                      ? 'bg-red-500'
                      : health.system.cpu_percent > 60
                      ? 'bg-yellow-500'
                      : 'bg-green-500'
                  }`}
                  style={{ width: `${Math.min(health.system.cpu_percent, 100)}%` }}
                />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Memory Usage */}
      {health?.system?.memory_percent !== undefined && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <MemoryStick className="h-4 w-4" />
              Memory Usage
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-2xl font-bold">{health.system.memory_percent.toFixed(1)}%</span>
                {getStatusIcon(
                  health.system.memory_percent > 85 ? 'warning' : health.system.memory_percent > 95 ? 'critical' : 'ok'
                )}
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all ${
                    health.system.memory_percent > 85
                      ? 'bg-red-500'
                      : health.system.memory_percent > 70
                      ? 'bg-yellow-500'
                      : 'bg-green-500'
                  }`}
                  style={{ width: `${Math.min(health.system.memory_percent, 100)}%` }}
                />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Disk Usage */}
      {health?.system?.disk_percent !== undefined && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <HardDrive className="h-4 w-4" />
              Disk Usage
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-2xl font-bold">{health.system.disk_percent.toFixed(1)}%</span>
                {getStatusIcon(
                  health.system.disk_percent > 85 ? 'warning' : health.system.disk_percent > 95 ? 'critical' : 'ok'
                )}
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all ${
                    health.system.disk_percent > 85
                      ? 'bg-red-500'
                      : health.system.disk_percent > 70
                      ? 'bg-yellow-500'
                      : 'bg-green-500'
                  }`}
                  style={{ width: `${Math.min(health.system.disk_percent, 100)}%` }}
                />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* API Status */}
      {/* Active Alerts */}
      {health?.alerts && health.alerts.total > 0 && (
        <Card className="col-span-full">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              Active Alerts ({health.alerts.total})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center p-3 border rounded">
                <div className="text-2xl font-bold">{health.alerts.total}</div>
                <div className="text-xs text-muted-foreground">Total</div>
              </div>
              <div className="text-center p-3 border rounded">
                <div className="text-2xl font-bold text-yellow-600">{health.alerts.warning}</div>
                <div className="text-xs text-muted-foreground">Warnings</div>
              </div>
              <div className="text-center p-3 border rounded">
                <div className="text-2xl font-bold text-red-600">{health.alerts.critical}</div>
                <div className="text-xs text-muted-foreground">Critical</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Processes Status */}
      {health?.processes && (
        <Card className="col-span-full">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Processes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center p-3 border rounded">
                <div className="text-2xl font-bold">{health.processes.total}</div>
                <div className="text-xs text-muted-foreground">Total</div>
              </div>
              <div className="text-center p-3 border rounded">
                <div className="text-2xl font-bold text-green-600">{health.processes.running}</div>
                <div className="text-xs text-muted-foreground">Running</div>
              </div>
              <div className="text-center p-3 border rounded">
                <div className="text-2xl font-bold text-red-600">{health.processes.crashed}</div>
                <div className="text-xs text-muted-foreground">Crashed</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
