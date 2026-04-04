# Vigil: Institutional-Grade Trading Intelligence

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](#license)
[![Status](https://img.shields.io/badge/status-Production%20Ready-brightgreen.svg)](#status)

Advanced automated breakout detection and signal analysis system with institutional-level risk management, decision intelligence, and real-time monitoring.

---

## Project Overview

Vigil is a **production-ready trading intelligence system** that detects high-probability breakouts and volume-based trading signals. It combines quantitative signal detection with a decision intelligence layer that provides explainable, confidence-scored trading signals backed by outcome tracking and portfolio simulation.

The system operates on a closed-loop architecture:

1. **Detection** — Scans market data using multi-timeframe analysis, regime detection, and bull trap filtering
2. **Scoring** — Calculates edge scores and confidence grades using adaptive weighted factors
3. **Notification** — Delivers real-time alerts via webhooks (Slack/Discord) and WebSocket
4. **Evaluation** — Tracks signal outcomes and auto-tunes scoring weights based on performance

**Performance Targets:** 60%+ win rate, 60% fewer false signals, 3x better returns vs standard approaches.

---

## Key Features

### Signal Detection & Analysis
- **Advanced signal detection** — Accumulation patterns, volume spikes, confirmed breakouts, multi-timeframe analysis
- **Regime-aware filtering** — Contextualizes signals based on market regime (TRENDING, RISK_OFF, SIDEWAYS, VOLATILE)
- **Bull trap detection** — 5-filter heuristic system (volume, RSI exhaustion, resistance, ATR rejection, overextension)
- **Edge scoring** — 0-10 scale combining signal combo, MTF alignment, trap penalty, and volume confirmation

### Decision Intelligence Platform
- **Multi-factor scoring** — Deterministic 0-100 confidence scoring with individual factor attribution
- **Structured explanations** — Machine-parseable rationales with primary trigger identification
- **Confidence grades** — Very Low (0-20), Low (21-40), Moderate (41-60), High (61-80), Very High (81-100)
- **Outcome tracking** — Post-signal state machine with peak drawdown monitoring and time-to-resolution

### Portfolio & Risk Management
- **Portfolio simulation** — Walk-forward simulation with Sharpe, Sortino, and Calmar ratios
- **Adaptive weights** — Self-tuning scoring weights based on historical outcome analysis
- **Correlation analysis** — Cross-asset correlation matrix for portfolio risk assessment
- **Kelly Criterion** — Position sizing based on edge score and volatility

### Real-Time Infrastructure
- **WebSocket streaming** — Real-time push for alerts, signals, and regime changes
- **Polling mode** — Cost-optimized alternative for free-tier deployments
- **Distributed locking** — Prevents duplicate detection runs across multiple instances
- **Prometheus metrics** — Observability with request-level metrics and health monitoring

### Frontend Dashboard
- **Signal intelligence** — Paginated signal list with filtering and factor breakdown
- **Outcome tracking** — Visual tracking of signal resolution and performance
- **Simulation runner** — Portfolio simulation interface with equity curve visualization
- **Regime indicator** — Real-time market regime display with confidence levels

---

## Prerequisites

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ (20+ recommended) | Frontend runtime |
| PostgreSQL | 16+ | Primary database |
| Docker & Compose | Latest (optional) | Containerized deployment |
| npm | 9+ | Frontend package management |

---

## Installation Instructions

### Option 1: Docker Compose (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/NadhanJosy/Vigil.git
cd Vigil

# 2. Configure environment
cp .env.example .env
# Edit .env with your values (see Configuration section)

# 3. Start all services
docker-compose up -d --build

# 4. Verify services are running
docker-compose ps
```

Services will be available at:
- **Frontend:** http://localhost:3000
- **API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **PostgreSQL:** localhost:5432

### Option 2: Local Development

#### Backend Setup

```bash
# 1. Navigate to backend directory
cd backend

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp ../.env.example .env
# Edit .env with your DATABASE_URL and other values

# 5. Run database migrations
psql $DATABASE_URL -f migrations/001_neon_optimizations.sql
psql $DATABASE_URL -f migrations/002_decision_intelligence.sql
psql $DATABASE_URL -f migrations/003_performance_indexes.sql
psql $DATABASE_URL -f migrations/004_simulation_results.sql
psql $DATABASE_URL -f migrations/005_weight_history.sql

# 6. Start the API server
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend Setup

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Start development server
npm run dev
```

---

## Quick Start

Minimal steps to get Vigil running with Docker Compose:

```bash
git clone https://github.com/NadhanJosy/Vigil.git && cd Vigil
cp .env.example .env
docker-compose up -d
```

Access the dashboard at http://localhost:3000 and the API documentation at http://localhost:8000/docs.

To trigger an immediate signal detection run:

```bash
curl -X POST http://localhost:8000/trigger \
  -H "X-API-KEY: ${VIGIL_API_KEY}" \
  -H "Content-Type: application/json"
```

---

## Usage Examples

### API Endpoints

#### Real-Time Monitoring

```bash
# Health check
curl http://localhost:8000/

# Query alerts with filters
curl "http://localhost:8000/alerts?ticker=AAPL&limit=50&offset=0"

# Get current market regime
curl http://localhost:8000/regime

# Polling status (for polling mode clients)
curl http://localhost:8000/health/polling-status
```

#### Trading Operations

```bash
# Trigger immediate detection run
curl -X POST http://localhost:8000/trigger \
  -H "X-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["AAPL", "TSLA"]}'

# Backfill historical data
curl -X POST http://localhost:8000/backfill \
  -H "X-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["SPY", "QQQ"], "days": 90}'

# Run portfolio backtest
curl -X POST http://localhost:8000/backtest/run \
  -H "X-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Q1-2026-Backtest",
    "start_date": "2026-01-01",
    "end_date": "2026-03-31",
    "tickers": ["AAPL", "MSFT", "GOOGL"],
    "capital": 100000
  }'
```

#### Watchlist Management

```bash
# List watched symbols
curl http://localhost:8000/watchlist

# Add ticker to watchlist
curl -X POST http://localhost:8000/watchlist \
  -H "X-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"ticker": "NVDA"}'

# Remove ticker from watchlist
curl -X DELETE "http://localhost:8000/watchlist?ticker=AAPL" \
  -H "X-API-KEY: your-api-key"
```

#### Decision Intelligence API

All DI endpoints are under `/api/di/`:

```bash
# Paginated signal list with filtering
curl "http://localhost:8000/api/di/signals?limit=20&status=active"

# Full signal detail with explanation
curl http://localhost:8000/api/di/signals/123

# Current regime state
curl http://localhost:8000/api/di/regimes/current

# Run portfolio simulation
curl -X POST http://localhost:8000/api/di/simulations/run \
  -H "Content-Type: application/json" \
  -d '{
    "simulation_type": "walk_forward",
    "start_date": "2026-01-01",
    "end_date": "2026-03-31",
    "initial_capital": 100000,
    "position_sizing": "equal_weight",
    "max_exposure_pct": 100
  }'

# Current active scoring weights
curl http://localhost:8000/api/di/weights/active

# Portfolio exposure summary
curl http://localhost:8000/api/di/portfolio/exposure
```

### WebSocket Connection

```javascript
// Connect to real-time WebSocket
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event type:', data.event_type);
  console.log('Data:', data.data);
};

// Subscribe to alert events
ws.onopen = () => {
  console.log('Connected to Vigil WebSocket');
};
```

### Example Alert Response

```json
{
  "id": 1234,
  "ticker": "AAPL",
  "signal_type": "VOLUME_SPIKE_UP",
  "edge_score": 7.2,
  "action": "ENTER",
  "regime": "TRENDING",
  "decay": {
    "pct": 85,
    "status": "FRESH",
    "hours_old": 2.3
  },
  "summary": "Breakout with 2.3x volume — confirmed multi-timeframe up alignment",
  "created_at": "2026-04-04T10:30:00Z"
}
```

### Example Signal Detail Response

```json
{
  "signal": {
    "id": 1234,
    "symbol": "AAPL",
    "direction": "bullish",
    "confidence_score": 78.5,
    "confidence_grade": "high",
    "status": "active",
    "detected_at": "2026-04-04T10:30:00Z",
    "entry_price": 185.50,
    "target_price": 195.00,
    "stop_price": 180.00
  },
  "explanation": {
    "signal_id": 1234,
    "primary_trigger": "volume_spike",
    "contributing_factors": [
      {
        "factor_name": "volume_ratio",
        "factor_value": 2.3,
        "weight": 0.25,
        "weighted_contribution": 18.5
      }
    ],
    "confidence_grade": "high",
    "regime_context": "TRENDING"
  }
}
```

---

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string | — | Yes |
| `JWT_SECRET` | JWT signing key | `dev-secret-change-me` | Yes (production) |
| `VIGIL_API_KEY` | API key for protected endpoints | — | Yes (production) |
| `LOG_LEVEL` | Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) | `INFO` | No |
| `WATCHLIST` | Comma-separated ticker symbols | `SPY,QQQ,IWM` | No |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL for alerts | — | No |
| `WEBHOOK_URL` | Generic webhook URL for alerts | — | No |
| `REDIS_URL` | Redis connection URL for caching and distributed locks | — | No |
| `CORS_ORIGINS` | Comma-separated allowed CORS origins | `http://localhost:3000` | No |
| `PROMETHEUS_ENABLED` | Enable Prometheus metrics endpoint | `true` | No |
| `NEXT_PUBLIC_API_URL` | Frontend API URL | `http://localhost:8000` | No |
| `NEXT_PUBLIC_WS_URL` | Frontend WebSocket URL | `ws://localhost:8000/ws` | No |

### Feature Flags

| Variable | Default | Effect |
|----------|---------|--------|
| `REALTIME_ENABLED` | `true` | Enables WebSocket endpoint (set `false` to disable) |
| `SCHEDULER_ENABLED` | `true` | Enables APScheduler for automatic daily scans at 21:00 ET |
| `POLLING_MODE` | `false` | Enables polling-optimized backend behavior |
| `NEXT_PUBLIC_POLLING_MODE` | `true` | Enables polling mode in the frontend |
| `NEXT_PUBLIC_POLL_INTERVAL_MS` | `15000` | Frontend polling interval in milliseconds |

### PostgreSQL Connection

```
# Local development
DATABASE_URL=postgresql://vigil:vigil@localhost:5432/vigil

# Production (Railway, Render, etc.)
DATABASE_URL=postgresql://user:password@host:port/database?sslmode=require
```

### Default Watchlist

The default watchlist is configured via the `WATCHLIST` environment variable:

```bash
WATCHLIST=SPY,QQQ,IWM
```

Modify this to focus on your preferred symbols.

---

## Testing

### Backend Tests

```bash
# Navigate to backend directory
cd backend

# Run all tests with pytest
python -m pytest tests/ -v

# Run end-to-end tests
python test_e2e.py

# Run adversarial tests
python test_adversarial.py
```

### Frontend Tests

```bash
# Navigate to frontend directory
cd frontend

# Run tests
npm test
```

### Test Coverage

The test suite covers:
- Database connection and CRUD operations
- Watchlist management
- Signal detection engine
- Webhook integration
- API endpoints (REST and DI)
- Backtest engine
- Adversarial input handling

---

## Contributing Guidelines

1. **Fork the repository** and create your feature branch from `main`
2. **Set up development environment** using the installation instructions above
3. **Make your changes** following the existing code style:
   - Backend: Ruff linting (`ruff check .`), target Python 3.11+
   - Frontend: ESLint (`npm run lint`), Prettier formatting
4. **Write or update tests** for any new functionality
5. **Run the test suite** to ensure nothing is broken
6. **Submit a pull request** with a clear description of changes

### Code Style

```bash
# Backend linting and formatting
cd backend
ruff check .
ruff format .

# Frontend linting
cd frontend
npm run lint
npx prettier --write .
```

### Commit Messages

Use conventional commit format:

```
feat: add correlation analysis endpoint
fix: resolve WebSocket reconnection issue
docs: update architecture diagram
test: add adversarial input tests
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `DATABASE_URL` not set | Copy `.env.example` to `.env` and fill in your PostgreSQL connection string |
| Port 8000 already in use | Change the port in your `.env` file or kill the existing process: `lsof -ti:8000 \| xargs kill` |
| Frontend can't connect to API | Verify `NEXT_PUBLIC_API_URL` in `.env` matches your backend URL |
| PostgreSQL authentication failed | Verify `DATABASE_URL` credentials match your database configuration |
| Import errors in backend | Ensure working directory is `backend/` or set `PYTHONPATH=.` |
| WebSocket connection refused | Check `REALTIME_ENABLED=true` in `.env` and verify the WebSocket endpoint is accessible |
| Scheduler not running | Verify `SCHEDULER_ENABLED=true` and check logs for APScheduler startup messages |
| Docker build fails | Ensure Docker Compose version is 2.0+ and all required files exist |
| Migration errors | Run migrations in order (001 through 005) and verify database exists |

### Health Check Endpoints

```bash
# Basic health check
curl http://localhost:8000/

# Polling mode status
curl http://localhost:8000/health/polling-status

# Prometheus metrics
curl http://localhost:8000/metrics
```

### Logs

```bash
# Docker Compose logs
docker-compose logs -f api
docker-compose logs -f frontend
docker-compose logs -f postgres

# Local development logs
# Backend: visible in terminal running uvicorn
# Frontend: visible in terminal running npm run dev
```

---

## License

**Proprietary and Confidential.** This software is for private use only. Unauthorized copying, distribution, or modification is strictly prohibited.

---

## Project Structure

```
Vigil/
├── .env.example              # Environment variable template
├── .gitignore
├── docker-compose.yml        # Docker Compose configuration
├── Dockerfile                # Backend Docker image
├── Procfile                  # Heroku/Railway process definition
├── nixpacks.toml             # Railway build configuration
├── README.md                 # This file
├── DEPLOYMENT.md             # Detailed deployment guide
├── backend/
│   ├── api.py                # FastAPI application and endpoints
│   ├── data.py               # Signal detection engine
│   ├── database.py           # PostgreSQL connection and queries
│   ├── models.py             # Pydantic response models
│   ├── advanced_signals.py   # Advanced signal analysis
│   ├── requirements.txt      # Python dependencies
│   ├── pyproject.toml        # Ruff and pytest configuration
│   ├── backtest/             # Backtesting engine
│   │   ├── engine.py         # Backtest orchestration
│   │   ├── broker.py         # Simulated broker
│   │   └── metrics.py        # Performance metrics
│   ├── config/               # Configuration modules
│   │   └── regime_config.yaml
│   ├── migrations/           # Database migration scripts
│   │   ├── 001_neon_optimizations.sql
│   │   ├── 002_decision_intelligence.sql
│   │   ├── 003_performance_indexes.sql
│   │   ├── 004_simulation_results.sql
│   │   └── 005_weight_history.sql
│   ├── services/             # Microservices
│   │   ├── alert_router.py   # Alert routing and delivery
│   │   ├── cache.py          # Caching layer
│   │   ├── correlation_engine.py
│   │   ├── dedup.py          # Signal deduplication
│   │   ├── distributed_lock.py
│   │   ├── event_bus.py      # Event pub/sub system
│   │   ├── explainability.py # Signal explanation engine
│   │   ├── feature_flags.py  # Feature flag management
│   │   ├── health.py         # Health check endpoints
│   │   ├── lru_cache.py      # LRU cache implementation
│   │   ├── observability.py  # Logging and metrics
│   │   ├── outcome_tracker.py
│   │   ├── portfolio_risk.py # Portfolio risk analysis
│   │   ├── rate_limiter.py   # API rate limiting
│   │   ├── regime_detector.py
│   │   ├── regime_engine.py  # Regime detection engine
│   │   ├── scoring_engine.py # Signal scoring
│   │   ├── security.py       # JWT and CORS
│   │   ├── self_evaluation.py
│   │   └── ws_manager.py     # WebSocket connection manager
│   └── tests/                # Test suite
├── frontend/
│   ├── app/                  # Next.js App Router pages
│   │   ├── page.tsx          # Home page
│   │   ├── signals/          # Signal intelligence pages
│   │   └── simulations/      # Simulation runner page
│   ├── components/           # React components
│   ├── lib/                  # API clients and utilities
│   ├── types/                # TypeScript type definitions
│   ├── package.json          # Frontend dependencies
│   └── next.config.js        # Next.js configuration
├── docs/                     # Documentation
│   ├── ARCHITECTURE.md       # System architecture overview
│   ├── DECISION_INTELLIGENCE_ARCHITECTURE.md
│   ├── IMPLEMENTATION_PLAN.md
│   └── POLLING_MIGRATION_PLAN.md
└── scripts/                  # Setup and utility scripts
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design, data flow, component overview |
| [`docs/DECISION_INTELLIGENCE_ARCHITECTURE.md`](docs/DECISION_INTELLIGENCE_ARCHITECTURE.md) | Decision intelligence layer architecture |
| [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) | Implementation roadmap and milestones |
| [`docs/POLLING_MIGRATION_PLAN.md`](docs/POLLING_MIGRATION_PLAN.md) | WebSocket to polling migration guide |
| [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | Version history and changes |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | Detailed deployment instructions |

---

**Status:** Production Ready | **Version:** 2.0 | **Last Updated:** April 2026
