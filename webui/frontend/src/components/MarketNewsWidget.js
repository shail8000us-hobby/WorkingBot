import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  Collapse,
  CircularProgress,
  Chip,
  List,
  ListItem,
  ListItemText,
  Button,
  Badge,
} from '@mui/material';
import {
  TrendingUp,
  ExpandMore,
  ExpandLess,
  Refresh,
  Link as LinkIcon,
  Warning,
  Error as ErrorIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import api from '../utils/apiShim';

export default function MarketNewsWidget({ onNavigate }) {
  const [expanded, setExpanded] = useState(false);
  const [news, setNews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('all');

  // Fetch news
  const fetchNews = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/api/news/feed?limit=10&priority=${filter}`);
      if (response.data.success) {
        setNews(response.data.news);
      }
    } catch (err) {
      console.error('Error fetching news:', err);
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh every 30 seconds
  useEffect(() => {
    if (expanded) {
      fetchNews();
      const interval = setInterval(fetchNews, 30000);
      return () => clearInterval(interval);
    }
  }, [expanded, filter]);

  const handleRefresh = async () => {
    try {
      await api.post('/api/news/refresh');
      fetchNews();
    } catch (err) {
      console.error('Error refreshing news:', err);
    }
  };

  const handleActionClick = (item) => {
    if (item.action_link && onNavigate) {
      onNavigate(item.action_link.tab, item.action_link.section);
    } else if (item.url && item.url !== '#') {
      window.open(item.url, '_blank');
    }
  };

  const getPriorityIcon = (priority) => {
    switch (priority) {
      case 'critical':
        return <ErrorIcon color="error" />;
      case 'high':
        return <Warning color="warning" />;
      case 'medium':
        return <InfoIcon color="info" />;
      default:
        return <InfoIcon />;
    }
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'critical':
        return 'error';
      case 'high':
        return 'warning';
      case 'medium':
        return 'info';
      default:
        return 'default';
    }
  };

  const criticalCount = news.filter((n) => n.priority === 'critical').length;
  const highCount = news.filter((n) => n.priority === 'high').length;

  return (
    <Paper
      elevation={4}
      sx={{
        position: 'fixed',
        bottom: 20,
        right: expanded ? 440 : 100,
        width: expanded ? 400 : 60,
        height: expanded ? 'auto' : 60,
        maxHeight: expanded ? '70vh' : 60,
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        zIndex: 1300,
        overflow: 'hidden',
        borderRadius: 3,
        boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(255,255,255,0.1)',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: expanded ? 'space-between' : 'center',
          p: 1.5,
          bgcolor: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
          color: 'white',
          cursor: 'pointer',
          minHeight: 60,
          '&:hover': {
            bgcolor: 'linear-gradient(135deg, #f5576c 0%, #f093fb 100%)',
            transform: 'translateY(-2px)',
            boxShadow: '0 4px 20px rgba(245, 87, 108, 0.4)',
          },
          transition: 'all 0.2s ease-in-out',
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1 }}>
          <Badge badgeContent={criticalCount + highCount} color="error">
            <TrendingUp sx={{ fontSize: '1.5rem' }} />
          </Badge>
          {expanded && <Typography variant="h6">Market News</Typography>}
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
          {/* Filters */}
          <Box sx={{ display: 'flex', gap: 1, mb: 2, alignItems: 'center' }}>
            <Typography variant="caption" color="text.secondary">
              Filter:
            </Typography>
            {['all', 'critical', 'high', 'medium', 'low'].map((f) => (
              <Chip
                key={f}
                label={f}
                size="small"
                color={filter === f ? 'primary' : 'default'}
                onClick={() => setFilter(f)}
                sx={{ textTransform: 'capitalize', cursor: 'pointer' }}
              />
            ))}
            <IconButton size="small" onClick={handleRefresh} disabled={loading}>
              {loading ? <CircularProgress size={20} /> : <Refresh />}
            </IconButton>
          </Box>

          {/* News List */}
          {news.length === 0 && !loading && (
            <Typography variant="body2" color="text.secondary" align="center">
              No news available
            </Typography>
          )}

          <List sx={{ p: 0 }}>
            {news.map((item, index) => (
              <Paper
                key={item.id || index}
                elevation={2}
                sx={{
                  mb: 1,
                  p: 1.5,
                  border: item.priority === 'critical' ? '2px solid' : 'none',
                  borderColor: 'error.main',
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                  {getPriorityIcon(item.priority)}
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="subtitle2" fontWeight="bold">
                      {item.title}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block">
                      {item.source} • {new Date(item.timestamp * 1000).toLocaleTimeString()}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 0.5, mb: 1 }}>
                      {item.summary}
                    </Typography>

                    {/* Category & Priority */}
                    <Box sx={{ display: 'flex', gap: 0.5, mb: 1 }}>
                      <Chip
                        label={item.category}
                        size="small"
                        variant="outlined"
                        sx={{ textTransform: 'capitalize' }}
                      />
                      <Chip
                        label={item.priority}
                        size="small"
                        color={getPriorityColor(item.priority)}
                        sx={{ textTransform: 'capitalize' }}
                      />
                    </Box>

                    {/* Action Button */}
                    {item.actionable && (
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<LinkIcon />}
                        onClick={() => handleActionClick(item)}
                        fullWidth
                      >
                        {item.action_text || 'View Details'}
                      </Button>
                    )}
                  </Box>
                </Box>
              </Paper>
            ))}
          </List>

          {/* Footer */}
          <Typography
            variant="caption"
            color="text.secondary"
            align="center"
            display="block"
            sx={{ mt: 2 }}
          >
            Auto-refreshes every 30 seconds
          </Typography>
        </Box>
      </Collapse>
    </Paper>
  );
}
