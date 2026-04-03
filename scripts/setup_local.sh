#!/bin/bash
# Setup script for local Vigil testing

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  VIGIL LOCAL SETUP - DATABASE CONFIGURATION                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check for DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
    echo "⚠️  DATABASE_URL not set"
    echo ""
    echo "You have 3 options:"
    echo ""
    echo "OPTION 1: PostgreSQL (Recommended for production testing)"
    echo "  1. Install PostgreSQL: apt update && apt install -y postgresql"
    echo "  2. Start PostgreSQL: service postgresql start"
    echo "  3. Create database: sudo -u postgres createdb vigil"
    echo "  4. Set URL: export DATABASE_URL='postgresql://postgres:password@localhost/vigil'"
    echo ""
    echo "OPTION 2: ElephantSQL (Free cloud Postgres)"
    echo "  1. Sign up at https://www.elephantsql.com"
    echo "  2. Create a free instance (20MB)"
    echo "  3. Copy the connection string"
    echo "  4. Set: export DATABASE_URL='<your-elephantsql-url>'"
    echo ""
    echo "OPTION 3: Heroku Postgres (if deploying there)"
    echo "  1. heroku addons:create heroku-postgresql:hobby-dev"
    echo "  2. heroku config:get DATABASE_URL"
    echo "  3. Set locally: export DATABASE_URL='<copied-url>'"
    echo ""
    exit 1
fi

echo "✓ DATABASE_URL is set"
echo "  Testing connection..."

# Try to connect
python3 -c "
import os
import psycopg2
try:
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    cursor = conn.cursor()
    cursor.execute('SELECT 1')
    print('✓ Database connection successful')
    conn.close()
except Exception as e:
    print(f'✗ Connection failed: {e}')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Setup complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Run tests: python test_e2e.py"
    echo "  2. Or start API: python api.py"
    echo "  3. Or trigger detection: curl http://localhost:5000/trigger"
else
    echo ""
    echo "✗ Database connection failed"
    exit 1
fi
