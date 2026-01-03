'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { FileText, Download, Upload, Trash2, Star } from 'lucide-react';

interface Template {
  id: string;
  name: string;
  description: string;
  category: 'grid' | 'safety' | 'custom';
  is_default: boolean;
  created_at: string;
  config: Record<string, any>;
}

interface TemplatesResponse {
  data: {
    templates: Template[];
    total: number;
  };
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchTemplates(): Promise<TemplatesResponse> {
  const response = await fetch('http://localhost:5555/api/templates/list');
  if (!response.ok) {
    throw new Error('Failed to fetch templates');
  }
  return response.json();
}

async function applyTemplate(id: string) {
  const response = await fetch(`http://localhost:5555/api/templates/${id}/apply`, {
    method: 'POST',
  });
  return response.json();
}

export function TemplatePanel() {
  const [applying, setApplying] = useState<string | null>(null);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(
    null
  );

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['templates'],
    queryFn: fetchTemplates,
    refetchInterval: 30000,
  });

  const handleApply = async (id: string, name: string) => {
    setApplying(id);
    try {
      const result = await applyTemplate(id);
      if (result.success) {
        showNotification(`Template "${name}" applied successfully`, 'success');
        refetch();
      } else {
        showNotification(result.error || 'Failed to apply template', 'error');
      }
    } catch (err) {
      showNotification((err as Error).message || 'Error applying template', 'error');
    } finally {
      setApplying(null);
    }
  };

  const showNotification = (message: string, type: 'success' | 'error') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3000);
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Configuration Templates
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading templates...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Configuration Templates</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load templates'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const templates = data?.data.templates || [];
  const stats = data?.data;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Configuration Templates
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm">
              <Upload className="h-4 w-4 mr-2" />
              Import
            </Button>
            <Button variant="outline" size="sm">
              <Download className="h-4 w-4 mr-2" />
              Save Current
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Notification */}
        {notification && (
          <Alert variant={notification.type === 'error' ? 'destructive' : 'default'}>
            <AlertDescription>{notification.message}</AlertDescription>
          </Alert>
        )}

        {/* Info */}
        <Alert>
          <AlertDescription className="text-xs">
            Templates allow you to quickly switch between different bot configurations. Apply a
            template to load pre-configured settings.
          </AlertDescription>
        </Alert>

        {/* Templates List */}
        <div className="space-y-3">
          {templates.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <FileText className="h-12 w-12 mx-auto mb-3 opacity-20" />
              <p>No templates available</p>
              <Button variant="outline" size="sm" className="mt-4">
                <Download className="h-4 w-4 mr-2" />
                Save Current Config as Template
              </Button>
            </div>
          ) : (
            templates.map((template) => (
              <Card key={template.id} className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <FileText className="h-4 w-4 text-muted-foreground" />
                      <h3 className="font-semibold">{template.name}</h3>
                      {template.is_default && (
                        <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                      )}
                      <Badge
                        variant={
                          template.category === 'grid'
                            ? 'default'
                            : template.category === 'safety'
                            ? 'secondary'
                            : 'outline'
                        }
                        className="text-xs"
                      >
                        {template.category}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground mb-2">
                      {template.description}
                    </p>
                    <div className="text-xs text-muted-foreground">
                      Created {new Date(template.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <Button
                      variant="default"
                      size="sm"
                      onClick={() => handleApply(template.id, template.name)}
                      disabled={applying === template.id}
                    >
                      {applying === template.id ? 'Applying...' : 'Apply'}
                    </Button>
                    <Button variant="ghost" size="sm">
                      <Download className="h-4 w-4" />
                    </Button>
                    {!template.is_default && (
                      <Button variant="ghost" size="sm">
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    )}
                  </div>
                </div>
              </Card>
            ))
          )}
        </div>

        {/* Template Categories */}
        <div className="mt-6 p-4 border-t">
          <h3 className="text-sm font-semibold mb-3">Template Categories</h3>
          <div className="grid grid-cols-3 gap-3">
            <Card className="p-3 text-center">
              <Badge variant="default" className="mb-2">
                Grid
              </Badge>
              <p className="text-xs text-muted-foreground">
                Grid trading configurations
              </p>
            </Card>
            <Card className="p-3 text-center">
              <Badge variant="secondary" className="mb-2">
                Safety
              </Badge>
              <p className="text-xs text-muted-foreground">
                Risk management presets
              </p>
            </Card>
            <Card className="p-3 text-center">
              <Badge variant="outline" className="mb-2">
                Custom
              </Badge>
              <p className="text-xs text-muted-foreground">User-created templates</p>
            </Card>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
