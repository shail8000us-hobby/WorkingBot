/**
 * AutomationButton - Small ⚡ icon button placed between Strike and Symbol
 * 
 * Features:
 * - Shows ⚡ icon
 * - Status indicator (🟢🟡🔴) based on automation state
 * - Opens AutomationDialog on click
 */

import React from 'react';
import { IconButton, Badge, Tooltip } from '@mui/material';
import FlashOnIcon from '@mui/icons-material/FlashOn';
import { useAutomation } from '../hooks/useAutomation';
import { STATUS_ICONS, STATUS_COLORS, AUTOMATION_STATUS } from '../types/constants';
import AutomationDialog from './AutomationDialog';

const AutomationButton = ({ position }) => {
  const {
    isDialogOpen,
    openDialog,
    closeDialog,
    rules,
    updateRules,
    status,
    automationId,
    startAutomation,
    stopAutomation,
  } = useAutomation(position);

  const getTooltipText = () => {
    switch (status) {
      case AUTOMATION_STATUS.WAITING:
        return 'Automation active - waiting for conditions';
      case AUTOMATION_STATUS.TRIGGERED:
        return 'Automation triggered!';
      case AUTOMATION_STATUS.ACTIVE:
        return 'Position active - monitoring exit';
      case AUTOMATION_STATUS.ERROR:
        return 'Automation error - click to view';
      default:
        return 'Setup automation rules';
    }
  };

  const getStatusColor = () => {
    return STATUS_COLORS[status] || '#6b7280';
  };

  const isActive = status !== AUTOMATION_STATUS.INACTIVE && status !== AUTOMATION_STATUS.COMPLETED;

  return (
    <>
      <Tooltip title={getTooltipText()} arrow>
        <IconButton
          onClick={openDialog}
          size="small"
          sx={{
            color: isActive ? getStatusColor() : 'rgba(255,255,255,0.5)',
            '&:hover': {
              bgcolor: 'rgba(59, 130, 246, 0.1)',
            },
            position: 'relative',
          }}
        >
          <Badge
            badgeContent={isActive ? STATUS_ICONS[status] : null}
            anchorOrigin={{
              vertical: 'top',
              horizontal: 'right',
            }}
            sx={{
              '& .MuiBadge-badge': {
                fontSize: '10px',
                minWidth: '14px',
                height: '14px',
                padding: 0,
              },
            }}
          >
            <FlashOnIcon fontSize="small" />
          </Badge>
        </IconButton>
      </Tooltip>

      {/* Dialog */}
      <AutomationDialog
        open={isDialogOpen}
        onClose={closeDialog}
        position={position}
        rules={rules}
        onRulesChange={updateRules}
        onStart={startAutomation}
        onStop={stopAutomation}
        status={status}
        automationId={automationId}
      />
    </>
  );
};

export default AutomationButton;
