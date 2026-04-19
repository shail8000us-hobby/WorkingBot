/**
 * OptionsPositionsPropDeskHeader
 *
 * UI-only redesign of the Options Positions control header to match the
 * "Prop Desk" reference style.
 *
 * ⚠️ IMPORTANT: Trading logic is NOT modified here.
 * All click handlers and live bindings are received via props.
 */

import React, { useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Tooltip,
  Typography,
} from '@mui/material';
import { alpha, styled } from '@mui/material/styles';
import {
  Block as BlockIcon,
  CheckCircle as CheckCircleIcon,
  HelpOutline as HelpOutlineIcon,
  KeyboardArrowDown as ChevronIcon,
  Refresh as RefreshIcon,
  Settings as SettingsIcon,
  Timer as TimerIcon,
  TuneRounded as AdjustIcon,
  VolumeUp as VolumeIcon,
} from '@mui/icons-material';

const ACCENT_BLUE = '#60a5fa';
const ACCENT_CYAN = '#22d3ee';
const ACCENT_ORANGE = '#f97316';
const ACCENT_PURPLE = '#a855f7';

const Shell = styled(Box)(({ theme }) => ({
  borderRadius: 14,
  padding: theme.spacing(1),
  backgroundImage: `linear-gradient(180deg, ${alpha('#0b1220', 0.92)} 0%, ${alpha('#070b14', 0.92)} 100%)`,
  border: `1px solid ${alpha(ACCENT_BLUE, 0.35)}`,
  boxShadow: [
    `0 0 0 1px ${alpha(ACCENT_BLUE, 0.12)}`,
    `0 14px 32px ${alpha('#000', 0.55)}`,
    `0 0 22px ${alpha(ACCENT_BLUE, 0.14)}`,
  ].join(', '),
  backdropFilter: 'blur(10px)',
}));

const Row = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: theme.spacing(1),
  flexWrap: 'wrap',
}));

const Cluster = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: theme.spacing(0.75),
  flexWrap: 'wrap',
}));

const PillsRow = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: theme.spacing(0.75),
  flexWrap: 'wrap',
}));

const ExpiryScroller = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: theme.spacing(0.75),
  overflowX: 'auto',
  overflowY: 'hidden',
  flexWrap: 'nowrap',
  paddingBottom: 2,
  scrollbarWidth: 'none',
  '&::-webkit-scrollbar': { display: 'none' },
}));

const TitleText = styled(Typography)(({ theme }) => ({
  fontWeight: 900,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  color: theme.palette.common.white,
  fontSize: '0.95rem',
  lineHeight: 1.1,
}));

const activeBadgeSx = {
  height: 22,
  borderRadius: 999,
  borderColor: alpha(ACCENT_CYAN, 0.55),
  bgcolor: alpha(ACCENT_CYAN, 0.12),
  color: ACCENT_CYAN,
  fontWeight: 900,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  boxShadow: `0 0 0 1px ${alpha(ACCENT_CYAN, 0.18)}, 0 0 18px ${alpha(ACCENT_CYAN, 0.18)}`,
  '& .MuiChip-label': { px: 0.9, fontSize: '0.72rem' },
};

const statusChipSx = {
  height: 22,
  borderRadius: 999,
  fontWeight: 800,
  letterSpacing: '0.04em',
  textTransform: 'uppercase',
  '& .MuiChip-label': { px: 0.75, fontSize: '0.7rem' },
};

const expiryChipSx = (selected) => ({
  height: 24,
  borderRadius: 999,
  fontWeight: selected ? 900 : 700,
  letterSpacing: '0.03em',
  textTransform: 'uppercase',
  borderColor: selected ? alpha(ACCENT_BLUE, 0.7) : alpha('#94a3b8', 0.25),
  bgcolor: selected ? alpha(ACCENT_BLUE, 0.22) : alpha('#0f172a', 0.35),
  color: selected ? '#dbeafe' : alpha('#e2e8f0', 0.8),
  transition: 'transform 120ms ease, background-color 120ms ease, border-color 120ms ease',
  '&:hover': {
    transform: 'translateY(-1px)',
    borderColor: selected ? alpha(ACCENT_BLUE, 0.9) : alpha(ACCENT_BLUE, 0.45),
    bgcolor: selected ? alpha(ACCENT_BLUE, 0.26) : alpha(ACCENT_BLUE, 0.12),
  },
  '& .MuiChip-label': { px: 0.9, fontSize: '0.72rem' },
});

const badgeChipSx = (accentColor) => ({
  height: 24,
  borderRadius: 999,
  borderColor: alpha(accentColor, 0.55),
  bgcolor: alpha(accentColor, 0.12),
  color: accentColor,
  fontWeight: 900,
  letterSpacing: '0.03em',
  '& .MuiChip-label': { px: 0.9, fontSize: '0.72rem' },
});

const pillButtonSx = {
  borderRadius: 999,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  fontWeight: 900,
  fontSize: '0.72rem',
  py: 0.35,
  px: 1.25,
  minHeight: 28,
  transition: 'filter 140ms ease, transform 140ms ease, background-color 140ms ease, border-color 140ms ease',
  '&:hover': { transform: 'translateY(-1px)' },
};

function formatExpiryLabel(expiry) {
  const day = expiry.substring(0, 2);
  const month = expiry.substring(2, 4);
  const year = '20' + expiry.substring(4, 6);
  return `${day} ${new Date(`${year}-${month}-${day}T00:00:00`).toLocaleString('en-US', {
    month: 'short',
  })} ${year}`;
}

export default function OptionsPositionsPropDeskHeader({
  status,
  positions,
  positionsCount,
  advisory,
  customOrderCount,
  hiddenCount,
  payoffSelectedCount,
  onResetOrder,
  onClearHidden,

  turboMode,
  onToggleTurbo,
  showAdjust,
  onAdjust,

  pollInterval,
  onTogglePollInterval,

  uniqueExpiries,
  selectedExpiries,
  onClearExpirySelection,
  onToggleExpirySelection,
  getExpiryCode,

  indexPrices,

  scalingCollapsed,
  onToggleScaling,

  maxLossCollapsed,
  onToggleMaxLoss,

  onOpenSoundSettings,
  onRefresh,
  refreshing,
}) {
  const [settingsAnchorEl, setSettingsAnchorEl] = useState(null);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  const advisoryTone = advisory?.color || ACCENT_CYAN;

  const expiryMeta = useMemo(() => {
    const counts = {};
    (positions || []).forEach((p) => {
      const exp = getExpiryCode?.(p.product_symbol);
      if (!exp) return;
      counts[exp] = (counts[exp] || 0) + 1;
    });

    return (uniqueExpiries || []).map((expiry) => ({
      expiry,
      label: formatExpiryLabel(expiry),
      count: counts[expiry] || 0,
    }));
  }, [positions, uniqueExpiries, getExpiryCode]);

  const pollLabel = `${(Number(pollInterval) / 1000).toFixed(1)}s`;

  const openSettings = (e) => setSettingsAnchorEl(e.currentTarget);
  const closeSettings = () => setSettingsAnchorEl(null);

  return (
    <Shell data-testid="options-propdesk-header">
      {/* ROW 1 — Top Bar */}
      <Row>
        <Cluster
          sx={{
            minWidth: { xs: 260, lg: 0 },
            flex: { lg: '1 1 0' },
          }}
        >
          <ChevronIcon sx={{ color: alpha('#e2e8f0', 0.8), fontSize: 20 }} />
          <TitleText>Options Positions</TitleText>
          <Chip
            icon={<CheckCircleIcon sx={{ fontSize: 16 }} />}
            label={`${positionsCount} ACTIVE`}
            size="small"
            variant="outlined"
            sx={activeBadgeSx}
          />

          {status && (
            <Chip
              icon={status.trading_allowed ? <CheckCircleIcon sx={{ fontSize: 16 }} /> : <BlockIcon sx={{ fontSize: 16 }} />}
              label={status.guardian_signal}
              size="small"
              color={status.trading_allowed ? 'success' : 'error'}
              sx={statusChipSx}
            />
          )}

          {customOrderCount > 0 && (
            <Chip
              label="CUSTOM"
              size="small"
              color="primary"
              variant="outlined"
              onDelete={onResetOrder}
              sx={{ ...statusChipSx, borderColor: alpha(ACCENT_BLUE, 0.6) }}
            />
          )}

          {hiddenCount > 0 && (
            <Chip
              label={`${hiddenCount} HIDDEN`}
              size="small"
              color="warning"
              variant="outlined"
              onClick={onClearHidden}
              onDelete={onClearHidden}
              sx={statusChipSx}
            />
          )}

          {payoffSelectedCount > 0 && (
            <Chip
              label={`${payoffSelectedCount} PAYOFF`}
              size="small"
              color="primary"
              variant="outlined"
              sx={statusChipSx}
            />
          )}
        </Cluster>

        {advisory && (
          <Box
            sx={{
              flex: { lg: '0 0 auto' },
              width: { xs: '100%', lg: 640 },
              maxWidth: '100%',
              minWidth: { xs: '100%', lg: 320 },
              display: 'flex',
              justifyContent: 'center',
              px: { xs: 0, lg: 1 },
              order: { xs: 3, lg: 2 },
            }}
          >
            <Tooltip title={advisory.reasons ? `Why: ${advisory.reasons}` : ''} arrow disableHoverListener={!advisory.reasons}>
              <Box
                sx={{
                  width: '100%',
                  maxWidth: 640,
                  borderRadius: 999,
                  border: `1px solid ${alpha(advisoryTone, 0.55)}`,
                  bgcolor: alpha(advisoryTone, 0.12),
                  boxShadow: `0 0 14px ${alpha(advisoryTone, 0.2)}`,
                  px: 0.9,
                  py: 0.45,
                  minHeight: 30,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.7,
                }}
              >
                <Chip
                  label={`Signal: ${advisory.label}`}
                  size="small"
                  variant="outlined"
                  sx={{
                    height: 18,
                    fontSize: '0.62rem',
                    fontWeight: 900,
                    borderColor: alpha(advisoryTone, 0.75),
                    color: advisoryTone,
                    bgcolor: alpha(advisoryTone, 0.12),
                    '& .MuiChip-label': { px: 0.7 },
                  }}
                />

                <Typography
                  sx={{
                    color: alpha('#dbeafe', 0.9),
                    fontSize: '0.68rem',
                    fontWeight: 700,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    flex: 1,
                    minWidth: 0,
                  }}
                >
                  {advisory.action}
                </Typography>

                <Typography
                  sx={{
                    color: advisoryTone,
                    fontSize: '0.66rem',
                    fontWeight: 900,
                    letterSpacing: '0.04em',
                    whiteSpace: 'nowrap',
                  }}
                >
                  Confidence {advisory.confidence}%
                </Typography>
              </Box>
            </Tooltip>
          </Box>
        )}

        <PillsRow
          sx={{
            flex: { lg: '1 1 0' },
            minWidth: { lg: 0 },
            justifyContent: { xs: 'flex-start', lg: 'flex-end' },
          }}
        >
          <Button
            size="small"
            variant="contained"
            onClick={onToggleTurbo}
            sx={{
              ...pillButtonSx,
              bgcolor: alpha(ACCENT_ORANGE, turboMode ? 0.95 : 0.5),
              border: `1px solid ${alpha(ACCENT_ORANGE, 0.65)}`,
              boxShadow: `0 0 0 1px ${alpha(ACCENT_ORANGE, 0.18)}, 0 0 18px ${alpha(ACCENT_ORANGE, turboMode ? 0.28 : 0.14)}`,
              '&:hover': {
                bgcolor: alpha(ACCENT_ORANGE, 0.95),
                filter: 'brightness(1.06)',
                transform: 'translateY(-1px)',
              },
            }}
          >
            Turbo
          </Button>

          {showAdjust && (
            <Button
              size="small"
              variant="outlined"
              onClick={onAdjust}
              startIcon={<AdjustIcon sx={{ fontSize: 16 }} />}
              sx={{
                ...pillButtonSx,
                color: '#93c5fd',
                borderColor: alpha(ACCENT_BLUE, 0.55),
                bgcolor: alpha('#0b1220', 0.35),
                '&:hover': {
                  bgcolor: alpha(ACCENT_BLUE, 0.12),
                  borderColor: alpha(ACCENT_BLUE, 0.85),
                  transform: 'translateY(-1px)',
                },
              }}
            >
              Adjust
            </Button>
          )}

          <Button
            size="small"
            variant="outlined"
            onClick={onTogglePollInterval}
            startIcon={<TimerIcon sx={{ fontSize: 16 }} />}
            sx={{
              ...pillButtonSx,
              color: alpha('#e2e8f0', 0.9),
              borderColor: alpha('#94a3b8', 0.28),
              bgcolor: alpha('#0b1220', 0.25),
              '&:hover': {
                bgcolor: alpha('#0b1220', 0.38),
                borderColor: alpha(ACCENT_BLUE, 0.5),
                transform: 'translateY(-1px)',
              },
            }}
          >
            {pollLabel}
          </Button>

          <Tooltip title="Settings" arrow>
            <IconButton
              onClick={openSettings}
              size="small"
              sx={{
                borderRadius: 2,
                border: `1px solid ${alpha(ACCENT_BLUE, 0.3)}`,
                bgcolor: alpha('#0b1220', 0.35),
                color: alpha('#e2e8f0', 0.9),
                '&:hover': { bgcolor: alpha(ACCENT_BLUE, 0.12), borderColor: alpha(ACCENT_BLUE, 0.55) },
                '&:focus-visible': { outline: `2px solid ${alpha(ACCENT_BLUE, 0.55)}`, outlineOffset: 2 },
              }}
              aria-label="Options positions settings"
            >
              <SettingsIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Tooltip>

          <Menu
            anchorEl={settingsAnchorEl}
            open={Boolean(settingsAnchorEl)}
            onClose={closeSettings}
            PaperProps={{
              sx: {
                mt: 1,
                borderRadius: 2,
                bgcolor: alpha('#0b1220', 0.96),
                border: `1px solid ${alpha(ACCENT_BLUE, 0.25)}`,
                boxShadow: `0 20px 60px ${alpha('#000', 0.65)}`,
                minWidth: 220,
              },
            }}
          >
            <MenuItem
              onClick={() => {
                setShortcutsOpen(true);
                closeSettings();
              }}
            >
              <ListItemIcon>
                <HelpOutlineIcon fontSize="small" sx={{ color: alpha('#e2e8f0', 0.85) }} />
              </ListItemIcon>
              <ListItemText primary="Keyboard Shortcuts" />
            </MenuItem>
            <MenuItem
              onClick={() => {
                onOpenSoundSettings?.();
                closeSettings();
              }}
            >
              <ListItemIcon>
                <VolumeIcon fontSize="small" sx={{ color: alpha('#e2e8f0', 0.85) }} />
              </ListItemIcon>
              <ListItemText primary="Sound Settings" />
            </MenuItem>
            <MenuItem
              onClick={() => {
                onRefresh?.();
                closeSettings();
              }}
              disabled={!!refreshing}
            >
              <ListItemIcon>
                <RefreshIcon fontSize="small" sx={{ color: alpha('#e2e8f0', 0.85) }} />
              </ListItemIcon>
              <ListItemText primary={refreshing ? 'Refreshing…' : 'Refresh Now'} />
            </MenuItem>

            {typeof onToggleMaxLoss === 'function' && (
              <>
                <Divider sx={{ my: 0.5, borderColor: alpha('#94a3b8', 0.18) }} />
                <MenuItem
                  onClick={() => {
                    onToggleMaxLoss();
                    closeSettings();
                  }}
                >
                  <ListItemText
                    primary={maxLossCollapsed ? 'Show Max Loss Panel' : 'Hide Max Loss Panel'}
                    secondary="Risk controls"
                  />
                </MenuItem>
              </>
            )}
          </Menu>

          <Dialog open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} maxWidth="xs" fullWidth>
            <DialogTitle sx={{ fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Keyboard Shortcuts
            </DialogTitle>
            <DialogContent>
              <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                Turbo navigation + execution shortcuts.
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
                <Typography variant="body2"><b>B</b> — Buy</Typography>
                <Typography variant="body2"><b>S</b> — Sell</Typography>
                <Typography variant="body2"><b>C</b> — Close</Typography>
                <Typography variant="body2"><b>R</b> — Refresh</Typography>
                <Typography variant="body2"><b>Esc</b> — Cancel</Typography>
                <Typography variant="body2"><b>↑/↓</b> — Navigate</Typography>
              </Box>
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setShortcutsOpen(false)} variant="contained">Close</Button>
            </DialogActions>
          </Dialog>
        </PillsRow>
      </Row>

      {/* ROW 2 — Control Bar */}
      <Row sx={{ mt: 0.75 }}>
        <Cluster sx={{ minWidth: 260, flex: 1 }}>
          <Chip
            label={selectedExpiries?.length === 0 ? 'ALL' : `ALL (${selectedExpiries.length})`}
            size="small"
            onClick={onClearExpirySelection}
            variant={selectedExpiries?.length === 0 ? 'filled' : 'outlined'}
            sx={expiryChipSx(selectedExpiries?.length === 0)}
          />

          <ExpiryScroller aria-label="Expiry filters">
            {expiryMeta.map(({ expiry, label, count }) => {
              const isSelected = (selectedExpiries || []).includes(expiry);
              return (
                <Chip
                  key={expiry}
                  label={`${label} (${count})`}
                  size="small"
                  onClick={() => onToggleExpirySelection(expiry)}
                  variant={isSelected ? 'filled' : 'outlined'}
                  sx={expiryChipSx(isSelected)}
                />
              );
            })}
          </ExpiryScroller>
        </Cluster>

        <Cluster sx={{ justifyContent: 'flex-end' }}>
          {indexPrices?.BTC > 0 && (
            <Chip
              label={`BTC $${indexPrices.BTC.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
              size="small"
              variant="outlined"
              sx={badgeChipSx(ACCENT_BLUE)}
            />
          )}
          {indexPrices?.ETH > 0 && (
            <Chip
              label={`ETH $${indexPrices.ETH.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
              size="small"
              variant="outlined"
              sx={badgeChipSx(ACCENT_PURPLE)}
            />
          )}

          <Button
            size="small"
            variant={scalingCollapsed ? 'outlined' : 'contained'}
            onClick={onToggleScaling}
            endIcon={
              <ChevronIcon
                sx={{
                  fontSize: 18,
                  transform: scalingCollapsed ? 'rotate(0deg)' : 'rotate(180deg)',
                  transition: 'transform 140ms ease',
                }}
              />
            }
            sx={{
              ...pillButtonSx,
              minHeight: 28,
              bgcolor: scalingCollapsed ? 'transparent' : alpha(ACCENT_BLUE, 0.18),
              borderColor: alpha(ACCENT_BLUE, scalingCollapsed ? 0.45 : 0.7),
              color: '#dbeafe',
              boxShadow: scalingCollapsed ? 'none' : `0 0 18px ${alpha(ACCENT_BLUE, 0.14)}`,
              '&:hover': {
                bgcolor: alpha(ACCENT_BLUE, scalingCollapsed ? 0.12 : 0.22),
                borderColor: alpha(ACCENT_BLUE, 0.85),
                transform: 'translateY(-1px)',
              },
            }}
          >
            Scaling
          </Button>
        </Cluster>
      </Row>

      {/* Turbo hint — compact, desk-style */}
      {turboMode && (
        <Box
          sx={{
            mt: 0.75,
            px: 1,
            py: 0.5,
            borderRadius: 2,
            border: `1px solid ${alpha(ACCENT_ORANGE, 0.4)}`,
            bgcolor: alpha(ACCENT_ORANGE, 0.08),
          }}
        >
          <Typography variant="caption" sx={{ fontWeight: 900, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
            Turbo Hotkeys: ↑↓ Navigate · B Buy · S Sell · C Close · Esc Cancel
          </Typography>
        </Box>
      )}
    </Shell>
  );
}

OptionsPositionsPropDeskHeader.propTypes = {
  status: PropTypes.object,
  positions: PropTypes.array,
  positionsCount: PropTypes.number.isRequired,
  advisory: PropTypes.shape({
    signalState: PropTypes.string,
    label: PropTypes.string,
    color: PropTypes.string,
    action: PropTypes.string,
    confidence: PropTypes.number,
    reasons: PropTypes.string,
  }),
  customOrderCount: PropTypes.number,
  hiddenCount: PropTypes.number,
  payoffSelectedCount: PropTypes.number,
  onResetOrder: PropTypes.func,
  onClearHidden: PropTypes.func,

  turboMode: PropTypes.bool,
  onToggleTurbo: PropTypes.func,
  showAdjust: PropTypes.bool,
  onAdjust: PropTypes.func,

  pollInterval: PropTypes.number,
  onTogglePollInterval: PropTypes.func,

  uniqueExpiries: PropTypes.array,
  selectedExpiries: PropTypes.array,
  onClearExpirySelection: PropTypes.func,
  onToggleExpirySelection: PropTypes.func,
  getExpiryCode: PropTypes.func,

  indexPrices: PropTypes.object,

  scalingCollapsed: PropTypes.bool,
  onToggleScaling: PropTypes.func,

  maxLossCollapsed: PropTypes.bool,
  onToggleMaxLoss: PropTypes.func,

  onOpenSoundSettings: PropTypes.func,
  onRefresh: PropTypes.func,
  refreshing: PropTypes.bool,
};

OptionsPositionsPropDeskHeader.defaultProps = {
  status: null,
  positions: [],
  advisory: null,
  customOrderCount: 0,
  hiddenCount: 0,
  payoffSelectedCount: 0,
  onResetOrder: null,
  onClearHidden: null,

  turboMode: false,
  onToggleTurbo: null,
  showAdjust: false,
  onAdjust: null,

  pollInterval: 5000,
  onTogglePollInterval: null,

  uniqueExpiries: [],
  selectedExpiries: [],
  onClearExpirySelection: null,
  onToggleExpirySelection: null,
  getExpiryCode: null,

  indexPrices: null,

  scalingCollapsed: true,
  onToggleScaling: null,

  maxLossCollapsed: true,
  onToggleMaxLoss: null,

  onOpenSoundSettings: null,
  onRefresh: null,
  refreshing: false,
};
