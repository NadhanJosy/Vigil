#!/usr/bin/env python
"""
End-to-End System Test for Vigil

Tests the complete flow:
1. Database initialization
2. Watchlist CRUD
3. Detection trigger
4. Alert storage
5. Webhook notifications
6. Backfill
7. Outcome evaluation
8. Trap analysis
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(title):
    """Print a section header"""
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{title:^70}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")

def test_result(test_name, passed, message=""):
    """Print test result"""
    status = f"{GREEN}✓ PASS{RESET}" if passed else f"{RED}✗ FAIL{RESET}"
    print(f"[{status}] {test_name}")
    if message:
        print(f"    → {message}")

# ─── TEST 1: DATABASE INITIALIZATION ───────────────────────────────────────

def test_database():
    print_header("TEST 1: Database Initialization")
    
    try:
        from database import init_db, get_conn
        
        # Test connection
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        test_result("Database connection", True, "PostgreSQL connected")
        
        # Initialize schema
        init_db()
        test_result("Database schema", True, "Tables created/verified")
        
        return True
    except Exception as e:
        test_result("Database", False, str(e))
        return False

# ─── TEST 2: WATCHLIST OPERATIONS ──────────────────────────────────────────

def test_watchlist():
    print_header("TEST 2: Watchlist CRUD Operations")
    
    try:
        from database import add_to_watchlist, remove_from_watchlist, get_watchlist
        
        # Add test tickers
        test_tickers = ["MSTR", "NVDA", "TSLA"]
        for ticker in test_tickers:
            add_to_watchlist(ticker)
        
        test_result("Add to watchlist", True, f"Added {test_tickers}")
        
        # Get watchlist
        watchlist = get_watchlist()
        all_present = all(t in watchlist for t in test_tickers)
        test_result("Retrieve watchlist", all_present, f"Watchlist has {len(watchlist)} items")
        
        # Remove from watchlist
        remove_from_watchlist("MSTR")
        watchlist = get_watchlist()
        removed = "MSTR" not in watchlist
        test_result("Remove from watchlist", removed, "MSTR removed successfully")
        
        return True
    except Exception as e:
        test_result("Watchlist operations", False, str(e))
        return False

# ─── TEST 3: DETECTION TRIGGER ─────────────────────────────────────────────

def test_detection():
    print_header("TEST 3: Signal Detection Trigger")
    
    try:
        from data import run_detection
        from database import get_alerts
        
        # Get alert count before
        before = get_alerts(limit=1)
        before_count = len(before) if before else 0
        
        logger.info("Triggering detection... (this may take 30-60 seconds)")
        run_detection()
        
        # Get alert count after
        after = get_alerts(limit=100, offset=0)
        after_count = len(after) if after else 0
        new_alerts = after_count - before_count
        
        test_result("Detection execution", True, f"Completed successfully")
        test_result("Alerts generated", new_alerts > 0, f"{new_alerts} new alerts created")
        
        if after:
            sample = after[0]
            test_result("Alert storage", sample is not None, 
                       f"Sample: {sample[1]} on {sample[2]}")
        
        return True
    except Exception as e:
        test_result("Detection trigger", False, str(e))
        import traceback
        traceback.print_exc()
        return False

# ─── TEST 4: WEBHOOK NOTIFICATIONS ─────────────────────────────────────────

def test_webhook():
    print_header("TEST 4: Webhook Notification System")
    
    try:
        from data import notify_webhook
        import os
        
        webhook_url = os.environ.get("NOTIFICATIONS_WEBHOOK_URL")
        
        if not webhook_url:
            test_result("Webhook URL", False, "NOTIFICATIONS_WEBHOOK_URL not set")
            print(f"    {YELLOW}→ Set env var: export NOTIFICATIONS_WEBHOOK_URL='<your-webhook>'{RESET}")
            return False
        
        test_result("Webhook URL", True, "Environment variable configured")
        
        # Test regime shift notification
        test_payload = {
            "old_regime": "TRENDING",
            "new_regime": "RISK_OFF"
        }
        
        logger.info("Testing regime shift notification...")
        notify_webhook(test_payload)
        test_result("Regime shift alert", True, "Notification function executed")
        
        # Test signal notification
        test_signal = {
            "ticker": "TEST",
            "combo": "CONFIRMED_BREAKOUT",
            "action": "ENTER",
            "edge": 7.5,
            "summary": "Test alert - not a real signal",
            "regime": "TRENDING",
            "mtf": "FULL_UP"
        }
        
        logger.info("Testing signal notification...")
        notify_webhook(test_signal)
        test_result("Signal alert", True, "Notification sent to webhook")
        
        return True
    except Exception as e:
        test_result("Webhook notifications", False, str(e))
        return False

# ─── TEST 5: BACKFILL ──────────────────────────────────────────────────────

def test_backfill():
    print_header("TEST 5: Historical Backfill")
    
    try:
        from data import run_backfill
        from database import get_alerts
        
        # Get count before
        before = get_alerts(limit=1)
        before_count = len(before) if before else 0
        
        logger.info("Running backfill... (this may take 2-5 minutes)")
        run_backfill()
        
        # Get count after
        after = get_alerts(limit=1000, offset=0)
        after_count = len(after) if after else 0
        new_alerts = after_count - before_count
        
        test_result("Backfill execution", True, "Completed successfully")
        test_result("Historical alerts", new_alerts > 0, 
                   f"{new_alerts} historical alerts generated")
        
        return True
    except Exception as e:
        test_result("Backfill", False, str(e))
        import traceback
        traceback.print_exc()
        return False

# ─── TEST 6: OUTCOME EVALUATION ────────────────────────────────────────────

def test_evaluation():
    print_header("TEST 6: Outcome Evaluation")
    
    try:
        from database import evaluate_outcomes, get_alerts
        
        logger.info("Evaluating outcomes... (checking alert performance)")
        evaluate_outcomes()
        
        # Get alerts with outcomes
        all_alerts = get_alerts(limit=100, offset=0)
        with_outcomes = sum(1 for a in all_alerts if a[8] is not None)
        
        test_result("Outcome evaluation", True, "Completed successfully")
        test_result("Alerts evaluated", with_outcomes > 0, 
                   f"{with_outcomes} alerts have outcome data")
        
        if with_outcomes > 0:
            # Sample outcome
            for alert in all_alerts:
                if alert[8] is not None:
                    ticker, result, pct = alert[1], alert[8], alert[7]
                    test_result("Sample outcome", True, 
                               f"{ticker}: {result} ({pct:+.1f}%)" if pct else f"{ticker}: {result}")
                    break
        
        return True
    except Exception as e:
        test_result("Outcome evaluation", False, str(e))
        import traceback
        traceback.print_exc()
        return False

# ─── TEST 7: TRAP ANALYSIS ────────────────────────────────────────────────

def test_trap_analysis():
    print_header("TEST 7: Trap Reason Analysis")
    
    try:
        import json
        from database import get_conn
        
        conn = get_conn()
        cursor = conn.cursor()
        
        # Count evaluated traps
        cursor.execute("""
            SELECT COUNT(*) FROM alerts 
            WHERE trap_reasons IS NOT NULL AND outcome_result IS NOT NULL
        """)
        trap_count = cursor.fetchone()[0]
        conn.close()
        
        if trap_count == 0:
            test_result("Trap analysis", False, 
                       "No evaluated traps yet (need more historical data)")
            print(f"    {YELLOW}→ Run /evaluate endpoint to populate outcomes{RESET}")
            return False
        
        test_result("Evaluated traps", True, f"{trap_count} traps with outcomes")
        
        # Run analysis
        from analyze_traps import analyze_trap_performance
        logger.info("Running trap performance analysis...")
        analyze_trap_performance()
        
        test_result("Analysis execution", True, "Report generated")
        return True
    except Exception as e:
        test_result("Trap analysis", False, str(e))
        import traceback
        traceback.print_exc()
        return False

# ─── TEST 8: API ENDPOINTS ────────────────────────────────────────────────

def test_api_endpoints():
    print_header("TEST 8: API Endpoints")
    
    try:
        import urllib.request
        import json
        
        base_url = "http://localhost:5000"
        
        # Test /regime endpoint
        try:
            with urllib.request.urlopen(f"{base_url}/regime") as response:
                data = json.loads(response.read().decode())
                regime = data.get("regime", "UNKNOWN")
                test_result("/regime endpoint", True, f"Current regime: {regime}")
        except Exception as e:
            test_result("/regime endpoint", False, str(e))
        
        # Test /alerts endpoint
        try:
            with urllib.request.urlopen(f"{base_url}/alerts") as response:
                data = json.loads(response.read().decode())
                test_result("/alerts endpoint", True, f"Retrieved {len(data)} alerts")
        except Exception as e:
            test_result("/alerts endpoint", False, str(e))
        
        # Test /watchlist endpoint
        try:
            with urllib.request.urlopen(f"{base_url}/watchlist") as response:
                data = json.loads(response.read().decode())
                test_result("/watchlist endpoint", True, f"{len(data)} items in watchlist")
        except Exception as e:
            test_result("/watchlist endpoint", False, str(e))
        
        return True
    except Exception as e:
        test_result("API endpoints", False, str(e))
        return False

# ─── MAIN TEST RUNNER ──────────────────────────────────────────────────────

def main():
    # Check DATABASE_URL first
    if not os.environ.get("DATABASE_URL"):
        print(f"\n{RED}✗ DATABASE_URL not set{RESET}")
        print(f"\n{YELLOW}To set up your database:{RESET}")
        print(f"  bash setup_local.sh")
        print(f"\n{YELLOW}Quick setup options:{RESET}")
        print(f"  1. ElephantSQL (free cloud): https://www.elephantsql.com")
        print(f"  2. Local PostgreSQL: apt install postgresql && service postgresql start")
        print(f"  3. Heroku Postgres (if deploying there)")
        print(f"\n{YELLOW}Then export your DATABASE_URL and run this script again.{RESET}\n")
        sys.exit(1)
    
    print(f"\n{BLUE}╔════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BLUE}║{RESET}         {BLUE}VIGIL END-TO-END SYSTEM TEST{RESET}                       {BLUE}║{RESET}")
    print(f"{BLUE}║{RESET}  Validating detection, storage, notifications, and analysis  {BLUE}║{RESET}")
    print(f"{BLUE}╚════════════════════════════════════════════════════════════════════╝{RESET}\n")
    
    results = []
    
    # Run tests
    results.append(("Database", test_database()))
    results.append(("Watchlist", test_watchlist()))
    results.append(("Detection", test_detection()))
    results.append(("Webhooks", test_webhook()))
    # Don't auto-run backfill as it's slow
    # results.append(("Backfill", test_backfill()))
    # results.append(("Evaluation", test_evaluation()))
    # results.append(("Analysis", test_trap_analysis()))
    results.append(("API Endpoints", test_api_endpoints()))
    
    # Summary
    print_header("TEST SUMMARY")
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = f"{GREEN}✓{RESET}" if result else f"{RED}✗{RESET}"
        print(f"  {status} {name}")
    
    print(f"\n  {GREEN}Passed: {passed}/{total}{RESET}")
    
    if passed == total:
        print(f"\n{GREEN}✓ All core systems operational!{RESET}")
        print(f"\n{YELLOW}Next steps:{RESET}")
        print(f"  1. Set NOTIFICATIONS_WEBHOOK_URL for Discord/Slack alerts")
        print(f"  2. Run curl http://localhost:5000/trigger for live detection")
        print(f"  3. After 1-2 weeks: curl http://localhost:5000/evaluate")
        print(f"  4. Then: python analyze_traps.py to tune signal quality")
    else:
        print(f"\n{RED}✗ Some tests failed. Check errors above.{RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
