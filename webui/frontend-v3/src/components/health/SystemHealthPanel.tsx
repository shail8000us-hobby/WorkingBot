'use client'

import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Activity,
  Cpu,
  HardDrive,
  MemoryStick,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
} from 'lucide-react'

interface HealthData {
  success: boolean
  data: {
    status: string
    uptime: {
      formatted: string
      seconds: number
    }
    resources: {
      cpu: {
        percent: number
        cores: number
        healthy: boolean
      }
      memory: {
        percent_used: number
        total_gb: number
        used_gb: number
        available_gb: number
        healthy: boolean
      }
      disk: {
        percent_used: number
        total_gb: number
        used_gb: number
        free_gb: number
        healthy: boolean
      }
    }
    services: {
      trading_bot: {
        status: string
        healthy: boolean
      }
      guardian_bot: {
        status: string
        healthy: boolean
      }
    }
    circuit_breakers?: Record<string, any>
    dependencies?: Record<string, any>
  }
}

import { useHealthDetailed } from '@/hooks'

export function SystemHealthPanel() {
  const { data, isLoading, error } = useHealthDetailed()

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'healthy':
      case 'running':
        return 'bg-green-500/10 text-green-500 border-green-500/20'
      case 'degraded':
      case 'warning':
        return 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20'
      case 'unhealthy':
      case 'stopped':
      case 'error':
        return 'bg-red-500/10 text-red-500 border-red-500/20'
      default:
        return 'bg-muted text-muted-foreground'
    }
  }

  const getResourceColor = (percent: number, isHealthy: boolean) => {
    if (!isHealthy) return 'bg-red-500'
    if (percent > 85) return 'bg-red-500'
    if (percent > 70) return 'bg-yellow-500'
    return 'bg-green-500'
  }

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

  if (error || !data) {
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

  const health = data

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {/* Overall Status */}
      <Card className="md:col-span-2 lg:col-span-4">
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              System Health
            </div>
            <Badge className={getStatusColor(health.status)}>
              {health.status.toUpperCase()}
            </Badge>
          </CardTitle>
          <CardDescription className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Uptime: {health.uptime.formatted}
          </CardDescription>
        </CardHeader>
      </Card>

      {/* CPU Usage */}
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
              <span className="text-2xl font-bold">{health.resources.cpu.percent.toFixed(1)}%</span>
              {health.resources.cpu.healthy ? (
                <CheckCircle2 className="h-4 w-4 text-green-500" />
              ) : (
                <XCircle className="h-4 w-4 text-red-500" />
              )}
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div
                className={`h-full transition-all ${getResourceColor(
                  health.resources.cpu.percent,
                  health.resources.cpu.healthy
                )}`}
                style={{ width: `${Math.min(health.resources.cpu.percent, 100)}%` }}
              />
            </div>
            <div className="text-xs text-muted-foreground">
              {health.resources.cpu.cores} cores
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Memory Usage */}
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
              <span className="text-2xl font-bold">
                {health.resources.memory.percent_used.toFixed(1)}%
              </span>
              {health.resources.memory.healthy ? (
                <CheckCircle2 className="h-4 w-4 text-green-500" />
              ) : (
                <XCircle className="h-4 w-4 text-red-500" />
              )}
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div
                className={`h-full transition-all ${getResourceColor(
                  health.resources.memory.percent_used,
                  health.resources.memory.healthy
                )}`}
                style={{ width: `${Math.min(health.resources.memory.percent_used, 100)}%` }}
              />
            </div>
            <div className="text-xs text-muted-foreground">
              {health.resources.memory.used_gb.toFixed(1)} GB / {health.resources.memory.total_gb.toFixed(1)} GB
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Disk Usage */}
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
              <span className="text-2xl font-bold">
                {health.resources.disk.percent_used.toFixed(1)}%
              </span>
              {health.resources.disk.healthy ? (
                <CheckCircle2 className="h-4 w-4 text-green-500" />
              ) : (
                <XCircle className="h-4 w-4 text-red-500" />
              )}
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div
                className={`h-full transition-all ${getResourceColor(
                  health.resources.disk.percent_used,
                  health.resources.disk.healthy
                )}`}
                style={{ width: `${Math.min(health.resources.disk.percent_used, 100)}%` }}
              />
            </div>
            <div className="text-xs text-muted-foreground">
              {health.resources.disk.free_gb.toFixed(1)} GB free / {health.resources.disk.total_gb.toFixed(1)} GB
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Services Status */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Services
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm">Trading Bot</span>
              <Badge className={getStatusColor(health.services.trading_bot.status)}>
                {health.services.trading_bot.status}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Guardian Bot</span>
              <Badge className={getStatusColor(health.services.guardian_bot.status)}>
                {health.services.guardian_bot.status}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
