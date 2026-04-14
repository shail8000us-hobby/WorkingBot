/**
 * useVisibilityAwarePolling - Smart Polling Hook
 * ================================================
 *
 * Performance optimization hook that:
 * - Pauses polling when tab is not visible
 * - Slows down polling when tab regains focus (to reduce burst)
 * - Automatically adjusts polling interval based on activity
 * - Prevents memory leaks with proper cleanup
 * - Uses refs instead of state to avoid re-render spam
 *
 * Created: January 27, 2026
 * Updated: February 28, 2026 — eliminated re-render overhead
 * Purpose: Dramatically reduce API load and improve WebUI performance
 */

import { useEffect, useRef, useCallback } from 'react';

/**
 * Smart polling hook that pauses when tab is hidden
 *
 * @param {Function} fetchFn - The function to call on each poll
 * @param {number} activeInterval - Interval in ms when tab is active (default: 10000)
 * @param {number} inactiveInterval - Interval in ms when returning from inactive (default: 30000)
 * @param {boolean} enabled - Whether polling is enabled (default: true)
 * @returns {Object} - { refresh, pause, resume }
 */
const useVisibilityAwarePolling = (
    fetchFn,
    activeInterval = 10000,
    inactiveInterval = 30000,
    enabled = true
) => {
    const intervalRef = useRef(null);
    const timeoutRef = useRef(null);
    const isPausedRef = useRef(false);
    const wasHiddenRef = useRef(false);
    const inFlightRef = useRef(false);
    const pendingFetchRef = useRef(false);
    // Keep a ref to the latest fetchFn so the interval closure always calls the current one
    const fetchFnRef = useRef(fetchFn);
    fetchFnRef.current = fetchFn;

    // Perform fetch using the ref (no dependency on fetchFn identity)
    const performFetch = useCallback(async () => {
        if (inFlightRef.current) {
            pendingFetchRef.current = true;
            return;
        }

        if (typeof fetchFnRef.current === 'function') {
            inFlightRef.current = true;
            try {
                await fetchFnRef.current();
            } catch (err) {
                // Silently handle — individual fetch functions log their own errors
            } finally {
                inFlightRef.current = false;

                // Coalesce bursty intervals/events into one trailing fetch.
                if (pendingFetchRef.current && !isPausedRef.current && enabled && !document.hidden) {
                    pendingFetchRef.current = false;
                    Promise.resolve().then(() => {
                        performFetch();
                    });
                } else {
                    pendingFetchRef.current = false;
                }
            }
        }
    }, [enabled]);

    // Start polling at a given interval
    const startPolling = useCallback((interval) => {
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
        }
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
        pendingFetchRef.current = false;
    }, []);

    // Manual refresh
    const refresh = useCallback(() => {
        performFetch();
    }, [performFetch]);

    // Pause polling
    const pause = useCallback(() => {
        isPausedRef.current = true;
        stopPolling();
    }, [stopPolling]);

    // Resume polling
    const resume = useCallback(() => {
        isPausedRef.current = false;
        if (enabled) {
            performFetch();
            startPolling(activeInterval);
        }
    }, [enabled, activeInterval, performFetch, startPolling]);

    // Handle visibility change + initial setup
    useEffect(() => {
        if (!enabled || isPausedRef.current) {
            stopPolling();
            return;
        }

        const handleVisibilityChange = () => {
            if (document.hidden) {
                // Tab became hidden — stop polling entirely
                wasHiddenRef.current = true;
                stopPolling();
            } else if (wasHiddenRef.current) {
                // Tab became visible again
                wasHiddenRef.current = false;

                // Immediate fetch when returning
                performFetch();

                // Start with slower interval briefly, then speed up
                startPolling(inactiveInterval);

                // After 10 seconds, switch to active interval
                timeoutRef.current = setTimeout(() => {
                    startPolling(activeInterval);
                }, 10000);
            }
        };

        document.addEventListener('visibilitychange', handleVisibilityChange);

        // Initial setup — only start polling if tab is visible
        if (!document.hidden) {
            performFetch();
            startPolling(activeInterval);
        }

        return () => {
            document.removeEventListener('visibilitychange', handleVisibilityChange);
            stopPolling();
        };
    }, [enabled, activeInterval, inactiveInterval, performFetch, startPolling, stopPolling]);

    return {
        refresh,
        pause,
        resume,
    };
};

export default useVisibilityAwarePolling;
