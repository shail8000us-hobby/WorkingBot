/**
 * useVisibilityAwarePolling - Smart Polling Hook
 * ================================================
 * 
 * Performance optimization hook that:
 * - Pauses polling when tab is not visible
 * - Slows down polling when tab regains focus (to reduce burst)
 * - Automatically adjusts polling interval based on activity
 * - Prevents memory leaks with proper cleanup
 * 
 * Created: January 27, 2026
 * Purpose: Dramatically reduce API load and improve WebUI performance
 */

import { useEffect, useRef, useCallback, useState } from 'react';

/**
 * Smart polling hook that pauses when tab is hidden
 * 
 * @param {Function} fetchFn - The function to call on each poll
 * @param {number} activeInterval - Interval in ms when tab is active (default: 10000)
 * @param {number} inactiveInterval - Interval in ms when returning from inactive (default: 30000)
 * @param {boolean} enabled - Whether polling is enabled (default: true)
 * @returns {Object} - { isPolling, lastFetch, refresh, pause, resume }
 */
const useVisibilityAwarePolling = (
    fetchFn,
    activeInterval = 10000,
    inactiveInterval = 30000,
    enabled = true
) => {
    const intervalRef = useRef(null);
    const timeoutRef = useRef(null);
    const [isPolling, setIsPolling] = useState(false);
    const [lastFetch, setLastFetch] = useState(null);
    const [isPaused, setIsPaused] = useState(false);
    const wasHiddenRef = useRef(false);

    // Memoize the fetch wrapper
    const performFetch = useCallback(async () => {
        if (typeof fetchFn === 'function') {
            try {
                await fetchFn();
                setLastFetch(new Date());
            } catch (err) {
                console.error('Polling fetch error:', err);
            }
        }
    }, [fetchFn]);

    // Start polling
    const startPolling = useCallback((interval) => {
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
        }

        setIsPolling(true);
        intervalRef.current = setInterval(performFetch, interval);
    }, [performFetch]);

    // Stop polling
    const stopPolling = useCallback(() => {
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        }
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
            timeoutRef.current = null;
        }
        setIsPolling(false);
    }, []);

    // Manual refresh
    const refresh = useCallback(() => {
        performFetch();
    }, [performFetch]);

    // Pause polling
    const pause = useCallback(() => {
        setIsPaused(true);
        stopPolling();
    }, [stopPolling]);

    // Resume polling
    const resume = useCallback(() => {
        setIsPaused(false);
        if (enabled) {
            performFetch();
            startPolling(activeInterval);
        }
    }, [enabled, activeInterval, performFetch, startPolling]);

    // Handle visibility change
    useEffect(() => {
        if (!enabled || isPaused) return;

        const handleVisibilityChange = () => {
            if (document.hidden) {
                // Tab became hidden - stop polling
                wasHiddenRef.current = true;
                stopPolling();
                console.log('📡 Polling paused (tab hidden)');
            } else {
                // Tab became visible
                if (wasHiddenRef.current) {
                    wasHiddenRef.current = false;

                    // Immediate fetch when returning
                    performFetch();

                    // Start with slower interval briefly, then speed up
                    console.log('📡 Polling resumed (tab visible) - starting slow');
                    startPolling(inactiveInterval);

                    // After 10 seconds, switch to active interval
                    timeoutRef.current = setTimeout(() => {
                        console.log('📡 Switching to active polling interval');
                        startPolling(activeInterval);
                    }, 10000);
                }
            }
        };

        document.addEventListener('visibilitychange', handleVisibilityChange);

        // Initial setup - only start polling if visible
        if (!document.hidden) {
            performFetch();
            startPolling(activeInterval);
        }

        return () => {
            document.removeEventListener('visibilitychange', handleVisibilityChange);
            stopPolling();
        };
    }, [enabled, isPaused, activeInterval, inactiveInterval, performFetch, startPolling, stopPolling]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            stopPolling();
        };
    }, [stopPolling]);

    return {
        isPolling,
        lastFetch,
        refresh,
        pause,
        resume,
    };
};

export default useVisibilityAwarePolling;
