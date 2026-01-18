import React, { useState, useRef, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  Button,
  Tooltip,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  Switch,
  FormControlLabel,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Snackbar,
  CircularProgress,
  Divider,
} from '@mui/material';
import {
  Save as SaveIcon,
  Undo as UndoIcon,
  Redo as RedoIcon,
  FormatAlignLeft as FormatIcon,
  BugReport as FixIcon,
  Help as HelpIcon,
  Lock as LockIcon,
  LockOpen as UnlockIcon,
  ContentCopy as CopyIcon,
  Search as SearchIcon,
  FindReplace as ReplaceIcon,
  AutoAwesome as AIIcon,
  InsertDriveFile as TemplateIcon,
  Backup as BackupIcon,
  History as HistoryIcon,
} from '@mui/icons-material';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5555';

// Code templates for common tasks
const CODE_TEMPLATES = {
  python: {
    'Basic Strategy': `# Strategy Template
from typing import Dict, List, Optional

class MyStrategy:
    def __init__(self, config: Dict):
        self.config = config
        self.name = config.get('name', 'MyStrategy')
    
    def should_buy(self, price: float, indicators: Dict) -> bool:
        """Determine if we should place a buy order"""
        # Add your buy logic here
        return False
    
    def should_sell(self, price: float, indicators: Dict) -> bool:
        """Determine if we should place a sell order"""
        # Add your sell logic here
        return False
    
    def calculate_grid_levels(self, base_price: float, num_levels: int) -> List[float]:
        """Calculate grid price levels"""
        levels = []
        # Add your grid calculation logic here
        return levels
`,
    'API Integration': `# API Integration Template
import aiohttp
import asyncio
from typing import Dict, Optional

class APIClient:
    def __init__(self, api_key: str, secret: str):
        self.api_key = api_key
        self.secret = secret
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_balance(self) -> Dict:
        """Fetch account balance"""
        # Add API call logic here
        pass
    
    async def place_order(self, symbol: str, side: str, amount: float, price: float) -> Dict:
        """Place a trading order"""
        # Add order placement logic here
        pass
`,
    'Data Analysis': `# Data Analysis Template
import pandas as pd
import numpy as np
from typing import Dict, List

def analyze_trading_data(data: pd.DataFrame) -> Dict:
    """Analyze trading performance"""
    
    # Calculate metrics
    total_trades = len(data)
    winning_trades = len(data[data['profit'] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    total_profit = data['profit'].sum()
    avg_profit = data['profit'].mean()
    max_profit = data['profit'].max()
    max_loss = data['profit'].min()
    
    return {
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'win_rate': win_rate,
        'total_profit': total_profit,
        'avg_profit': avg_profit,
        'max_profit': max_profit,
        'max_loss': max_loss
    }
`,
  },
  javascript: {
    'React Component': `import React, { useState, useEffect } from 'react';

function MyComponent() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    // Fetch data on mount
    fetchData();
  }, []);
  
  const fetchData = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/data');
      const result = await response.json();
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  
  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;
  
  return (
    <div>
      <h1>My Component</h1>
      {/* Add your JSX here */}
    </div>
  );
}

export default MyComponent;
`,
    'API Service': `import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5555';

class APIService {
  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    });
  }
  
  async get(endpoint) {
    try {
      const response = await this.client.get(endpoint);
      return response.data;
    } catch (error) {
      console.error('GET Error:', error);
      throw error;
    }
  }
  
  async post(endpoint, data) {
    try {
      const response = await this.client.post(endpoint, data);
      return response.data;
    } catch (error) {
      console.error('POST Error:', error);
      throw error;
    }
  }
}

export default new APIService();
`,
  },
  yaml: {
    'Bot Config': `# Bot Configuration Template
bot:
  name: "MyTradingBot"
  version: "1.0.0"
  mode: LIVE  # DEMO or LIVE

trading:
  symbol: "BTC/USDT"
  base_amount: 100.0
  grid_levels: 10
  grid_spacing: 1.0  # percentage
  
safety:
  max_drawdown: 10.0  # percentage
  max_position_size: 1000.0
  stop_loss: 5.0
  
timeframes:
  primary: "1h"
  secondary: "15m"
  
alerts:
  email: true
  telegram: false
`,
    'Strategy Config': `# Strategy Configuration
strategy:
  name: "GridStrategy"
  type: "grid"
  
  # Grid parameters
  grid:
    levels: 10
    spacing: 1.5  # percentage
    buy_amount: 100.0
    sell_amount: 100.0
  
  # Entry conditions
  entry:
    rsi_lower: 30
    rsi_upper: 70
    volume_threshold: 1000000
  
  # Exit conditions
  exit:
    take_profit: 2.0  # percentage
    stop_loss: 1.0    # percentage
    trailing_stop: true
`,
  },
  json: {
    'Package Config': `{
  "name": "my-trading-bot",
  "version": "1.0.0",
  "description": "Automated trading bot",
  "main": "index.js",
  "scripts": {
    "start": "node index.js",
    "dev": "nodemon index.js",
    "test": "jest"
  },
  "dependencies": {
    "axios": "^1.0.0",
    "dotenv": "^16.0.0"
  },
  "devDependencies": {
    "jest": "^29.0.0",
    "nodemon": "^2.0.0"
  }
}
`,
  },
};

const CodeEditor = ({
  filePath = '',
  initialValue = '',
  language = 'python',
  theme = 'vs-dark',
  readOnly = true,
  height = '600px',
  onSave,
  showToolbar = true,
  enableAI = true,
}) => {
  const [code, setCode] = useState(initialValue);
  const [originalCode, setOriginalCode] = useState(initialValue);
  const [isReadOnly, setIsReadOnly] = useState(readOnly);
  const [isSaving, setIsSaving] = useState(false);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [showTemplateDialog, setShowTemplateDialog] = useState(false);
  const [showAIDialog, setShowAIDialog] = useState(false);
  const [aiSuggestion, setAISuggestion] = useState('');
  const [aiLoading, setAILoading] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [anchorEl, setAnchorEl] = useState(null);
  const [hasChanges, setHasChanges] = useState(false);

  const editorRef = useRef(null);
  const monacoRef = useRef(null);

  useEffect(() => {
    setCode(initialValue);
    setOriginalCode(initialValue);
    setHasChanges(false);
  }, [initialValue, filePath]);

  const handleEditorDidMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;

    // Configure IntelliSense for Python
    if (language === 'python') {
      monaco.languages.registerCompletionItemProvider('python', {
        provideCompletionItems: (model, position) => {
          const suggestions = [
            {
              label: 'async def',
              kind: monaco.languages.CompletionItemKind.Snippet,
              insertText: 'async def ${1:function_name}(${2:params}):\n    ${3:pass}',
              insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
              documentation: 'Async function definition',
            },
            {
              label: 'try-except',
              kind: monaco.languages.CompletionItemKind.Snippet,
              insertText: 'try:\n    ${1:pass}\nexcept ${2:Exception} as e:\n    ${3:pass}',
              insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
              documentation: 'Try-except block',
            },
            {
              label: 'logger.info',
              kind: monaco.languages.CompletionItemKind.Function,
              insertText: 'logger.info("${1:message}")',
              insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
              documentation: 'Log info message',
            },
          ];
          return { suggestions };
        },
      });
    }

    // Add keyboard shortcuts
    editor.addAction({
      id: 'save-file',
      label: 'Save File',
      keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.KEY_S],
      run: () => handleSave(),
    });

    editor.addAction({
      id: 'format-document',
      label: 'Format Document',
      keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.KEY_F],
      run: () => handleFormat(),
    });
  };

  const handleEditorChange = (value) => {
    setCode(value);
    setHasChanges(value !== originalCode);
  };

  const handleSave = async () => {
    if (isReadOnly) {
      setSnackbar({ open: true, message: 'Enable edit mode to save changes', severity: 'warning' });
      return;
    }

    if (!hasChanges) {
      setSnackbar({ open: true, message: 'No changes to save', severity: 'info' });
      return;
    }

    setIsSaving(true);
    try {
      // Create backup first
      await createBackup();

      // Save the file
      if (onSave) {
        await onSave(code);
      } else if (filePath) {
        await axios.post(`${API_BASE_URL}/api/file-manager/save`, {
          path: filePath,
          content: code,
        });
      }

      setOriginalCode(code);
      setHasChanges(false);
      setSnackbar({ open: true, message: 'File saved successfully!', severity: 'success' });
    } catch (error) {
      console.error('Save error:', error);
      setSnackbar({ open: true, message: `Failed to save: ${error.message}`, severity: 'error' });
    } finally {
      setIsSaving(false);
    }
  };

  const createBackup = async () => {
    if (!filePath) return;

    try {
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
      const backupPath = `${filePath}.backup_${timestamp}`;

      await axios.post(`${API_BASE_URL}/api/config-backup/backup`, {
        source: filePath,
        destination: backupPath,
      });

      console.log('Backup created:', backupPath);
    } catch (error) {
      console.error('Backup creation failed:', error);
      // Don't fail the save if backup fails
    }
  };

  const handleFormat = () => {
    if (editorRef.current) {
      editorRef.current.getAction('editor.action.formatDocument').run();
      setSnackbar({ open: true, message: 'Code formatted', severity: 'success' });
    }
  };

  const handleUndo = () => {
    if (editorRef.current) {
      editorRef.current.trigger('keyboard', 'undo');
    }
  };

  const handleRedo = () => {
    if (editorRef.current) {
      editorRef.current.trigger('keyboard', 'redo');
    }
  };

  const handleCopy = () => {
    if (editorRef.current) {
      const selection = editorRef.current.getSelection();
      const selectedText = editorRef.current.getModel().getValueInRange(selection);
      navigator.clipboard.writeText(selectedText || code);
      setSnackbar({ open: true, message: 'Code copied to clipboard', severity: 'success' });
    }
  };

  const handleToggleReadOnly = () => {
    if (!isReadOnly) {
      // Switching to read-only
      if (hasChanges) {
        setShowConfirmDialog(true);
      } else {
        setIsReadOnly(true);
      }
    } else {
      // Switching to edit mode
      setIsReadOnly(false);
      setSnackbar({
        open: true,
        message: '⚠️ Edit mode enabled - changes will affect the live file',
        severity: 'warning',
      });
    }
  };

  const handleConfirmReadOnly = (saveChanges) => {
    if (saveChanges) {
      handleSave().then(() => {
        setIsReadOnly(true);
        setShowConfirmDialog(false);
      });
    } else {
      setCode(originalCode);
      setHasChanges(false);
      setIsReadOnly(true);
      setShowConfirmDialog(false);
    }
  };

  const handleAIFix = async () => {
    setAILoading(true);
    setShowAIDialog(true);

    try {
      // In a real implementation, this would call an AI service
      // For now, we'll provide syntax checking and basic suggestions
      const errors = await checkSyntax();

      if (errors.length === 0) {
        setAISuggestion(
          '✅ No obvious errors found! Your code looks good.\n\nSuggestions:\n• Add more comments for clarity\n• Consider error handling\n• Add logging for debugging'
        );
      } else {
        const errorList = errors.map((e, i) => `${i + 1}. Line ${e.line}: ${e.message}`).join('\n');
        setAISuggestion(
          `⚠️ Found ${errors.length} potential issue(s):\n\n${errorList}\n\nClick "Apply Fix" to auto-correct these issues.`
        );
      }
    } catch (error) {
      setAISuggestion(`❌ Error analyzing code: ${error.message}`);
    } finally {
      setAILoading(false);
    }
  };

  const checkSyntax = async () => {
    // Basic syntax checking (in production, use a proper linter/parser)
    const errors = [];
    const lines = code.split('\n');

    lines.forEach((line, index) => {
      // Check for common Python errors
      if (language === 'python') {
        if (line.trim().startsWith('def ') && !line.trim().endsWith(':')) {
          errors.push({ line: index + 1, message: 'Missing colon after function definition' });
        }
        if (line.includes('=') && !line.includes('==') && line.includes('if ')) {
          errors.push({
            line: index + 1,
            message: 'Possible assignment in condition (use == for comparison)',
          });
        }
      }
    });

    return errors;
  };

  const handleApplyTemplate = (templateName) => {
    const templates = CODE_TEMPLATES[language] || {};
    const template = templates[templateName];

    if (template) {
      if (hasChanges) {
        setSnackbar({
          open: true,
          message: 'Save or discard current changes before applying template',
          severity: 'warning',
        });
      } else {
        setCode(template);
        setHasChanges(true);
        setShowTemplateDialog(false);
        setSnackbar({
          open: true,
          message: `Template "${templateName}" applied`,
          severity: 'success',
        });
      }
    }
  };

  const openTemplateMenu = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const closeTemplateMenu = () => {
    setAnchorEl(null);
  };

  const getLanguageIcon = () => {
    const icons = {
      python: '🐍',
      javascript: '📜',
      yaml: '⚙️',
      json: '📋',
      markdown: '📝',
    };
    return icons[language] || '📄';
  };

  return (
    <Paper elevation={3} sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Toolbar */}
      {showToolbar && (
        <Box
          sx={{
            p: 1.5,
            borderBottom: 1,
            borderColor: 'divider',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: 'background.paper',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography
              variant="subtitle2"
              sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
            >
              {getLanguageIcon()} {filePath ? filePath.split('/').pop() : 'Untitled'}
            </Typography>
            {hasChanges && <Chip label="Modified" size="small" color="warning" />}
            {isReadOnly && (
              <Chip label="Read-Only" size="small" color="default" icon={<LockIcon />} />
            )}
          </Box>

          <Box sx={{ display: 'flex', gap: 0.5 }}>
            <Tooltip title="Undo (Ctrl+Z)">
              <IconButton size="small" onClick={handleUndo} disabled={isReadOnly}>
                <UndoIcon fontSize="small" />
              </IconButton>
            </Tooltip>

            <Tooltip title="Redo (Ctrl+Y)">
              <IconButton size="small" onClick={handleRedo} disabled={isReadOnly}>
                <RedoIcon fontSize="small" />
              </IconButton>
            </Tooltip>

            <Tooltip title="Format Code (Ctrl+Shift+F)">
              <IconButton size="small" onClick={handleFormat}>
                <FormatIcon fontSize="small" />
              </IconButton>
            </Tooltip>

            <Tooltip title="Copy to Clipboard">
              <IconButton size="small" onClick={handleCopy}>
                <CopyIcon fontSize="small" />
              </IconButton>
            </Tooltip>

            <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

            {enableAI && (
              <Tooltip title="AI Fix This">
                <IconButton size="small" onClick={handleAIFix} color="primary">
                  <AIIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}

            <Tooltip title="Code Templates">
              <IconButton size="small" onClick={openTemplateMenu}>
                <TemplateIcon fontSize="small" />
              </IconButton>
            </Tooltip>

            <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

            <Tooltip title={isReadOnly ? 'Enable Edit Mode' : 'Enable Read-Only Mode'}>
              <IconButton
                size="small"
                onClick={handleToggleReadOnly}
                color={isReadOnly ? 'default' : 'warning'}
              >
                {isReadOnly ? <LockIcon fontSize="small" /> : <UnlockIcon fontSize="small" />}
              </IconButton>
            </Tooltip>

            <Tooltip title="Save (Ctrl+S)">
              <span>
                <IconButton
                  size="small"
                  onClick={handleSave}
                  disabled={isReadOnly || !hasChanges || isSaving}
                  color="primary"
                >
                  {isSaving ? <CircularProgress size={20} /> : <SaveIcon fontSize="small" />}
                </IconButton>
              </span>
            </Tooltip>
          </Box>
        </Box>
      )}

      {/* Editor */}
      <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
        <Editor
          height={height}
          language={language}
          theme={theme}
          value={code}
          onChange={handleEditorChange}
          onMount={handleEditorDidMount}
          options={{
            readOnly: isReadOnly,
            minimap: { enabled: true },
            fontSize: 14,
            lineNumbers: 'on',
            rulers: [80, 120],
            wordWrap: 'on',
            automaticLayout: true,
            scrollBeyondLastLine: false,
            folding: true,
            lineDecorationsWidth: 10,
            lineNumbersMinChars: 3,
            glyphMargin: true,
            fixedOverflowWidgets: true,
            smoothScrolling: true,
            cursorBlinking: 'smooth',
            cursorSmoothCaretAnimation: true,
            formatOnPaste: true,
            formatOnType: true,
            suggestOnTriggerCharacters: true,
            acceptSuggestionOnEnter: 'on',
            quickSuggestions: true,
            parameterHints: { enabled: true },
            snippetSuggestions: 'inline',
          }}
        />
      </Box>

      {/* Template Menu */}
      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={closeTemplateMenu}>
        {Object.keys(CODE_TEMPLATES[language] || {}).map((templateName) => (
          <MenuItem
            key={templateName}
            onClick={() => {
              handleApplyTemplate(templateName);
              closeTemplateMenu();
            }}
          >
            <ListItemIcon>
              <TemplateIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>{templateName}</ListItemText>
          </MenuItem>
        ))}
        {(!CODE_TEMPLATES[language] || Object.keys(CODE_TEMPLATES[language]).length === 0) && (
          <MenuItem disabled>
            <ListItemText>No templates for {language}</ListItemText>
          </MenuItem>
        )}
      </Menu>

      {/* Confirm Dialog */}
      <Dialog open={showConfirmDialog} onClose={() => setShowConfirmDialog(false)}>
        <DialogTitle>Unsaved Changes</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            You have unsaved changes. What would you like to do?
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => handleConfirmReadOnly(false)}>Discard Changes</Button>
          <Button onClick={() => handleConfirmReadOnly(true)} variant="contained" color="primary">
            Save Changes
          </Button>
        </DialogActions>
      </Dialog>

      {/* AI Suggestions Dialog */}
      <Dialog open={showAIDialog} onClose={() => setShowAIDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <AIIcon color="primary" />
          AI Code Analysis
        </DialogTitle>
        <DialogContent>
          {aiLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 4 }}>
              <CircularProgress />
              <Typography sx={{ ml: 2 }}>Analyzing your code...</Typography>
            </Box>
          ) : (
            <Alert severity="info" sx={{ whiteSpace: 'pre-wrap' }}>
              {aiSuggestion}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowAIDialog(false)}>Close</Button>
          {aiSuggestion.includes('⚠️') && (
            <Button variant="contained" color="primary" disabled>
              Apply Fix (Coming Soon)
            </Button>
          )}
        </DialogActions>
      </Dialog>

      {/* Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          variant="filled"
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Paper>
  );
};

export default CodeEditor;
