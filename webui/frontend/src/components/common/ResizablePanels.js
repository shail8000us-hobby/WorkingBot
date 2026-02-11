/**
 * Resizable Panels Component
 * 
 * Provides a two-panel layout with a draggable divider for manual resizing.
 * Used in SSR Algo dashboard to separate configuration from payoff chart.
 * 
 * Created: February 10, 2026
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Box } from '@mui/material';

/**
 * Resizable container with draggable divider
 */
const ResizablePanels = ({
  leftPanel,
  rightPanel,
  defaultLeftWidth = 25,
  minLeftWidth = 20,
  minRightWidth = 30,
  storageKey = 'resizable-panels-width',
}) => {
  // Get initial width from localStorage or use default
  const getInitialWidth = () => {
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const parsed = parseInt(stored, 10);
        if (parsed >= minLeftWidth && parsed <= (100 - minRightWidth)) {
          return parsed;
        }
      }
    } catch (err) {
      console.error('Failed to load panel width:', err);
    }
    return defaultLeftWidth;
  };

  const [leftWidth, setLeftWidth] = useState(getInitialWidth);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef(null);

  // Save width to localStorage when it changes
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, leftWidth.toString());
    } catch (err) {
      console.error('Failed to save panel width:', err);
    }
  }, [leftWidth, storageKey]);

  // Handle mouse down on divider
  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  // Handle mouse move while dragging
  const handleMouseMove = useCallback((e) => {
    if (!isDragging || !containerRef.current) return;

    const container = containerRef.current;
    const containerRect = container.getBoundingClientRect();
    const mouseX = e.clientX - containerRect.left;
    const newLeftWidth = (mouseX / containerRect.width) * 100;

    // Enforce min/max constraints
    if (newLeftWidth >= minLeftWidth && newLeftWidth <= (100 - minRightWidth)) {
      setLeftWidth(newLeftWidth);
    }
  }, [isDragging, minLeftWidth, minRightWidth]);

  // Handle mouse up anywhere
  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Add global mouse listeners when dragging
  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      // Prevent text selection while dragging
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'col-resize';

      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
        document.body.style.userSelect = '';
        document.body.style.cursor = '';
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp]);

  return (
    <Box
      ref={containerRef}
      sx={{
        display: 'flex',
        width: '100%',
        height: '100%',
        gap: 0,
        position: 'relative',
        flexWrap: { xs: 'wrap', lg: 'nowrap' },
      }}
    >
      {/* Left Panel */}
      <Box
        sx={{
          width: { xs: '100%', lg: `calc(${leftWidth}% - 6px)` },
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          transition: isDragging ? 'none' : 'width 0.1s ease',
        }}
      >
        {leftPanel}
      </Box>

      {/* Draggable Divider - Only visible on large screens */}
      <Box
        onMouseDown={handleMouseDown}
        sx={{
          display: { xs: 'none', lg: 'flex' },
          width: 12,
          cursor: 'col-resize',
          flexShrink: 0,
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          zIndex: 10,
          background: isDragging
            ? 'linear-gradient(90deg, rgba(129, 140, 248, 0.4), rgba(129, 140, 248, 0.7), rgba(129, 140, 248, 0.4))'
            : 'linear-gradient(90deg, rgba(71, 85, 105, 0.3), rgba(100, 116, 139, 0.6), rgba(71, 85, 105, 0.3))',
          transition: isDragging ? 'none' : 'background 0.2s ease',
          borderLeft: '1px solid rgba(71, 85, 105, 0.4)',
          borderRight: '1px solid rgba(71, 85, 105, 0.4)',
          '&:hover': {
            background: 'linear-gradient(90deg, rgba(129, 140, 248, 0.5), rgba(129, 140, 248, 0.8), rgba(129, 140, 248, 0.5))',
            borderLeft: '1px solid rgba(129, 140, 248, 0.7)',
            borderRight: '1px solid rgba(129, 140, 248, 0.7)',
          },
          '&::before': {
            content: '""',
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            width: 3,
            height: 32,
            borderLeft: '1.5px solid rgba(148, 163, 184, 0.6)',
            borderRight: '1.5px solid rgba(148, 163, 184, 0.6)',
          },
          '&::after': {
            content: '"⋮"',
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            fontSize: '14px',
            color: 'rgba(148, 163, 184, 0.8)',
            fontWeight: 'bold',
            letterSpacing: '-2px',
          },
        }}
      />

      {/* Right Panel */}
      <Box
        sx={{
          width: { xs: '100%', lg: `calc(${100 - leftWidth}% - 6px)` },
          flex: { xs: '1', lg: '0 0 auto' },
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          transition: isDragging ? 'none' : 'width 0.1s ease',
        }}
      >
        {rightPanel}
      </Box>
    </Box>
  );
};

// PropTypes
ResizablePanels.propTypes = {
  /** Content for the left panel */
  leftPanel: PropTypes.node.isRequired,
  /** Content for the right panel */
  rightPanel: PropTypes.node.isRequired,
  /** Default width of left panel in percentage (0-100) */
  defaultLeftWidth: PropTypes.number,
  /** Minimum width of left panel in percentage */
  minLeftWidth: PropTypes.number,
  /** Minimum width of right panel in percentage */
  minRightWidth: PropTypes.number,
  /** LocalStorage key for persisting panel width */
  storageKey: PropTypes.string,
};

export default ResizablePanels;
