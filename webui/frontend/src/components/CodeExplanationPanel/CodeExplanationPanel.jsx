import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
  Button,
  IconButton,
  Chip,
  Divider,
  Paper,
  Grid,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Tooltip,
  CircularProgress,
  Stack,
} from '@mui/material';
import {
  Close as CloseIcon,
  ContentCopy as CopyIcon,
  Download as DownloadIcon,
  ExpandMore as ExpandMoreIcon,
  CheckCircle as CheckIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  Code as CodeIcon,
  Functions as FunctionIcon,
  Class as ClassIcon,
  BugReport as BugIcon,
  Analytics as AnalyticsIcon,
} from '@mui/icons-material';

const CodeExplanationPanel = ({ open, onClose, explanation, loading, error }) => {
  const [copied, setCopied] = useState(false);

  const handleCopyExplanation = () => {
    if (explanation?.explanation) {
      navigator.clipboard.writeText(explanation.explanation);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownloadMarkdown = () => {
    if (!explanation) return;

    const markdown = generateMarkdown();
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `code_explanation_${Date.now()}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const generateMarkdown = () => {
    if (!explanation) return '';

    let md = `# Code Explanation\n\n`;
    md += `**Mode**: ${explanation.mode}\n`;
    md += `**Generated**: ${new Date().toLocaleString()}\n\n`;
    md += `---\n\n`;
    md += `## Summary\n\n`;
    md += `${explanation.explanation}\n\n`;
    md += `---\n\n`;
    md += `## Statistics\n\n`;
    md += `- **Total Lines**: ${explanation.statistics?.total_lines || 0}\n`;
    md += `- **Functions**: ${explanation.statistics?.functions_count || 0}\n`;
    md += `- **Classes**: ${explanation.statistics?.classes_count || 0}\n`;
    md += `- **Complexity Score**: ${explanation.statistics?.complexity_score || 0}\n`;
    md += `- **Issues**: ${explanation.statistics?.issues_count || 0}\n\n`;

    if (explanation.functions?.length > 0) {
      md += `## Functions\n\n`;
      explanation.functions.forEach((func) => {
        md += `### ${func.async ? 'async ' : ''}${func.name}(${func.args?.join(', ') || ''})\n`;
        if (func.docstring) md += `${func.docstring}\n`;
        md += `- **Lines**: ${func.line_start}-${func.line_end}\n`;
        md += `- **Complexity**: ${func.complexity}\n\n`;
      });
    }

    if (explanation.classes?.length > 0) {
      md += `## Classes\n\n`;
      explanation.classes.forEach((cls) => {
        md += `### ${cls.name}\n`;
        if (cls.docstring) md += `${cls.docstring}\n`;
        md += `- **Methods**: ${cls.methods_count}\n`;
        md += `- **Lines**: ${cls.line_start}-${cls.line_end}\n\n`;
      });
    }

    if (explanation.issues?.length > 0) {
      md += `## Issues Detected\n\n`;
      explanation.issues.forEach((issue) => {
        md += `- **${issue.type}** (Line ${issue.line}): ${issue.description}\n`;
      });
    }

    return md;
  };

  const getComplexityColor = (score) => {
    if (score < 10) return 'success';
    if (score < 20) return 'warning';
    return 'error';
  };

  const getComplexityLabel = (score) => {
    if (score < 10) return 'Simple';
    if (score < 20) return 'Moderate';
    return 'Complex';
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          minHeight: '60vh',
          maxHeight: '90vh',
        },
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <CodeIcon color="primary" />
          <Typography variant="h6">Code Explanation</Typography>
          {explanation?.mode && (
            <Chip
              label={explanation.mode.toUpperCase()}
              size="small"
              color="primary"
              variant="outlined"
            />
          )}
        </Box>
        <IconButton edge="end" onClick={onClose}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers>
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 8 }}>
            <CircularProgress />
            <Typography sx={{ ml: 2 }}>Analyzing code...</Typography>
          </Box>
        )}

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {!loading && !error && explanation && (
          <Box>
            {/* Statistics Overview */}
            <Paper variant="outlined" sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
              <Typography
                variant="subtitle2"
                gutterBottom
                sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
              >
                <AnalyticsIcon fontSize="small" /> Quick Statistics
              </Typography>
              <Grid container spacing={2} sx={{ mt: 1 }}>
                <Grid item xs={6} sm={3}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" color="primary">
                      {explanation.statistics?.total_lines || 0}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Lines of Code
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={3}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" color="secondary">
                      {explanation.statistics?.functions_count || 0}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Functions
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={3}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" color="info.main">
                      {explanation.statistics?.classes_count || 0}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Classes
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={3}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Chip
                      label={getComplexityLabel(explanation.statistics?.complexity_score || 0)}
                      color={getComplexityColor(explanation.statistics?.complexity_score || 0)}
                      sx={{ fontSize: '1rem', fontWeight: 'bold' }}
                    />
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      display="block"
                      sx={{ mt: 0.5 }}
                    >
                      Complexity: {explanation.statistics?.complexity_score || 0}
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </Paper>

            {/* Main Explanation */}
            <Accordion defaultExpanded>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <InfoIcon color="primary" />
                  <Typography variant="subtitle1" fontWeight="bold">
                    Summary Explanation
                  </Typography>
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                <Typography
                  variant="body1"
                  sx={{
                    whiteSpace: 'pre-wrap',
                    lineHeight: 1.8,
                    fontFamily: 'system-ui, -apple-system, sans-serif',
                  }}
                >
                  {explanation.explanation}
                </Typography>
              </AccordionDetails>
            </Accordion>

            {/* Functions */}
            {explanation.functions && explanation.functions.length > 0 && (
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <FunctionIcon color="secondary" />
                    <Typography variant="subtitle1" fontWeight="bold">
                      Functions ({explanation.functions.length})
                    </Typography>
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  <List dense>
                    {explanation.functions.map((func, index) => (
                      <ListItem
                        key={index}
                        sx={{ flexDirection: 'column', alignItems: 'flex-start' }}
                      >
                        <Box sx={{ width: '100%' }}>
                          <Typography
                            variant="subtitle2"
                            sx={{ fontFamily: 'monospace', color: 'primary.main' }}
                          >
                            {func.async ? 'async ' : ''}
                            {func.name}({func.args?.join(', ') || ''})
                          </Typography>
                          {func.docstring && (
                            <Typography
                              variant="body2"
                              color="text.secondary"
                              sx={{ mt: 0.5, ml: 2 }}
                            >
                              {func.docstring}
                            </Typography>
                          )}
                          <Stack direction="row" spacing={1} sx={{ mt: 1, ml: 2 }}>
                            <Chip
                              label={`Lines ${func.line_start}-${func.line_end}`}
                              size="small"
                              variant="outlined"
                            />
                            <Chip
                              label={`Complexity: ${func.complexity}`}
                              size="small"
                              color={getComplexityColor(func.complexity)}
                            />
                            {func.async && <Chip label="Async" size="small" color="info" />}
                          </Stack>
                        </Box>
                        {index < explanation.functions.length - 1 && (
                          <Divider sx={{ width: '100%', mt: 1 }} />
                        )}
                      </ListItem>
                    ))}
                  </List>
                </AccordionDetails>
              </Accordion>
            )}

            {/* Classes */}
            {explanation.classes && explanation.classes.length > 0 && (
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <ClassIcon color="info" />
                    <Typography variant="subtitle1" fontWeight="bold">
                      Classes ({explanation.classes.length})
                    </Typography>
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  <List dense>
                    {explanation.classes.map((cls, index) => (
                      <ListItem
                        key={index}
                        sx={{ flexDirection: 'column', alignItems: 'flex-start' }}
                      >
                        <Box sx={{ width: '100%' }}>
                          <Typography
                            variant="subtitle2"
                            sx={{ fontFamily: 'monospace', color: 'info.main' }}
                          >
                            class {cls.name}
                            {cls.bases && cls.bases.length > 0 && ` (${cls.bases.join(', ')})`}
                          </Typography>
                          {cls.docstring && (
                            <Typography
                              variant="body2"
                              color="text.secondary"
                              sx={{ mt: 0.5, ml: 2 }}
                            >
                              {cls.docstring}
                            </Typography>
                          )}
                          <Stack direction="row" spacing={1} sx={{ mt: 1, ml: 2 }}>
                            <Chip
                              label={`${cls.methods_count} methods`}
                              size="small"
                              variant="outlined"
                            />
                            <Chip
                              label={`Lines ${cls.line_start}-${cls.line_end}`}
                              size="small"
                              variant="outlined"
                            />
                          </Stack>
                          {cls.methods && cls.methods.length > 0 && (
                            <Typography
                              variant="caption"
                              color="text.secondary"
                              sx={{ mt: 1, ml: 2, display: 'block' }}
                            >
                              Methods: {cls.methods.join(', ')}
                            </Typography>
                          )}
                        </Box>
                        {index < explanation.classes.length - 1 && (
                          <Divider sx={{ width: '100%', mt: 1 }} />
                        )}
                      </ListItem>
                    ))}
                  </List>
                </AccordionDetails>
              </Accordion>
            )}

            {/* Issues */}
            {explanation.issues && explanation.issues.length > 0 && (
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <BugIcon color="error" />
                    <Typography variant="subtitle1" fontWeight="bold">
                      Issues Detected ({explanation.issues.length})
                    </Typography>
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  <List dense>
                    {explanation.issues.map((issue, index) => (
                      <ListItem key={index}>
                        <ListItemIcon>
                          <WarningIcon color="warning" />
                        </ListItemIcon>
                        <ListItemText
                          primary={
                            <Typography variant="body2">
                              <strong>{issue.type}</strong> (Line {issue.line})
                            </Typography>
                          }
                          secondary={issue.description}
                        />
                      </ListItem>
                    ))}
                  </List>
                </AccordionDetails>
              </Accordion>
            )}

            {/* No Issues */}
            {(!explanation.issues || explanation.issues.length === 0) && (
              <Alert severity="success" icon={<CheckIcon />} sx={{ mt: 2 }}>
                No issues detected! This code looks clean.
              </Alert>
            )}
          </Box>
        )}
      </DialogContent>

      <DialogActions>
        <Tooltip title="Copy explanation to clipboard">
          <Button
            startIcon={copied ? <CheckIcon /> : <CopyIcon />}
            onClick={handleCopyExplanation}
            disabled={!explanation || loading}
            color={copied ? 'success' : 'primary'}
          >
            {copied ? 'Copied!' : 'Copy'}
          </Button>
        </Tooltip>
        <Tooltip title="Download as Markdown file">
          <Button
            startIcon={<DownloadIcon />}
            onClick={handleDownloadMarkdown}
            disabled={!explanation || loading}
          >
            Download MD
          </Button>
        </Tooltip>
        <Button onClick={onClose} variant="contained">
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default CodeExplanationPanel;
