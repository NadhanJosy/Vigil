# Vigil Deployment Guide

## Table of Contents
- [Local Development](#local-development)
- [Docker Deployment](#docker-deployment)
- [Cloud Deployment](#cloud-deployment)
- [Environment Variables](#environment-variables)
- [Database Migrations](#database-migrations)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

---

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 16+ (or use Docker)

### Setup

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your values

# 2. Backend setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Frontend setup
cd frontend
npm install
cd ..

# 4. Start PostgreSQL (if not using Docker)
# Ensure DATABASE_URL in .env points to your local Postgres

# 5. Run migrations
psql $DATABASE_URL -f migrations/001_neon_optimizations.sql

# 6. Start backend
uvicorn api:app --reload --host 0.0.0.0 --port 8000

# 7. Start frontend (in another terminal)
cd frontend && npm run dev
```

Access:
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## Docker Deployment

### Quick Start

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your values (change JWT_SECRET!)

# 2. Build and start all services
docker compose up --build -d

# 3. Check status
docker compose ps

# 4. View logs
docker compose logs -f api
docker compose logs -f frontend
docker compose logs -f postgres
```

### Stop Services

```bash
docker compose down
# To also remove volumes (deletes database!):
docker compose down -v
```

### Architecture

| Service    | Port | Description              |
|------------|------|--------------------------|
| postgres   | 5432 | PostgreSQL database      |
| api        | 8000 | FastAPI backend          |
| frontend   | 3000 | Next.js frontend         |

---

## Cloud Deployment

### Railway

1. Connect your GitHub repo to Railway
2. Add services:
   - **Backend**: Root directory, start command `uvicorn api:app --host 0.0.0.0 --port $PORT`
   - **Frontend**: `frontend` directory, start command `npm run start`
   - **Database**: Add PostgreSQL plugin
3. Set environment variables in Railway dashboard
4. Deploy

### Render

**Backend (Web Service):**
- Build: `pip install -r requirements.txt`
- Start: `uvicorn api:app --host 0.0.0.0 --port $PORT`
- Add PostgreSQL database

**Frontend (Web Service):**
- Root directory: `frontend`
- Build: `npm install && npm run build`
- Start: `npm run start`

### Fly.io

```bash
# Backend
fly launch --name vigil-api
fly secrets set DATABASE_URL="..." JWT_SECRET="..."
fly deploy

# Frontend
cd frontend
fly launch --name vigil-frontend
fly deploy
```

### Docker (Any Provider)

```bash
# Build
docker build -t vigil-api .

# Run
docker run -d \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://..." \
  -e JWT_SECRET="your-secret" \
  --name vigil-api \
  vigil-api
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `JWT_SECRET` | Yes | - | JWT signing key (use strong random) |
| `REDIS_URL` | No | - | Redis URL for caching/locks |
| `SLACK_WEBHOOK_URL` | No | - | Slack incoming webhook for alerts |
| `WEBHOOK_URL` | No | - | Generic webhook for alerts |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `PROMETHEUS_ENABLED` | No | `true` | Enable `/metrics` endpoint |
| `CORS_ORIGINS` | No | - | Comma-separated allowed origins |
| `WATCHLIST` | No | `SPY,QQQ,IWM` | Default ticker watchlist |

---

## Database Migrations

### Apply Migrations

```bash
# Using psql
psql $DATABASE_URL -f migrations/001_neon_optimizations.sql

# Using Docker
docker compose exec postgres psql -U vigil -d vigil -f /docker-entrypoint-initdb.d/001_neon_optimizations.sql
```

### Creating New Migrations

1. Create a new SQL file in `migrations/`
2. Name it with a sequence number: `002_description.sql`
3. Include both `UP` and `DOWN` logic in comments
4. Apply to your database

---

## Monitoring

### Prometheus Metrics

When `PROMETHEUS_ENABLED=true`, metrics are available at `/metrics`.

```bash
# Scrape metrics
curl http://localhost:8000/metrics
```

### Grafana Dashboard

1. Add Prometheus as a data source in Grafana
2. Import dashboard using the `/metrics` endpoint
3. Key metrics to track:
   - Request rate and latency
   - Signal detection counts
   - Alert delivery success rate
   - Database connection pool usage

### Health Check

```bash
curl http://localhost:8000/health
```

Response includes:
- Database connection status
- Scheduler status
- System metrics (CPU, memory)

---

## Troubleshooting

### API won't start

```bash
# Check logs
docker compose logs api

# Common issues:
# - DATABASE_URL is incorrect
# - Port 8000 is already in use
# - Missing dependencies (run pip install -r requirements.txt)
```

### Database connection refused

```bash
# Check PostgreSQL is running
docker compose ps postgres

# Restart PostgreSQL
docker compose restart postgres

# Check connection
docker compose exec postgres pg_isready -U vigil
```

### Frontend can't reach API

- Ensure `NEXT_PUBLIC_API_URL` points to the correct API URL
- Check CORS settings include the frontend origin
- Verify both services are on the same Docker network

### High memory usage

```bash
# Check system metrics
curl http://localhost:8000/health

# Reduce uvicorn workers (default is 1)
# In Dockerfile CMD, keep --workers 1 for low-memory environments
```

### Scheduler jobs not running

```bash
# Check scheduler status in health endpoint
curl http://localhost:8000/health | jq .scheduler

# Restart the API service
docker compose restart api
```
