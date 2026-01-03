/**
 * Symbol Color Utilities (v5.0 Multi-Symbol)
 * 
 * Purpose: Instant visual recognition of which symbol you're viewing
 * Phase 2: Visual Symbol Context
 * 
 * Color Palette:
 * - BTCUSD: Blue (#3B82F6) - Primary, most allocated capital
 * - ETHUSD: Purple (#A855F7) - Secondary
 * - SOLUSD: Orange (#F97316) - If added later
 * - BNBUSD: Yellow (#EAB308) - If added later
 * - XRPUSD: Green (#10B981) - If added later
 */

export const SYMBOL_COLORS = {
  BTCUSD: { 
    primary: '#3B82F6', 
    bg: 'rgba(59, 130, 246, 0.1)', 
    border: 'rgba(59, 130, 246, 0.3)',
    bgSolid: '#1E3A8A',
    text: '#DBEAFE',
    gradient: 'linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(59, 130, 246, 0.05) 100%)'
  },
  ETHUSD: { 
    primary: '#A855F7', 
    bg: 'rgba(168, 85, 247, 0.1)', 
    border: 'rgba(168, 85, 247, 0.3)',
    bgSolid: '#581C87',
    text: '#F3E8FF',
    gradient: 'linear-gradient(135deg, rgba(168, 85, 247, 0.15) 0%, rgba(168, 85, 247, 0.05) 100%)'
  },
  SOLUSD: { 
    primary: '#F97316', 
    bg: 'rgba(249, 115, 22, 0.1)', 
    border: 'rgba(249, 115, 22, 0.3)',
    bgSolid: '#9A3412',
    text: '#FFEDD5',
    gradient: 'linear-gradient(135deg, rgba(249, 115, 22, 0.15) 0%, rgba(249, 115, 22, 0.05) 100%)'
  },
  BNBUSD: { 
    primary: '#EAB308', 
    bg: 'rgba(234, 179, 8, 0.1)', 
    border: 'rgba(234, 179, 8, 0.3)',
    bgSolid: '#854D0E',
    text: '#FEF9C3',
    gradient: 'linear-gradient(135deg, rgba(234, 179, 8, 0.15) 0%, rgba(234, 179, 8, 0.05) 100%)'
  },
  XRPUSD: { 
    primary: '#10B981', 
    bg: 'rgba(16, 185, 129, 0.1)', 
    border: 'rgba(16, 185, 129, 0.3)',
    bgSolid: '#065F46',
    text: '#D1FAE5',
    gradient: 'linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(16, 185, 129, 0.05) 100%)'
  },
  default: { 
    primary: '#64748B', 
    bg: 'rgba(100, 116, 139, 0.1)', 
    border: 'rgba(100, 116, 139, 0.3)',
    bgSolid: '#334155',
    text: '#E2E8F0',
    gradient: 'linear-gradient(135deg, rgba(100, 116, 139, 0.15) 0%, rgba(100, 116, 139, 0.05) 100%)'
  }
};

/**
 * Get color scheme for a symbol
 * @param {string} symbolName - Symbol name (e.g., 'BTCUSD', 'ETHUSD')
 * @returns {object} Color scheme with primary, bg, border, etc.
 */
export const getSymbolColor = (symbolName) => {
  return SYMBOL_COLORS[symbolName] || SYMBOL_COLORS.default;
};

/**
 * Get symbol dot indicator (for logs, badges, etc.)
 * @param {string} symbolName - Symbol name
 * @returns {string} Colored dot emoji or circle
 */
export const getSymbolDot = (symbolName) => {
  const colors = getSymbolColor(symbolName);
  return colors.primary;
};

/**
 * Apply symbol border accent to component style
 * @param {string} symbolName - Symbol name
 * @param {string} side - Which side to apply border ('left', 'top', 'right', 'bottom')
 * @returns {object} Style object for React/MUI
 */
export const getSymbolBorderStyle = (symbolName, side = 'left') => {
  const colors = getSymbolColor(symbolName);
  return {
    [`border${side.charAt(0).toUpperCase() + side.slice(1)}`]: `3px solid ${colors.primary}`,
    backgroundColor: colors.bg
  };
};

/**
 * Get symbol badge component props
 * @param {string} symbolName - Symbol name
 * @param {string} variant - 'solid' or 'outlined'
 * @returns {object} Props for MUI Chip component
 */
export const getSymbolBadgeProps = (symbolName, variant = 'solid') => {
  const colors = getSymbolColor(symbolName);
  
  if (variant === 'solid') {
    return {
      sx: {
        backgroundColor: colors.primary,
        color: '#fff',
        fontWeight: 600
      }
    };
  }
  
  return {
    variant: 'outlined',
    sx: {
      borderColor: colors.primary,
      color: colors.primary,
      fontWeight: 600
    }
  };
};

export default {
  SYMBOL_COLORS,
  getSymbolColor,
  getSymbolDot,
  getSymbolBorderStyle,
  getSymbolBadgeProps
};
