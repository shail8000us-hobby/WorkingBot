import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Grid,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemButton,
  Typography,
  Breadcrumbs,
  Link,
  IconButton,
  Tooltip,
  TextField,
  InputAdornment,
  Chip,
  Alert,
  CircularProgress,
  Button,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
} from '@mui/material';
import {
  Folder as FolderIcon,
  InsertDriveFile as FileIcon,
  Home as HomeIcon,
  Search as SearchIcon,
  Refresh as RefreshIcon,
  ArrowBack as BackIcon,
  Code as CodeIcon,
  Settings as SettingsIcon,
  Description as DescriptionIcon,
  Storage as DataIcon,
  Psychology as ExplainIcon,
} from '@mui/icons-material';
import CodeEditor from '../CodeEditor/CodeEditor';
import CodeExplanationPanel from '../CodeExplanationPanel/CodeExplanationPanel';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5555';

// File type configurations
const FILE_TYPES = {
  '.py': { language: 'python', icon: <CodeIcon color="primary" /> },
  '.js': { language: 'javascript', icon: <CodeIcon color="warning" /> },
  '.jsx': { language: 'javascript', icon: <CodeIcon color="warning" /> },
  '.ts': { language: 'typescript', icon: <CodeIcon color="info" /> },
  '.tsx': { language: 'typescript', icon: <CodeIcon color="info" /> },
  '.json': { language: 'json', icon: <DataIcon color="success" /> },
  '.yaml': { language: 'yaml', icon: <SettingsIcon color="secondary" /> },
  '.yml': { language: 'yaml', icon: <SettingsIcon color="secondary" /> },
  '.md': { language: 'markdown', icon: <DescriptionIcon /> },
  '.txt': { language: 'plaintext', icon: <DescriptionIcon /> },
  '.log': { language: 'plaintext', icon: <DescriptionIcon /> },
};

const IMPORTANT_DIRS = [
  { path: 'bot', label: 'Bot Source Code', icon: '🤖' },
  { path: 'bot/strategy', label: 'Strategies', icon: '📊' },
  { path: 'bot/utils', label: 'Utilities', icon: '🛠️' },
  { path: 'bot/safety', label: 'Safety Modules', icon: '🛡️' },
  { path: 'webui', label: 'Web UI', icon: '🌐' },
  { path: 'config', label: 'Configuration', icon: '⚙️' },
];

const FileEditor = () => {
  const [currentPath, setCurrentPath] = useState('');
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [pathHistory, setPathHistory] = useState(['']);

  // Code Explanation State
  const [explanationMode, setExplanationMode] = useState('trader');
  const [explanationOpen, setExplanationOpen] = useState(false);
  const [explanation, setExplanation] = useState(null);
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [explanationError, setExplanationError] = useState(null);

  useEffect(() => {
    loadDirectory(currentPath);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPath]);

  const loadDirectory = async (path) => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/file-manager/list`, {
        path: path || '.',
      });

      if (response.data.status === 'success') {
        // Sort: directories first, then files alphabetically
        const sorted = [...response.data.items].sort((a, b) => {
          if (a.type !== b.type) {
            return a.type === 'directory' ? -1 : 1;
          }
          return a.name.localeCompare(b.name);
        });
        setFiles(sorted);
      } else {
        setError(response.data.message || 'Failed to load directory');
      }
    } catch (err) {
      console.error('Load directory error:', err);
      setError(err.response?.data?.message || err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadFile = async (filePath) => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/file-manager/read`, {
        path: filePath,
      });

      if (response.data.status === 'success') {
        setFileContent(response.data.content);
        setSelectedFile(filePath);
      } else {
        setError(response.data.message || 'Failed to load file');
      }
    } catch (err) {
      console.error('Load file error:', err);
      setError(err.response?.data?.message || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFileClick = (item) => {
    if (item.type === 'directory') {
      const newPath = currentPath ? `${currentPath}/${item.name}` : item.name;
      setPathHistory([...pathHistory, newPath]);
      setCurrentPath(newPath);
    } else {
      const fullPath = currentPath ? `${currentPath}/${item.name}` : item.name;
      loadFile(fullPath);
    }
  };

  const handleNavigateTo = (path) => {
    setPathHistory([...pathHistory, path]);
    setCurrentPath(path);
  };

  const handleBack = () => {
    if (pathHistory.length > 1) {
      const newHistory = pathHistory.slice(0, -1);
      setPathHistory(newHistory);
      setCurrentPath(newHistory[newHistory.length - 1]);
    }
  };

  const handleBreadcrumbClick = (index) => {
    const pathParts = currentPath.split('/');
    const newPath = pathParts.slice(0, index + 1).join('/');
    setCurrentPath(newPath);
  };

  const handleSaveFile = async (content) => {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/file-manager/save`, {
        path: selectedFile,
        content: content,
      });

      if (response.data.status === 'success') {
        return true;
      } else {
        throw new Error(response.data.message || 'Failed to save file');
      }
    } catch (err) {
      throw err;
    }
  };

  const handleCloseFile = () => {
    setSelectedFile(null);
    setFileContent('');
    setExplanation(null);
  };

  const handleExplainCode = async () => {
    if (!selectedFile) return;

    // Check if file is Python
    if (!selectedFile.endsWith('.py')) {
      setExplanationError('Only Python (.py) files can be explained');
      setExplanationOpen(true);
      return;
    }

    setExplanationLoading(true);
    setExplanationError(null);
    setExplanationOpen(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/code-explainer/explain`, {
        file_path: selectedFile,
        mode: explanationMode,
      });

      if (response.data.status === 'success') {
        setExplanation(response.data);
      } else {
        setExplanationError(response.data.message || 'Failed to explain code');
      }
    } catch (err) {
      console.error('Explain code error:', err);
      setExplanationError(err.response?.data?.message || err.message || 'Failed to explain code');
    } finally {
      setExplanationLoading(false);
    }
  };

  const handleExplanationClose = () => {
    setExplanationOpen(false);
  };

  const getFileExtension = (filename) => {
    const match = filename.match(/\.[^.]+$/);
    return match ? match[0] : '';
  };

  const getFileLanguage = (filename) => {
    const ext = getFileExtension(filename);
    return FILE_TYPES[ext]?.language || 'plaintext';
  };

  const getFileIcon = (item) => {
    if (item.type === 'directory') {
      return <FolderIcon color="primary" />;
    }
    const ext = getFileExtension(item.name);
    return FILE_TYPES[ext]?.icon || <FileIcon />;
  };

  const getFilteredFiles = () => {
    if (!searchTerm) return files;

    return files.filter((item) => item.name.toLowerCase().includes(searchTerm.toLowerCase()));
  };

  const getBreadcrumbs = () => {
    if (!currentPath) return ['Root'];
    return ['Root', ...currentPath.split('/')];
  };

  const canGoBack = pathHistory.length > 1;

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', p: 2 }}>
      <Typography variant="h5" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <CodeIcon /> File Editor with AI
      </Typography>

      <Grid container spacing={2} sx={{ flexGrow: 1, overflow: 'hidden' }}>
        {/* File Browser */}
        <Grid item xs={12} md={selectedFile ? 3 : 12}>
          <Paper sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* Browser Header */}
            <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <Tooltip title="Go Back">
                  <span>
                    <IconButton size="small" onClick={handleBack} disabled={!canGoBack}>
                      <BackIcon />
                    </IconButton>
                  </span>
                </Tooltip>

                <Tooltip title="Refresh">
                  <IconButton size="small" onClick={() => loadDirectory(currentPath)}>
                    <RefreshIcon />
                  </IconButton>
                </Tooltip>

                <Breadcrumbs sx={{ flexGrow: 1 }}>
                  {getBreadcrumbs().map((part, index) => (
                    <Link
                      key={index}
                      component="button"
                      variant="body2"
                      onClick={() => {
                        if (index === 0) {
                          setCurrentPath('');
                        } else {
                          handleBreadcrumbClick(index - 1);
                        }
                      }}
                      sx={{ cursor: 'pointer' }}
                    >
                      {index === 0 ? <HomeIcon fontSize="small" /> : part}
                    </Link>
                  ))}
                </Breadcrumbs>
              </Box>

              <TextField
                size="small"
                fullWidth
                placeholder="Search files..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon />
                    </InputAdornment>
                  ),
                }}
              />
            </Box>

            {/* Quick Access */}
            {!currentPath && !searchTerm && (
              <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
                <Typography variant="subtitle2" gutterBottom>
                  Quick Access
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {IMPORTANT_DIRS.map((dir) => (
                    <Chip
                      key={dir.path}
                      label={`${dir.icon} ${dir.label}`}
                      onClick={() => handleNavigateTo(dir.path)}
                      variant="outlined"
                      size="small"
                    />
                  ))}
                </Box>
              </Box>
            )}

            {/* File List */}
            <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
              {loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', p: 4 }}>
                  <CircularProgress />
                </Box>
              ) : error ? (
                <Alert severity="error" sx={{ m: 2 }}>
                  {error}
                </Alert>
              ) : (
                <List dense>
                  {getFilteredFiles().map((item, index) => (
                    <ListItem key={index} disablePadding>
                      <ListItemButton onClick={() => handleFileClick(item)}>
                        <ListItemIcon>{getFileIcon(item)}</ListItemIcon>
                        <ListItemText
                          primary={item.name}
                          secondary={
                            item.type === 'file' && item.size
                              ? `${(item.size / 1024).toFixed(1)} KB`
                              : undefined
                          }
                        />
                      </ListItemButton>
                    </ListItem>
                  ))}
                  {getFilteredFiles().length === 0 && (
                    <ListItem>
                      <ListItemText
                        primary="No files found"
                        secondary={
                          searchTerm ? 'Try a different search term' : 'This directory is empty'
                        }
                      />
                    </ListItem>
                  )}
                </List>
              )}
            </Box>
          </Paper>
        </Grid>

        {/* Code Editor */}
        {selectedFile && (
          <Grid item xs={12} md={9}>
            <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
              <Box
                sx={{
                  mb: 2,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 2,
                }}
              >
                <Typography variant="h6">{selectedFile}</Typography>

                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                  {/* Explain Code Section */}
                  {selectedFile.endsWith('.py') && (
                    <>
                      <FormControl size="small" sx={{ minWidth: 120 }}>
                        <InputLabel>Reading Level</InputLabel>
                        <Select
                          value={explanationMode}
                          label="Reading Level"
                          onChange={(e) => setExplanationMode(e.target.value)}
                        >
                          <MenuItem value="simple">🎓 Simple</MenuItem>
                          <MenuItem value="trader">📊 Trader</MenuItem>
                          <MenuItem value="tech">⚙️ Technical</MenuItem>
                        </Select>
                      </FormControl>

                      <Tooltip title="Explain this code in plain English">
                        <Button
                          variant="contained"
                          color="secondary"
                          startIcon={<ExplainIcon />}
                          onClick={handleExplainCode}
                          disabled={explanationLoading}
                        >
                          {explanationLoading ? 'Analyzing...' : 'Explain Code'}
                        </Button>
                      </Tooltip>
                    </>
                  )}

                  <Button variant="outlined" size="small" onClick={handleCloseFile}>
                    Close File
                  </Button>
                </Box>
              </Box>

              <CodeEditor
                filePath={selectedFile}
                initialValue={fileContent}
                language={getFileLanguage(selectedFile)}
                theme="vs-dark"
                readOnly={true}
                height="calc(100vh - 250px)"
                onSave={handleSaveFile}
                showToolbar={true}
                enableAI={true}
              />
            </Box>
          </Grid>
        )}
      </Grid>

      {!selectedFile && (
        <Alert severity="info" sx={{ mt: 2 }}>
          <strong>💡 Getting Started:</strong>
          <ul style={{ marginBottom: 0, paddingLeft: 20 }}>
            <li>Use Quick Access chips to navigate to common directories</li>
            <li>Click folders to browse, click files to open in the editor</li>
            <li>
              Files open in <strong>Read-Only mode</strong> by default for safety
            </li>
            <li>Click the 🔒 button to enable editing (creates auto-backup)</li>
            <li>
              Use <strong>AI Fix This</strong> ✨ button for code analysis and suggestions
            </li>
            <li>Access code templates via the 📋 button</li>
            <li>Keyboard shortcuts: Ctrl+S (Save), Ctrl+Shift+F (Format)</li>
          </ul>
        </Alert>
      )}

      {/* Code Explanation Panel */}
      <CodeExplanationPanel
        open={explanationOpen}
        onClose={handleExplanationClose}
        explanation={explanation}
        loading={explanationLoading}
        error={explanationError}
      />
    </Box>
  );
};

export default FileEditor;
