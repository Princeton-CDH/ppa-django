#!/bin/bash
set -e

echo "🔧 PPA Django Reuse Setup Script"
echo "================================"

# Check if services are running
echo "📡 Checking Docker services..."
if ! docker compose -f docker/docker-compose.dev.yml ps | grep -q "Up"; then
    echo "❌ Docker services not running. Starting..."
    docker compose -f docker/docker-compose.dev.yml up -d
    sleep 10
fi

# Wait for PostgreSQL
echo "⏳ Waiting for PostgreSQL..."
until docker compose -f docker/docker-compose.dev.yml exec -T db pg_isready -U ppa; do
    sleep 1
done

# Run migrations
echo "🗄️  Running database migrations..."
python manage.py migrate

# Setup Wagtail pages
echo "📄 Setting up Wagtail pages..."
python manage.py setup_site_pages

# Create superuser if not exists
echo "👤 Creating admin user..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('✅ Admin user created: admin/admin123')
else:
    print('ℹ️  Admin user already exists')
"

# Setup Waffle switches
echo "🎛️  Setting up feature flags..."
python manage.py shell -c "
from waffle.models import Switch
Switch.objects.update_or_create(name='enable_solr_indexing', defaults={'active': False})
Switch.objects.update_or_create(name='enable_hathi', defaults={'active': False})
Switch.objects.update_or_create(name='enable_corppa', defaults={'active': False})
print('✅ Feature flags configured')
"

# Setup Solr (optional)
if docker compose -f docker/docker-compose.dev.yml ps | grep -q "solr.*Up"; then
    echo "🔍 Setting up Solr schema..."

    # Wait for Solr to be ready
    echo "⏳ Waiting for Solr..."
    for i in $(seq 1 30); do
        if curl -s -o /dev/null -w "%{http_code}" "http://localhost:8983/solr/ppa/admin/ping" 2>/dev/null | grep -q "200"; then
            break
        fi
        sleep 2
    done

    # Copy project schema config into the Solr container
    echo "📋 Uploading Solr schema config..."
    docker cp solr_conf/conf/managed-schema.xml docker-solr-1:/var/solr/data/ppa/conf/managed-schema.xml 2>/dev/null || true
    docker cp solr_conf/conf/solrconfig.xml docker-solr-1:/var/solr/data/ppa/conf/solrconfig.xml 2>/dev/null || true
    docker cp solr_conf/conf/elevate.xml docker-solr-1:/var/solr/data/ppa/conf/elevate.xml 2>/dev/null || true
    docker cp solr_conf/conf/params.json docker-solr-1:/var/solr/data/ppa/conf/params.json 2>/dev/null || true
    docker cp solr_conf/conf/stemdict_ppa.txt docker-solr-1:/var/solr/data/ppa/conf/stemdict_ppa.txt 2>/dev/null || true
    docker cp solr_conf/conf/synonyms.txt docker-solr-1:/var/solr/data/ppa/conf/synonyms.txt 2>/dev/null || true
    docker cp solr_conf/conf/protwords.txt docker-solr-1:/var/solr/data/ppa/conf/protwords.txt 2>/dev/null || true
    docker cp solr_conf/conf/stopwords.txt docker-solr-1:/var/solr/data/ppa/conf/stopwords.txt 2>/dev/null || true

    # Reload the core to pick up the new config
    RELOAD_STATUS=$(curl -s "http://localhost:8983/solr/admin/cores?action=RELOAD&core=ppa" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('responseHeader',{}).get('status','?'))" 2>/dev/null)
    if [ "$RELOAD_STATUS" = "0" ]; then
        echo "✅ Solr schema loaded"
    else
        echo "⚠️  Solr schema reload returned status $RELOAD_STATUS (may still work)"
    fi

    echo "📊 Indexing data to Solr..."
    python manage.py index --index work || echo "⚠️  Solr indexing failed (optional)"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Run: devbox run dev"
echo "  2. Visit: http://localhost:8000"
echo "  3. Admin: http://localhost:8000/admin (admin/admin123)"
