# Vigil End-to-End Testing Guide

## Prerequisites

Your system needs a PostgreSQL database. Choose one:

### Option 1: ElephantSQL (Recommended for quick testing) ⭐

Free tier, cloud-hosted, easiest setup.

1. Go to https://www.elephantsql.com
2. Sign up (free account)
3. Create a new instance (pick "Tiny Turtle" free plan, any region)
4. Copy the **URL** from the dashboard
5. In your terminal:
   ```bash
   export DATABASE_URL="<paste-the-url-here>"
   ```
6. Verify it works:
   ```bash
   python test_e2e.py
   ```

### Option 2: Local PostgreSQL

If you have PostgreSQL installed locally:

```bash
# Start PostgreSQL
service postgresql start

# Create database
sudo -u postgres createdb vigil

# Set connection string
export DATABASE_URL="postgresql://postgres:password@localhost/vigil"

# Run tests
python test_e2e.py
```

### Option 3: Docker PostgreSQL

```bash
# Start Postgres in Docker
docker run --name vigil-postgres -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=vigil -p 5432:5432 -d postgres

# Set connection
export DATABASE_URL="postgresql://postgres:password@localhost:5432/vigil"

# Run tests
python test_e2e.py
```

---

## Running the Tests

Once `DATABASE_URL` is set:

```bash
# Test database, watchlist, detection, webhooks, API
python test_e2e.py
```

**What it tests:**
- ✓ Database connection & schema
- ✓ Watchlist CRUD (add/remove tickers)
- ✓ Signal detection trigger
- ✓ Webhook notifications
- ✓ API endpoints (/alerts, /regime, /watchlist)

### Optional: Full System Test (Slow - 5-10 minutes)

Edit `test_e2e.py`, uncomment these lines (~line 289):

```python
results.append(("Backfill", test_backfill()))        # ~2-5 min
results.append(("Evaluation", test_evaluation()))    # ~1 min
results.append(("Analysis", test_trap_analysis()))   # ~30 sec
```

Then run:
```bash
python test_e2e.py
```

---

## Quick Test Flow

Once tests pass, you can manually verify the system:

```bash
# 1. Start the Flask server
python api.py &

# 2. Trigger detection (scans watchlist)
curl http://localhost:5000/trigger

# 3. Check current alerts
curl http://localhost:5000/alerts | jq '.[0]'

# 4. View your watchlist
curl http://localhost:5000/watchlist

# 5. Add a stock to focus on
curl -X POST http://localhost:5000/watchlist \
  -H "Content-Type: application/json" \
  -d '{"ticker": "MSTR"}'

# 6. Check market regime
curl http://localhost:5000/regime
```

---

## Setting Up Webhooks (Optional but Recommended)

To get alerts pushed to Discord/Slack:

### Discord

1. Create a test server or use existing one
2. Server Settings → Integrations → Webhooks → New Webhook
3. Give it a name (e.g., "Vigil Alerts")
4. Copy the **Webhook URL**
5. Set env var:
   ```bash
   export NOTIFICATIONS_WEBHOOK_URL="https://discord.com/api/webhooks/..."
   ```
6. Test it:
   ```bash
   curl -X POST http://localhost:5000/trigger
   # Check Discord for alerts
   ```

### Slack

1. Create a test workspace or use existing
2. Create a channel for alerts (e.g., #vigil)
3. Apps → Incoming Webhooks → New
4. Select channel → Copy Webhook URL
5. Set env var:
   ```bash
   export NOTIFICATIONS_WEBHOOK_URL="https://hooks.slack.com/services/..."
   ```

---

## Troubleshooting

### "Connection refused" when testing API endpoints

The Flask server isn't running. Start it:
```bash
python api.py
```

### "No DATABASE_URL found"

Set the environment variable:
```bash
export DATABASE_URL="postgresql://..."
python test_e2e.py
```

### Detection takes too long

First run will scan 60 days * 5 tickers = lots of data. Subsequent runs are faster.

### Webhook test says "not set"

You can skip this for now. It's optional. Set `NOTIFICATIONS_WEBHOOK_URL` when ready.

---

## Expected Output

After successful test run:

```
======================================================================
                             TEST SUMMARY
======================================================================

  ✓ Database
  ✓ Watchlist
  ✓ Detection
  ✓ Webhooks
  ✓ API Endpoints

  Passed: 5/5

✓ All core systems operational!

Next steps:
  1. Set NOTIFICATIONS_WEBHOOK_URL for Discord/Slack alerts
  2. Run curl http://localhost:5000/trigger for live detection
  3. After 1-2 weeks: curl http://localhost:5000/evaluate
  4. Then: python analyze_traps.py to tune signal quality
```

---

## Next Steps

1. **Get data** (~1-2 weeks)
   ```bash
   # Runs nightly at 21:00 ET automatically, or trigger manually:
   curl http://localhost:5000/trigger
   ```

2. **Evaluate outcomes** (after 1+ alert age has passed)
   ```bash
   curl http://localhost:5000/evaluate
   ```

3. **Analyze trap quality**
   ```bash
   python analyze_traps.py
   ```

4. **Tune penalties** based on results

5. **Build UI** for watchlist management (optional)

---

## Need Help?

- Check your DATABASE_URL with: `echo $DATABASE_URL`
- Test DB connection: `python -c "from database import get_conn; get_conn()"`
- Check logs: `tail -f api.py` (while running)
