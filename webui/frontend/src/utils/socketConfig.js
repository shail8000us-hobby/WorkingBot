// Flask-SocketIO runs in threading async mode — WebSocket upgrades fail with
// "Invalid frame header". Polling is stable and delivers all real-time events.
export const POLLING_SOCKET_OPTIONS = {
  transports: ['polling'],
  upgrade: false,
  rememberUpgrade: false,
};
