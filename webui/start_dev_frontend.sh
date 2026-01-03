#!/bin/bash
# Start React development server for BTEH branch multi-symbol WebUI
cd "$(dirname "$0")/frontend"
export REACT_APP_API_URL=http://localhost:5556
export REACT_APP_SOCKET_URL=http://localhost:5556
export REACT_APP_API_BASE_URL=http://localhost:5556
export PORT=3001
export BROWSER=none
npm start
