/**
 * Strategy Leg Selector
 * =====================
 * Allows selecting multiple option legs for a strategy from the chain.
 * Shows which legs are needed and tracks selections.
 * 
 * Created: January 5, 2026
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  LinearProgress,
  Alert,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Divider
} from '@mui/material';
import {
  CheckCircle as CheckIcon,
  Cancel as CancelIcon,
  ArrowForward as NextIcon,
  Replay as ResetIcon
} from '@mui/icons-material';

export default function StrategyLegSelector({ 
  strategyContext, 
  selectedLegs,
  onLegSelected,
  onComplete,
  onCancel 
}) {
  if (!strategyContext) return null;

  const { strategyName, requiredLegs, suggestedStrikes, legHints, legDefinitions } = strategyContext;
  const progress = (selectedLegs.length / requiredLegs) * 100;
  const isComplete = selectedLegs.length === requiredLegs;

  const getLegDescription = (index) => {
    // Use leg definitions if available to show exact requirement
    if (legDefinitions && legDefinitions[index]) {
      const leg = legDefinitions[index];
      const strikeValue = suggestedStrikes?.[leg.strikeKey];
      const sideText = leg.side === 'buy' ? 'BUY' : 'SELL';
      const typeText = leg.type.toUpperCase();
      return strikeValue 
        ? `${sideText} ${typeText} @ ~$${strikeValue.toLocaleString()}`
        : `${sideText} ${typeText}`;
    }
    
    // Fallback to leg hints if available
    if (legHints && legHints[index]) {
      return legHints[index];
    }
    
    // Last fallback to suggested strikes
    const legKeys = Object.keys(suggestedStrikes || {});
    if (index < legKeys.length) {
      const key = legKeys[index];
      const strike = suggestedStrikes[key];
      return `${key.replace(/_/g, ' ')}: ~$${strike?.toLocaleString()}`;
    }
    return `Leg ${index + 1}`;
  };

  return (
    <Card 
      sx={{ 
        position: 'sticky',
        top: 16,
        zIndex: 1000,
        border: 2,
        borderColor: 'primary.main',
        boxShadow: 4
      }}
    >
      <CardContent>
        {/* Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Box>
            <Typography variant="h6" fontWeight="bold">
              🎯 Building: {strategyName}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Select {requiredLegs} legs from the chain below
            </Typography>
          </Box>
          <IconButton onClick={onCancel} size="small">
            <CancelIcon />
          </IconButton>
        </Box>

        {/* Progress */}
        <Box sx={{ mb: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography variant="body2" fontWeight="medium">
              Progress
            </Typography>
            <Typography variant="body2" color="primary">
              {selectedLegs.length} / {requiredLegs} legs selected
            </Typography>
          </Box>
          <LinearProgress 
            variant="determinate" 
            value={progress} 
            sx={{ height: 8, borderRadius: 1 }}
          />
        </Box>

        {/* Selected Legs */}
        <List dense sx={{ bgcolor: 'background.default', borderRadius: 1, mb: 2 }}>
          {Array.from({ length: requiredLegs }).map((_, index) => {
            const leg = selectedLegs[index];
            const isSelected = !!leg;
            
            return (
              <React.Fragment key={index}>
                {index > 0 && <Divider />}
                <ListItem
                  secondaryAction={
                    isSelected && (
                      <IconButton 
                        edge="end" 
                        size="small"
                        onClick={() => {
                          const newLegs = [...selectedLegs];
                          newLegs.splice(index, 1);
                          onLegSelected(newLegs);
                        }}
                      >
                        <CancelIcon fontSize="small" />
                      </IconButton>
                    )
                  }
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                    {isSelected ? (
                      <CheckIcon color="success" fontSize="small" />
                    ) : (
                      <Box 
                        sx={{ 
                          width: 20, 
                          height: 20, 
                          border: 2, 
                          borderColor: 'divider',
                          borderRadius: '50%'
                        }} 
                      />
                    )}
                    <ListItemText
                      primary={isSelected ? leg.symbol : getLegDescription(index)}
                      secondary={isSelected ? 
                        `${leg.side.toUpperCase()} @ $${leg.strike} • IV: ${leg.iv || 'N/A'}` :
                        'Click a row in the chain below to select'
                      }
                      primaryTypographyProps={{
                        variant: 'body2',
                        fontWeight: isSelected ? 'bold' : 'normal',
                        color: isSelected ? 'text.primary' : 'text.secondary'
                      }}
                      secondaryTypographyProps={{
                        variant: 'caption'
                      }}
                    />
                  </Box>
                </ListItem>
              </React.Fragment>
            );
          })}
        </List>

        {/* Hints */}
        {!isComplete && (
          <Alert severity="info" icon="💡" sx={{ mb: 2 }}>
            {legDefinitions && legDefinitions[selectedLegs.length] ? (
              <>
                <strong>Next: </strong>
                Click the <strong>{legDefinitions[selectedLegs.length].side === 'buy' ? 'B (Buy)' : 'S (Sell)'}</strong> button 
                {' '}for a <strong>{legDefinitions[selectedLegs.length].type.toUpperCase()}</strong> option near the suggested strike.
              </>
            ) : (
              'Click on option rows in the chain below to add them to your strategy. Suggested strikes are highlighted.'
            )}
          </Alert>
        )}

        {/* Actions */}
        <Box sx={{ display: 'flex', gap: 1 }}>
          {selectedLegs.length > 0 && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<ResetIcon />}
              onClick={() => onLegSelected([])}
              fullWidth
            >
              Reset
            </Button>
          )}
          <Button
            variant="contained"
            size="large"
            endIcon={<NextIcon />}
            onClick={onComplete}
            disabled={!isComplete}
            fullWidth
            sx={{ fontWeight: 'bold' }}
          >
            {isComplete ? 'Review & Execute Strategy' : 'Select All Legs First'}
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
}
