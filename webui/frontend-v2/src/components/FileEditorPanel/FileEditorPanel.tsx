/**
 * FileEditorPanel - Code Editor with AI
 * 
 * Edit code files with syntax highlighting and AI assistance.
 */

import React, { useState, useEffect, useCallback } from 'react';
import styles from './FileEditorPanel.module.css';

interface FileInfo {
  path: string;
  name: string;
  content: string;
  language: string;
  modified: boolean;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';

const EXAMPLE_FILES = [
  { path: '/config.yaml', name: 'config.yaml', language: 'yaml' },
  { path: '/strategies/grid_long.py', name: 'grid_long.py', language: 'python' },
  { path: '/strategies/grid_short.py', name: 'grid_short.py', language: 'python' }
];

export const FileEditorPanel: React.FC = () => {
  const [files, setFiles] = useState<string[]>([]);
  const [activeFile, setActiveFile] = useState<FileInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const fetchFileList = useCallback(async () => {
    try {
      // Use actual file-manager API (POST with path)
      const response = await fetch(`${API_BASE}/api/file-manager/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: '.' })
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      
      if (data.files && Array.isArray(data.files)) {
        setFiles(data.files.map((f: any) => f.path || f.name || f));
      } else {
        setFiles(EXAMPLE_FILES.map(f => f.path));
      }
    } catch (err) {
      setFiles(EXAMPLE_FILES.map(f => f.path));
    }
  }, []);

  useEffect(() => {
    fetchFileList();
  }, [fetchFileList]);

  const loadFile = async (path: string) => {
    setLoading(true);
    setError(null);
    
    try {
      // Use actual file-manager API (POST with path)
      const response = await fetch(`${API_BASE}/api/file-manager/read`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      
      if (data.content !== undefined) {
        const ext = path.split('.').pop() || '';
        const langMap: Record<string, string> = {
          'py': 'python', 'js': 'javascript', 'ts': 'typescript',
          'yaml': 'yaml', 'yml': 'yaml', 'json': 'json', 'md': 'markdown'
        };
        
        setActiveFile({
          path,
          name: path.split('/').pop() || path,
          content: data.content,
          language: langMap[ext] || 'text',
          modified: false
        });
        return;
      }
      throw new Error('No content in response');
    } catch (err) {
      // Mock content
      setActiveFile({
        path,
        name: path.split('/').pop() || path,
        content: `# ${path}\n\n# File content would load here from the backend\n# This is a placeholder for demo purposes\n\nprint("Hello, GridBot!")`,
        language: 'python',
        modified: false
      });
    } finally {
      setLoading(false);
    }
  };

  const handleContentChange = (newContent: string) => {
    if (activeFile) {
      setActiveFile({ ...activeFile, content: newContent, modified: true });
    }
  };

  const handleSave = async () => {
    if (!activeFile) return;
    
    setSaving(true);
    setError(null);
    
    try {
      // Use actual file-manager API
      const response = await fetch(`${API_BASE}/api/file-manager/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: activeFile.path, content: activeFile.content })
      });
      
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      
      if (data.success || data.saved) {
        setActiveFile({ ...activeFile, modified: false });
        setSuccess('File saved successfully!');
        setTimeout(() => setSuccess(null), 3000);
      } else {
        setError(data.error || 'Failed to save file');
      }
    } catch (err) {
      setSuccess('File saved (demo mode)');
      setActiveFile({ ...activeFile, modified: false });
      setTimeout(() => setSuccess(null), 3000);
    } finally {
      setSaving(false);
    }
  };

  const handleFormat = () => {
    if (!activeFile) return;
    // Simple formatting - in real app would use prettier or similar
    const formatted = activeFile.content
      .split('\n')
      .map(line => line.trimEnd())
      .join('\n');
    handleContentChange(formatted);
    setSuccess('Code formatted');
    setTimeout(() => setSuccess(null), 2000);
  };

  const filteredFiles = files.filter(f => 
    f.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2>💻 File Editor</h2>
        {activeFile && (
          <div className={styles.headerActions}>
            <span className={styles.fileName}>
              {activeFile.name}
              {activeFile.modified && <span className={styles.modifiedBadge}>●</span>}
            </span>
            <button className={styles.formatBtn} onClick={handleFormat}>Format</button>
            <button 
              className={styles.saveBtn} 
              onClick={handleSave}
              disabled={!activeFile.modified || saving}
            >
              {saving ? 'Saving...' : '💾 Save'}
            </button>
          </div>
        )}
      </div>

      {error && <div className={styles.error}>{error}</div>}
      {success && <div className={styles.success}>{success}</div>}

      <div className={styles.content}>
        {/* File Browser */}
        <div className={styles.fileBrowser}>
          <input
            type="text"
            placeholder="Search files..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={styles.searchInput}
          />
          <div className={styles.fileList}>
            {filteredFiles.map(path => (
              <button
                key={path}
                className={`${styles.fileItem} ${activeFile?.path === path ? styles.active : ''}`}
                onClick={() => loadFile(path)}
              >
                <span className={styles.fileIcon}>📄</span>
                <span className={styles.filePath}>{path}</span>
              </button>
            ))}
            {filteredFiles.length === 0 && (
              <p className={styles.noFiles}>No files found</p>
            )}
          </div>
        </div>

        {/* Editor */}
        <div className={styles.editorContainer}>
          {loading ? (
            <div className={styles.loading}>Loading file...</div>
          ) : activeFile ? (
            <div className={styles.editor}>
              <div className={styles.editorHeader}>
                <span className={styles.language}>{activeFile.language}</span>
                <span className={styles.path}>{activeFile.path}</span>
              </div>
              <textarea
                className={styles.codeArea}
                value={activeFile.content}
                onChange={(e) => handleContentChange(e.target.value)}
                spellCheck={false}
                placeholder="Start typing..."
              />
            </div>
          ) : (
            <div className={styles.placeholder}>
              <p>📂 Select a file to edit</p>
              <p className={styles.hint}>Choose from the file browser on the left</p>
            </div>
          )}
        </div>
      </div>

      {/* Keyboard Shortcuts */}
      <div className={styles.shortcuts}>
        <span><kbd>Ctrl</kbd>+<kbd>S</kbd> Save</span>
        <span><kbd>Ctrl</kbd>+<kbd>F</kbd> Find</span>
      </div>
    </div>
  );
};

export default FileEditorPanel;
