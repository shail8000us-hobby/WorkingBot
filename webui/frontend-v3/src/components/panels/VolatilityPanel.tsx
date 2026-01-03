'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { TrendingUp, TrendingDown, Activity, AlertTriangle } from 'lucide-react'
import { useVolatility } from '@/hooks'

export function VolatilityPanel() {
  const { data, isLoading, error } = useVolatility()

  const getBadgeColor = (color: string) => {
    switch (color.toLowerCase()) {
      case 'green':
        return 'bg-green-500/10 text-green-500 border-green-500/20'
      case 'yellow':
        return 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20'
      case 'red':
        return 'bg-red-500/10 text-red-500 border-red-500/20'
      default:
        return 'bg-muted text-muted-foreground'
    }
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Market Volatility
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <div className="animate-pulse text-sm text-muted-foreground">
              Loading volatility data...
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
            Market Volatility
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-sm text-destructive">
            <AlertTriangle className="h-4 w-4" />
            Failed to load volatility data
          </div>
        </CardContent>
      </Card>
    )
  }

  const vol = data

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5" />
          Market Volatility
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Volatility Signal */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Signal</span>
          <Badge className={getBadgeColor(vol.volatility_signal.color)}>
            {vol.volatility_signal.value.replace(/_/g, ' ')}
          </Badge>
        </div>

        {/* Market Regime */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Market Regime</span>
          <Badge className={getBadgeColor(vol.market_regime.color)}>
            {vol.market_regime.value.replace(/_/g, ' ')}
          </Badge>
        </div>

        {/* IV/RV Spread */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">IV/RV Spread</span>
            <span className="text-sm font-medium">
              {vol.volatility_signal.spread.toFixed(2)}%
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="flex items-center gap-1">
              <span className="text-muted-foreground">IV:</span>
              <span className="font-medium">{vol.volatility_signal.iv.toFixed(2)}%</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-muted-foreground">RV:</span>
              <span className="font-medium">{vol.volatility_signal.rv.toFixed(2)}%</span>
            </div>
          </div>
        </div>

        {/* Overall Risk */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Risk Level</span>
          <Badge className={getBadgeColor(vol.overall_risk_status.color)}>
            {vol.overall_risk_status.value} RISK
          </Badge>
        </div>

        {/* Grid Suitability */}
        <div className="pt-2 border-t space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Grid Suitability</span>
            <Badge className={getBadgeColor(vol.grid_suitability.color)}>
              {vol.grid_suitability.rating}
            </Badge>
          </div>
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Score</span>
              <span className="font-medium">
                {vol.grid_suitability.score}/{vol.grid_suitability.score_max}
              </span>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div
                className={`h-full transition-all ${
                  vol.grid_suitability.color === 'green'
                    ? 'bg-green-500'
                    : vol.grid_suitability.color === 'yellow'
                    ? 'bg-yellow-500'
                    : 'bg-red-500'
                }`}
                style={{
                  width: `${(vol.grid_suitability.score / vol.grid_suitability.score_max) * 100}%`,
                }}
              />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
