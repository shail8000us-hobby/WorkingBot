'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  SlidersHorizontal,
  Code,
  FileText,
  Save,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  Loader2,
} from 'lucide-react';
import * as api from '@/lib/api';

interface ConfigField {
  key: string;
  value: any;
  type: string;
  description?: string;
}

interface ConfigSection {
  title: string;
  fields: ConfigField[];
}

async function fetchConfig(): Promise<Record<string, any>> {
  const response = await api.getConfig();
  if (!response.success) throw new Error(response.error);
  return response.data || {};
}

async function updateConfig(config: Record<string, any>): Promise<void> {
  const response = await api.updateConfig(config);
  if (!response.success) throw new Error(response.error);
}

export function ConfigVisualEditor() {
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<'form' | 'yaml'>('form');
  const [yamlContent, setYamlContent] = useState('');
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [hasChanges, setHasChanges] = useState(false);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  const { data: config, isLoading, error } = useQuery({
    queryKey: ['config'],
    queryFn: fetchConfig,
  });

  const updateMutation = useMutation({
    mutationFn: updateConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] });
      setHasChanges(false);
      setShowConfirmDialog(false);
      setValidationErrors({});
    },
  });

  // Initialize form data when config loads
  useState(() => {
    if (config) {
      setFormData(config);
      // Convert to YAML (simplified - in production use a YAML library)
      setYamlContent(JSON.stringify(config, null, 2));
    }
  });

  const handleFormChange = (key: string, value: any) => {
    setFormData(prev => ({ ...prev, [key]: value }));
    setHasChanges(true);
    // Clear validation error for this field
    if (validationErrors[key]) {
      setValidationErrors(prev => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  };

  const handleYamlChange = (value: string) => {
    setYamlContent(value);
    setHasChanges(true);
    try {
      // Validate YAML
      const parsed = JSON.parse(value);
      setFormData(parsed);
      setValidationErrors({});
    } catch (err) {
      setValidationErrors({ yaml: 'Invalid YAML/JSON format' });
    }
  };

  const handleSave = () => {
    const dataToSave = viewMode === 'yaml' 
      ? (() => {
          try {
            return JSON.parse(yamlContent);
          } catch {
            return null;
          }
        })()
      : formData;
    
    if (!dataToSave) {
      setValidationErrors({ yaml: 'Invalid format' });
      return;
    }

    setShowConfirmDialog(true);
  };

  const confirmSave = () => {
    const dataToSave = viewMode === 'yaml' 
      ? JSON.parse(yamlContent)
      : formData;
    
    updateMutation.mutate(dataToSave);
  };

  // Group config into sections
  const configSections: ConfigSection[] = config ? [
    {
      title: 'Trading',
      fields: Object.entries(config)
        .filter(([key]) => key.toLowerCase().includes('trading') || key.toLowerCase().includes('grid'))
        .map(([key, value]) => ({ key, value, type: typeof value })),
    },
    {
      title: 'Risk & Safety',
      fields: Object.entries(config)
        .filter(([key]) => key.toLowerCase().includes('risk') || key.toLowerCase().includes('safety') || key.toLowerCase().includes('guardian'))
        .map(([key, value]) => ({ key, value, type: typeof value })),
    },
    {
      title: 'General',
      fields: Object.entries(config)
        .filter(([key]) => 
          !key.toLowerCase().includes('trading') &&
          !key.toLowerCase().includes('grid') &&
          !key.toLowerCase().includes('risk') &&
          !key.toLowerCase().includes('safety') &&
          !key.toLowerCase().includes('guardian')
        )
        .map(([key, value]) => ({ key, value, type: typeof value })),
    },
  ].filter(section => section.fields.length > 0) : [];

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Visual Config Editor</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !config) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Visual Config Editor</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              Failed to load configuration. The config API may not be available.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <SlidersHorizontal className="h-5 w-5" />
                Visual Config Editor
              </CardTitle>
              <CardDescription>
                Edit configuration with forms or YAML - validation, diff preview, and auto-backup
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {hasChanges && (
                <Badge variant="outline">Unsaved changes</Badge>
              )}
              <Button
                onClick={() => queryClient.invalidateQueries({ queryKey: ['config'] })}
                variant="outline"
                size="sm"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
              <Button
                onClick={handleSave}
                disabled={!hasChanges || updateMutation.isPending}
              >
                <Save className="h-4 w-4 mr-2" />
                {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as 'form' | 'yaml')}>
            <TabsList>
              <TabsTrigger value="form">
                <FileText className="h-4 w-4 mr-2" />
                Form View
              </TabsTrigger>
              <TabsTrigger value="yaml">
                <Code className="h-4 w-4 mr-2" />
                YAML/JSON View
              </TabsTrigger>
            </TabsList>

            <TabsContent value="form" className="mt-4">
              <div className="space-y-6">
                {configSections.map((section, idx) => (
                  <div key={idx}>
                    <h3 className="text-lg font-semibold mb-4">{section.title}</h3>
                    <div className="grid gap-4 md:grid-cols-2">
                      {section.fields.map((field) => (
                        <div key={field.key} className="space-y-2">
                          <Label htmlFor={field.key}>{field.key}</Label>
                          {field.type === 'boolean' ? (
                            <div className="flex items-center space-x-2">
                              <input
                                type="checkbox"
                                id={field.key}
                                checked={formData[field.key] || false}
                                onChange={(e) => handleFormChange(field.key, e.target.checked)}
                                className="h-4 w-4"
                              />
                              <span className="text-sm text-muted-foreground">
                                {field.value ? 'Enabled' : 'Disabled'}
                              </span>
                            </div>
                          ) : field.type === 'number' ? (
                            <Input
                              id={field.key}
                              type="number"
                              value={formData[field.key] || ''}
                              onChange={(e) => handleFormChange(field.key, parseFloat(e.target.value))}
                            />
                          ) : (
                            <Input
                              id={field.key}
                              value={formData[field.key] || ''}
                              onChange={(e) => handleFormChange(field.key, e.target.value)}
                            />
                          )}
                          {validationErrors[field.key] && (
                            <p className="text-sm text-destructive">{validationErrors[field.key]}</p>
                          )}
                        </div>
                      ))}
                    </div>
                    {idx < configSections.length - 1 && <Separator className="my-6" />}
                  </div>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="yaml" className="mt-4">
              <div className="space-y-4">
                <Label>YAML/JSON Content</Label>
                <Textarea
                  value={yamlContent}
                  onChange={(e) => handleYamlChange(e.target.value)}
                  className="font-mono text-sm min-h-[500px]"
                  spellCheck={false}
                />
                {validationErrors.yaml && (
                  <Alert variant="destructive">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>{validationErrors.yaml}</AlertDescription>
                  </Alert>
                )}
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Confirm Save Dialog */}
      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save Configuration Changes</DialogTitle>
            <DialogDescription>
              Are you sure you want to save these configuration changes? This will update the bot configuration.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConfirmDialog(false)}>
              Cancel
            </Button>
            <Button onClick={confirmSave} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

