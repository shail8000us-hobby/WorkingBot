'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Palette, Sun, Moon, Monitor, Check } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

type ThemeMode = 'light' | 'dark' | 'system';
type ColorScheme = 'default' | 'blue' | 'green' | 'purple' | 'orange';

export function ThemePanel() {
  const [themeMode, setThemeMode] = useState<ThemeMode>('system');
  const [colorScheme, setColorScheme] = useState<ColorScheme>('default');
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(
    null
  );

  const handleThemeChange = (mode: ThemeMode) => {
    setThemeMode(mode);
    // Apply theme to document
    document.documentElement.classList.remove('light', 'dark');
    if (mode === 'system') {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      document.documentElement.classList.add(prefersDark ? 'dark' : 'light');
    } else {
      document.documentElement.classList.add(mode);
    }
    localStorage.setItem('theme-mode', mode);
    showNotification(`Theme changed to ${mode}`, 'success');
  };

  const handleColorSchemeChange = (scheme: ColorScheme) => {
    setColorScheme(scheme);
    // Apply color scheme
    document.documentElement.setAttribute('data-color-scheme', scheme);
    localStorage.setItem('color-scheme', scheme);
    showNotification(`Color scheme changed to ${scheme}`, 'success');
  };

  const showNotification = (message: string, type: 'success' | 'error') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3000);
  };

  const colorSchemes = [
    { value: 'default', label: 'Default', color: 'bg-slate-500' },
    { value: 'blue', label: 'Blue', color: 'bg-blue-500' },
    { value: 'green', label: 'Green', color: 'bg-green-500' },
    { value: 'purple', label: 'Purple', color: 'bg-purple-500' },
    { value: 'orange', label: 'Orange', color: 'bg-orange-500' },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Palette className="h-5 w-5" />
          Theme Settings
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Notification */}
        {notification && (
          <Alert variant={notification.type === 'error' ? 'destructive' : 'default'} className="mb-4">
            <AlertDescription className="flex items-center gap-2">
              <Check className="h-4 w-4" />
              {notification.message}
            </AlertDescription>
          </Alert>
        )}

        {/* Theme Mode */}
        <div className="space-y-3">
          <Label className="text-base font-semibold">Theme Mode</Label>
          <div className="grid grid-cols-3 gap-3">
            <Button
              variant={themeMode === 'light' ? 'default' : 'outline'}
              className="flex flex-col items-center gap-2 h-24"
              onClick={() => handleThemeChange('light')}
            >
              <Sun className="h-6 w-6" />
              <span>Light</span>
              {themeMode === 'light' && <Check className="h-4 w-4" />}
            </Button>
            <Button
              variant={themeMode === 'dark' ? 'default' : 'outline'}
              className="flex flex-col items-center gap-2 h-24"
              onClick={() => handleThemeChange('dark')}
            >
              <Moon className="h-6 w-6" />
              <span>Dark</span>
              {themeMode === 'dark' && <Check className="h-4 w-4" />}
            </Button>
            <Button
              variant={themeMode === 'system' ? 'default' : 'outline'}
              className="flex flex-col items-center gap-2 h-24"
              onClick={() => handleThemeChange('system')}
            >
              <Monitor className="h-6 w-6" />
              <span>System</span>
              {themeMode === 'system' && <Check className="h-4 w-4" />}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            System mode automatically switches between light and dark based on your OS settings
          </p>
        </div>

        {/* Color Scheme */}
        <div className="space-y-3">
          <Label className="text-base font-semibold">Color Scheme</Label>
          <Select value={colorScheme} onValueChange={(value) => handleColorSchemeChange(value as ColorScheme)}>
            <SelectTrigger>
              <SelectValue placeholder="Select color scheme" />
            </SelectTrigger>
            <SelectContent>
              {colorSchemes.map((scheme) => (
                <SelectItem key={scheme.value} value={scheme.value}>
                  <div className="flex items-center gap-2">
                    <div className={`w-4 h-4 rounded-full ${scheme.color}`} />
                    {scheme.label}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Choose your preferred accent color for the interface
          </p>
        </div>

        {/* Color Preview */}
        <div className="space-y-3">
          <Label className="text-base font-semibold">Preview</Label>
          <div className="grid grid-cols-5 gap-2">
            {colorSchemes.map((scheme) => (
              <div
                key={scheme.value}
                className="relative rounded-lg overflow-hidden cursor-pointer border-2 transition-all"
                style={{
                  borderColor: colorScheme === scheme.value ? 'hsl(var(--primary))' : 'transparent',
                }}
                onClick={() => handleColorSchemeChange(scheme.value as ColorScheme)}
              >
                <div className={`h-16 ${scheme.color}`} />
                <div className="absolute inset-0 flex items-center justify-center">
                  {colorScheme === scheme.value && (
                    <Badge className="bg-white text-black">
                      <Check className="h-3 w-3" />
                    </Badge>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Current Settings */}
        <div className="p-4 rounded-lg bg-muted space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Current Theme:</span>
            <Badge variant="outline">{themeMode}</Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Color Scheme:</span>
            <Badge variant="outline">{colorScheme}</Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
