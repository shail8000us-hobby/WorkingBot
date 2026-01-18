import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  CircularProgress,
  Alert,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Paper,
  Divider,
  Chip,
  Tooltip,
} from '@mui/material';
import {
  Close as CloseIcon,
  Refresh as RefreshIcon,
  Download as DownloadIcon,
  OpenInNew as OpenInNewIcon,
  Book as BookIcon,
  Security as SecurityIcon,
} from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import api from '../utils/apiShim';

const DocumentationViewer = ({ open, onClose, docType = 'capital-protection' }) => {
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchDocumentation = async () => {
    setLoading(true);
    setError(null);

    try {
      const { data } = await api.get(`/api/docs/${docType}`);

      if (data.success) {
        setContent(data.content);
        setLastUpdated(data.last_updated);
      } else {
        setError(data.error || 'Failed to load documentation');
      }
    } catch (err) {
      setError('Failed to fetch documentation');
      console.error('Documentation fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      fetchDocumentation();
    }
  }, [open, docType]);

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${docType}-documentation.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const getDocIcon = () => {
    switch (docType) {
      case 'capital-protection':
        return <SecurityIcon />;
      default:
        return <BookIcon />;
    }
  };

  const getDocTitle = () => {
    switch (docType) {
      case 'capital-protection':
        return 'Capital Protection System Documentation';
      default:
        return 'Documentation';
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: {
          height: '90vh',
          maxHeight: '90vh',
        },
      }}
    >
      <DialogTitle
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          pb: 1,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {getDocIcon()}
          <Typography variant="h6" component="div">
            {getDocTitle()}
          </Typography>
          {lastUpdated && (
            <Chip
              label={`Updated: ${new Date(lastUpdated * 1000).toLocaleDateString()}`}
              size="small"
              variant="outlined"
            />
          )}
        </Box>
        <Box>
          <Tooltip title="Refresh">
            <IconButton onClick={fetchDocumentation} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Download">
            <IconButton onClick={handleDownload} disabled={!content}>
              <DownloadIcon />
            </IconButton>
          </Tooltip>
          <IconButton onClick={onClose}>
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <Divider />

      <DialogContent sx={{ p: 0, overflow: 'hidden' }}>
        {loading && (
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              height: '200px',
            }}
          >
            <CircularProgress />
          </Box>
        )}

        {error && (
          <Box sx={{ p: 2 }}>
            <Alert
              severity="error"
              action={
                <Button color="inherit" size="small" onClick={fetchDocumentation}>
                  Retry
                </Button>
              }
            >
              {error}
            </Alert>
          </Box>
        )}

        {content && !loading && !error && (
          <Paper
            sx={{
              height: '100%',
              overflow: 'auto',
              p: 3,
              '& h1, & h2, & h3, & h4, & h5, & h6': {
                color: 'primary.main',
                mt: 3,
                mb: 2,
              },
              '& h1': {
                borderBottom: '2px solid',
                borderColor: 'primary.main',
                pb: 1,
              },
              '& h2': {
                borderBottom: '1px solid',
                borderColor: 'divider',
                pb: 0.5,
              },
              '& code': {
                backgroundColor: 'grey.800',
                color: 'grey.100',
                px: 0.5,
                py: 0.25,
                borderRadius: 0.5,
                fontFamily: 'monospace',
              },
              '& pre': {
                backgroundColor: 'grey.900',
                color: 'grey.100',
                p: 2,
                borderRadius: 1,
                overflow: 'auto',
                border: '1px solid',
                borderColor: 'divider',
              },
              '& blockquote': {
                borderLeft: '4px solid',
                borderColor: 'primary.main',
                pl: 2,
                ml: 0,
                fontStyle: 'italic',
                backgroundColor: 'grey.800',
                py: 1,
              },
              '& table': {
                borderCollapse: 'collapse',
                width: '100%',
                mb: 2,
              },
              '& th, & td': {
                border: '1px solid',
                borderColor: 'divider',
                px: 2,
                py: 1,
                textAlign: 'left',
              },
              '& th': {
                backgroundColor: 'grey.800',
                color: 'grey.100',
                fontWeight: 'bold',
              },
              '& ul, & ol': {
                pl: 2,
              },
              '& li': {
                mb: 0.5,
              },
            }}
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                // Custom components for better styling
                h1: ({ children }) => (
                  <Typography variant="h4" component="h1" gutterBottom>
                    {children}
                  </Typography>
                ),
                h2: ({ children }) => (
                  <Typography variant="h5" component="h2" gutterBottom>
                    {children}
                  </Typography>
                ),
                h3: ({ children }) => (
                  <Typography variant="h6" component="h3" gutterBottom>
                    {children}
                  </Typography>
                ),
                h4: ({ children }) => (
                  <Typography variant="subtitle1" component="h4" gutterBottom>
                    {children}
                  </Typography>
                ),
                p: ({ children }) => (
                  <Typography variant="body1" paragraph>
                    {children}
                  </Typography>
                ),
                code: ({ children, className }) => {
                  const isInline = !className;
                  return isInline ? (
                    <code>{children}</code>
                  ) : (
                    <pre>
                      <code>{children}</code>
                    </pre>
                  );
                },
              }}
            >
              {content}
            </ReactMarkdown>
          </Paper>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Close</Button>
        <Button onClick={handleDownload} disabled={!content} startIcon={<DownloadIcon />}>
          Download
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default DocumentationViewer;
