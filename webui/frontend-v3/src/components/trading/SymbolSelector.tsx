'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { ChevronDown, Check, Circle } from 'lucide-react'

interface Symbol {
  name: string
  enabled: boolean
  mode?: string
  modes?: string[]
  product_id: number
  grid?: {
    lower: string
    upper: string
    step: string
    reference: string
  }
  limits?: {
    lot_size: string
    max_open_positions: string
    max_qty_per_order: string
  }
}

interface SymbolsResponse {
  symbols: Symbol[]
  total: number
  enabled_count: number
  config_version: string
  trading_mode: string
}

async function fetchSymbols(): Promise<SymbolsResponse> {
  const res = await fetch('http://localhost:5555/api/symbols')
  if (!res.ok) throw new Error('Failed to fetch symbols')
  return res.json()
}

export function SymbolSelector() {
  const { data, isLoading } = useQuery({
    queryKey: ['symbols'],
    queryFn: fetchSymbols,
    refetchInterval: 10000,
  })

  const [searchTerm, setSearchTerm] = useState('')
  const [selectedSymbol, setSelectedSymbol] = useState<string>('')

  const symbols = data?.symbols || []
  const filteredSymbols = symbols.filter((symbol) =>
    symbol?.name?.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const activeSymbol = symbols.find((s) => s.enabled)
  const currentSymbol = symbols.find((s) => s.name === selectedSymbol) || activeSymbol

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className="w-full justify-between">
          <div className="flex items-center gap-2">
            {currentSymbol?.enabled && (
              <Circle className="h-3 w-3 fill-green-500 text-green-500" />
            )}
            <span>{currentSymbol?.name || 'Select Symbol'}</span>
            {currentSymbol?.mode && (
              <Badge variant="outline" className="text-xs">
                {currentSymbol.mode}
              </Badge>
            )}
            {currentSymbol?.modes && currentSymbol.modes.length > 0 && (
              <Badge variant="outline" className="text-xs">
                {currentSymbol.modes[0]}
              </Badge>
            )}
          </div>
          <ChevronDown className="h-4 w-4 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[320px]">
        <DropdownMenuLabel>Trading Symbols</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <div className="p-2">
          <Input
            placeholder="Search symbols..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="mb-2"
          />
        </div>
        <DropdownMenuSeparator />
        <div className="max-h-[300px] overflow-y-auto">
          {isLoading ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              Loading symbols...
            </div>
          ) : filteredSymbols.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              No symbols found
            </div>
          ) : (
            filteredSymbols.map((symbol) => (
              <DropdownMenuItem
                key={symbol.name}
                onClick={() => setSelectedSymbol(symbol.name)}
                className="flex items-center justify-between cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  {symbol.enabled && (
                    <Circle className="h-3 w-3 fill-green-500 text-green-500" />
                  )}
                  <div>
                    <div className="font-medium">{symbol.name}</div>
                    {symbol.grid && (
                      <div className="text-xs text-muted-foreground">
                        Grid: {symbol.grid.lower} - {symbol.grid.upper} (step: {symbol.grid.step})
                      </div>
                    )}
                    {!symbol.grid && symbol.enabled && (
                      <div className="text-xs text-muted-foreground">No grid configuration</div>
                    )}
                    {!symbol.enabled && (
                      <div className="text-xs text-muted-foreground">Disabled</div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {symbol.mode && (
                    <Badge variant="outline" className="text-xs">
                      {symbol.mode}
                    </Badge>
                  )}
                  {symbol.modes && symbol.modes.length > 0 && (
                    <Badge variant="outline" className="text-xs">
                      {symbol.modes.join(', ')}
                    </Badge>
                  )}
                  {symbol.enabled && (
                    <Badge className="text-xs bg-green-500">Active</Badge>
                  )}
                  {selectedSymbol === symbol.name && (
                    <Check className="h-4 w-4 text-primary" />
                  )}
                </div>
              </DropdownMenuItem>
            ))
          )}
        </div>
        {data && (
          <>
            <DropdownMenuSeparator />
            <div className="p-2 text-xs text-muted-foreground">
              {data.enabled_count} active / {data.total} total symbols
            </div>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
