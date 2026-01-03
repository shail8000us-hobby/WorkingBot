'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Plus, Trash2, Edit, Settings, Save, TrendingUp } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface Symbol {
  symbol: string;
  mode: 'LONG' | 'SHORT' | 'HYBRID';
  enabled: boolean;
  grid_lower: number;
  grid_upper: number;
  num_grids: number;
  position_size: number;
}

interface SymbolsResponse {
  data: { symbols: Symbol[] };
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchSymbols(): Promise<SymbolsResponse> {
  const response = await fetch('http://localhost:5555/api/symbols/list');
  if (!response.ok) {
    throw new Error('Failed to fetch symbols');
  }
  return response.json();
}

async function updateSymbol(symbol: Symbol) {
  const response = await fetch(`http://localhost:5555/api/symbols/${symbol.symbol}/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(symbol),
  });
  return response.json();
}

async function deleteSymbol(symbolName: string) {
  const response = await fetch(`http://localhost:5555/api/symbols/${symbolName}/delete`, {
    method: 'DELETE',
  });
  return response.json();
}

export function SymbolManagementPanel() {
  const [editingSymbol, setEditingSymbol] = useState<Symbol | null>(null);
  const [showDialog, setShowDialog] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['symbols'],
    queryFn: fetchSymbols,
    refetchInterval: 30000,
  });

  const handleEdit = (symbol: Symbol) => {
    setEditingSymbol({ ...symbol });
    setShowDialog(true);
  };

  const handleSave = async () => {
    if (!editingSymbol) return;

    try {
      const result = await updateSymbol(editingSymbol);
      if (result.success) {
        showNotification(`${editingSymbol.symbol} updated successfully`, 'success');
        setShowDialog(false);
        refetch();
      } else {
        showNotification(result.message || 'Failed to update symbol', 'error');
      }
    } catch (err) {
      showNotification((err as Error).message || 'Error updating symbol', 'error');
    }
  };

  const handleDelete = async (symbolName: string) => {
    if (!window.confirm(`Are you sure you want to delete ${symbolName}?`)) return;

    try {
      const result = await deleteSymbol(symbolName);
      if (result.success) {
        showNotification(`${symbolName} deleted successfully`, 'success');
        refetch();
      } else {
        showNotification(result.message || 'Failed to delete symbol', 'error');
      }
    } catch (err) {
      showNotification((err as Error).message || 'Error deleting symbol', 'error');
    }
  };

  const showNotification = (message: string, type: 'success' | 'error') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Symbol Management
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading symbols...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Symbol Management</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load symbols'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const symbols = data?.data?.symbols || [];

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              Symbol Management
            </CardTitle>
            <Button size="sm">
              <Plus className="h-4 w-4 mr-2" />
              Add Symbol
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* Notification */}
          {notification && (
            <Alert variant={notification.type === 'error' ? 'destructive' : 'default'} className="mb-4">
              <AlertDescription>{notification.message}</AlertDescription>
            </Alert>
          )}

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Symbol</TableHead>
                <TableHead>Mode</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Grid Range</TableHead>
                <TableHead className="text-right">Grid Levels</TableHead>
                <TableHead className="text-right">Position Size</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {symbols.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    No symbols configured
                  </TableCell>
                </TableRow>
              ) : (
                symbols.map((symbol) => (
                  <TableRow key={symbol.symbol}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <TrendingUp className="h-4 w-4" />
                        {symbol.symbol}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={symbol.mode === 'LONG' ? 'default' : 'destructive'}>
                        {symbol.mode}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={symbol.enabled ? 'default' : 'secondary'}>
                        {symbol.enabled ? 'Active' : 'Disabled'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      ₹{symbol.grid_lower} - ₹{symbol.grid_upper}
                    </TableCell>
                    <TableCell className="text-right">{symbol.num_grids}</TableCell>
                    <TableCell className="text-right">₹{symbol.position_size}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => handleEdit(symbol)}>
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(symbol.symbol)}
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Symbol: {editingSymbol?.symbol}</DialogTitle>
            <DialogDescription>Update symbol configuration</DialogDescription>
          </DialogHeader>

          {editingSymbol && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Mode</Label>
                  <Select
                    value={editingSymbol.mode}
                    onValueChange={(value: 'LONG' | 'SHORT' | 'HYBRID') =>
                      setEditingSymbol({ ...editingSymbol, mode: value })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="LONG">LONG</SelectItem>
                      <SelectItem value="SHORT">SHORT</SelectItem>
                      <SelectItem value="HYBRID">HYBRID</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center space-x-2">
                  <Switch
                    checked={editingSymbol.enabled}
                    onCheckedChange={(checked) =>
                      setEditingSymbol({ ...editingSymbol, enabled: checked })
                    }
                  />
                  <Label>Enabled</Label>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Grid Lower Bound</Label>
                  <Input
                    type="number"
                    value={editingSymbol.grid_lower}
                    onChange={(e) =>
                      setEditingSymbol({ ...editingSymbol, grid_lower: parseFloat(e.target.value) })
                    }
                  />
                </div>

                <div className="space-y-2">
                  <Label>Grid Upper Bound</Label>
                  <Input
                    type="number"
                    value={editingSymbol.grid_upper}
                    onChange={(e) =>
                      setEditingSymbol({ ...editingSymbol, grid_upper: parseFloat(e.target.value) })
                    }
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Number of Grids</Label>
                  <Input
                    type="number"
                    value={editingSymbol.num_grids}
                    onChange={(e) =>
                      setEditingSymbol({ ...editingSymbol, num_grids: parseInt(e.target.value) })
                    }
                  />
                </div>

                <div className="space-y-2">
                  <Label>Position Size (₹)</Label>
                  <Input
                    type="number"
                    value={editingSymbol.position_size}
                    onChange={(e) =>
                      setEditingSymbol({
                        ...editingSymbol,
                        position_size: parseFloat(e.target.value),
                      })
                    }
                  />
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave}>
              <Save className="h-4 w-4 mr-2" />
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
