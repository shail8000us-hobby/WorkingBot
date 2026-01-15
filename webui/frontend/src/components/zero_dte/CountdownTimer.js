/**
 * Countdown Timer - Time to Settlement
 * 
 * Shows countdown to 5:30 PM IST settlement.
 * Changes color based on urgency.
 */
import React, { useState, useEffect } from 'react';

const CountdownTimer = ({ isActive, timeToExpiryMinutes, settlementTime }) => {
  const [countdown, setCountdown] = useState({ hours: 0, minutes: 0, seconds: 0 });
  const [urgency, setUrgency] = useState('normal'); // normal, warning, critical

  useEffect(() => {
    if (!isActive) {
      // Calculate from current time to 5:30 PM
      const now = new Date();
      const [hours, mins] = (settlementTime || '17:30').split(':').map(Number);
      const settlement = new Date(now);
      settlement.setHours(hours, mins, 0, 0);
      
      const diff = settlement - now;
      if (diff > 0) {
        const h = Math.floor(diff / 3600000);
        const m = Math.floor((diff % 3600000) / 60000);
        const s = Math.floor((diff % 60000) / 1000);
        setCountdown({ hours: h, minutes: m, seconds: s });
      }
      return;
    }

    // When active, use provided timeToExpiryMinutes
    const updateCountdown = () => {
      if (timeToExpiryMinutes !== undefined) {
        const totalSeconds = timeToExpiryMinutes * 60;
        const h = Math.floor(totalSeconds / 3600);
        const m = Math.floor((totalSeconds % 3600) / 60);
        const s = totalSeconds % 60;
        
        setCountdown({ hours: h, minutes: m, seconds: s });
        
        // Set urgency level
        if (timeToExpiryMinutes <= 15) {
          setUrgency('critical');
        } else if (timeToExpiryMinutes <= 60) {
          setUrgency('warning');
        } else {
          setUrgency('normal');
        }
      }
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [isActive, timeToExpiryMinutes, settlementTime]);

  // Local countdown tick for seconds
  useEffect(() => {
    if (!isActive) return;
    
    const tick = setInterval(() => {
      setCountdown(prev => {
        let { hours, minutes, seconds } = prev;
        
        if (seconds > 0) {
          seconds--;
        } else if (minutes > 0) {
          minutes--;
          seconds = 59;
        } else if (hours > 0) {
          hours--;
          minutes = 59;
          seconds = 59;
        }
        
        return { hours, minutes, seconds };
      });
    }, 1000);
    
    return () => clearInterval(tick);
  }, [isActive]);

  const padZero = (num) => String(num).padStart(2, '0');

  return (
    <div className={`countdown-timer card countdown-${urgency}`}>
      <h3>Time to Settlement</h3>
      
      <div className="countdown-display">
        <div className="time-segment">
          <span className="time-value">{padZero(countdown.hours)}</span>
          <span className="time-label">Hours</span>
        </div>
        <span className="time-separator">:</span>
        <div className="time-segment">
          <span className="time-value">{padZero(countdown.minutes)}</span>
          <span className="time-label">Minutes</span>
        </div>
        <span className="time-separator">:</span>
        <div className="time-segment">
          <span className="time-value">{padZero(countdown.seconds)}</span>
          <span className="time-label">Seconds</span>
        </div>
      </div>

      <div className="settlement-info">
        <span>Settlement: {settlementTime || '17:30'} IST</span>
        <span>Forced Exit: 17:15 IST</span>
      </div>

      {urgency === 'warning' && (
        <div className="urgency-warning">
          ⚠️ Less than 1 hour remaining
        </div>
      )}
      
      {urgency === 'critical' && (
        <div className="urgency-critical">
          🚨 Less than 15 minutes - Forced exit imminent!
        </div>
      )}
    </div>
  );
};

export default CountdownTimer;
