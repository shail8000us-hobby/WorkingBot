import React from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Typography,
    Box,
    Button,
    Chip,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import { TrendingUp as IncreaseIcon } from '@mui/icons-material';

const MONO = 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace';
const GREEN = '#10b981';

function IncreasePositionDialog({ open, rows, pct, onClose, onConfirm, executing }) {
    if (!rows || rows.length === 0) return null;

    const skipped = rows.filter(r => r.lotsToAdd < 1);
    const actionable = rows.filter(r => r.lotsToAdd >= 1);

    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth="sm"
            fullWidth
            disableRestoreFocus
            PaperProps={{
                sx: {
                    bgcolor: '#0d1525',
                    border: `1px solid ${alpha(GREEN, 0.3)}`,
                    borderRadius: 2,
                    boxShadow: `0 0 40px ${alpha('#000', 0.7)}, 0 0 20px ${alpha(GREEN, 0.1)}`,
                },
            }}
        >
            <DialogTitle sx={{ pb: 1, pt: 2, px: 2.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Box sx={{
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        width: 32, height: 32, borderRadius: 1,
                        bgcolor: alpha(GREEN, 0.15),
                        border: `1px solid ${alpha(GREEN, 0.35)}`,
                        flexShrink: 0,
                    }}>
                        <IncreaseIcon sx={{ fontSize: 16, color: GREEN }} />
                    </Box>
                    <Box>
                        <Typography sx={{
                            color: GREEN,
                            fontSize: '0.95rem',
                            fontWeight: 900,
                            fontFamily: MONO,
                            letterSpacing: '0.04em',
                            lineHeight: 1.2,
                        }}>
                            Increase by {pct}%
                        </Typography>
                        <Typography sx={{
                            color: alpha('#94a3b8', 0.8),
                            fontSize: '0.67rem',
                            fontFamily: MONO,
                            letterSpacing: '0.04em',
                        }}>
                            Limit order at mid-price · {actionable.length} position{actionable.length !== 1 ? 's' : ''}
                        </Typography>
                    </Box>
                </Box>
            </DialogTitle>

            <DialogContent sx={{ px: 2.5, pb: 1 }}>
                {actionable.length > 0 && (
                    <Box sx={{ mt: 0.5 }}>
                        <Box sx={{
                            display: 'grid',
                            gridTemplateColumns: '1fr 60px 90px 60px 70px',
                            gap: 0.5,
                            px: 0.75,
                            pb: 0.5,
                            borderBottom: `1px solid ${alpha('#334155', 0.6)}`,
                            mb: 0.4,
                        }}>
                            {['Symbol', 'Now', 'Action', 'Add', 'New'].map((h, i) => (
                                <Typography key={h} sx={{
                                    fontSize: '0.6rem',
                                    fontWeight: 800,
                                    fontFamily: MONO,
                                    letterSpacing: '0.08em',
                                    textTransform: 'uppercase',
                                    color: alpha('#64748b', 0.9),
                                    textAlign: i === 0 ? 'left' : 'right',
                                }}>
                                    {h}
                                </Typography>
                            ))}
                        </Box>

                        {actionable.map((r, idx) => (
                            <Box
                                key={r.position.product_symbol}
                                sx={{
                                    display: 'grid',
                                    gridTemplateColumns: '1fr 60px 90px 60px 70px',
                                    gap: 0.5,
                                    px: 0.75,
                                    py: 0.55,
                                    borderRadius: 0.75,
                                    bgcolor: idx % 2 === 0 ? alpha('#1e293b', 0.4) : 'transparent',
                                    '&:hover': { bgcolor: alpha(GREEN, 0.06) },
                                    transition: 'background-color 120ms ease',
                                    alignItems: 'center',
                                }}
                            >
                                <Typography sx={{
                                    fontSize: '0.7rem',
                                    fontFamily: MONO,
                                    fontWeight: 700,
                                    color: alpha('#e2e8f0', 0.92),
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                }}>
                                    {r.position.product_symbol}
                                </Typography>

                                <Typography sx={{
                                    fontSize: '0.72rem',
                                    fontFamily: MONO,
                                    fontWeight: 700,
                                    color: alpha('#94a3b8', 0.9),
                                    textAlign: 'right',
                                }}>
                                    {r.currentSize}
                                </Typography>

                                <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                                    <Chip
                                        label={`${r.action}  ${r.lotsToAdd}`}
                                        size="small"
                                        sx={{
                                            fontSize: '0.64rem',
                                            fontWeight: 900,
                                            fontFamily: MONO,
                                            height: 20,
                                            letterSpacing: '0.04em',
                                            bgcolor: r.action === 'BUY'
                                                ? alpha('#3b82f6', 0.18)
                                                : alpha('#ef4444', 0.18),
                                            color: r.action === 'BUY' ? '#60a5fa' : '#f87171',
                                            border: `1px solid ${r.action === 'BUY' ? alpha('#3b82f6', 0.4) : alpha('#ef4444', 0.4)}`,
                                            '& .MuiChip-label': { px: 0.8 },
                                        }}
                                    />
                                </Box>

                                <Typography sx={{
                                    fontSize: '0.72rem',
                                    fontFamily: MONO,
                                    fontWeight: 800,
                                    color: GREEN,
                                    textAlign: 'right',
                                }}>
                                    {r.lotsToAdd}
                                </Typography>

                                <Typography sx={{
                                    fontSize: '0.72rem',
                                    fontFamily: MONO,
                                    fontWeight: 700,
                                    color: alpha(GREEN, 0.85),
                                    textAlign: 'right',
                                }}>
                                    {r.newSize}
                                </Typography>
                            </Box>
                        ))}
                    </Box>
                )}

                {skipped.length > 0 && (
                    <Box sx={{
                        mt: 1.2,
                        px: 1,
                        py: 0.7,
                        borderRadius: 0.85,
                        bgcolor: alpha(GREEN, 0.07),
                        border: `1px solid ${alpha(GREEN, 0.22)}`,
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 0.8,
                    }}>
                        <Typography sx={{ fontSize: '0.65rem', color: GREEN, fontWeight: 800, mt: 0.05 }}>⚠</Typography>
                        <Typography sx={{ fontSize: '0.65rem', color: alpha(GREEN, 0.85), fontFamily: MONO, lineHeight: 1.5 }}>
                            {skipped.length} skipped — {pct}% rounds to 0 lots:{' '}
                            <span style={{ color: alpha(GREEN, 0.65) }}>
                                {skipped.map(r => r.position.product_symbol).join(', ')}
                            </span>
                        </Typography>
                    </Box>
                )}

                {actionable.length === 0 && (
                    <Box sx={{
                        mt: 1, px: 1, py: 1,
                        borderRadius: 0.85,
                        bgcolor: alpha('#334155', 0.3),
                        border: `1px solid ${alpha('#475569', 0.3)}`,
                        textAlign: 'center',
                    }}>
                        <Typography sx={{ fontSize: '0.72rem', color: alpha('#94a3b8', 0.8), fontFamily: MONO }}>
                            Nothing to increase — {pct}% rounds to 0 lots for all selected strikes.
                        </Typography>
                    </Box>
                )}
            </DialogContent>

            <DialogActions sx={{ px: 2.5, pb: 2, pt: 1, gap: 1 }}>
                <Button
                    onClick={onClose}
                    disabled={executing}
                    variant="outlined"
                    size="small"
                    sx={{
                        fontSize: '0.72rem',
                        fontFamily: MONO,
                        fontWeight: 700,
                        px: 2,
                        borderColor: alpha('#475569', 0.5),
                        color: alpha('#94a3b8', 0.85),
                        '&:hover': { borderColor: '#64748b', bgcolor: alpha('#334155', 0.3) },
                    }}
                >
                    Cancel
                </Button>
                <Button
                    onClick={onConfirm}
                    disabled={executing || actionable.length === 0}
                    variant="contained"
                    size="small"
                    sx={{
                        fontSize: '0.72rem',
                        fontFamily: MONO,
                        fontWeight: 900,
                        px: 2,
                        letterSpacing: '0.04em',
                        bgcolor: GREEN,
                        color: '#0f172a',
                        boxShadow: `0 0 12px ${alpha(GREEN, 0.4)}`,
                        '&:hover': { bgcolor: '#34d399', boxShadow: `0 0 18px ${alpha(GREEN, 0.55)}` },
                        '&.Mui-disabled': { bgcolor: alpha('#334155', 0.4), color: alpha('#475569', 0.5), boxShadow: 'none' },
                    }}
                >
                    {executing
                        ? 'Increasing…'
                        : `Confirm  ·  ${actionable.length} position${actionable.length !== 1 ? 's' : ''}`}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

export default React.memo(IncreasePositionDialog);
