'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ScrollArea } from '@/components/ui/scroll-area';
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
  Folder,
  File,
  Home,
  Search,
  RefreshCw,
  Save,
  Code,
  Settings,
  FileText,
  Database,
  ChevronRight,
  AlertTriangle,
  Loader2,
} from 'lucide-react';

interface FileItem {
  name: string;
  type: 'file' | 'directory';
  path: string;
  size?: number;
}

interface FileListResponse {
  files: FileItem[];
  current_path: string;
  parent_path?: string;
}

const FILE_EXTENSIONS: Record<string, { language: string; icon: React.ReactNode }> = {
  '.py': { language: 'python', icon: <Code className="h-4 w-4 text-blue-500" /> },
  '.js': { language: 'javascript', icon: <Code className="h-4 w-4 text-yellow-500" /> },
  '.jsx': { language: 'javascript', icon: <Code className="h-4 w-4 text-yellow-500" /> },
  '.ts': { language: 'typescript', icon: <Code className="h-4 w-4 text-blue-400" /> },
  '.tsx': { language: 'typescript', icon: <Code className="h-4 w-4 text-blue-400" /> },
  '.json': { language: 'json', icon: <Database className="h-4 w-4 text-green-500" /> },
  '.yaml': { language: 'yaml', icon: <Settings className="h-4 w-4 text-purple-500" /> },
  '.yml': { language: 'yaml', icon: <Settings className="h-4 w-4 text-purple-500" /> },
  '.md': { language: 'markdown', icon: <FileText className="h-4 w-4 text-gray-500" /> },
  '.txt': { language: 'plaintext', icon: <FileText className="h-4 w-4 text-gray-500" /> },
  '.log': { language: 'plaintext', icon: <FileText className="h-4 w-4 text-gray-500" /> },
};

const IMPORTANT_DIRS = [
  { path: 'bot', label: 'Bot Source Code', icon: '🤖' },
  { path: 'bot/strategy', label: 'Strategies', icon: '📊' },
  { path: 'bot/utils', label: 'Utilities', icon: '🛠️' },
  { path: 'bot/safety', label: 'Safety Modules', icon: '🛡️' },
  { path: 'webui', label: 'Web UI', icon: '🌐' },
  { path: 'config', label: 'Configuration', icon: '⚙️' },
];

async function fetchFileList(path: string): Promise<FileListResponse> {
  const response = await fetch('http://localhost:5555/api/file-manager/list', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: path || '.' }),
  });
  if (!response.ok) throw new Error('Failed to fetch file list');
  return response.json();
}

async function fetchFileContent(path: string): Promise<string> {
  const response = await fetch('http://localhost:5555/api/file-manager/read', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  if (!response.ok) throw new Error('Failed to read file');
  const data = await response.json();
  return data.content || '';
}

async function saveFileContent(path: string, content: string): Promise<void> {
  const response = await fetch('http://localhost:5555/api/file-manager/write', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, content }),
  });
  if (!response.ok) throw new Error('Failed to save file');
}

export function FileEditor() {
  const queryClient = useQueryClient();
  const [currentPath, setCurrentPath] = useState('');
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [showSaveDialog, setShowSaveDialog] = useState(false);

  const { data: fileList, isLoading, error, refetch } = useQuery({
    queryKey: ['file-list', currentPath],
    queryFn: () => fetchFileList(currentPath),
    enabled: true,
  });

  const { data: fileData, isLoading: fileLoading } = useQuery({
    queryKey: ['file-content', selectedFile],
    queryFn: () => fetchFileContent(selectedFile!),
    enabled: !!selectedFile,
  });

  const saveMutation = useMutation({
    mutationFn: ({ path, content }: { path: string; content: string }) => saveFileContent(path, content),
    onSuccess: () => {
      setHasUnsavedChanges(false);
      setShowSaveDialog(false);
      queryClient.invalidateQueries({ queryKey: ['file-content', selectedFile] });
    },
  });

  useEffect(() => {
    if (fileData) {
      setFileContent(fileData);
      setHasUnsavedChanges(false);
    }
  }, [fileData]);

  const handleFileSelect = (file: FileItem) => {
    if (file.type === 'directory') {
      setCurrentPath(file.path);
      setSelectedFile(null);
      setFileContent('');
    } else {
      setSelectedFile(file.path);
    }
  };

  const handleGoHome = () => {
    setCurrentPath('');
    setSelectedFile(null);
    setFileContent('');
  };

  const handleGoUp = () => {
    if (fileList?.parent_path !== undefined) {
      setCurrentPath(fileList.parent_path);
      setSelectedFile(null);
      setFileContent('');
    }
  };

  const handleSave = () => {
    if (selectedFile && fileContent) {
      saveMutation.mutate({ path: selectedFile, content: fileContent });
    }
  };

  const getFileIcon = (fileName: string) => {
    const ext = fileName.substring(fileName.lastIndexOf('.'));
    const fileType = FILE_EXTENSIONS[ext];
    return fileType?.icon || <File className="h-4 w-4 text-gray-500" />;
  };

  const filteredFiles = fileList?.files.filter(file =>
    file.name.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  return (
    <div className="grid h-[calc(100vh-200px)] grid-cols-12 gap-4">
      {/* File Browser */}
      <div className="col-span-3 flex flex-col border-r">
        <Card className="h-full flex flex-col">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between mb-2">
              <CardTitle className="text-sm">File Browser</CardTitle>
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={handleGoHome}
                  title="Home"
                >
                  <Home className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => refetch()}
                  title="Refresh"
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div className="relative">
              <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search files..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-8 h-8 text-xs"
              />
            </div>
          </CardHeader>
          <CardContent className="flex-1 overflow-hidden p-0">
            {/* Breadcrumbs */}
            {fileList?.current_path && (
              <div className="px-4 py-2 border-b bg-muted/50">
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <button
                    onClick={handleGoUp}
                    className="hover:text-foreground"
                  >
                    {fileList.parent_path ? '..' : ''}
                  </button>
                  {fileList.current_path && fileList.current_path !== '.' && (
                    <>
                      <ChevronRight className="h-3 w-3" />
                      <span className="truncate">{fileList.current_path}</span>
                    </>
                  )}
                </div>
              </div>
            )}

            {/* Important Directories */}
            {currentPath === '' && (
              <div className="p-2 border-b">
                <div className="text-xs font-semibold text-muted-foreground mb-2 px-2">Quick Access</div>
                {IMPORTANT_DIRS.map((dir) => (
                  <button
                    key={dir.path}
                    onClick={() => setCurrentPath(dir.path)}
                    className="w-full text-left px-2 py-1.5 text-sm hover:bg-muted rounded flex items-center gap-2"
                  >
                    <span>{dir.icon}</span>
                    <span>{dir.label}</span>
                  </button>
                ))}
              </div>
            )}

            {/* File List */}
            <ScrollArea className="h-full">
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : error ? (
                <Alert variant="destructive" className="m-2">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription className="text-xs">
                    Failed to load files. The file-manager API may not be available.
                  </AlertDescription>
                </Alert>
              ) : filteredFiles.length === 0 ? (
                <div className="text-center py-8 text-sm text-muted-foreground">
                  No files found
                </div>
              ) : (
                <div className="p-2 space-y-1">
                  {filteredFiles.map((file) => (
                    <button
                      key={file.path}
                      onClick={() => handleFileSelect(file)}
                      className={`w-full text-left px-2 py-1.5 text-sm rounded flex items-center gap-2 hover:bg-muted ${
                        selectedFile === file.path ? 'bg-muted font-semibold' : ''
                      }`}
                    >
                      {file.type === 'directory' ? (
                        <Folder className="h-4 w-4 text-blue-500" />
                      ) : (
                        getFileIcon(file.name)
                      )}
                      <span className="truncate flex-1">{file.name}</span>
                      {file.size !== undefined && file.type === 'file' && (
                        <span className="text-xs text-muted-foreground">
                          {(file.size / 1024).toFixed(1)}KB
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      </div>

      {/* Code Editor */}
      <div className="col-span-9 flex flex-col">
        <Card className="h-full flex flex-col">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <CardTitle className="text-sm truncate">
                  {selectedFile || 'No file selected'}
                </CardTitle>
                {selectedFile && (
                  <CardDescription className="text-xs">
                    {FILE_EXTENSIONS[selectedFile.substring(selectedFile.lastIndexOf('.'))]?.language || 'plaintext'}
                  </CardDescription>
                )}
              </div>
              {selectedFile && (
                <div className="flex gap-2">
                  {hasUnsavedChanges && (
                    <Badge variant="outline" className="text-xs">
                      Unsaved changes
                    </Badge>
                  )}
                  <Button
                    size="sm"
                    onClick={handleSave}
                    disabled={!hasUnsavedChanges || saveMutation.isPending}
                  >
                    <Save className="h-4 w-4 mr-2" />
                    {saveMutation.isPending ? 'Saving...' : 'Save'}
                  </Button>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="flex-1 overflow-hidden p-0">
            {!selectedFile ? (
              <div className="flex items-center justify-center h-full text-muted-foreground">
                <div className="text-center">
                  <File className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>Select a file from the browser to edit</p>
                </div>
              </div>
            ) : fileLoading ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <div className="h-full">
                <textarea
                  value={fileContent}
                  onChange={(e) => {
                    setFileContent(e.target.value);
                    setHasUnsavedChanges(true);
                  }}
                  className="w-full h-full p-4 font-mono text-sm border-0 resize-none focus:outline-none"
                  style={{ fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace' }}
                  spellCheck={false}
                />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Save Dialog */}
      <Dialog open={showSaveDialog} onOpenChange={setShowSaveDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save Changes</DialogTitle>
            <DialogDescription>
              Are you sure you want to save changes to {selectedFile}?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSaveDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

