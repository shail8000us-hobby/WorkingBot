/**
 * ConditionChecks - Display detailed condition check results
 * 
 * Shows which entry conditions passed/failed with explanations
 */

import React from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import InfoIcon from '@mui/icons-material/Info';

const ConditionChecks = ({ rules }) => {
  const checks = [];

  // Check 1: IV Filter
  if (rules?.entry?.ivFilter?.enabled) {
    checks.push({
      name: 'IV Filter',
      enabled: true,
      detail: `IV ${rules.entry.ivFilter.operator} ${rules.entry.ivFilter.value}%`,
      type: 'entry'
    });
  }

  // Check 2: Moneyness
  if (rules?.entry?.moneyness) {
    checks.push({
      name: 'Moneyness',
      enabled: true,
      detail: `Must be ${rules.entry.moneyness.toUpperCase()}`,
      type: 'entry'
    });
  }

  // Check 3: Premium Range
  if (rules?.entry?.premiumRange?.enabled) {
    checks.push({
      name: 'Premium Range',
      enabled: true,
      detail: `₹${rules.entry.premiumRange.min} - ₹${rules.entry.premiumRange.max}`,
      type: 'entry'
    });
  }

  // Check 4: Time Filter
  if (rules?.entry?.timeFilter?.enabled) {
    checks.push({
      name: 'Trading Hours',
      enabled: true,
      detail: `${rules.entry.timeFilter.startTime} - ${rules.entry.timeFilter.endTime}`,
      type: 'entry'
    });
  }

  // Check 5: Underlying Price
  if (rules?.entry?.underlyingPrice?.enabled) {
    checks.push({
      name: 'Spot Price Range',
      enabled: true,
      detail: `$${rules.entry.underlyingPrice.min.toLocaleString()} - $${rules.entry.underlyingPrice.max.toLocaleString()}`,
      type: 'entry'
    });
  }

  // Check 6: Alert Only Mode
  if (rules?.risk?.alertOnlyMode) {
    checks.push({
      name: 'Safe Mode',
      enabled: true,
      detail: 'Orders will be simulated only (no real trades)',
      type: 'risk'
    });
  }

  if (checks.length === 0) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="caption" color="text.secondary">
          ℹ️ No conditions configured. Automation will trigger immediately when started.
        </Typography>
      </Box>
    );
  }

  return (
    <Paper 
      elevation={0} 
      sx={{ 
        p: 2, 
        bgcolor: 'background.default',
        border: '1px solid',
        borderColor: 'divider'
      }}
    >
      <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
        Active Conditions ({checks.length})
      </Typography>
      
      <List dense>
        {checks.map((check, index) => (
          <ListItem 
            key={index}
            sx={{ 
              py: 0.5,
              px: 1,
              borderRadius: 1,
              '&:hover': { bgcolor: 'action.hover' }
            }}
          >
            <ListItemIcon sx={{ minWidth: 32 }}>
              <InfoIcon fontSize="small" color="primary" />
            </ListItemIcon>
            <ListItemText
              primary={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="body2" fontWeight="medium">
                    {check.name}
                  </Typography>
                  <Chip 
                    label={check.type} 
                    size="small" 
                    sx={{ height: 16, fontSize: '9px' }}
                  />
                </Box>
              }
              secondary={
                <Typography variant="caption" color="text.secondary">
                  {check.detail}
                </Typography>
              }
            />
          </ListItem>
        ))}
      </List>

      <Box sx={{ mt: 2, p: 1, bgcolor: 'action.hover', borderRadius: 1 }}>
        <Typography variant="caption" color="text.secondary">
          💡 Open browser console to see live evaluation results for each check
        </Typography>
      </Box>
    </Paper>
  );
};

export default ConditionChecks;
