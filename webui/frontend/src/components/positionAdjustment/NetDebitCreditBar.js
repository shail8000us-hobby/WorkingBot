/**
 * Net Debit/Credit Summary Bar
 * ============================
 * Shows the net cost or income of proposed trades at a glance.
 * DEBIT = paying net premium, CREDIT = receiving net premium.
 *
 * Updates in real-time as legs are added/removed/qty changed.
 *
 * Created: March 6, 2026
 */

import React from 'react';
import { Box, Typography } from '@mui/material';
import {
    TrendingUp as CreditIcon,
    TrendingDown as DebitIcon,
} from '@mui/icons-material';

/**
 * @param {Object} props
 * @param {Object} props.netDebitCredit - Result from calculateNetDebitCredit()
 *   { netAmount, perLot, totalQty, isDebit }
 */
export default function NetDebitCreditBar({ netDebitCredit }) {
    if (!netDebitCredit || netDebitCredit.totalQty === 0) return null;

    const { netAmount, perLot, totalQty, isDebit } = netDebitCredit;
    const absAmount = Math.abs(netAmount);
    const absPerLot = Math.abs(perLot);

    const label = isDebit ? 'NET DEBIT —' : 'NET CREDIT +';
    const color = isDebit ? '#f97316' : '#22c55e'; // Orange for debit, green for credit
    const bgColor = isDebit ? 'rgba(249, 115, 22, 0.08)' : 'rgba(34, 197, 94, 0.08)';
    const borderColor = isDebit ? 'rgba(249, 115, 22, 0.3)' : 'rgba(34, 197, 94, 0.3)';
    const Icon = isDebit ? DebitIcon : CreditIcon;

    return (
        <Box sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            p: 1.5,
            mb: 1.5,
            bgcolor: bgColor,
            border: `1px solid ${borderColor}`,
            borderRadius: 1.5,
        }}>
            <Icon sx={{ color, fontSize: 20 }} />
            <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, flex: 1 }}>
                <Typography variant="body2" sx={{ color, fontWeight: 700, letterSpacing: 0.5 }}>
                    {label}
                </Typography>
                <Typography variant="body1" sx={{ color, fontWeight: 800, fontSize: '1.1rem' }}>
                    ${absAmount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </Typography>
                <Typography variant="caption" sx={{ color: 'rgba(148, 163, 184, 0.8)' }}>
                    ({totalQty} × ${absPerLot.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })})
                </Typography>
            </Box>
        </Box>
    );
}
