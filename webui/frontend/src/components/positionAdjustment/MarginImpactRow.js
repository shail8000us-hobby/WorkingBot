/**
 * Margin Impact Row
 * =================
 * Shows estimated margin utilization change after proposed adjustment.
 * Uses client-side estimation based on premium of new legs.
 *
 * Created: March 6, 2026
 */

import React, { useState, useEffect } from 'react';
import { Box, Typography, Chip, Tooltip } from '@mui/material';
import {
    TrendingUp as UpIcon,
    TrendingDown as DownIcon,
    Remove as NeutralIcon,
} from '@mui/icons-material';
import api from '../../utils/apiShim';

/**
 * @param {Object} props
 * @param {Object} props.netDebitCredit - { netAmount, isDebit }
 * @param {number} props.spotPrice - Current spot price
 */
export default function MarginImpactRow({ netDebitCredit, spotPrice }) {
    const [marginData, setMarginData] = useState(null);

    // Fetch current margin data
    useEffect(() => {
        const fetchMargin = async () => {
            try {
                const resp = await api.get('/api/options/margin-info');
                if (resp && resp.margin_used != null) {
                    setMarginData(resp);
                }
            } catch {
                // Try alternative endpoint
                try {
                    const resp2 = await api.get('/api/margin');
                    if (resp2) setMarginData(resp2);
                } catch {
                    // Margin data unavailable — silent fail
                }
            }
        };
        fetchMargin();
    }, []);

    // Estimate margin impact
    const currentMarginPct = marginData
        ? ((marginData.total_margin_used || marginData.margin_used || 0) /
            (marginData.net_equity || marginData.equity || marginData.balance || 1)) * 100
        : null;

    // Estimated additional margin = net debit of new legs (approximate)
    const additionalMargin = netDebitCredit?.isDebit ? Math.abs(netDebitCredit.netAmount) : 0;
    const equity = marginData?.net_equity || marginData?.equity || marginData?.balance || 0;
    const additionalPct = equity > 0 ? (additionalMargin / equity) * 100 : 0;
    const afterMarginPct = currentMarginPct != null ? currentMarginPct + additionalPct : null;
    const changePct = additionalPct;

    // Color coding
    let changeColor = '#94a3b8'; // neutral
    let ChangeIcon = NeutralIcon;
    if (changePct < -0.01) {
        changeColor = '#22c55e'; // Green — margin goes DOWN
        ChangeIcon = DownIcon;
    } else if (changePct > 5) {
        changeColor = '#ef4444'; // Red — margin goes UP > 5%
        ChangeIcon = UpIcon;
    } else if (changePct > 0.01) {
        changeColor = '#f97316'; // Orange — margin goes UP 1-5%
        ChangeIcon = UpIcon;
    }

    // No margin data available
    if (currentMarginPct == null) {
        return (
            <Box sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                mt: 1,
                pt: 1,
                borderTop: '1px solid rgba(71, 85, 105, 0.4)',
            }}>
                <Typography variant="caption" sx={{ color: '#94a3b8', fontSize: '0.65rem' }}>
                    Margin Impact
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b', fontSize: '0.75rem' }}>
                    Margin data unavailable
                </Typography>
            </Box>
        );
    }

    return (
        <Box sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            mt: 1,
            pt: 1,
            borderTop: '1px solid rgba(71, 85, 105, 0.4)',
        }}>
            <Typography variant="caption" sx={{ color: '#94a3b8', fontSize: '0.65rem', minWidth: 80 }}>
                Margin Impact
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Typography variant="body2" sx={{ color: '#e2e8f0', fontSize: '0.8rem' }}>
                    {currentMarginPct.toFixed(1)}%
                </Typography>
                <Typography variant="body2" sx={{ color: '#94a3b8', fontSize: '0.75rem' }}>→</Typography>
                <Typography variant="body2" sx={{ color: changeColor, fontWeight: 600, fontSize: '0.8rem' }}>
                    {afterMarginPct.toFixed(1)}%
                </Typography>
                {changePct !== 0 && (
                    <Tooltip title={`Margin ${changePct > 0 ? 'increases' : 'decreases'} by ${Math.abs(changePct).toFixed(1)}%`}>
                        <Chip
                            icon={<ChangeIcon sx={{ fontSize: 12, color: changeColor + ' !important' }} />}
                            label={`${changePct > 0 ? '+' : ''}${changePct.toFixed(1)}%`}
                            size="small"
                            sx={{
                                bgcolor: `${changeColor}15`,
                                color: changeColor,
                                height: 20,
                                fontSize: '0.65rem',
                                fontWeight: 600,
                                '& .MuiChip-icon': { ml: 0.5 },
                            }}
                        />
                    </Tooltip>
                )}
            </Box>
        </Box>
    );
}
