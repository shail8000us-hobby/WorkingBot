#!/bin/bash
# WorkingBot Observability Management Script
# Usage: ./observability_manager.sh [start|stop|restart|status]

case "$1" in
    start)
        echo "🚀 Starting observability stack..."
        
        # Start metrics server
        if ! lsof -i :9091 >/dev/null 2>&1; then
            echo "   Starting Metrics Server..."
            nohup python3 observability/start.py > /dev/null 2>&1 &
            sleep 2
        fi
        
        # Start Prometheus
        if ! lsof -i :9090 >/dev/null 2>&1; then
            echo "   Starting Prometheus..."
            brew services start prometheus
        fi
        
        # Start Grafana
        if ! lsof -i :3000 >/dev/null 2>&1; then
            echo "   Starting Grafana..."
            brew services start grafana
        fi
        
        sleep 3
        echo "✅ All services started!"
        $0 status
        ;;
        
    stop)
        echo "🛑 Stopping observability stack..."
        
        # Stop metrics server
        pkill -f "observability/start.py" && echo "   ✓ Metrics Server stopped"
        
        # Stop Prometheus
        brew services stop prometheus && echo "   ✓ Prometheus stopped"
        
        # Stop Grafana
        brew services stop grafana && echo "   ✓ Grafana stopped"
        
        echo "✅ All services stopped!"
        ;;
        
    restart)
        echo "🔄 Restarting observability stack..."
        $0 stop
        sleep 2
        $0 start
        ;;
        
    status)
        echo ""
        echo "════════════════════════════════════════════════════════"
        echo "         📊 OBSERVABILITY STACK STATUS"
        echo "════════════════════════════════════════════════════════"
        echo ""
        
        # Check each service
        if lsof -i :9091 >/dev/null 2>&1; then
            echo "   ✅ Metrics Server (9091):  RUNNING"
            echo "      → http://localhost:9091"
        else
            echo "   ❌ Metrics Server (9091):  STOPPED"
        fi
        
        if lsof -i :9090 >/dev/null 2>&1; then
            echo "   ✅ Prometheus (9090):      RUNNING"
            echo "      → http://localhost:9090"
        else
            echo "   ❌ Prometheus (9090):      STOPPED"
        fi
        
        if lsof -i :3000 >/dev/null 2>&1; then
            echo "   ✅ Grafana (3000):         RUNNING"
            echo "      → http://localhost:3000"
        else
            echo "   ❌ Grafana (3000):         STOPPED"
        fi
        
        echo ""
        echo "════════════════════════════════════════════════════════"
        ;;
        
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        echo ""
        echo "Commands:"
        echo "  start   - Start all observability services"
        echo "  stop    - Stop all observability services"
        echo "  restart - Restart all observability services"
        echo "  status  - Show status of all services"
        exit 1
        ;;
esac
