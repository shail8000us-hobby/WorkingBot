import React, { useMemo } from 'react';
import '../mobile/mobile.css';

/**
 * MobileMonitoring — System Health dashboard on mobile
 * Shows CPU, memory, disk usage, and process health
 */
const MobileMonitoring = ({ botStatus }) => {
  const healthMetrics = useMemo(() => {
    if (!botStatus) return null;

    const cpu = parseFloat(botStatus.cpu_percent || 0);
    const memory = parseFloat(botStatus.memory_percent || 0);
    const disk = parseFloat(botStatus.disk_percent || 0);

    return {
      cpu,
      memory,
      disk,
      processes: botStatus.processes || [],
      uptime: botStatus.uptime || 0,
      lastUpdate: botStatus.last_update || new Date().toISOString(),
    };
  }, [botStatus]);

  if (!healthMetrics) {
    return (
      <div className="mobile-screen">
        <div className="mobile-card" style={{ textAlign: 'center' }}>
          <p style={{ color: '#aaa', margin: 0 }}>Loading system health...</p>
        </div>
      </div>
    );
  }

  const getHealthColor = (value) => {
    if (value > 80) return '#c0392b';
    if (value > 60) return '#f39c12';
    return '#4caf50';
  };

  const HealthMetric = ({ label, value, unit = '%' }) => {
    const color = getHealthColor(value);
    return (
      <div className="mobile-card" style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div style={{ fontSize: '14px', color: '#aaa', fontWeight: 600 }}>{label}</div>
          <div style={{ fontSize: '18px', fontWeight: 700, color }}>{value.toFixed(1)}{unit}</div>
        </div>
        <div style={{
          height: '10px',
          background: '#1a1a2e',
          borderRadius: '5px',
          overflow: 'hidden',
          border: `1px solid ${color}`,
        }}>
          <div style={{
            height: '100%',
            width: `${Math.min(value, 100)}%`,
            background: color,
            transition: 'width 0.5s ease',
          }} />
        </div>
      </div>
    );
  };

  const formatUptime = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  return (
    <div className="mobile-screen">
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ margin: 0, color: '#fff', fontSize: '24px' }}>System Health</h2>
        <p style={{ margin: '8px 0 0 0', color: '#aaa', fontSize: '14px' }}>
          Monitor server resources and process health
        </p>
      </div>

      {/* System Resources */}
      <div style={{ marginBottom: 24 }}>
        <h3 style={{ margin: '0 0 12px 0', color: '#f39c12', fontSize: '16px' }}>Resources</h3>
      </div>

      <HealthMetric label="CPU Usage" value={healthMetrics.cpu} />
      <HealthMetric label="Memory Usage" value={healthMetrics.memory} />
      <HealthMetric label="Disk Usage" value={healthMetrics.disk} />

      {/* Uptime Card */}
      <div className="mobile-card">
        <div style={{ display: 'flex', justifyContent: 'space-around', textAlign: 'center' }}>
          <div>
            <div style={{ fontSize: '12px', color: '#aaa', textTransform: 'uppercase', fontWeight: 600 }}>
              Uptime
            </div>
            <div style={{ fontSize: '20px', fontWeight: 700, color: '#4caf50', marginTop: 8 }}>
              {formatUptime(healthMetrics.uptime)}
            </div>
          </div>
          <div style={{ width: '1px', background: '#333' }} />
          <div>
            <div style={{ fontSize: '12px', color: '#aaa', textTransform: 'uppercase', fontWeight: 600 }}>
              Last Update
            </div>
            <div style={{ fontSize: '13px', color: '#fff', marginTop: 8 }}>
              {new Date(healthMetrics.lastUpdate).toLocaleTimeString()}
            </div>
          </div>
        </div>
      </div>

      {/* Process Health */}
      {healthMetrics.processes.length > 0 && (
        <>
          <div style={{ marginTop: 24, marginBottom: 12 }}>
            <h3 style={{ margin: 0, color: '#f39c12', fontSize: '16px' }}>Running Processes</h3>
          </div>

          {healthMetrics.processes.map((proc, idx) => (
            <div
              key={idx}
              className="mobile-card"
              style={{
                borderLeft: `4px solid ${proc.status === 'running' ? '#4caf50' : '#f44336'}`,
                marginBottom: 8,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontSize: '15px', fontWeight: 700, color: '#fff' }}>
                    {proc.name || `Process ${proc.pid}`}
                  </div>
                  <div style={{ fontSize: '12px', color: '#aaa', marginTop: 4 }}>
                    PID: {proc.pid} · CPU: {proc.cpu_percent?.toFixed(1)}% · Mem: {proc.memory_percent?.toFixed(1)}%
                  </div>
                </div>
                <div style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  color: proc.status === 'running' ? '#4caf50' : '#f44336',
                  textTransform: 'uppercase',
                }}>
                  {proc.status || 'unknown'}
                </div>
              </div>
            </div>
          ))}
        </>
      )}

      {/* Warnings */}
      {healthMetrics.cpu > 80 && (
        <div className="mobile-card" style={{ background: '#f39c1222', border: '2px solid #f39c12', marginTop: 16 }}>
          <h4 style={{ margin: '0 0 8px 0', color: '#f39c12', fontSize: '16px' }}>⚠️ High CPU</h4>
          <p style={{ margin: 0, fontSize: '13px', color: '#f39c12' }}>
            CPU is at {healthMetrics.cpu.toFixed(1)}%. Check for heavy processes.
          </p>
        </div>
      )}

      {healthMetrics.memory > 80 && (
        <div className="mobile-card" style={{ background: '#c0392b22', border: '2px solid #c0392b', marginTop: 12 }}>
          <h4 style={{ margin: '0 0 8px 0', color: '#c0392b', fontSize: '16px' }}>⚠️ Low Memory</h4>
          <p style={{ margin: 0, fontSize: '13px', color: '#e74c3c' }}>
            Memory is at {healthMetrics.memory.toFixed(1)}%. Consider restarting services.
          </p>
        </div>
      )}

      {healthMetrics.disk > 90 && (
        <div className="mobile-card" style={{ background: '#c0392b22', border: '2px solid #c0392b', marginTop: 12 }}>
          <h4 style={{ margin: '0 0 8px 0', color: '#c0392b', fontSize: '16px' }}>🚨 Disk Full</h4>
          <p style={{ margin: 0, fontSize: '13px', color: '#e74c3c' }}>
            Disk is {healthMetrics.disk.toFixed(1)}% full. Clean up logs urgently.
          </p>
        </div>
      )}
    </div>
  );
};

export default React.memo(MobileMonitoring);
