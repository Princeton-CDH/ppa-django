#!/bin/bash
# Kill process using specified port
# Usage: bash scripts/kill_port.sh <port>

PORT=${1:-8000}

# Check if port is in use
PID=$(lsof -ti:$PORT 2>/dev/null)

if [ -n "$PID" ]; then
    echo "⚠️  Port $PORT is in use by process $PID"
    echo "🔄 Stopping process..."
    kill $PID 2>/dev/null

    # Wait a moment for process to stop
    sleep 1

    # Check if process is still running
    if lsof -ti:$PORT >/dev/null 2>&1; then
        echo "⚠️  Process still running, forcing kill..."
        kill -9 $PID 2>/dev/null
        sleep 1
    fi

    # Verify port is now free
    if lsof -ti:$PORT >/dev/null 2>&1; then
        echo "❌ Failed to free port $PORT"
        exit 1
    else
        echo "✅ Port $PORT is now free"
    fi
else
    echo "✅ Port $PORT is available"
fi
