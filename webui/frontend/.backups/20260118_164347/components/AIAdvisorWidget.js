import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  IconButton,
  Collapse,
  CircularProgress,
  Chip,
  List,
  ListItem,
  ListItemText,
  Divider
} from '@mui/material';
import {
  Psychology,
  Send,
  ExpandMore,
  ExpandLess,
  Refresh,
  Link as LinkIcon
} from '@mui/icons-material';
import api from '../utils/apiShim';

export default function AIAdvisorWidget({ onNavigate }) {
  const [expanded, setExpanded] = useState(false);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [history, setHistory] = useState([]);

  // Quick questions
  const quickQuestions = [
    "Why is trading stopped?",
    "What is volatility safety?",
    "How do I manage risk?",
    "Explain my current positions"
  ];

  const handleAsk = async () => {
    if (!question.trim()) return;

    setLoading(true);
    try {
      const res = await api.post('/api/ai/ask', { question });
      if (res.data.success) {
        setResponse(res.data);
        setHistory([{ question, answer: res.data.answer }, ...history.slice(0, 4)]);
        setQuestion('');
      }
    } catch (err) {
      setResponse({
        success: false,
        answer: `Error: ${err.message}`,
        suggestions: [],
        related_links: []
      });
    } finally {
      setLoading(false);
    }
  };

  const handleQuickQuestion = (q) => {
    setQuestion(q);
    setTimeout(() => handleAsk(), 100);
  };

  const handleLinkClick = (link) => {
    if (link.tab && onNavigate) {
      onNavigate(link.tab, link.section, link.field);
    } else if (link.url) {
      window.open(link.url, '_blank');
    }
  };

  return (
    <Paper
      elevation={4}
      sx={{
        position: 'fixed',
        bottom: 20,
        right: 20,
        width: expanded ? 400 : 60,
        height: expanded ? 'auto' : 60,
        maxHeight: expanded ? '70vh' : 60,
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        zIndex: 1300,
        overflow: 'hidden',
        borderRadius: 3,
        boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(255,255,255,0.1)'
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: expanded ? 'space-between' : 'center',
          p: 1.5,
          bgcolor: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          color: 'white',
          cursor: 'pointer',
          minHeight: 60,
          '&:hover': {
            bgcolor: 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)',
            transform: 'translateY(-2px)',
            boxShadow: '0 4px 20px rgba(102, 126, 234, 0.4)'
          },
          transition: 'all 0.2s ease-in-out'
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1 }}>
          <Psychology sx={{ fontSize: '1.5rem' }} />
          {expanded && <Typography variant="h6">AI Advisor</Typography>}
        </Box>
        {expanded && (
          <IconButton size="small" sx={{ color: 'white' }}>
            <ExpandMore />
          </IconButton>
        )}
      </Box>

      {/* Content */}
      <Collapse in={expanded}>
        <Box sx={{ p: 2, maxHeight: 'calc(70vh - 64px)', overflow: 'auto' }}>
          {/* Quick Questions */}
          <Typography variant="caption" color="text.secondary" gutterBottom>
            Quick Questions:
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 2 }}>
            {quickQuestions.map((q, i) => (
              <Chip
                key={i}
                label={q}
                size="small"
                onClick={() => handleQuickQuestion(q)}
                sx={{ cursor: 'pointer' }}
              />
            ))}
          </Box>

          {/* Input */}
          <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
            <TextField
              fullWidth
              size="small"
              placeholder="Ask me anything..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleAsk()}
              disabled={loading}
            />
            <IconButton
              color="primary"
              onClick={handleAsk}
              disabled={loading || !question.trim()}
            >
              {loading ? <CircularProgress size={24} /> : <Send />}
            </IconButton>
          </Box>

          {/* Response */}
          {response && (
            <Paper elevation={2} sx={{ p: 2, mb: 2, bgcolor: 'background.default' }}>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-line', mb: 1 }}>
                {response.answer}
              </Typography>

              {/* Suggestions */}
              {response.suggestions && response.suggestions.length > 0 && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="caption" color="text.secondary">
                    Suggestions:
                  </Typography>
                  <List dense>
                    {response.suggestions.map((suggestion, i) => (
                      <ListItem key={i} sx={{ py: 0.5 }}>
                        <ListItemText
                          primary={`• ${suggestion}`}
                          primaryTypographyProps={{ variant: 'caption' }}
                        />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              )}

              {/* Related Links */}
              {response.related_links && response.related_links.length > 0 && (
                <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {response.related_links.map((link, i) => (
                    <Chip
                      key={i}
                      label={link.title}
                      size="small"
                      icon={<LinkIcon />}
                      onClick={() => handleLinkClick(link)}
                      sx={{ cursor: 'pointer' }}
                    />
                  ))}
                </Box>
              )}
            </Paper>
          )}

          {/* History */}
          {history.length > 0 && (
            <Box>
              <Divider sx={{ my: 2 }} />
              <Typography variant="caption" color="text.secondary" gutterBottom>
                Recent Questions:
              </Typography>
              {history.map((item, i) => (
                <Paper
                  key={i}
                  elevation={1}
                  sx={{ p: 1, mb: 1, cursor: 'pointer' }}
                  onClick={() => setQuestion(item.question)}
                >
                  <Typography variant="caption" fontWeight="bold">
                    Q: {item.question}
                  </Typography>
                </Paper>
              ))}
            </Box>
          )}
        </Box>
      </Collapse>
    </Paper>
  );
}
