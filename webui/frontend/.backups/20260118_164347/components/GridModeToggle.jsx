import React, { useState, useEffect } from 'react';

const GridModeToggle = () => {
  const [mode, setMode] = useState('LONG');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetchMode();
  }, []);

  const fetchMode = async () => {
    try {
      const res = await fetch('http://localhost:5555/api/bot/grid-mode');
      const data = await res.json();
      if (data.success) {
        setMode(data.mode);
      }
    } catch (err) {
      console.error('Error fetching grid mode:', err);
    }
  };

  const toggleMode = async () => {
    const newMode = mode === 'LONG' ? 'SHORT' : 'LONG';
    setLoading(true);
    setMessage('');

    try {
      const res = await fetch('http://localhost:5555/api/bot/grid-mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          mode: newMode,
          auto_restart: true  // Automatically restart bot for mode transition
        })
      });

      const data = await res.json();
      
      if (data.success) {
        setMode(newMode);
        
        if (!data.changed) {
          setMessage(`ℹ️ Already in ${newMode} mode`);
        } else if (data.restart) {
          if (data.restart.success) {
            setMessage(`✅ Switched to ${newMode} mode & bot restarted! Mode transition active.`);
          } else {
            setMessage(`⚠️ Switched to ${newMode} mode but restart failed: ${data.restart.message}`);
          }
        } else if (data.requires_restart) {
          setMessage(`✅ Config updated to ${newMode} mode. ⚠️ RESTART BOT to activate mode transition.`);
        } else {
          setMessage(`✅ ${data.message}`);
        }
        
        setTimeout(() => setMessage(''), 6000);
      } else {
        setMessage(`❌ Error: ${data.error}`);
      }
    } catch (err) {
      setMessage(`❌ Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Grid Mode
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            {mode === 'LONG' 
              ? '📈 Buying below current price (Bullish)' 
              : '📉 Selling above current price (Bearish)'}
          </p>
        </div>

        <button
          onClick={toggleMode}
          disabled={loading}
          className={`
            px-6 py-3 rounded-lg font-semibold text-white transition-all
            ${mode === 'LONG' 
              ? 'bg-green-600 hover:bg-green-700' 
              : 'bg-red-600 hover:bg-red-700'}
            ${loading ? 'opacity-50 cursor-not-allowed' : 'hover:scale-105'}
          `}
        >
          {loading ? '⏳ Switching...' : (
            <>
              {mode === 'LONG' ? '🟢 LONG' : '🔴 SHORT'}
              <span className="ml-2 text-xs">
                (click to toggle)
              </span>
            </>
          )}
        </button>
      </div>

      {message && (
        <div className={`mt-4 p-3 rounded ${
          message.includes('✅') 
            ? 'bg-green-100 text-green-800' 
            : 'bg-red-100 text-red-800'
        }`}>
          {message}
        </div>
      )}

      <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 rounded border border-blue-200 dark:border-blue-800">
        <p className="text-sm text-blue-800 dark:text-blue-200">
          ℹ️ <strong>Mode Transition System:</strong>
          <br />
          🔄 Bot automatically restarts on mode switch
          <br />
          � Old state archived → Fresh start → Existing positions treated as manual
          <br />
          🛡️ Manual TPs remain untouched (sacred)
        </p>
      </div>
    </div>
  );
};

export default GridModeToggle;
