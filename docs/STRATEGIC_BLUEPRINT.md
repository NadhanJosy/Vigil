# Vigil Strategic Blueprint: Path to Global Market Dominance

**Version:** 3.0 — Absolute Zero-Cost Edition  
**Date:** 2026-04-02  
**Classification:** Confidential — Internal Use Only  
**Status:** Approved for Implementation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Zero-Cost Architecture Principles](#2-zero-cost-architecture-principles)
3. [Current State Assessment](#3-current-state-assessment)
4. [Advanced AI-Driven Analytics Architecture](#4-advanced-ai-driven-analytics-architecture)
5. [Sub-Millisecond Execution Infrastructure](#5-sub-millisecond-execution-infrastructure)
6. [Adaptive Risk Management System](#6-adaptive-risk-management-system)
7. [Dynamic Personalization Engine](#7-dynamic-personalization-engine)
8. [Zero-Downtime Reliability Standards](#8-zero-downtime-reliability-standards)
9. [Institutional-Grade Security](#9-institutional-grade-security)
10. [Behavioral UX/Interface Design](#10-behavioral-uxinterface-design)
11. [Free-Tier Resource Allocation](#11-free-tier-resource-allocation)
12. [Data Feed Strategy](#12-data-feed-strategy)
13. [Cost Avoidance Analysis](#13-cost-avoidance-analysis)
14. [Free-Tier Limitations & Workarounds](#14-free-tier-limitations--workarounds)
15. [Phased Implementation Roadmap](#15-phased-implementation-roadmap)
16. [Compliance Guardrails](#16-compliance-guardrails)
17. [Resource Optimization](#17-resource-optimization)
18. [Risk Mitigation Protocols](#18-risk-mitigation-protocols)
19. [Performance Benchmarks](#19-performance-benchmarks)
20. [Security and Compliance Checklist](#20-security-and-compliance-checklist)
21. [Risk Register](#21-risk-register)
22. [Self-Hosting Operations Guide](#22-self-hosting-operations-guide)
23. [Appendix A: Technology Stack Summary](#appendix-a-technology-stack-summary)
24. [Appendix B: Database Schema Evolution](#appendix-b-database-schema-evolution)
25. [Appendix C: API Endpoint Evolution](#appendix-c-api-endpoint-evolution)
26. [Appendix D: Glossary](#appendix-d-glossary)

---

## 1. Executive Summary

### Vision

Transform Vigil from a single-instance, daily-batch market surveillance tool into a **globally dominant, institutional-grade trading intelligence platform** capable of:

- **AI-powered predictive analytics** with regime-aware ensemble models
- **Sub-millisecond signal processing** via async event-driven architecture
- **Real-time portfolio risk management** with dynamic VaR/CVaR calculations
- **Adaptive user experiences** that personalize to trader expertise levels
- **99.9% availability** with self-hosted failover and self-healing infrastructure
- **Regulatory-ready platform** with full audit trails and compliance reporting

### Zero-Cost Mandate

**Every component in this architecture is free, open-source, or self-hosted.** No paid tiers, subscriptions, premium APIs, commercial SaaS, or usage-based billing. This is not a constraint — it is a design principle that forces architectural discipline.

| Principle | Implementation |
|-----------|----------------|
| **Zero Infrastructure Cost** | Oracle Cloud Free Tier (4 ARM cores, 24GB RAM, 200GB storage — permanent) |
| **Zero Data Cost** | yfinance (free, no key) + Alpha Vantage + Finnhub + CoinGecko fallback chain |
| **Zero AI/ML Cost** | PyTorch + scikit-learn (open-source) + Google Colab free tier (GPU training) |
| **Zero Monitoring Cost** | Prometheus + Grafana (self-hosted, open-source) |
| **Zero Communication Cost** | Discord webhooks (free, unlimited history) + self-hosted email |

### Strategic Pillars

| Pillar | Objective | Key Metric |
|--------|-----------|------------|
| **Intelligence** | AI-driven predictive accuracy | >65% directional accuracy |
| **Speed** | Sub-millisecond signal processing | <1ms p99 latency |
| **Reliability** | Zero-downtime operations | 99.9% uptime SLA |
| **Security** | Institutional-grade protection | Full audit trails, encrypted data |
| **Scale** | Multi-asset support | Equities, ETFs, FX, crypto |
| **Compliance** | Regulatory-ready platform | SEC/FINRA audit-ready logging |
| **Cost** | Absolute zero operational cost | $0/month infrastructure |

### Investment Summary

| Phase | Duration | Focus | Expected Outcome |
|-------|----------|-------|------------------|
| Phase 1 | Weeks 1-4 | Foundation | Async migration, DB optimization, security baseline, self-hosted stack |
| Phase 2 | Weeks 5-10 | Intelligence | AI/ML pipeline, predictive models, regime enhancement |
| Phase 3 | Weeks 11-18 | Scale | Distributed architecture, personalization, multi-asset |
| Phase 4 | Weeks 19-28 | Dominance | Advanced features, institutional integrations, compliance |

**Total Infrastructure Cost: $0/month** (see [Cost Avoidance Analysis](#15-cost-avoidance-analysis))

---

## 2. Zero-Cost Architecture Principles

### 2.1 The Zero-Cost Mandate

> **No service, library, or tool shall be introduced into the Vigil architecture if it requires payment at any scale.** This includes "freemium" services where core functionality is gated behind paid tiers, unless the free tier is sufficient for production operation and documented fallbacks exist for when limits are approached.

### 2.2 Core Principles

| # | Principle | Rationale | Enforcement |
|---|-----------|-----------|-------------|
| 1 | **Self-host over SaaS** | Eliminates recurring costs, ensures data sovereignty | All services run on free-tier VMs or local infrastructure |
| 2 | **Open-source over proprietary** | No licensing fees, full auditability, community support | Every dependency must have an OSI-approved license |
| 3 | **Aggressive caching over API calls** | Free data sources have strict rate limits; caching extends usable capacity | Multi-layer caching (L1 in-process, L2 Redis, L3 PostgreSQL) |
| 4 | **Data source rotation over single provider** | No single point of failure; distributes rate limit consumption | Round-robin across yfinance, Alpha Vantage, Finnhub, Twelve Data |
| 5 | **Local storage over cloud storage** | Eliminates S3/GCS costs; 200GB Oracle Cloud storage is sufficient | PostgreSQL for structured data, filesystem for models/artifacts |
| 6 | **Pull over push for data ingestion** | Control request timing to stay within rate limits | Scheduled batch downloads with exponential backoff on 429 responses |
| 7 | **Graceful degradation over hard failure** | Free services have no SLA; system must survive outages | Each component has a documented fallback path |

### 2.3 Free-Tier Service Selection Criteria

When selecting a free-tier service, evaluate against these criteria:

1. **Permanence**: Is the free tier permanent (not a trial)?
2. **Sufficiency**: Are the limits sufficient for production operation?
3. **Overage behavior**: What happens when limits are exceeded? (Must degrade gracefully, not charge)
4. **Data ownership**: Can you export all data if the service disappears?
5. **License**: Is the software open-source (OSI-approved) if self-hosted?

### 2.4 Approved Free-Tier Services

| Category | Service | Free Tier Limits | License | Production-Viable |
|----------|---------|-----------------|---------|-------------------|
| **Hosting** | Oracle Cloud Free Tier | 4 ARM cores, 24GB RAM, 200GB storage | N/A (IaaS) | Yes — permanent free tier |
| **Hosting** | Google Cloud Free Tier | e2-micro, 30GB storage | N/A (IaaS) | Yes — permanent free tier |
| **Hosting** | Render.com Free Tier | 512MB RAM, shared CPU | N/A | Yes — for web services |
| **Hosting** | Fly.io Free Allowance | 3 shared-CPU VMs | N/A | Yes — for small services |
| **CI/CD** | GitHub Actions | 2,000 minutes/month | N/A | Yes — sufficient for CI/CD |
| **Database** | PostgreSQL (self-hosted) | Unlimited (resource-bound) | PostgreSQL License | Yes |
| **Database** | Supabase Free Tier | 500MB PostgreSQL, 1GB bandwidth | N/A | Yes — for small deployments |
| **Cache** | Redis (self-hosted) | Unlimited (resource-bound) | BSD-3 | Yes |
| **Message Queue** | RabbitMQ (self-hosted) | Unlimited (resource-bound) | Apache 2.0 | Yes |
| **Monitoring** | Prometheus (self-hosted) | Unlimited (resource-bound) | Apache 2.0 | Yes |
| **Dashboards** | Grafana OSS (self-hosted) | Unlimited (resource-bound) | AGPL-3.0 | Yes |
| **Logging** | Loki + Grafana (self-hosted) | Unlimited (resource-bound) | AGPL-3.0 | Yes |
| **TLS** | Let's Encrypt + Certbot | Unlimited | N/A | Yes |
| **Secrets** | HashiCorp Vault OSS | Unlimited (resource-bound) | BUSL-1.1 | Yes |
| **Secrets** | python-dotenv | Unlimited | BSD-2 | Yes |
| **ML Training** | Google Colab Free | GPU access, 15hr sessions | N/A | Yes — for model training |
| **ML Training** | Kaggle Notebooks | 30 hours/week GPU | N/A | Yes — for model training |
| **Model Hosting** | Hugging Face Hub | Unlimited public models | N/A | Yes |
| **Charts** | Chart.js | Unlimited | MIT | Yes |
| **Communication** | Discord Webhooks | Unlimited messages | N/A | Yes |
| **Communication** | Slack Free Tier | 10,000 message history | N/A | Yes — for small teams |
| **Email** | SendGrid Free Tier | 100 emails/day | N/A | Yes — for alerts |
| **DNS** | DuckDNS | Free dynamic DNS | N/A | Yes |
| **Uptime** | Uptime Kuma (self-hosted) | Unlimited | MIT | Yes |

---

## 3. Current State Assessment

### 3.1 Existing Architecture

Vigil currently operates as a Flask-based application with:

- **Synchronous request handling** (Flask with thread-per-request model)
- **SQLite database** (single-file, limited concurrency)
- **Daily batch processing** (APScheduler for detection runs)
- **Basic signal detection** (technical indicators, trap detection, MTF alignment)
- **Simple web dashboard** (vanilla HTML/CSS/JS)
- **No caching layer** (every request hits the database)
- **No authentication** (open access)
- **No monitoring** (no metrics, no structured logging)

### 3.2 Identified Gaps

| Gap | Impact | Priority | Zero-Cost Solution |
|-----|--------|----------|-------------------|
| Synchronous Flask | High latency under load | P0 | Migrate to FastAPI (async) |
| SQLite | No concurrent writes, no replication | P0 | Migrate to PostgreSQL (self-hosted) |
| No caching | Every request hits DB | P1 | Add Redis (self-hosted) + in-process cache |
| No authentication | Open access | P0 | Add JWT + API keys (PyJWT) |
| No monitoring | Blind to failures | P1 | Add Prometheus + Grafana |
| No structured logging | Hard to debug | P1 | Add structlog |
| No rate limiting | Vulnerable to abuse | P1 | Add Flask-Limiter + Redis |
| No data source rotation | Single point of failure | P2 | Add yfinance + Alpha Vantage + Finnhub chain |
| No ML pipeline | No predictive capability | P2 | Add PyTorch + scikit-learn |
| No backup strategy | Data loss risk | P1 | Add pg_dump cron jobs |

### 3.3 Migration Priorities

1. **Database migration**: SQLite → PostgreSQL (self-hosted on Oracle Cloud Free Tier)
2. **Async migration**: Flask → FastAPI
3. **Security baseline**: JWT authentication, rate limiting, input validation
4. **Observability**: Prometheus metrics, structured logging, health checks
5. **Caching layer**: Self-hosted Redis with multi-layer strategy
6. **Data pipeline**: Multi-source data ingestion with fallback chains

---

## 4. Advanced AI-Driven Analytics Architecture

### 4.1 ML Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Feature Engineering Pipeline              │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ OHLCV    │  │ Alternative│  │ Sentiment │  │ Order    │   │
│  │ Features │  │ Data      │  │ Analysis  │  │ Flow     │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       └──────────────┴──────────────┴──────────────┘        │
│                          │                                  │
│                          ▼                                  │
│              ┌───────────────────────┐                      │
│              │   Feature Store       │                      │
│              │   (Redis + PostgreSQL)│                      │
│              └───────────┬───────────┘                      │
└──────────────────────────┼──────────────────────────────────┘
                           │
                           ▼
        # Regime features
        features["spy_correlation"] = history["Close"].pct_change().rolling(20).corr(spy_returns)
        features["sector_beta"] = self._compute_sector_beta(ticker, history)
        
        # Sentiment features (if available)
        features["sentiment_score"] = self._get_sentiment_score(ticker)
        
        return features.fillna(0)
```

#### Model Lifecycle Management

```
┌─────────────────────────────────────────────────────────────┐
│                    Model Lifecycle                           │
│                                                             │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐ │
│  │ Train   │───▶│ Validate│───▶│ Deploy  │───▶│ Monitor │ │
│  │         │    │         │    │         │    │         │ │
│  │ - Walk  │    │ - OOS   │    │ - Canary│    │ - Drift │ │
│  │ - Forward│   │ - Metrics│   │ - A/B   │    │ - Perf  │ │
│  │ - CV    │    │ - Back  │    │ - Roll  │    │ - Alert │ │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘ │
│       ▲                                              │     │
│       └────────────── Retrigger ─────────────────────┘     │
│                                                             │
│  Drift Detection Triggers:                                  │
│  - PSI (Population Stability Index) > 0.2                  │
│  - Prediction accuracy drop > 5%                           │
│  - Feature distribution shift (KS test p < 0.01)           │
└─────────────────────────────────────────────────────────────┘
```

#### Ensemble Strategy and Confidence Scoring

```python
# services/ml/ensemble.py
class RegimeAwareEnsemble:
    """
    Combines multiple models with regime-specific weights.
    
    Models: LSTM, Transformer, Statistical, Sentiment
    Regimes: TRENDING, RISK_OFF, SIDEWAYS, VOLATILE
    """
    
    REGIME_WEIGHTS = {
        "TRENDING":  {"lstm": 0.35, "transformer": 0.25, "statistical": 0.25, "sentiment": 0.15},
        "RISK_OFF":  {"lstm": 0.20, "transformer": 0.30, "statistical": 0.35, "sentiment": 0.15},
        "SIDEWAYS":  {"lstm": 0.25, "transformer": 0.25, "statistical": 0.30, "sentiment": 0.20},
        "VOLATILE":  {"lstm": 0.30, "transformer": 0.35, "statistical": 0.20, "sentiment": 0.15},
    }
    
    def predict(self, features: pd.DataFrame, regime: str) -> PredictionResult:
        weights = self.REGIME_WEIGHTS[regime]
        
        predictions = {}
        confidences = {}
        
        for model_name, model in self.models.items():
            pred, conf = model.predict_with_confidence(features)
            predictions[model_name] = pred
            confidences[model_name] = conf
        
        # Weighted ensemble prediction
        ensemble_pred = sum(predictions[m] * weights[m] for m in weights)
        ensemble_conf = sum(confidences[m] * weights[m] for m in weights)
        
        # Model disagreement penalty
        disagreement = np.std(list(predictions.values()))
        adjusted_conf = ensemble_conf * (1 - min(disagreement, 0.5))
        
        return PredictionResult(
            prediction=ensemble_pred,
            confidence=adjusted_conf,
            model_contributions={m: weights[m] * confidences[m] for m in weights},
            disagreement=disagreement
        )
```

### 3.2 Technology Recommendations

| Component | Technology | Justification |
|-----------|------------|---------------|
| ML Framework | PyTorch 2.x | Dynamic computation graphs, strong LSTM/transformer support |
| Model Registry | MLflow | Open-source, experiment tracking, model versioning |
| Feature Store | Redis (self-hosted) + PostgreSQL | Low-latency access + persistent storage, zero cost |
| Training Orchestration | APScheduler + custom DAG runner | Already in stack; no additional cost |
| Inference Serving | FastAPI + ONNX Runtime | Async serving, optimized inference |
| Drift Detection | Evidently AI (OSS core) | Open-source, statistical tests, dashboards |
| Alternative Data | yfinance + Finnhub (free) + SEC EDGAR + FRED | Zero-cost, no API key required or generous free tier |

---

## 4. Sub-Millisecond Execution Infrastructure

### 4.1 Async Migration Architecture

#### Current vs. Target Architecture

```
CURRENT (Synchronous Flask)                    TARGET (Async FastAPI)
─────────────────────────                      ────────────────────────
┌─────────────┐                                ┌─────────────────────┐
│   Flask     │                                │     FastAPI         │
│  (sync)     │                                │  (async/await)      │
│             │                                │                     │
│  Thread-per-│                                │  Event loop         │
│  request    │                                │  Non-blocking I/O   │
│             │                                │                     │
│  p99: 200ms │                                │  p99: <5ms          │
└──────┬──────┘                                └──────────┬──────────┘
       │                                                  │
       ▼                                                  ▼
┌─────────────┐                                ┌─────────────────────┐
│  psycopg2   │                                │  asyncpg            │
│  (sync)     │                                │  (async)            │
└─────────────┘                                └─────────────────────┘
```

#### Migration Path

```python
# api_async.py — FastAPI migration example
from fastapi import FastAPI, Depends, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncpg
import asyncio

app = FastAPI(title="Vigil API", version="2.0.0")

# Connection pool managed at application level
@app.on_event("startup")
async def startup():
    app.state.db_pool = await asyncpg.create_pool(
        dsn=os.environ["DATABASE_URL"],
        min_size=5,
        max_size=20,
        command_timeout=30
    )

@app.on_event("shutdown")
async def shutdown():
    await app.state.db_pool.close()

async def get_db():
    async with app.state.db_pool.acquire() as conn:
        yield conn

@app.get("/alerts")
async def get_alerts(
    ticker: str | None = None,
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    db = Depends(get_db)
):
    """Async alert retrieval with connection pooling."""
    query = """
        SELECT * FROM alerts 
        WHERE ($1::text IS NULL OR ticker = $1)
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
    """
    rows = await db.fetch(query, ticker, limit, offset)
    return [dict(r) for r in rows]

@app.get("/alerts/stream")
async def alert_stream(websocket: WebSocket):
    """WebSocket stream for real-time alerts."""
    await websocket.accept()
    try:
        while True:
            # Listen to event bus for new alerts
            alert = await event_bus.subscribe("new_alert")
            await websocket.send_json(alert)
    except WebSocketDisconnect:
        event_bus.unsubscribe("new_alert")
```

### 4.2 In-Memory Data Grid (Redis)

#### Multi-Layer Caching Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    Cache Hierarchy                           │
│                                                             │
│  L1: Application Memory (in-process)                        │
│  - TTL: 5 seconds                                           │
│  - Use: Regime state, current signals, user session         │
│  - Size: <100MB per instance                                │
│                                                             │
│  L2: Redis Cache (shared)                                   │
│  - TTL: 1 minute - 24 hours (by data type)                  │
│  - Use: Correlation matrices, computed features, predictions│
│  - Size: 1-5GB                                              │
│                                                             │
│  L3: PostgreSQL (persistent)                                │
│  - TTL: Permanent                                           │
│  - Use: Historical alerts, backtest results, audit logs     │
│  - Size: Unlimited                                          │
│                                                             │
│  Cache Invalidation:                                        │
│  - Write-through for critical data                          │
│  - Cache-aside for read-heavy data                          │
│  - Pub/sub invalidation for distributed consistency         │
└─────────────────────────────────────────────────────────────┘
```

#### Redis Data Structures

```python
# services/cache.py
class RedisCache:
    """
    Multi-layer caching with Redis.
    
    Key patterns:
    - vigil:regime:{ticker} — Current regime (TTL: 1h)
    - vigil:signal:{ticker}:{date} — Signal data (TTL: 24h)
    - vigil:correlation:{date} — Correlation matrix (TTL: 24h)
    - vigil:prediction:{ticker}:{model} — ML predictions (TTL: 1h)
    - vigil:user:{user_id}:prefs — User preferences (TTL: 7d)
    """
    
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=1,
            socket_connect_timeout=1,
            retry_on_timeout=True
        )
    
    async def get_or_compute(
        self,
        key: str,
        compute_fn: Callable,
        ttl: int = 300
    ) -> Any:
        """Cache-aside pattern with async compute."""
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)
        
        result = await compute_fn()
        await self.redis.setex(key, ttl, json.dumps(result))
        return result
    
    async def invalidate_pattern(self, pattern: str):
        """Invalidate all keys matching pattern."""
        async for key in self.redis.scan_iter(match=pattern):
            await self.redis.delete(key)
```

### 4.3 PostgreSQL Query Optimization

#### Connection Pool Configuration

```python
# database.py — Async connection pool
import asyncpg

class DatabasePool:
    """
    Async PostgreSQL connection pool.
    
    Sizing guidelines:
    - min_size = CPU cores × 2
    - max_size = (CPU cores × 2) + disk_spindles
    - For cloud: max_size = 20 per instance
    - Total across instances < max_connections × 0.8
    """
    
    def __init__(self, dsn: str, min_size: int = 5, max_size: int = 20):
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self.pool: asyncpg.Pool | None = None
    
    async def initialize(self):
        self.pool = await asyncpg.create_pool(
            dsn=self.dsn,
            min_size=self.min_size,
            max_size=self.max_size,
            command_timeout=30,
            server_settings={
                "jit": "off",  # Disable JIT for OLTP workloads
                "statement_timeout": "30000"  # 30s timeout
            }
        )
    
    async def execute(self, query: str, *args) -> list[asyncpg.Record]:
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)
```

#### Index Strategy

```sql
-- Critical indexes for query optimization
CREATE INDEX CONCURRENTLY idx_alerts_ticker_date ON alerts(ticker, date DESC);
CREATE INDEX CONCURRENTLY idx_alerts_edge_score ON alerts(edge_score DESC) WHERE edge_score >= 7.0;
CREATE INDEX CONCURRENTLY idx_alerts_regime ON alerts(regime, created_at DESC);
CREATE INDEX CONCURRENTLY idx_alerts_action ON alerts(action, created_at DESC);

-- Partial indexes for common queries
CREATE INDEX CONCURRENTLY idx_alerts_enter_signals 
    ON alerts(ticker, date DESC) 
    WHERE action = 'ENTER' AND edge_score >= 7.0;

-- Covering index for dashboard queries
CREATE INDEX CONCURRENTLY idx_alerts_dashboard 
    ON alerts(created_at DESC) 
    INCLUDE (ticker, signal_type, edge_score, action, summary);

-- Correlation matrix queries
CREATE INDEX CONCURRENTLY idx_correlation_computed ON correlation_matrix(computed_at DESC);
```

### 4.4 CQRS Pattern for Read/Write Separation

```
┌─────────────────────────────────────────────────────────────┐
│                    CQRS Architecture                         │
│                                                             │
│  Command Side (Writes)          Query Side (Reads)          │
│  ────────────────────           ──────────────────          │
│                                                             │
│  ┌─────────────┐                ┌─────────────────────┐    │
│  │ Command     │                │ Query               │    │
│  │ Handlers    │                │ Handlers            │    │
│  │             │                │                     │    │
│  │ - SaveAlert │                │ - GetAlerts         │    │
│  │ - UpdateRegime│              │ - GetRegime         │    │
│  │ - RunBacktest│               │ - GetBacktestResults│    │
│  └──────┬──────┘                └──────────┬──────────┘    │
│         │                                  │               │
│         ▼                                  ▼               │
│  ┌─────────────┐                ┌─────────────────────┐    │
│  │ Write       │                │ Read                │    │
│  │ Database    │────Event──────▶│ Database            │    │
│  │ (Primary)   │   Stream       │ (Replica/Cache)     │    │
│  └─────────────┘                └─────────────────────┘    │
│                                                             │
│  Event Stream: PostgreSQL Logical Replication or Debezium   │
└─────────────────────────────────────────────────────────────┘
```

### 4.5 Technology Recommendations

| Component | Technology | Justification |
|-----------|------------|---------------|
| Web Framework | FastAPI | Native async, automatic OpenAPI docs, high performance |
| WebSocket | FastAPI WebSocket + Socket.IO | Real-time push with fallback |
| Async DB Driver | asyncpg | Fastest async PostgreSQL driver |
| In-Memory Cache | Redis 7.x (self-hosted) | Data structures, pub/sub, Streams — zero cost |
| Connection Pool | PgBouncer (self-hosted) | Transaction-level pooling for high concurrency — zero cost |
| Event Streaming | Redis Streams (Phase 1-3), RabbitMQ (Phase 4) | Ordered event delivery — both open-source |
| API Gateway | nginx + OpenResty (self-hosted) | Rate limiting, SSL termination, load balancing — zero cost |

---

## 5. Adaptive Risk Management System

### 5.1 Real-Time VaR/CVaR Calculations

#### Risk Metrics Architecture

```python
# services/portfolio_risk.py
class PortfolioRiskManager:
    """
    Real-time portfolio risk management.
    
    Metrics:
    - Value at Risk (VaR) — Parametric and Historical
    - Conditional VaR (CVaR/Expected Shortfall)
    - Maximum Drawdown
    - Correlation Breakdown Detection
    - Concentration Risk
    """
    
    def __init__(self, confidence: float = 0.95, lookback: int = 252):
        self.confidence = confidence
        self.lookback = lookback
    
    async def compute_var(self, positions: dict[str, float], 
                          returns: pd.DataFrame) -> RiskMetrics:
        """
        Compute portfolio VaR using multiple methods.
        
        Returns:
        - Parametric VaR (variance-covariance)
        - Historical VaR (empirical distribution)
        - Monte Carlo VaR (simulation)
        """
        weights = np.array([positions.get(t, 0) for t in returns.columns])
        
        # Parametric VaR
        cov_matrix = returns.cov() * 252  # Annualized
        portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
        parametric_var = portfolio_vol * norm.ppf(self.confidence)
        
        # Historical VaR
        portfolio_returns = returns @ weights
        historical_var = np.percentile(portfolio_returns, (1 - self.confidence) * 100)
        
        # Monte Carlo VaR
        mc_var = await self._monte_carlo_var(returns, weights, n_simulations=10000)
        
        return RiskMetrics(
            parametric_var=parametric_var,
            historical_var=historical_var,
            monte_carlo_var=mc_var,
            portfolio_volatility=portfolio_vol
        )
    
    async def compute_cvar(self, returns: pd.DataFrame, 
                           weights: np.ndarray) -> float:
        """
        Conditional VaR (Expected Shortfall).
        
        Average loss beyond VaR threshold.
        """
        portfolio_returns = returns @ weights
        var_threshold = np.percentile(portfolio_returns, (1 - self.confidence) * 100)
        cvar = portfolio_returns[portfolio_returns <= var_threshold].mean()
        return cvar
```

### 5.2 Dynamic Position Sizing

```python
# services/position_sizing.py
class DynamicPositionSizer:
    """
    Position sizing based on volatility regime and conviction.
    
    Methods:
    - Kelly Criterion (fractional)
    - Volatility-targeted sizing
    - Risk parity allocation
    - Maximum drawdown constraints
    """
    
    def __init__(self, max_position_pct: float = 0.10, 
                 max_portfolio_risk: float = 0.02):
        self.max_position_pct = max_position_pct
        self.max_portfolio_risk = max_portfolio_risk
    
    def compute_size(self, 
                     edge_score: float,
                     volatility: float,
                     regime: str,
                     account_value: float,
                     current_positions: dict[str, float]) -> PositionSizing:
        """
        Compute optimal position size.
        
        Factors:
        - Edge score (conviction)
        - Current volatility
        - Market regime
        - Portfolio constraints
        """
        # Base Kelly fraction
        win_rate = self._edge_to_win_rate(edge_score)
        avg_win_loss_ratio = 1.5  # Historical average
        kelly_f = (win_rate * avg_win_loss_ratio - (1 - win_rate)) / avg_win_loss_ratio
        
        # Fractional Kelly (25% to reduce variance)
        fractional_kelly = kelly_f * 0.25
        
        # Volatility adjustment
        vol_multiplier = self._volatility_multiplier(volatility, regime)
        
        # Regime adjustment
        regime_multiplier = {
            "TRENDING": 1.0,
            "RISK_OFF": 0.5,
            "SIDEWAYS": 0.7,
            "VOLATILE": 0.6
        }.get(regime, 0.8)
        
        # Final position size
        raw_size = fractional_kelly * vol_multiplier * regime_multiplier
        position_size = min(raw_size, self.max_position_pct)
        
        # Portfolio risk check
        portfolio_risk = self._compute_portfolio_risk(current_positions, position_size)
        if portfolio_risk > self.max_portfolio_risk:
            position_size *= self.max_portfolio_risk / portfolio_risk
        
        return PositionSizing(
            size_pct=position_size,
            dollar_amount=account_value * position_size,
            kelly_fraction=fractional_kelly,
            risk_contribution=portfolio_risk
        )
```

### 5.3 Circuit Breakers and Stress Testing

```
┌─────────────────────────────────────────────────────────────┐
│                    Circuit Breaker System                    │
│                                                             │
│  Level 1: Position-Level                                   │
│  ─────────────────────                                      │
│  Trigger: Single position loss > 2% of portfolio            │
│  Action: Reduce position by 50%, alert risk manager         │
│                                                             │
│  Level 2: Portfolio-Level                                   │
│  ────────────────────                                       │
│  Trigger: Daily portfolio loss > 5%                         │
│  Action: Halt new entries, reduce all positions by 25%      │
│                                                             │
│  Level 3: System-Level                                      │
│  ─────────────────                                          │
│  Trigger: Daily portfolio loss > 10% OR VaR breach > 3x     │
│  Action: Close all positions, disable trading, alert team   │
│                                                             │
│  Recovery Protocol:                                         │
│  1. Root cause analysis required                            │
│  2. Manual override by risk manager                         │
│  3. Gradual position rebuilding (25% per day)               │
│  4. Post-incident review within 24 hours                    │
└─────────────────────────────────────────────────────────────┘
```

#### Stress Testing Engine

```python
# services/stress_test.py
class StressTestEngine:
    """
    Scenario analysis and stress testing.
    
    Scenarios:
    - Historical: 2008 crash, 2020 COVID, 2022 rate hikes
    - Hypothetical: Rate shock, volatility spike, correlation breakdown
    - Custom: User-defined scenarios
    """
    
    HISTORICAL_SCENARIOS = {
        "2008_financial_crisis": {"SPY": -0.55, "TLT": 0.20, "GLD": 0.05},
        "2020_covid_crash": {"SPY": -0.34, "TLT": 0.15, "GLD": 0.10},
        "2022_rate_hikes": {"SPY": -0.25, "TLT": -0.15, "GLD": -0.03},
        "2000_dotcom_bust": {"SPY": -0.49, "TLT": 0.10, "GLD": -0.05},
    }
    
    def run_stress_test(self, 
                        positions: dict[str, float],
                        scenario: str | dict) -> StressTestResult:
        """Run portfolio through stress scenario."""
        shocks = self.HISTORICAL_SCENARIOS.get(scenario, scenario)
        
        pnl = {}
        total_pnl = 0
        for ticker, weight in positions.items():
            shock = shocks.get(ticker, shocks.get("SPY", -0.10))
            pnl[ticker] = weight * shock
            total_pnl += pnl[ticker]
        
        return StressTestResult(
            scenario=scenario,
            total_pnl=total_pnl,
            position_pnl=pnl,
            var_breach=abs(total_pnl) > self.current_var
        )
```

### 5.4 Technology Recommendations

| Component | Technology | Justification |
|-----------|------------|---------------|
| Risk Calculations | NumPy/SciPy | Vectorized operations, statistical functions — open-source |
| Monte Carlo | NumPy + Numba | JIT-compiled simulations — open-source |
| Stress Testing | Custom Python engine | Scenario-specific logic — zero cost |
| Real-Time Monitoring | Prometheus + Grafana (self-hosted) | Metrics collection and alerting — open-source |
| Position Management | PostgreSQL with row-level locking | ACID compliance for position updates — open-source |

---

## 6. Dynamic Personalization Engine

### 6.1 User Behavior Tracking and Preference Learning

```
┌─────────────────────────────────────────────────────────────┐
│                    Personalization Architecture              │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              User Profile Store                     │   │
│  │                                                     │   │
│  │  - Expertise level (novice/intermediate/pro)        │   │
│  │  - Preferred assets and sectors                     │   │
│  │  - Risk tolerance (conservative/moderate/aggressive)│   │
│  │  - Notification preferences                         │   │
│  │  - UI customization settings                        │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                  │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │              Behavior Tracking                      │   │
│  │                                                     │   │
│  │  - Feature usage patterns                           │   │
│  │  - Alert interaction (dismiss, act, ignore)         │   │
│  │  - Time spent on views                              │   │
│  │  - Search and filter patterns                       │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                  │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │              Preference Learning                    │   │
│  │                                                     │   │
│  │  - Collaborative filtering for similar users        │   │
│  │  - Reinforcement learning for UI adaptation         │   │
│  │  - Automatic threshold tuning based on feedback     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Adaptive UI for Novice vs Professional Users

```python
# services/personalization.py
class PersonalizationEngine:
    """
    Dynamic UI adaptation based on user profile.
    
    User Tiers:
    - Novice: Simplified views, educational tooltips, guided workflows
    - Intermediate: Standard features, customizable dashboards
    - Professional: Advanced analytics, API access, custom alerts
    """
    
    UI_CONFIGS = {
        "novice": {
            "dashboard": "simplified",
            "metrics_shown": ["edge_score", "action", "summary"],
            "tooltips_enabled": True,
            "advanced_signals_hidden": True,
            "max_alerts_per_day": 10,
            "default_timeframe": "daily",
        },
        "intermediate": {
            "dashboard": "standard",
            "metrics_shown": ["edge_score", "action", "summary", "mtf_alignment", "regime"],
            "tooltips_enabled": False,
            "advanced_signals_hidden": False,
            "max_alerts_per_day": 50,
            "default_timeframe": "daily",
        },
        "professional": {
            "dashboard": "advanced",
            "metrics_shown": ["all"],
            "tooltips_enabled": False,
            "advanced_signals_hidden": False,
            "max_alerts_per_day": None,
            "default_timeframe": "intraday",
            "api_access": True,
            "custom_strategies": True,
        }
    }
    
    def get_ui_config(self, user_id: str) -> dict:
        profile = self._get_user_profile(user_id)
        base_config = self.UI_CONFIGS[profile.expertise_level]
        
        # Apply learned preferences
        if profile.preferred_metrics:
            base_config["metrics_shown"] = profile.preferred_metrics
        
        return base_config
```

### 6.3 Strategy Templating and Sharing System

```python
# services/strategy_templates.py
class StrategyTemplateEngine:
    """
    Strategy templating system for sharing and reuse.
    
    Components:
    - Signal configuration (thresholds, filters)
    - Risk parameters (position sizing, stop loss)
    - Alert routing (channels, thresholds)
    - Backtest configuration
    """
    
    def create_template(self, user_id: str, config: StrategyConfig) -> Template:
        """Create a strategy template from current configuration."""
        template = Template(
            id=uuid4(),
            user_id=user_id,
            name=config.name,
            description=config.description,
            signal_config=config.signal_config,
            risk_config=config.risk_config,
            alert_config=config.alert_config,
            is_public=config.is_public,
            created_at=datetime.now(timezone.utc)
        )
        self._save_template(template)
        return template
    
    def apply_template(self, user_id: str, template_id: str) -> AppliedTemplate:
        """Apply a strategy template to user account."""
        template = self._get_template(template_id)
        
        # Validate template compatibility
        self._validate_compatibility(template, user_id)
        
        # Apply configuration
        self._apply_signal_config(user_id, template.signal_config)
        self._apply_risk_config(user_id, template.risk_config)
        self._apply_alert_config(user_id, template.alert_config)
        
        return AppliedTemplate(template_id=template_id, applied_at=datetime.now(timezone.utc))
```

### 6.4 Technology Recommendations

| Component | Technology | Justification |
|-----------|------------|---------------|
| User Profile Store | PostgreSQL (JSONB) | Flexible schema, ACID compliance — open-source |
| Behavior Tracking | Redis Streams (self-hosted) | High-throughput event capture — zero cost |
| Preference Learning | Scikit-learn | Collaborative filtering, clustering — open-source |
| UI Adaptation | React + Unleash (self-hosted OSS) | Dynamic component rendering — Unleash OSS for feature flags |
| Template Storage | PostgreSQL | Structured data with relationships — open-source |

---

## 7. Zero-Downtime Reliability Standards

### 7.1 Blue-Green Deployment Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    Blue-Green Deployment                     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Load Balancer                       │   │
│  │                                                     │   │
│  │  Active:  Blue (v1.0)  ←── serving traffic          │   │
│  │  Standby: Green (v2.0) ←── deploying, health checks │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                  │
│  Switch Criteria:                                         │
│  1. Green passes /health/ready                            │
│  2. All integration tests pass                            │
│  3. Smoke tests on critical paths                         │
│  4. Database migrations applied successfully              │
│                                                             │
│  Switch Process:                                          │
│  1. Update LB to route 10% to Green (canary)              │
│  2. Monitor error rates for 5 minutes                     │
│  3. If stable, route 50% to Green                         │
│  4. Monitor for 5 more minutes                            │
│  5. If stable, route 100% to Green                        │
│  6. Blue becomes standby                                  │
│  7. Drain Blue connections gracefully                     │
│                                                             │
│  Rollback:                                                │
│  1. If error rate > 1% during canary, immediate rollback  │
│  2. LB switches back to Blue in <10 seconds               │
│  3. Alert sent to engineering team                        │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Database Migration Patterns (Alembic)

```python
# migrations/versions/005_ai_ml_infrastructure.py
"""Add AI/ML infrastructure tables

Revision ID: 005
Revises: 004
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Model registry
    op.create_table(
        'ml_models',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('model_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), default='staging'),
        sa.Column('metrics', postgresql.JSONB),
        sa.Column('training_data_hash', sa.String(64)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('deployed_at', sa.DateTime),
        sa.UniqueConstraint('name', 'version')
    )
    
    # Feature store
    op.create_table(
        'feature_values',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('ticker', sa.String(10), nullable=False),
        sa.Column('feature_name', sa.String(100), nullable=False),
        sa.Column('feature_value', postgresql.JSONB),
        sa.Column('computed_at', sa.DateTime, nullable=False),
        sa.Column('expires_at', sa.DateTime),
        sa.Index('idx_feature_lookup', 'ticker', 'feature_name', 'computed_at')
    )
    
    # Predictions
    op.create_table(
        'predictions',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('ticker', sa.String(10), nullable=False),
        sa.Column('model_id', sa.Integer, sa.ForeignKey('ml_models.id')),
        sa.Column('prediction', postgresql.JSONB),
        sa.Column('confidence', sa.Float),
        sa.Column('predicted_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('horizon', sa.String(20)),
        sa.Index('idx_predictions_ticker', 'ticker', 'predicted_at')
    )

def downgrade():
    op.drop_table('predictions')
    op.drop_table('feature_values')
    op.drop_table('ml_models')
```

### 7.3 Health Check and Self-Healing Infrastructure

```python
# services/health.py
class HealthChecker:
    """
    Comprehensive health checking with self-healing capabilities.
    
    Checks:
    - Database connectivity and query latency
    - Redis connectivity and memory usage
    - Detection engine freshness
    - API response times
    - System resources (CPU, memory, disk)
    """
    
    async def check_readiness(self) -> HealthStatus:
        """Readiness check — all dependencies must be healthy."""
        checks = {}
        
        # Database
        try:
            start = time.time()
            await self.db.execute("SELECT 1")
            latency = time.time() - start
            checks["database"] = HealthCheck(
                status="healthy" if latency < 1.0 else "degraded",
                latency_ms=latency * 1000
            )
        except Exception as e:
            checks["database"] = HealthCheck(status="unhealthy", error=str(e))
        
        # Redis
        try:
            await self.redis.ping()
            checks["redis"] = HealthCheck(status="healthy")
        except Exception as e:
            checks["redis"] = HealthCheck(status="degraded", error=str(e))
        
        # Detection freshness
        last_run = await self.get_last_detection_time()
        staleness = (datetime.now(timezone.utc) - last_run).total_seconds()
        checks["detection"] = HealthCheck(
            status="healthy" if staleness < 90000 else "stale",
            staleness_seconds=staleness
        )
        
        all_healthy = all(c.status in ("healthy", "degraded") for c in checks.values())
        
        return HealthStatus(
            status="ready" if all_healthy else "not_ready",
            checks=checks
        )
    
    async def self_heal(self) -> SelfHealResult:
        """
        Automatic remediation actions.
        
        Actions:
        - Restart stale detection (no run in >25 hours)
        - Clear Redis if memory > 90%
        - Reconnect database pool if connections exhausted
        """
        actions = []
        
        if self._detection_stale():
            actions.append(HealAction(
                action="restart_detection",
                reason="Detection run stale (>25 hours)"
            ))
            await self.trigger_detection()
        
        if await self._redis_memory_high():
            actions.append(HealAction(
                action="flush_expired_cache",
                reason="Redis memory > 90%"
            ))
            await self.redis.execute_command("MEMORY PURGE")
        
        return SelfHealResult(actions=actions)
```

### 7.4 Multi-Region Failover Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Multi-Region Architecture                 │
│                                                             │
│  Region: US-East (Primary)          Region: EU-West (DR)    │
│  ─────────────────────────          ────────────────────    │
│                                                             │
│  ┌─────────────┐                    ┌─────────────┐        │
│  │  Vigil × 3  │                    │  Vigil × 2  │        │
│  │  (active)   │                    │  (standby)  │        │
│  └──────┬──────┘                    └──────┬──────┘        │
│         │                                  │               │
│  ┌──────▼──────┐                    ┌──────▼──────┐        │
│  │  PostgreSQL │◄───Replication────│  PostgreSQL │        │
│  │  (primary)  │    (async)        │  (replica)  │        │
│  └──────┬──────┘                    └──────┬──────┘        │
│         │                                  │               │
│  ┌──────▼──────┐                    ┌──────▼──────┐        │
│  │    Redis    │◄───Replication────│    Redis    │        │
│  │  (primary)  │    (async)        │  (replica)  │        │
│  └─────────────┘                    └─────────────┘        │
│                                                             │
│  Failover Triggers:                                        │
│  - Primary region unavailable for > 5 minutes              │
│  - Database replication lag > 30 seconds                   │
│  - Manual failover by operations team                      │
│                                                             │
│  RTO: < 15 minutes                                         │
│  RPO: < 5 minutes (async replication lag)                  │
└─────────────────────────────────────────────────────────────┘
```

### 7.5 Technology Recommendations

| Component | Technology | Justification |
|-----------|------------|---------------|
| Migrations | Alembic | SQLAlchemy integration, version control — open-source |
| Health Checks | Custom + Docker healthchecks | Flexible, container-native — zero cost |
| Load Balancing | nginx (self-hosted) | Proven, configurable — open-source |
| Multi-Region | PostgreSQL logical replication + pglogical | Async replication between self-hosted instances — zero cost |
| Deployment | GitHub Actions + Docker Compose on Oracle Cloud Free Tier | CI/CD automation — 2,000 free minutes/month |

---

## 8. Institutional-Grade Security

### 8.1 API Key Rotation and Management

```
┌─────────────────────────────────────────────────────────────┐
│                    API Key Lifecycle                         │
│                                                             │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐ │
│  │ Generate│───▶│ Distribute│──▶│ Rotate  │───▶│ Revoke  │ │
│  │         │    │         │    │         │    │         │ │
│  │ - UUID  │    │ - Secure│    │ - 90 day│    │ - Immed │ │
│  │ - Hash  │    │ - Channel│   │ - Auto  │    │ - Immed │ │
│  │ - Store │    │ - Env var│   │ - Notify│    │ - Audit │ │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘ │
│                                                             │
│  Key Storage:                                              │
│  - Hashed with bcrypt (never store plaintext)              │
│  - Salt per key                                            │
│  - Rate-limited validation (prevent brute force)           │
│                                                             │
│  Rotation Policy:                                          │
│  - Automatic rotation every 90 days                        │
│  - 7-day overlap period (old + new both valid)             │
│  - Notification 14 days before expiry                      │
│  - Immediate rotation on suspected compromise              │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Request Signing and Replay Attack Prevention

```python
# services/security.py
class RequestSigner:
    """
    HMAC-based request signing to prevent tampering and replay attacks.
    
    Flow:
    1. Client creates request payload
    2. Client computes signature: HMAC-SHA256(payload + timestamp + nonce, secret)
    3. Client sends: payload, timestamp, nonce, signature
    4. Server verifies:
       - Timestamp within 5-minute window (replay prevention)
       - Not seen before (nonce deduplication)
       - Signature matches
    """
    
    MAX_TIMESTAMP_DRIFT = 300  # 5 minutes
    NONCE_TTL = 300  # 5 minutes
    
    def verify_request(self, 
                       payload: bytes,
                       timestamp: int,
                       nonce: str,
                       signature: str,
                       secret: str) -> bool:
        # 1. Check timestamp
        if abs(time.time() - timestamp) > self.MAX_TIMESTAMP_DRIFT:
            raise SecurityError("Request timestamp expired")
        
        # 2. Check nonce (replay prevention)
        if self._nonce_exists(nonce):
            raise SecurityError("Request nonce already used")
        self._record_nonce(nonce, timestamp)
        
        # 3. Verify signature
        expected = hmac.new(
            secret.encode(),
            f"{payload.decode()}:{timestamp}:{nonce}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected):
            raise SecurityError("Invalid request signature")
        
        return True
```

### 8.3 Audit Logging and Compliance Trails

```python
# services/audit.py
class AuditLogger:
    """
    Immutable audit logging for compliance.
    
    Logged Events:
    - Authentication (login, logout, failed attempts)
    - Authorization (permission changes, role changes)
    - Data access (alert queries, watchlist changes)
    - Configuration changes (threshold updates, risk parameter changes)
    - Trading actions (signal generation, position changes)
    - System events (deployments, migrations, health failures)
    """
    
    async def log(self, event: AuditEvent):
        """
        Log audit event to immutable append-only store.
        
        Properties:
        - Immutable (no updates or deletes)
        - Timestamped (UTC, synchronized)
        - User-attributed (who did what)
        - Context-rich (IP, user agent, request ID)
        """
        record = AuditRecord(
            timestamp=datetime.now(timezone.utc),
            event_type=event.type,
            user_id=event.user_id,
            action=event.action,
            resource=event.resource,
            details=event.details,
            ip_address=event.ip_address,
            user_agent=event.user_agent,
            request_id=event.request_id
        )
        
        # Append to PostgreSQL (append-only table)
        await self.db.execute("""
            INSERT INTO audit_log 
            (timestamp, event_type, user_id, action, resource, details, ip_address, user_agent, request_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, record.timestamp, record.event_type, record.user_id, 
            record.action, record.resource, record.details,
            record.ip_address, record.user_agent, record.request_id)
```

### 8.4 Data Encryption

| Data Type | At Rest | In Transit |
|-----------|---------|------------|
| Database | AES-256 (LUKS/dm-crypt on Oracle Cloud volume) | TLS 1.3 (Let's Encrypt) |
| Redis | AES-256 (LUKS on volume) + Redis ACL | TLS 1.3 (stunnel or Redis TLS) |
| API Keys | bcrypt hash | TLS 1.3 |
| Secrets | HashiCorp Vault OSS (self-hosted) + python-dotenv | TLS 1.3 |
| Audit Logs | AES-256 (LUKS on volume) | TLS 1.3 |
| Backups | AES-256 (gpg encrypted) | TLS 1.3 (rsync over SSH) |

### 8.5 Technology Recommendations

| Component | Technology | Justification |
|-----------|------------|---------------|
| Rate Limiting | Flask-Limiter + Redis (self-hosted) | Distributed rate limiting — zero cost |
| Authentication | JWT + API keys (PyJWT) | Stateless, scalable — open-source |
| Request Signing | HMAC-SHA256 | Industry standard — zero cost |
| Audit Logging | PostgreSQL (append-only) | Immutable, queryable — open-source |
| Secrets Management | HashiCorp Vault OSS (self-hosted) | Auditable, zero cost |
| TLS | Let's Encrypt + Certbot | Automated certificate management — free |

---

## 9. Behavioral UX/Interface Design

### 9.1 Zero-Friction Onboarding Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Onboarding Flow                           │
│                                                             │
│  Step 1: Account Creation (30 seconds)                      │
│  ─────────────────────────────────                          │
│  - Email + password OR OAuth (Google, GitHub)               │
│  - No credit card required                                  │
│  - Immediate access to dashboard                            │
│                                                             │
│  Step 2: Expertise Assessment (1 minute)                    │
│  ─────────────────────────────────────                      │
│  - 3-question quiz to determine experience level            │
│  - Auto-configures UI complexity                            │
│  - Can be changed later in settings                         │
│                                                             │
│  Step 3: Watchlist Setup (2 minutes)                        │
│  ─────────────────────────────                              │
│  - Suggest popular tickers based on sector interest         │
│  - Import from CSV or broker statement                      │
│  - Start with default watchlist (SPY, QQQ, IWM)             │
│                                                             │
│  Step 4: First Alert (automatic)                            │
│  ───────────────────────────────                            │
│  - System runs detection on watchlist                       │
│  - User sees first alerts within 60 seconds                 │
│  - Interactive tutorial explains each metric                │
│                                                             │
│  Total Time to First Value: < 5 minutes                     │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 Progressive Disclosure for Complex Features

```
┌─────────────────────────────────────────────────────────────┐
│                    Progressive Disclosure                    │
│                                                             │
│  Level 1: Basic (Novice)                                    │
│  ─────────────────────                                      │
│  Shows: Ticker, Action (ENTER/WAIT/AVOID), Edge Score       │
│  Hides: MTF alignment, trap conviction, regime details      │
│                                                             │
│  Level 2: Standard (Intermediate)                           │
│  ────────────────────────                                   │
│  Shows: + Signal type, regime, MTF alignment, summary       │
│  Hides: Advanced signal components, position sizing         │
│                                                             │
│  Level 3: Advanced (Professional)                           │
│  ────────────────────────                                   │
│  Shows: All metrics, signal breakdown, position sizing      │
│  Hides: Nothing                                             │
│                                                             │
│  Interaction Pattern:                                       │
│  - Click "Show more" to expand alert details                │
│  - Hover tooltips explain each metric                       │
│  - "Learn more" links to documentation                      │
└─────────────────────────────────────────────────────────────┘
```

### 9.3 Real-Time Visualization Requirements

| Component | Technology | Purpose |
|-----------|------------|---------|
| Candlestick Charts | Lightweight Charts (TradingView, free) | Price visualization |
| Heatmaps | D3.js | Sector/correlation visualization — open-source |
| Order Flow | Custom Canvas rendering | Volume profile, order book — zero cost |
| Real-time Updates | WebSocket + vanilla JS | Live data streaming — zero cost |
| Animations | CSS transitions + vanilla JS | Smooth transitions — zero cost |

### 9.4 Accessibility Standards (WCAG 2.1 AA)

| Requirement | Implementation |
|-------------|----------------|
| Color contrast | Minimum 4.5:1 for text, 3:1 for UI elements |
| Keyboard navigation | All interactive elements tab-accessible |
| Screen reader support | ARIA labels, semantic HTML |
| Focus indicators | Visible focus rings on all interactive elements |
| Reduced motion | Respect `prefers-reduced-motion` media query |
| Font scaling | Support up to 200% zoom without breaking layout |

### 9.5 Technology Recommendations

| Component | Technology | Justification |
|-----------|------------|---------------|
| Frontend Framework | Vanilla JS (current) or Vue.js 3 (OSS) | Zero migration cost; Vue.js if reactivity needed |
| State Management | Vanilla JS module pattern or Pinia (Vue) | Lightweight, zero cost |
| Charts | TradingView Lightweight Charts (free) | Financial charting standard — free license |
| Styling | Vanilla CSS (current) or Tailwind CSS | Utility-first, responsive — open-source |
| Accessibility | axe-core (OSS) | Automated a11y testing — open-source |
| Mobile | Responsive PWA | Single codebase, installable — zero cost |

---

## 10. Phased Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4)

**Objective:** Infrastructure hardening, async migration, database optimization

| Task | Owner | Dependencies | Success Criteria |
|------|-------|--------------|------------------|
| Remove competing scheduler | Backend | None | Single detection run per cycle |
| Migrate to FastAPI | Backend | None | All endpoints functional, p99 < 50ms |
| Implement async PostgreSQL | Backend | FastAPI migration | Connection pooling, async queries |
| Add Alembic migrations | Backend | Database access | Schema versioning operational |
| Implement input validation | Backend | Marshmallow | All endpoints validated |
| Add rate limiting | Backend | Redis | Per-endpoint rate limits active |
| Add structured logging | Backend | None | JSON logs, request IDs |
| Add Prometheus metrics | Backend | None | /metrics endpoint operational |
| Health check endpoints | Backend | None | /health, /health/ready, /health/live |
| Batch yfinance downloads | Backend | None | Detection < 15s for 50 tickers |
| Redis caching layer | Backend | Redis deployment | L2 cache operational |
| WebSocket push alerts | Frontend + Backend | SocketIO | Real-time alert delivery < 1s |

**Milestone:** Production-ready async API with observability

### Phase 2: Intelligence (Weeks 5-10)

**Objective:** AI/ML pipeline, predictive models, regime detection enhancement

| Task | Owner | Dependencies | Success Criteria |
|------|-------|--------------|------------------|
| ML infrastructure setup | ML Engineer | Phase 1 complete | PyTorch, MLflow operational |
| Feature engineering pipeline | ML Engineer | Data sources available | 50+ features computed |
| LSTM price forecaster | ML Engineer | Feature pipeline | >55% directional accuracy |
| Transformer regime classifier | ML Engineer | Historical data | Regime prediction >70% accuracy |
| Regime-aware ensemble | ML Engineer | Individual models | Ensemble >60% accuracy |
| Model drift detection | ML Engineer | MLflow | Automated retraining triggers |
| Dynamic regime engine | Backend | ML models | Adaptive thresholds operational |
| Backtest API endpoints | Backend | Backtest engine | Run backtests via API |
| Walk-forward optimization | ML Engineer | Backtest engine | Parameter optimization pipeline |

**Milestone:** AI-powered predictive analytics with regime awareness

### Phase 3: Scale (Weeks 11-18)

**Objective:** Distributed architecture, multi-asset support, personalization

| Task | Owner | Dependencies | Success Criteria |
|------|-------|--------------|------------------|
| Distributed locking | Backend | Redis | Single detection run across instances |
| Multi-instance deployment | DevOps | Distributed locking | Horizontal scaling operational |
| CQRS implementation | Backend | Phase 2 complete | Read/write separation |
| User profile system | Backend | Database | User preferences stored |
| Behavior tracking | Backend | Redis Streams | Event capture operational |
| Adaptive UI | Frontend | User profiles | Novice/Pro UI modes |
| Strategy templating | Backend + Frontend | User profiles | Template creation/sharing |
| Multi-asset support | Backend | Data sources | Equities, ETFs, FX, crypto |
| Correlation engine | Backend | Multi-asset data | Daily correlation matrix |
| Portfolio risk metrics | Backend | Correlation engine | VaR/CVaR computed |

**Milestone:** Scalable, personalized, multi-asset platform

### Phase 4: Dominance (Weeks 19-28)

**Objective:** Advanced features, institutional integrations, compliance certifications

| Task | Owner | Dependencies | Success Criteria |
|------|-------|--------------|------------------|
| Multi-region deployment | DevOps | Phase 3 complete | Active-passive failover |
| SOC 2 Type II audit | Security | All security controls | Certification achieved |
| SEC/FINRA compliance | Legal + Engineering | Audit logs | Regulatory reporting ready |
| Broker API integrations | Backend | Compliance | Automated execution |
| Advanced order types | Backend | Broker integration | Limit, stop, OCO orders |
| Institutional reporting | Backend + Frontend | All data | PDF/Excel report generation |
| API marketplace | Backend + Frontend | Phase 3 complete | Third-party strategy sharing |
| Mobile app | Mobile Team | API ready | iOS/Android native apps |
| Performance optimization | Backend | All features | p99 < 5ms, 10K concurrent users |

**Milestone:** Institutional-grade, globally dominant platform

---

## 11. Compliance Guardrails

### 11.1 SEC/FINRA Regulatory Considerations

| Regulation | Requirement | Implementation |
|------------|-------------|----------------|
| SEC Rule 15c3-5 (Market Access) | Risk controls before order entry | Pre-trade risk checks, circuit breakers |
| FINRA Rule 3110 (Supervision) | Supervisory procedures | Audit logs, approval workflows |
| SEC Regulation SCI | Systems compliance for market infrastructure | High availability, disaster recovery |
| FINRA Rule 4511 (Books and Records) | Record retention | 7-year audit log retention |
| SEC Rule 17a-4 | Electronic record storage | WORM storage for audit logs |

### 11.2 Data Privacy

| Regulation | Requirement | Implementation |
|------------|-------------|----------------|
| GDPR (EU users) | Right to access, delete, portability | Data export, deletion APIs |
| CCPA (California) | Right to know, delete | Privacy dashboard, deletion workflows |
| Data Minimization | Collect only necessary data | Configurable data retention policies |
| Consent Management | Explicit consent for data processing | Cookie consent, preference center |

### 11.3 Trading Restrictions and Kill Switches

```
┌─────────────────────────────────────────────────────────────┐
│                    Kill Switch Architecture                  │
│                                                             │
│  Levels of Kill Switch:                                     │
│                                                             │
│  Level 1: Ticker-Level                                      │
│  ───────────────────                                        │
│  Trigger: Single ticker anomaly (flash crash, halt)         │
│  Action: Suspend alerts for ticker, notify risk team        │
│  Recovery: Manual review required before resuming           │
│                                                             │
│  Level 2: Strategy-Level                                    │
│  ─────────────────────                                      │
│  Trigger: Strategy drawdown > threshold                     │
│  Action: Disable strategy, close positions                  │
│  Recovery: Backtest validation + manual approval            │
│                                                             │
│  Level 3: System-Level                                      │
│  ─────────────────                                          │
│  Trigger: System-wide anomaly, regulatory event             │
│  Action: Halt all trading, close all positions              │
│  Recovery: Full incident review + regulatory notification   │
│                                                             │
│  Kill Switch Activation:                                    │
│  - Automated (threshold-based)                              │
│  - Manual (risk manager override)                           │
│  - Regulatory (external directive)                          │
│                                                             │
│  Response Time: < 100ms for automated kill switch           │
└─────────────────────────────────────────────────────────────┘
```

## 12. Data Feed Strategy

### 12.1 Multi-Source Data Ingestion with Intelligent Fallback

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Data Source Fallback Chain                            │
│                                                                         │
│  Priority 1: yfinance (Yahoo Finance)                                   │
│  ──────────────────────────────────────                                 │
│  - Cost: $0, no API key required                                        │
│  - Coverage: Global equities, ETFs, FX, crypto, indices                 │
│  - Frequency: Daily (end-of-day) or 1-minute intraday (60-day window)   │
│  - Rate Limit: ~2,000 requests/hour (unofficial, may vary)              │
│  - Fallback Trigger: HTTP 429, connection timeout, data format change   │
│                                                                         │
│  Priority 2: Alpha Vantage                                              │
│  ─────────────────                                                      │
│  - Cost: $0, free API key required                                      │
│  - Coverage: US equities, ETFs, FX, crypto                              │
│  - Frequency: Daily, intraday (15-min delayed for free tier)            │
│  - Rate Limit: 25 requests/day, 5 requests/minute                       │
│  - Fallback Trigger: Daily quota exhausted, HTTP 429                    │
│                                                                         │
│  Priority 3: Finnhub                                                    │
│  ─────────                                                              │
│  - Cost: $0, free API key required                                      │
│  - Coverage: US equities, ETFs, crypto, forex                           │
│  - Frequency: Real-time (WebSocket), daily (REST)                       │
│  - Rate Limit: 60 requests/minute (REST), 30 WebSocket connections      │
│  - Fallback Trigger: Rate limit hit, WebSocket disconnect               │
│                                                                         │
│  Priority 4: Twelve Data                                                │
│  ─────────────────                                                      │
│  - Cost: $0, free API key required                                      │
│  - Coverage: 50,000+ symbols, global equities, ETFs, FX, crypto         │
│  - Frequency: Daily, 1-minute intraday                                  │
│  - Rate Limit: 800 requests/day, 8 requests/minute                      │
│  - Fallback Trigger: Daily quota exhausted                              │
│                                                                         │
│  Priority 5: CoinGecko (Crypto Only)                                    │
│  ─────────────────────────                                              │
│  - Cost: $0, no API key required                                        │
│  - Coverage: 10,000+ cryptocurrencies                                   │
│  - Frequency: Real-time via WebSocket, REST polling                     │
│  - Rate Limit: 10-30 requests/min (no key), 50/sec (demo key)           │
│  - Fallback Trigger: Rate limit hit                                     │
│                                                                         │
│  Priority 6: FRED (Macroeconomic Data)                                  │
│  ─────────────────────────────────                                      │
│  - Cost: $0, free API key required                                      │
│  - Coverage: 800,000+ economic time series                              │
│  - Frequency: Daily/weekly/monthly (varies by series)                   │
│  - Rate Limit: 120 requests/minute                                      │
│  - Fallback Trigger: Rate limit hit                                     │
│                                                                         │
│  Priority 7: SEC EDGAR (Filings)                                        │
│  ─────────────────────                                                  │
│  - Cost: $0, no API key required                                        │
│  - Coverage: All SEC filings (10-K, 10-Q, 8-K, etc.)                    │
│  - Frequency: Real-time as filed                                        │
│  - Rate Limit: 10 requests/second (fair use)                            │
│  - Fallback Trigger: Rate limit hit                                     │
│                                                                         │
│  Caching Strategy:                                                      │
│  ─────────────────                                                      │
│  - All responses cached in PostgreSQL with TTL based on data type       │
│  - Daily OHLCV: cached for 24 hours                                     │
│  - Intraday: cached for 1 minute                                        │
│  - Fundamentals: cached for 7 days                                      │
│  - Macroeconomic: cached for 30 days                                    │
│  - Historical data: cached permanently (never re-fetched)               │
└─────────────────────────────────────────────────────────────────────────┘
```

### 12.2 Data Source Rotation Algorithm

```python
# services/data_rotator.py
class DataSourceRotator:
    """
    Round-robin data source selection with health tracking.
    
    Ensures no single free-tier source is exhausted by distributing
    requests across all available sources.
    """
    
    SOURCES = {
        "yfinance": {"priority": 0, "daily_limit": 2000, "cost": 0},
        "alphavantage": {"priority": 1, "daily_limit": 25, "cost": 0},
        "finnhub": {"priority": 2, "daily_limit": 86400, "cost": 0},  # 60/min
        "twelvedata": {"priority": 3, "daily_limit": 800, "cost": 0},
        "coingecko": {"priority": 4, "daily_limit": 14400, "cost": 0},  # 10/min
    }
    
    def __init__(self):
        self.usage = {s: 0 for s in self.SOURCES}
        self.health = {s: True for s in self.SOURCES}
    
    def get_next_source(self, data_type: str) -> str:
        """
        Select next data source based on priority, usage, and health.
        
        Algorithm:
        1. Filter sources that haven't exceeded daily limit
        2. Filter sources that are healthy
        3. Sort by priority
        4. Return highest priority available source
        """
        available = [
            (name, config) for name, config in self.SOURCES.items()
            if self.usage[name] < config["daily_limit"]
            and self.health[name]
            and self._supports_type(name, data_type)
        ]
        
        if not available:
            raise DataExhaustionError(
                f"All data sources exhausted for {data_type}. "
                f"Usage: {self.usage}"
            )
        
        # Sort by priority, return highest
        available.sort(key=lambda x: x[1]["priority"])
        source = available[0][0]
        self.usage[source] += 1
        return source
    
    def record_failure(self, source: str):
        """Mark source as unhealthy after consecutive failures."""
        self.health[source] = False
        # Auto-recovery after 1 hour
        asyncio.get_event_loop().call_later(3600, self._recover_source, source)
    
    def _recover_source(self, source: str):
        """Attempt to recover a failed source."""
        self.health[source] = True
        self.usage[source] = max(0, self.usage[source] - 10)  # Penalty
```

### 12.3 Historical Data Preloading Strategy

To minimize API calls during production operation:

1. **Preload 2 years of daily OHLCV** for all watchlist tickers during setup
2. **Store in PostgreSQL** with `ON CONFLICT DO NOTHING` for idempotent loading
3. **Daily incremental updates** — only fetch the latest day's data
4. **Weekly full sync** — verify data completeness, fill gaps from alternate sources
5. **Data quality checks** — detect and flag gaps, anomalies, split-adjusted prices

---

## 13. Cost Avoidance Analysis

### 13.1 Traditional Architecture Cost Comparison

| Component | Traditional Cost/Month | Zero-Cost Alternative | Savings |
|-----------|----------------------|----------------------|---------|
| Compute (AWS EC2 c6i.xlarge × 3) | $450 | Oracle Cloud Free Tier (4 ARM cores) | $450 |
| Database (RDS PostgreSQL db.r6g.large) | $300 | Self-hosted PostgreSQL on Oracle Cloud | $300 |
| Cache (ElastiCache Redis cache.t3.medium) | $50 | Self-hosted Redis on same VM | $50 |
| Storage (S3 + EBS) | $100 | 200GB Oracle Cloud block volume | $100 |
| Data Feeds (Polygon.io starter) | $200 | yfinance + Alpha Vantage + Finnhub | $200 |
| Monitoring (Datadog/New Relic) | $150 | Prometheus + Grafana (self-hosted) | $150 |
| Logging (ELK Cloud) | $75 | Loki + Grafana (self-hosted) | $75 |
| TLS Certificates | $20 | Let's Encrypt | $20 |
| Secrets Management (AWS Secrets Manager) | $40 | HashiCorp Vault OSS | $40 |
| CI/CD (CircleCI/Jenkins Cloud) | $50 | GitHub Actions (free tier) | $50 |
| Load Balancer (AWS ALB) | $25 | nginx (self-hosted) | $25 |
| **Total** | **$1,460/month** | **$0/month** | **$1,460/month** |

### 13.2 Annual Savings

| Category | Annual Savings |
|----------|---------------|
| Infrastructure | $10,200 |
| Data Feeds | $2,400 |
| Monitoring & Logging | $2,700 |
| Security & Compliance | $720 |
| Development Tools | $600 |
| **Total Annual Savings** | **$16,620** |

### 13.3 Trade-Offs Accepted

| Trade-Off | Impact | Mitigation |
|-----------|--------|------------|
| Lower compute resources (4 cores vs 12) | Longer backtest runs | Optimize with Numba, parallelize across free-tier VMs |
| No managed database | Manual backup/restore required | Automated pg_dump cron jobs, encrypted backups to GitHub |
| No managed Redis | Single point of failure on same VM | Run Redis as systemd service with auto-restart |
| Free data source rate limits | Slower data refresh | Aggressive caching, source rotation, preloading |
| No managed load balancer | Manual nginx configuration | Documented nginx configs, health check scripts |
| No commercial support | Community support only | Active open-source communities, comprehensive docs |

---

## 14. Free-Tier Limitations & Workarounds

### 14.1 Oracle Cloud Free Tier

| Limitation | Impact | Workaround |
|------------|--------|------------|
| 4 ARM cores, 24GB RAM total | Limited horizontal scaling | Run all services on single VM; use Docker Compose |
| 200GB block storage | Limited data retention | Compress historical data; archive to GitHub (git-lfs) |
| No auto-scaling | Fixed capacity | Design for peak load within resource constraints |
| Single region (free tier) | No geographic redundancy | Accept single-region; implement local failover |
| No managed services | All services self-managed | Use Docker Compose for easy service management |

### 14.2 GitHub Actions Free Tier

| Limitation | Impact | Workaround |
|------------|--------|------------|
| 2,000 minutes/month | Limited CI/CD pipeline runs | Optimize pipelines; run only on PR, not every commit |
| 6-hour job timeout | Long backtests may timeout | Split backtests into parallel jobs; use external compute |
| Shared runners | Variable performance | Use self-hosted runner on Oracle Cloud VM |

### 14.3 Free Data Sources

| Source | Limitation | Workaround |
|--------|------------|------------|
| yfinance | Unofficial API, may break | Cache all data; have 4 fallback sources ready |
| Alpha Vantage | 25 requests/day | Use only for critical real-time; cache everything |
| Finnhub | 60 requests/min | Batch requests; use WebSocket for streaming |
| Twelve Data | 800 requests/day | Use as secondary source; cache aggressively |
| CoinGecko | Rate-limited without key | Register for free demo key (50 req/sec) |

### 14.4 Google Colab Free Tier

| Limitation | Impact | Workaround |
|------------|--------|------------|
| 15-hour session limit | Long training runs interrupted | Save checkpoints every hour; resume from checkpoint |
| GPU not guaranteed | Training may run on CPU | Schedule training during off-peak hours; use Kaggle as backup |
| 15GB RAM limit | Large datasets may not fit | Use data generators; reduce batch size; use Kaggle (30GB) |
| Idle timeout (90 min) | Notebook disconnects | Use Colab Pro alternatives: Kaggle (30 hrs/week free) |

### 14.5 Slack Free Tier

| Limitation | Impact | Workaround |
|------------|--------|------------|
| 10,000 message history | Old alerts lost | Use Discord webhooks (unlimited history) as primary |
| Limited app integrations | Fewer automation options | Use webhooks + custom bots instead of Slack apps |

---

## 15. Phased Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4)

**Objective:** Infrastructure hardening, async migration, database optimization, self-hosted stack deployment

| Task | Owner | Dependencies | Success Criteria |
|------|-------|--------------|------------------|
| Provision Oracle Cloud Free Tier VM | DevOps | Oracle Cloud account | VM running Ubuntu 22.04, 4 ARM cores, 24GB RAM |
| Install Docker + Docker Compose | DevOps | VM provisioned | Docker Compose v2 operational |
| Deploy PostgreSQL via Docker Compose | DevOps | Docker installed | PostgreSQL 15 running, persistent volume |
| Deploy Redis via Docker Compose | DevOps | Docker installed | Redis 7 running, persistent volume |
| Deploy nginx via Docker Compose | DevOps | Docker installed | nginx reverse proxy with Let's Encrypt TLS |
| Deploy Prometheus + Grafana | DevOps | Docker installed | Metrics collection and dashboards operational |
| Deploy Loki for logging | DevOps | Docker installed | Structured log aggregation operational |
| Migrate SQLite → PostgreSQL | Backend | PostgreSQL running | All data migrated, schema validated |
| Remove competing scheduler | Backend | None | Single detection run per cycle |
| Migrate to FastAPI | Backend | None | All endpoints functional, p99 < 50ms |
| Implement async PostgreSQL | Backend | FastAPI migration | Connection pooling, async queries |
| Add Alembic migrations | Backend | Database access | Schema versioning operational |
| Implement input validation | Backend | Marshmallow | All endpoints validated |
| Add rate limiting | Backend | Redis | Per-endpoint rate limits active |
| Add structured logging | Backend | None | JSON logs, request IDs |
| Add Prometheus metrics | Backend | None | /metrics endpoint operational |
| Health check endpoints | Backend | None | /health, /health/ready, /health/live |
| Batch yfinance downloads | Backend | None | Detection < 15s for 50 tickers |
| Redis caching layer | Backend | Redis deployment | L2 cache operational |
| WebSocket push alerts | Frontend + Backend | SocketIO | Real-time alert delivery < 1s |
| Setup pg_dump cron backups | DevOps | PostgreSQL running | Daily encrypted backups to local storage |
| Setup Uptime Kuma monitoring | DevOps | Docker installed | Health monitoring with alerting |

**Milestone:** Production-ready async API with full observability stack, zero cost

### Phase 2: Intelligence (Weeks 5-10)

**Objective:** AI/ML pipeline, predictive models, regime detection enhancement

| Task | Owner | Dependencies | Success Criteria |
|------|-------|--------------|------------------|
| ML infrastructure setup | ML Engineer | Phase 1 complete | PyTorch, scikit-learn, MLflow operational |
| Feature engineering pipeline | ML Engineer | Data sources available | 50+ features computed, stored in PostgreSQL |
| LSTM price forecaster | ML Engineer | Feature pipeline | >55% directional accuracy (Google Colab training) |
| Transformer regime classifier | ML Engineer | Historical data | Regime prediction >70% accuracy |
| Regime-aware ensemble | ML Engineer | Individual models | Ensemble >60% accuracy |
| Model drift detection | ML Engineer | MLflow | Automated retraining triggers (PSI > 0.2) |
| Dynamic regime engine | Backend | ML models | Adaptive thresholds operational |
| Backtest API endpoints | Backend | Backtest engine | Run backtests via API |
| Walk-forward optimization | ML Engineer | Backtest engine | Parameter optimization pipeline |
| Data source rotator | Backend | Multiple API keys | Round-robin across all free sources |
| Historical data preloader | Backend | Data sources | 2 years of OHLCV preloaded for watchlist |

**Milestone:** AI-powered predictive analytics with regime awareness, zero cost

### Phase 3: Scale (Weeks 11-18)

**Objective:** Distributed architecture, multi-asset support, personalization

| Task | Owner | Dependencies | Success Criteria |
|------|-------|--------------|------------------|
| Distributed locking | Backend | Redis | Single detection run across instances |
| Multi-instance deployment | DevOps | Distributed locking | Horizontal scaling on additional free-tier VMs |
| CQRS implementation | Backend | Phase 2 complete | Read/write separation |
| User profile system | Backend | Database | User preferences stored |
| Behavior tracking | Backend | Redis Streams | Event capture operational |
| Adaptive UI | Frontend | User profiles | Novice/Pro UI modes |
| Strategy templating | Backend + Frontend | User profiles | Template creation/sharing |
| Multi-asset support | Backend | Data sources | Equities, ETFs, FX, crypto |
| Correlation engine | Backend | Multi-asset data | Daily correlation matrix |
| Portfolio risk metrics | Backend | Correlation engine | VaR/CVaR computed |
| Discord webhook alerts | Backend | Discord server | Unlimited alert delivery via webhooks |

**Milestone:** Scalable, personalized, multi-asset platform, zero cost

### Phase 4: Dominance (Weeks 19-28)

**Objective:** Advanced features, institutional integrations, compliance certifications

| Task | Owner | Dependencies | Success Criteria |
|------|-------|--------------|------------------|
| Multi-VM deployment | DevOps | Phase 3 complete | Active-passive failover across free-tier VMs |
| PostgreSQL logical replication | DevOps | Multi-VM | Async replication between instances |
| SEC/FINRA compliance | Legal + Engineering | Audit logs | Regulatory reporting ready |
| Advanced order types | Backend | Broker integration | Limit, stop, OCO orders (paper trading) |
| Institutional reporting | Backend + Frontend | All data | PDF/Excel report generation |
| API marketplace | Backend + Frontend | Phase 3 complete | Third-party strategy sharing |
| Performance optimization | Backend | All features | p99 < 5ms, 10K concurrent users |
| OWASP ZAP security scan | Security | All endpoints | Zero critical vulnerabilities |
| Community bug bounty | Security | OWASP ZAP clean | External security validation |

**Milestone:** Institutional-grade, globally dominant platform, zero cost

---

## 16. Compliance Guardrails

### 16.1 SEC/FINRA Regulatory Considerations

| Regulation | Requirement | Implementation |
|------------|-------------|----------------|
| SEC Rule 15c3-5 (Market Access) | Risk controls before order entry | Pre-trade risk checks, circuit breakers |
| FINRA Rule 3110 (Supervision) | Supervisory procedures | Audit logs, approval workflows |
| SEC Regulation SCI | Systems compliance for market infrastructure | High availability, disaster recovery |
| FINRA Rule 4511 (Books and Records) | Record retention | 7-year audit log retention |
| SEC Rule 17a-4 | Electronic record storage | WORM storage for audit logs |

### 16.2 Data Privacy

| Regulation | Requirement | Implementation |
|------------|-------------|----------------|
| GDPR (EU users) | Right to access, delete, portability | Data export, deletion APIs |
| CCPA (California) | Right to know, delete | Privacy dashboard, deletion workflows |
| Data Minimization | Collect only necessary data | Configurable data retention policies |
| Consent Management | Explicit consent for data processing | Cookie consent, preference center |

### 16.3 Trading Restrictions and Kill Switches

```
┌─────────────────────────────────────────────────────────────┐
│                    Kill Switch Architecture                  │
│                                                             │
│  Levels of Kill Switch:                                     │
│                                                             │
│  Level 1: Ticker-Level                                      │
│  ───────────────────                                        │
│  Trigger: Single ticker anomaly (flash crash, halt)         │
│  Action: Suspend alerts for ticker, notify risk team        │
│  Recovery: Manual review required before resuming           │
│                                                             │
│  Level 2: Strategy-Level                                    │
│  ─────────────────────                                      │
│  Trigger: Strategy drawdown > threshold                     │
│  Action: Disable strategy, close positions                  │
│  Recovery: Backtest validation + manual approval            │
│                                                             │
│  Level 3: System-Level                                      │
│  ─────────────────                                          │
│  Trigger: System-wide anomaly, regulatory event             │
│  Action: Halt all trading, close all positions              │
│  Recovery: Full incident review + regulatory notification   │
│                                                             │
│  Kill Switch Activation:                                    │
│  - Automated (threshold-based)                              │
│  - Manual (risk manager override)                           │
│  - Regulatory (external directive)                          │
│                                                             │
│  Response Time: < 100ms for automated kill switch           │
└─────────────────────────────────────────────────────────────┘
```

---

## 17. Resource Optimization

### 17.1 Zero-Cost Cloud Architecture

| Resource | Strategy | Cost | Free-Tier Provider |
|----------|----------|------|-------------------|
| Compute | Oracle Cloud Free Tier (4 ARM cores, 24GB RAM) | $0 | Oracle Cloud — permanent free tier |
| Database | Self-hosted PostgreSQL on Oracle Cloud volume | $0 | Included in Oracle Cloud Free Tier |
| Cache | Self-hosted Redis on same VM | $0 | Open-source, runs on Oracle Cloud |
| Storage | 200GB block volume (Oracle Cloud) + gpg-encrypted backups to GitHub | $0 | Included in Oracle Cloud Free Tier |
| Data Feeds | yfinance (no key) + Alpha Vantage (25/day) + Finnhub (60/min) + CoinGecko | $0 | All free tiers, no payment required |
| Monitoring | Prometheus + Grafana (self-hosted on Oracle Cloud) | $0 | Open-source |
| CI/CD | GitHub Actions (2,000 min/month) | $0 | GitHub Free |
| TLS | Let's Encrypt + Certbot | $0 | Free certificates |
| DNS | DuckDNS or Oracle Cloud DNS | $0 | Free dynamic DNS |
| **Total** | | **$0/month** | All components free, open-source, or self-hosted |

### 17.2 Multi-Layer Caching Strategy

| Layer | Technology | TTL | Hit Rate Target |
|-------|------------|-----|-----------------|
| L1 (In-process) | Python dict + TTL | 5s | 40% |
| L2 (Redis) | Redis Hash/JSON | 1m-24h | 80% |
| L3 (Database) | PostgreSQL | Permanent | 100% |

### 17.3 Compute Optimization for Backtesting

| Optimization | Technique | Speedup |
|--------------|-----------|---------|
| Vectorization | NumPy/Pandas operations | 10-100x |
| Parallelization | Multiprocessing for parameter grids | Nx cores |
| JIT Compilation | Numba for hot loops | 5-50x |
| Caching | Cache intermediate results | 2-5x |
| GPU Acceleration | CuPy for matrix operations | 10-100x |

### 17.4 API Rate Limit Management

| Data Source | Rate Limit | Strategy |
|-------------|------------|----------|
| yfinance | ~2000 requests/hour (unofficial) | Batch downloads, cache 24h in PostgreSQL, exponential backoff on 429 |
| Alpha Vantage | 25 requests/day, 5/min (free) | Rotate with other sources, cache all responses, store historical data locally |
| Finnhub | 60 requests/min (free) | Use for real-time supplement, cache aggressively |
| CoinGecko | 10-30 requests/min (free, no key) | Primary crypto data source, no rate limit enforcement needed |
| Twelve Data | 800 requests/day (free) | Fallback for equities, cache all responses |
| FRED | 120 requests/min (free) | Macroeconomic data, cache daily |
| SEC EDGAR | 10 requests/sec (fair use) | Filings data, cache permanently |
| Internal API | 200/day, 50/hour (default) | Per-user rate limits, Redis-backed, Flask-Limiter |

---

## 18. Risk Mitigation Protocols

### 18.1 Failure Mode Analysis

| Failure Mode | Likelihood | Impact | Detection | Mitigation |
|--------------|------------|--------|-----------|------------|
| Data source outage | High | High | Health check, missing data alert | Fallback data source, cached data |
| Database connection exhaustion | Medium | High | Connection pool metrics | PgBouncer, connection timeout |
| Redis failure | Medium | Medium | Redis health check | Graceful degradation to DB |
| Model drift | High | Medium | PSI monitoring, accuracy tracking | Automated retraining |
| API abuse | Medium | Medium | Rate limit hits, error spikes | Rate limiting, IP blocking |
| Deployment failure | Low | High | Health check, error rate | Blue-green rollback |
| Security breach | Low | High | Anomaly detection, audit logs | Incident response plan |

### 18.2 Data Quality Monitoring

```python
# services/data_quality.py
class DataQualityMonitor:
    """
    Monitor data quality for all data sources.
    
    Checks:
    - Completeness: Missing values, gaps in time series
    - Timeliness: Data freshness, update frequency
    - Accuracy: Out-of-range values, statistical anomalies
    - Consistency: Cross-source validation
    """
    
    async def check_quality(self, ticker: str, data: pd.DataFrame) -> QualityReport:
        issues = []
        
        # Completeness
        missing_pct = data.isnull().sum().sum() / data.size
        if missing_pct > 0.05:
            issues.append(QualityIssue(
                type="missing_data",
                severity="high",
                detail=f"{missing_pct:.1%} missing values"
            ))
        
        # Timeliness
        last_timestamp = data.index.max()
        staleness = datetime.now(timezone.utc) - last_timestamp
        if staleness > timedelta(hours=24):
            issues.append(QualityIssue(
                type="stale_data",
                severity="critical",
                detail=f"Data {staleness.days} days old"
            ))
        
        # Accuracy
        price_anomalies = self._detect_price_anomalies(data)
        if price_anomalies:
            issues.append(QualityIssue(
                type="price_anomaly",
                severity="high",
                detail=f"{len(price_anomalies)} price anomalies detected"
            ))
        
        return QualityReport(ticker=ticker, issues=issues, passed=len(issues) == 0)
```

### 18.3 Model Risk Management

| Risk | Mitigation |
|------|------------|
| Overfitting | Walk-forward validation, out-of-sample testing |
| Data snooping | Bonferroni correction, deflated Sharpe ratio |
| Regime change | Regime-aware models, frequent retraining |
| Feature decay | Feature importance monitoring, automatic refresh |
| Model correlation | Ensemble diversity, decorrelation penalties |

### 18.4 Incident Response Procedures

```
┌─────────────────────────────────────────────────────────────┐
│                    Incident Response                         │
│                                                             │
│  Severity Levels:                                           │
│  ────────────────                                           │
│  SEV-1 (Critical): System down, data breach, trading loss   │
│  SEV-2 (High): Degraded performance, partial outage         │
│  SEV-3 (Medium): Non-critical bug, minor degradation        │
│  SEV-4 (Low): Cosmetic issue, enhancement request           │
│                                                             │
│  Response Times:                                            │
│  ──────────────                                             │
│  SEV-1: Acknowledge < 5 min, Resolve < 1 hour               │
│  SEV-2: Acknowledge < 15 min, Resolve < 4 hours             │
│  SEV-3: Acknowledge < 1 hour, Resolve < 24 hours            │
│  SEV-4: Acknowledge < 4 hours, Resolve < 1 week             │
│                                                             │
│  Response Process:                                          │
│  ────────────────                                           │
│  1. Detect (automated alert or user report)                 │
│  2. Acknowledge (on-call engineer)                          │
│  3. Triage (assess severity, impact)                        │
│  4. Mitigate (apply fix or workaround)                      │
│  5. Resolve (verify fix, monitor)                           │
│  6. Post-mortem (within 48 hours for SEV-1/2)               │
│  7. Document (incident report, action items)                │
└─────────────────────────────────────────────────────────────┘
```

---

## 19. Performance Benchmarks

### 19.1 Target Metrics

| Metric | Current | Phase 1 Target | Phase 4 Target | Measurement |
|--------|---------|----------------|----------------|-------------|
| Detection run time (50 tickers) | 30-60s | <15s | <5s | End-to-end timing |
| API p50 latency | Unknown | <20ms | <5ms | Prometheus histogram |
| API p95 latency | Unknown | <100ms | <20ms | Prometheus histogram |
| API p99 latency | Unknown | <200ms | <50ms | Prometheus histogram |
| Alert delivery latency | 60s (polling) | <1s | <100ms | WebSocket push |
| WebSocket connections/instance | 0 | 500 | 10,000 | Load test |
| Concurrent users | 1 | 100 | 10,000 | Load test |
| Memory usage (idle) | ~100MB | <200MB | <500MB | psutil |
| Error rate | Unknown | <0.1% | <0.01% | Prometheus counter |
| Alert delivery success rate | Unknown | >99% | >99.99% | Delivery tracking |
| Uptime | ~99% | 99.9% | 99.99% | Health monitoring |
| Model accuracy (directional) | N/A | >55% | >65% | Backtest validation |
| VaR backtest exceptions | N/A | <2.5% | <1% | Risk monitoring |

### 19.2 Load Test Scenarios

| Scenario | Target | Tool |
|----------|--------|------|
| GET /alerts (100 req/s) | p95 < 50ms | Locust |
| WebSocket connections (1000 concurrent) | <1% disconnect rate | Artillery |
| Detection run under load (50 tickers) | <15s | Custom benchmark |
| Concurrent backtest runs (10 parallel) | Complete within 5 min each | Custom benchmark |
| Alert delivery burst (100 alerts/min) | 100% delivery, <1s latency | Custom benchmark |

---

## 20. Security and Compliance Checklist

### 20.1 Security Controls

| Control | Status | Implementation |
|---------|--------|----------------|
| Input validation | ✅ Planned | Marshmallow schemas on all endpoints |
| Rate limiting | ✅ Planned | Flask-Limiter + Redis (self-hosted) |
| JWT authentication | ✅ Planned | PyJWT with rotation |
| API key management | ✅ Planned | Hashed storage, 90-day rotation |
| Request signing | ✅ Planned | HMAC-SHA256 with nonce |
| CORS restrictions | ✅ Planned | Explicit origin allowlist |
| TLS encryption | ✅ Planned | TLS 1.3 via Let's Encrypt + Certbot |
| Database encryption | ✅ Planned | LUKS/dm-crypt on Oracle Cloud block volume |
| Secret management | ✅ Planned | HashiCorp Vault OSS (self-hosted) + python-dotenv |
| Audit logging | ✅ Planned | Append-only PostgreSQL |
| Vulnerability scanning | ✅ Planned | GitHub Dependabot (free) + safety (pip) |
| Penetration testing | ⬜ Planned | Community bug bounty + OWASP ZAP (free) |

### 20.2 Compliance Requirements

| Requirement | Status | Notes |
|-------------|--------|-------|
| GDPR data rights | ⬜ Planned | Export, delete, access APIs |
| CCPA compliance | ⬜ Planned | Privacy dashboard |
| SEC record retention | ⬜ Planned | 7-year audit log retention |
| FINRA supervision | ⬜ Planned | Approval workflows |
| SOC 2 Type II | ⬜ Planned | Year 2 target |
| PCI DSS | N/A | No card data processed |
| HIPAA | N/A | No health data processed |

---

## 21. Risk Register

| Risk | Likelihood | Impact | Mitigation | Owner |
|------|------------|--------|------------|-------|
| yfinance API changes/rate limits | High | High | Add Finnhub/Twelve Data fallback, circuit breaker | Backend |
| PostgreSQL connection exhaustion | Medium | High | PgBouncer, strict pool sizing, monitoring | DevOps |
| WebSocket connection drops | Medium | Medium | Client reconnection with backoff, heartbeat | Frontend |
| Redis dependency failure | Medium | Medium | Graceful degradation to in-memory cache | Backend |
| Backtest overfitting | High | Medium | Walk-forward optimization, OOS testing | ML Engineer |
| Alert fatigue from false positives | Medium | Medium | Adaptive thresholds, deduplication, user config | Backend |
| Security breach via API | Low | High | JWT, rate limiting, input validation, audits | Security |
| Schema migration failure | Low | High | Alembic with rollback, staging testing | Backend |
| Detection run timeout | Medium | Medium | Timeout, alert on failure, partial results | Backend |
| Memory leak in long-running process | Low | High | psutil monitoring, gunicorn worker recycling | DevOps |
| Model drift undetected | Medium | High | PSI monitoring, accuracy tracking, alerts | ML Engineer |
| Regulatory changes | Medium | High | Legal review, compliance monitoring | Legal |
| Key personnel dependency | Low | High | Documentation, cross-training, runbooks | Management |
| Data source concentration | Medium | High | Multiple data providers, fallback sources | Backend |
| Cloud provider outage | Low | High | Multi-VM deployment, DR plan | DevOps |

---

## 22. Self-Hosting Operations Guide

### 22.1 Oracle Cloud Free Tier Setup

#### Step 1: Create Oracle Cloud Account
1. Go to https://www.oracle.com/cloud/free/
2. Sign up with email and credit card (required for identity verification, never charged)
3. Select region closest to your users (e.g., us-ashburn-1 for US East)
4. Wait for account activation (usually immediate)

#### Step 2: Create Always Free VM
1. Navigate to Compute > Instances > Create Instance
2. Select "Always Free Eligible" image (Ubuntu 22.04 or Oracle Linux 8)
3. Select "VM.Standard.A1.Flex" shape (Ampere ARM, 4 OCPUs, 24GB RAM)
4. Add SSH key (generate with `ssh-keygen -t ed25519`)
5. Attach to VCN (default compartment)
6. Click Create

#### Step 3: Configure Networking
1. Navigate to Networking > Virtual Cloud Networks > [Your VCN] > Subnets
2. Edit Security List for your subnet
3. Add Ingress Rules:
   - Port 22 (SSH) — restrict to your IP
   - Port 80 (HTTP) — 0.0.0.0/0
   - Port 443 (HTTPS) — 0.0.0.0/0
   - Port 3000 (Grafana) — restrict to your IP
   - Port 9090 (Prometheus) — restrict to your IP
   - Port 3001 (Uptime Kuma) — restrict to your IP

#### Step 4: Attach Block Volume
1. Navigate to Block Storage > Boot Volumes (200GB included in free tier)
2. If not already attached, create and attach a new block volume
3. SSH into VM and format: `sudo mkfs.ext4 /dev/sdb`
4. Mount: `sudo mkdir /data && sudo mount /dev/sdb /data`
5. Add to `/etc/fstab` for persistence

### 22.2 Docker Compose Deployment

#### Install Docker
```bash
# SSH into your Oracle Cloud VM
ssh -i ~/.ssh/vigil_key ubuntu@<your-vm-public-ip>

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
exit  # Reconnect for group change
ssh -i ~/.ssh/vigil_key ubuntu@<your-vm-public-ip>
```

#### Create Docker Compose File
```yaml
# docker-compose.yml
version: "3.8"

services:
  postgres:
    image: postgres:15-alpine
    container_name: vigil-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: vigil
      POSTGRES_USER: vigil
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./backups:/backups
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vigil"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 4G

  redis:
    image: redis:7-alpine
    container_name: vigil-redis
    restart: unless-stopped
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    ports:
      - "127.0.0.1:6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 2G

  nginx:
    image: nginx:alpine
    container_name: vigil-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certbot/conf:/etc/letsencrypt:ro
      - ./certbot/www:/var/www/certbot:ro
    depends_on:
      - api
    deploy:
      resources:
        limits:
          memory: 256M

  api:
    build: .
    container_name: vigil-api
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql://vigil:${POSTGRES_PASSWORD}@postgres:5432/vigil
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 4G

  prometheus:
    image: prom/prometheus:latest
    container_name: vigil-prometheus
    restart: unless-stopped
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prom_data:/prometheus
    ports:
      - "127.0.0.1:9090:9090"
    deploy:
      resources:
        limits:
          memory: 1G

  grafana:
    image: grafana/grafana-oss:latest
    container_name: vigil-grafana
    restart: unless-stopped
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
    ports:
      - "127.0.0.1:3000:3000"
    depends_on:
      - prometheus
    deploy:
      resources:
        limits:
          memory: 512M

  loki:
    image: grafana/loki:latest
    container_name: vigil-loki
    restart: unless-stopped
    volumes:
      - ./loki-config.yaml:/etc/loki/local-config.yaml:ro
      - loki_data:/loki
    ports:
      - "127.0.0.1:3100:3100"
    deploy:
      resources:
        limits:
          memory: 512M

  promtail:
    image: grafana/promtail:latest
    container_name: vigil-promtail
    restart: unless-stopped
    volumes:
      - /var/log:/var/log:ro
      - ./promtail-config.yaml:/etc/promtail/config.yaml:ro
    command: -config.file=/etc/promtail/config.yaml
    depends_on:
      - loki
    deploy:
      resources:
        limits:
          memory: 256M

  uptime-kuma:
    image: louislam/uptime-kuma:latest
    container_name: vigil-uptime-kuma
    restart: unless-stopped
    volumes:
      - kuma_data:/app/data
    ports:
      - "127.0.0.1:3001:3001"
    deploy:
      resources:
        limits:
          memory: 256M

volumes:
  pg_data:
  redis_data:
  prom_data:
  grafana_data:
  loki_data:
  kuma_data:
```

#### nginx Configuration
```nginx
# nginx.conf
events {
    worker_connections 1024;
}

http {
    upstream api {
        server api:8000;
    }

    server {
        listen 80;
        server_name your-domain.duckdns.org;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 301 https://$host$request_uri;
        }
    }

    server {
        listen 443 ssl;
        server_name your-domain.duckdns.org;

        ssl_certificate /etc/letsencrypt/live/your-domain.duckdns.org/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/your-domain.duckdns.org/privkey.pem;

        location / {
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /ws {
            proxy_pass http://api;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }

        location /grafana {
            proxy_pass http://grafana:3000;
            proxy_set_header Host $host;
        }

        location /prometheus {
            proxy_pass http://prometheus:9090;
            proxy_set_header Host $host;
        }
    }
}
```

#### Environment File
```bash
# .env
POSTGRES_PASSWORD=<generate-with: openssl rand -hex 32>
SECRET_KEY=<generate-with: openssl rand -hex 32>
GRAFANA_PASSWORD=<generate-with: openssl rand -hex 16>
```

### 22.3 Let's Encrypt TLS Setup

```bash
# Install Certbot
sudo apt update && sudo apt install -y certbot

# Obtain certificate (stop nginx first if port 80 is in use)
sudo certbot certonly --standalone -d your-domain.duckdns.org \
  --email your-email@example.com --agree-tos --non-interactive

# Setup auto-renewal cron
echo "0 3 * * * root certbot renew --quiet && docker compose restart nginx" | \
  sudo tee /etc/cron.d/certbot-renew
```

### 22.4 Automated Backup Strategy

```bash
#!/bin/bash
# backup.sh — Daily encrypted PostgreSQL backup
set -euo pipefail

BACKUP_DIR="/workspaces/Vigil/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/vigil_${DATE}.sql.gz"

# Create backup
docker exec vigil-postgres pg_dump -U vigil vigil | gzip > "$BACKUP_FILE"

# Encrypt with gpg (symmetric, AES-256)
gpg --batch --yes --symmetric --cipher-algo AES256 \
  --passphrase-file /etc/vigil/backup_key "$BACKUP_FILE"

# Remove unencrypted backup
rm "$BACKUP_FILE"

# Keep only last 7 days
find "$BACKUP_DIR" -name "vigil_*.sql.gz.gpg" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE.gpg"
```

```bash
# Add to crontab
echo "0 2 * * * /workspaces/Vigil/backup.sh >> /var/log/vigil-backup.log 2>&1" | crontab -
```

### 22.5 Monitoring and Alerting Setup

#### Prometheus Configuration
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'vigil-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:5432']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']

  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```

### 22.6 Deployment Commands

```bash
# Initial deployment
cd /workspaces/Vigil
docker compose up -d --build

# View logs
docker compose logs -f api

# Restart a service
docker compose restart api

# Update and redeploy
git pull
docker compose up -d --build

# Health check
curl -f http://localhost/health || echo "UNHEALTHY"

# Database migration
docker compose exec api alembic upgrade head

# View resource usage
docker stats
```

### 22.7 Maintenance Procedures

| Task | Frequency | Command |
|------|-----------|---------|
| Check disk usage | Daily | `df -h /data` |
| Check container health | Hourly (automated via Uptime Kuma) | `docker compose ps` |
| Rotate logs | Weekly | `docker compose logs --tail=1000 > logs.txt` |
| Update Docker images | Monthly | `docker compose pull && docker compose up -d` |
| Test backup restore | Monthly | `gunzip -c backup.sql.gz | psql -U vigil vigil` |
| Renew TLS cert | Every 90 days (automated) | `certbot renew` |
| Review Grafana dashboards | Daily | https://your-domain.duckdns.org/grafana |
| Check Uptime Kuma alerts | Continuous | https://your-domain.duckdns.org:3001 |

---

## Appendix A: Technology Stack Summary

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Web Framework** | FastAPI | 0.109+ | Async API serving |
| **WebSocket** | Socket.IO | 5.3+ | Real-time push |
| **Database** | PostgreSQL | 15+ | Primary data store |
| **Async DB Driver** | asyncpg | 0.29+ | Async PostgreSQL |
| **Cache** | Redis | 7.x | In-memory data grid |
| **Connection Pool** | PgBouncer | 1.20+ | Connection management |
| **ML Framework** | PyTorch | 2.x | Model training |
| **Model Registry** | MLflow | 2.x | Model versioning |
| **Data Processing** | pandas | 2.x | Data manipulation |
| **Numerical** | NumPy | 1.24+ | Vectorized operations |
| **Scheduler** | APScheduler | 3.10+ | Background jobs |
| **Web Server** | Gunicorn + Uvicorn | 21+ | WSGI/ASGI server |
| **Monitoring** | Prometheus | 2.x | Metrics collection |
| **Visualization** | Grafana | 10.x | Dashboards |
| **Logging** | structlog | 23.x | Structured logging |
| **Migrations** | Alembic | 1.13+ | Schema versioning |
| **Validation** | Marshmallow | 3.20+ | Input validation |
| **Authentication** | PyJWT | 2.8+ | JWT tokens |
| **Deployment** | Docker Compose on Oracle Cloud Free Tier | - | Zero-cost hosting |
| **CI/CD** | GitHub Actions | - | Automation (2,000 min/month free) |

---

## Appendix B: Database Schema Evolution

### Current Schema (alerts table)
- 28 columns covering signal detection, trap analysis, MTF alignment, outcomes

### Planned Additions

| Table | Purpose | Phase |
|-------|---------|-------|
| `ml_models` | Model registry | 2 |
| `feature_values` | Feature store | 2 |
| `predictions` | ML predictions | 2 |
| `user_profiles` | User preferences | 3 |
| `user_behavior` | Behavior tracking | 3 |
| `strategy_templates` | Strategy sharing | 3 |
| `audit_log` | Compliance trail | 1 |
| `alert_deliveries` | Delivery tracking | 1 |
| `alert_dedup` | Deduplication | 1 |
| `correlation_matrix` | Correlation data | 3 |
| `portfolio_risk` | Risk metrics | 3 |
| `backtest_runs` | Backtest metadata | 2 |
| `backtest_results` | Trade-level results | 2 |
| `backtest_metrics` | Performance metrics | 2 |

---

## Appendix C: API Endpoint Evolution

### Current Endpoints
- `GET /` — Dashboard
- `GET /alerts` — Query alerts
- `GET /regime` — Current regime
- `GET /watchlist` — List watchlist
- `POST /watchlist` — Add ticker
- `DELETE /watchlist` — Remove ticker
- `POST /trigger` — Manual detection
- `POST /backfill` — Historical generation
- `POST /evaluate` — Outcome evaluation

### Planned Additions

| Endpoint | Method | Purpose | Phase |
|----------|--------|---------|-------|
| `/health` | GET | Basic health check | 1 |
| `/health/ready` | GET | Readiness check | 1 |
| `/health/live` | GET | Liveness check | 1 |
| `/metrics` | GET | Prometheus metrics | 1 |
| `/auth/token` | POST | JWT token generation | 1 |
| `/alerts/stream` | WebSocket | Real-time alert stream | 1 |
| `/backtest/run` | POST | Start backtest | 2 |
| `/backtest/<id>` | GET | Backtest results | 2 |
| `/backtest/compare` | GET | Compare backtests | 2 |
| `/portfolio/correlation` | GET | Correlation matrix | 3 |
| `/portfolio/risk` | GET | Risk metrics | 3 |
| `/user/profile` | GET/PUT | User preferences | 3 |
| `/user/behavior` | GET | Behavior analytics | 3 |
| `/templates` | GET/POST | Strategy templates | 3 |
| `/models` | GET | Model registry | 2 |
| `/predictions` | GET | Latest predictions | 2 |

---

## Appendix D: Glossary

| Term | Definition |
|------|------------|
| **Edge Score** | 0-10 scale measuring signal quality |
| **MTF** | Multi-Timeframe Analysis |
| **ATR** | Average True Range (volatility measure) |
| **VaR** | Value at Risk |
| **CVaR** | Conditional Value at Risk (Expected Shortfall) |
| **PSI** | Population Stability Index (model drift metric) |
| **CQRS** | Command Query Responsibility Segregation |
| **RTO** | Recovery Time Objective |
| **RPO** | Recovery Point Objective |
| **SLA** | Service Level Agreement |
| **WORM** | Write Once Read Many (compliance storage) |

---

**Document Control**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-02 | Architect Mode | Initial release |

**Next Review:** 2026-05-02

---

*This document is confidential and intended for internal use only. Distribution outside the organization requires explicit authorization.*
