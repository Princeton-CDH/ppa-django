#!/bin/bash

echo "🔍 Verifying PPA Django Reuse Setup"
echo "===================================="

ERRORS=0

# Check if running in Devbox shell
if [ -n "$DEVBOX_SHELL_ENABLED" ]; then
    echo "✅ Devbox: Shell active"
else
    echo "⚠️  Devbox: Not in shell (manual mode)"
fi

# Check virtual environment
if [ -d ".venv" ]; then
    echo "✅ Virtual environment: Exists"
    if [ -n "$VIRTUAL_ENV" ]; then
        echo "✅ Virtual environment: Activated"
    else
        echo "⚠️  Virtual environment: Not activated (run: source .venv/bin/activate)"
        # Try to activate for remaining checks
        source .venv/bin/activate 2>/dev/null || true
    fi
else
    echo "❌ Virtual environment: Not found"
    ERRORS=$((ERRORS + 1))
fi

# Check Python
if command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR_MINOR=$(echo $PYTHON_VERSION | grep -oE '^[0-9]+\.[0-9]+')
    if [ "$PYTHON_MAJOR_MINOR" = "3.12" ]; then
        echo "✅ Python: $PYTHON_VERSION (matches devbox.json)"
    else
        echo "⚠️  Python: $PYTHON_VERSION (expected 3.12)"
    fi
else
    echo "❌ Python not found"
    ERRORS=$((ERRORS + 1))
fi

# Check Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    NODE_MAJOR=$(echo $NODE_VERSION | grep -oE '[0-9]+' | head -1)
    if [ "$NODE_MAJOR" = "22" ]; then
        echo "✅ Node.js: $NODE_VERSION (matches devbox.json)"
    else
        echo "⚠️  Node.js: $NODE_VERSION (expected v22.x)"
    fi
else
    # Node.js not found - check if node_modules exists (might be using devbox)
    if [ -d "node_modules" ]; then
        echo "⚠️  Node.js: Not in PATH (but node_modules exists - may need devbox shell)"
    else
        echo "❌ Node.js: Not found"
        ERRORS=$((ERRORS + 1))
    fi
fi

# Check PostgreSQL
if docker compose -f docker/docker-compose.dev.yml ps | grep -q "db.*Up"; then
    echo "✅ PostgreSQL: Running"
else
    echo "❌ PostgreSQL: Not running"
    ERRORS=$((ERRORS + 1))
fi

# Check Solr
if docker compose -f docker/docker-compose.dev.yml ps 2>/dev/null | grep -q "solr.*Up"; then
    if docker compose -f docker/docker-compose.dev.yml ps 2>/dev/null | grep -q "solr.*healthy"; then
        echo "✅ Solr: Running (healthy)"
        # Test Solr API
        if curl -s http://localhost:8983/solr/ppa/admin/ping 2>/dev/null | grep -q "OK"; then
            echo "✅ Solr API: Responding"
        else
            echo "⚠️  Solr API: Not responding yet"
        fi
    else
        echo "⚠️  Solr: Running but not healthy yet"
    fi
else
    echo "⚠️  Solr: Not running (optional)"
fi

# Check Django
if python manage.py check 2>&1 | grep -q "System check identified no issues"; then
    echo "✅ Django: Configuration OK"
else
    # Try with --deploy flag to see if it's just deployment warnings
    DEPLOY_CHECK=$(python manage.py check --deploy 2>&1)
    if echo "$DEPLOY_CHECK" | grep -q "System check identified no issues"; then
        echo "✅ Django: Configuration OK"
    elif echo "$DEPLOY_CHECK" | grep -q "WARNINGS:" && ! echo "$DEPLOY_CHECK" | grep -q "ERRORS:"; then
        echo "✅ Django: Configuration OK (deployment warnings expected in dev)"
    else
        echo "❌ Django: Configuration issues"
        ERRORS=$((ERRORS + 1))
    fi
fi

# Check database connection
if python manage.py showmigrations &> /dev/null; then
    echo "✅ Database: Connected"
else
    echo "❌ Database: Connection failed"
    ERRORS=$((ERRORS + 1))
fi

# Check static files (webpack outputs to bundles/)
if [ -f "webpack-stats.json" ] && [ -d "bundles/js" ] && [ -d "bundles/css" ]; then
    echo "✅ Static files: Built"
else
    echo "⚠️  Static files: Not built (run npm run build)"
fi

# Check npm dependencies
if [ -d "node_modules" ]; then
    echo "✅ npm: Dependencies installed"
else
    echo "❌ npm: Dependencies missing (run: npm install)"
    ERRORS=$((ERRORS + 1))
fi

# Check adapter system
if command -v python &> /dev/null; then
    ARCHIVE_ADAPTER=${ARCHIVE_ADAPTER:-}
    if [ -n "$ARCHIVE_ADAPTER" ]; then
        ADAPTER_CHECK=$(python -c "
from ppa.adapters.loader import get_adapter
a = get_adapter('$ARCHIVE_ADAPTER')
print('successfully' if a else 'failed')
" 2>&1)
        if echo "$ADAPTER_CHECK" | grep -q "successfully"; then
            echo "✅ Adapter: $ARCHIVE_ADAPTER validated"
        else
            echo "⚠️  Adapter: Validation issues"
        fi
    else
        echo "⚠️  Adapter: Not configured (optional)"
    fi
fi

# Check waffle switches
if command -v python &> /dev/null; then
    WAFFLE_COUNT=$(python manage.py shell -c "from waffle.models import Switch; print(Switch.objects.count())" 2>/dev/null | grep -oE '^[0-9]+$' || echo "0")
    if [ "$WAFFLE_COUNT" -gt 0 ] 2>/dev/null; then
        echo "✅ Waffle: $WAFFLE_COUNT feature flag(s) configured"
    else
        echo "⚠️  Waffle: No feature flags configured"
    fi
fi

echo ""
if [ $ERRORS -eq 0 ]; then
    echo "✅ All checks passed!"
    exit 0
else
    echo "❌ $ERRORS error(s) found"
    exit 1
fi
