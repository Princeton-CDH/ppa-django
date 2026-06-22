#!/bin/bash
# Wait for Solr to be ready
# Usage: bash scripts/wait_for_solr.sh

SOLR_URL="http://localhost:8983/solr/ppa/admin/ping"
MAX_ATTEMPTS=30

for i in $(seq 1 $MAX_ATTEMPTS); do
    if curl -s -o /dev/null -w "%{http_code}" "$SOLR_URL" 2>/dev/null | grep -q "200"; then
        echo "✅ Solr is ready"
        exit 0
    fi
    echo "⏳ Waiting for Solr... (${i}/${MAX_ATTEMPTS})"
    sleep 2
done

echo "⚠️  Solr did not become ready in time — continuing anyway"
exit 0
