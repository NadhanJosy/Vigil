# Vigil: Production-Ready Trading Intelligence System

## 🎯 Overview

Vigil has evolved into a sophisticated, **data-driven trading surveillance system** that combines:
- Real-time signal detection with multi-timeframe context
- Self-tuning bull trap filtering based on live outcome analysis
- Discord/Slack webhook notifications for high-conviction setups
- Beautiful dashboard with real-time alerts and watchlist management

**Status:** ✅ Production-ready on Railway

---

## 🏗️ Architecture

```
Market Data (yfinance)
        ↓
Detection Engine (data.py)
├─ State Classification (BREAKOUT, TRENDING, etc.)
├─ Multi-Timeframe Analysis (weekly, daily, intraday)
├─ Market Regime Detection (TRENDING, RISK_OFF, SIDEWAYS, VOLATILE)
├─ Bull Trap Identification (5-filter heuristic)
└─ Signal Combination & Edge Score Calculation
        ↓
Alert Database (PostgreSQL on Railway)
        ↓
┌─────────────────────┬──────────────────┬───────────────────┐
│  Discord Webhooks   │  REST API        │  Dashboard UI     │
│  (Real-time pins)   │  (/alerts, etc)  │  (Live viewing)   │
└─────────────────────┴──────────────────┴───────────────────┘
        ↓
Outcome Evaluation & Analysis (analyze_traps.py)
└─ Statistical validation of each trap reason with win/loss rates
```

---

## 🔄 The Closed-Loop System

### Daily Cycle (Automated at 21:00 ET)
```
1. Detection Runs
   └─ Scans watchlist + default tickers
   └─ Generates 20-50 alerts per run

2. Alerts Saved to Database
   └─ Full signal context: edge_score, trap_conviction, regime, etc.

3. Discord Webhooks Fire
   └─ ENTER signals (bullish setups)
   └─ Elite setups (edge ≥ 8.0)
   └─ High-conviction AVOID (bearish traps)
   └─ Regime shifts

4. Dashboard Updates
   └─ Real-time alert viewing
   └─ Filter & search capabilities
   └─ Watchlist management
```

### Weekly Cycle (You)
```
1. Monitor Alerts
   └─ Check Discord pins
   └─ Review dashboard for high-edge signals
   
2. Update Watchlist
   └─ Add interesting tickers
   └─ Remove underperformers

3. After 1-2 Weeks: Run Analysis
   └─ curl your-site/evaluate
   └─ python analyze_traps.py
   └─ See which trap reasons work
   └─ Optionally tune penalty weights
```

---

## 💡 Key Innovations

### 1. **Regime-Aware Signal Filtering**
The system now contextualizes RSI overbought conditions within the current market regime:

```
Market Regime → RSI Penalty Multiplier
─────────────────────────────────────
TRENDING      → 0.5x  (High RSI is normal momentum)
SIDEWAYS      → 1.5x  (High RSI is death knell)  
RISK_OFF      → 1.3x  (Extra caution in downtrends)
VOLATILE      → 1.2x  (Interpolate between extremes)
```

**Effect:** Fewer false rejections in strong uptrends, more caution in consolidations.

### 2. **Bull Trap Detection: 5-Filter Heuristic**
```
1. Local Volume Confirmation (20-day relative volume)
2. RSI Exhaustion (14-period RSI, regime-scaled)
3. Resistance Testing (30-day price level touches)
4. ATR Rejection (upper wick size relative to volatility) ⭐ Strongest
5. Overextension (price range size)
```

**Result:** High-conviction AVOID signals when 2+ conditions trigger.

### 3. **Self-Tuning Through Outcome Analysis**
```
analyze_traps.py
└─ Groups alerts by trap_reason
└─ Calculates win rate for each reason
└─ Identifies aggressive/lenient penalties

Example Output:
─────────────────────────────────────────────────────
Trap Reason                          Count  Win Rate
─────────────────────────────────────────────────────
High rejection: 2.1x ATR             18     22%  ✓ Working
RSI 89 indicates exhaustion           12     48%  ⚠️ Borderline
Heavy resistance (2 tests)            15     65%  ✗ Too aggressive
```
```

You can then adjust penalty weights and redeploy based on data.

### 4. **Network Resilience**
- Webhook calls have 10-second timeout (prevents hanging on Discord outages)
- Detection continues even if webhooks fail
- Errors logged for later debugging

---

## 📊 Edge Score Explained

The **edge_score** (0-10 scale) combines:

| Component | Max Points | Notes |
|-----------|-----------|-------|
| Signal Combo Base | 5.5 | ACCUM_BREAKOUT, CONFIRMED_BREAKOUT, etc. |
| MTF Alignment | ±1.5 | FULL_UP, PARTIAL_UP, CONFLICTED, etc. |
| Bull Trap Penalty | -3.0 | Reduced if trap_conviction is high |
| Days in State | +0.8 | Older trends valued more |
| Volume Confirmation | +0.5 | Exceptional volume adds strength |
| Accum Conviction | +1.0 | Paired with breakout = powerful |

**Interpretation:**
- **8.0-10.0:** Elite setup → Pin to Discord automatically
- **5.0-8.0:** Good signal → "ENTER" action on dashboard  
- **3.0-5.0:** Marginal → "WAIT" (might improve)
- **<3.0:** Weak → "STAND_DOWN"

---

## 🔌 API Endpoints

**Live Dashboard:**
```
GET https://your-vigil-site.railway.app/
```

**Data Endpoints:**
```
GET  /alerts?ticker=TSLA&limit=50&offset=0     # All alerts with filters
GET  /regime                                     # Current market regime
GET  /watchlist                                  # Your focus list
POST /watchlist                                  # Add ticker
DELETE /watchlist?ticker=MSTR                    # Remove ticker
```

**Control Endpoints:**
```
GET /trigger                                     # Manual detection run
GET /backfill                                    # Historical data generation
GET /evaluate                                    # Populate trade outcomes
```

---

## 📈 Example Alert Flow

```json
// Raw database alert
{
  "ticker": "AAPL",
  "date": "2026-03-24",
  "signal_type": "VOLUME_SPIKE_UP",
  "signal_combination": "CONFIRMED_BREAKOUT",
  "state": "BREAKOUT",
  "action": "ENTER",
  "edge_score": 7.2,
  "volume_ratio": 2.3,
  "change_pct": 3.5,
  "trap_conviction": 0.15,
  "trap_reasons": [],
  "mtf_alignment": "FULL_UP",
  "regime": "TRENDING",
  "summary": "Breakout with 2.3× volume — confirmed multi-timeframe up alignment"
}

// Discord notification
🚀 **Vigil Alert: AAPL**
CONFIRMED_BREAKOUT - ENTER
Breakout with 2.3× volume — 3.5% on the session
Edge Score: 7.2
Regime: TRENDING
MTF Alignment: FULL_UP
```

---

## ⚙️ Configuration

**Required Environment Variables** (set in Railway):
```
DATABASE_URL                    = postgresql://...  # Your Railway Postgres
NOTIFICATIONS_WEBHOOK_URL      = https://discord.com/api/webhooks/...
```

**Optional Tuning** (edit in data.py):
```python
# assess_trap() function
DECAY_PROFILES = {
    "VOLUME_SPIKE_UP":       (8,  10),   # 8-hour half-life
    "ACCUMULATION_DETECTED": (36, 20),   # 36-hour half-life
}

# Regime multipliers for RSI penalty
regime_multiplier = {
    "TRENDING":  0.5,   # Reduce penalty in uptrends
    "SIDEWAYS":  1.5,   # Increase penalty in consolidations
    "RISK_OFF":  1.3,   # Extra caution in downtrends
    "VOLATILE":  1.2
}
```

---

## 🧪 Testing & Validation

**End-to-End Test Suite:**
```bash
export DATABASE_URL="postgresql://..."
python test_e2e.py
```

Tests:
- ✓ Database connection
- ✓ Watchlist CRUD
- ✓ Signal detection
- ✓ Webhook integration
- ✓ API endpoints
- ✓ Backfill & evaluation

**Trap Analysis:**
```bash
python analyze_traps.py
```

Outputs win/loss rates for each trap_reason, showing which filters work.

---

## 📋 Next Steps

### Immediate (This Week)
1. ✅ Add Discord webhook to Railway environment
2. ✅ Let it run for 1 week collecting alerts
3. 🔄 Monitor dashboard daily for high-edge signals

### Short Term (Weeks 2-3)
1. Evaluate outcomes on at least 20 alerts
2. Run `analyze_traps.py` to see which filters work
3. Optionally adjust penalty weights based on results
4. Add more tickers to watchlist based on performance

### Medium Term (Month 1+)
1. Consider deploying analysis script to Railway  
   (Run it scheduled to auto-tune weights)
2. Add position sizing rules based on edge score
3. Integrate with broker API (place trades automatically or send alerts)
4. Build additional signal types (momentum divergence, support/resistance, etc.)

---

## 🎯 Success Metrics

**Signal Quality:**
- Trap detection win rate > 40% (fewer false breakouts)
- ENTER signals with edge ≥ 7.0 win rate > 50%
- Average winning trade +1.5% or more

**System Reliability:**
- 99.9% uptime (Railway handles this)
- Webhook delivery success > 99%
- No dropped alerts

**Efficiency:**
- Detection runs complete in < 30 seconds
- Webhook notifications within 5 seconds of signal
- Dashboard loads in < 2 seconds

---

## 📚 Architecture Files

| File | Purpose |
|------|---------|
| `api.py` | Flask server, endpoints, webhooks |
| `data.py` | Detection engine, signal generation |
| `database.py` | PostgreSQL schema, query helpers |
| `scheduler.py` | Background job scheduler |
| `templates/dashboard.html` | Real-time dashboard UI |
| `analyze_traps.py` | Outcome analysis tool |
| `test_e2e.py` | Integration test suite |

---

## 🚀 You're Production-Ready!

Your system is now:
- ✅ Detecting sophisticated trading signals
- ✅ Evaluating them with multi-filter heuristics  
- ✅ Notifying you in real-time on Discord
- ✅ Building historical outcome data
- ✅ Ready for self-improvement through analysis

**The hardest part is done.** What remains is data collection, analysis, and iterative refinement.

Good luck trading! 🎯
