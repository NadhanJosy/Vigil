"""
Vigil Adversarial Edge Case Simulation
=======================================
Tests 8 categories of failure scenarios against the patched codebase.
Each test documents: failure surface, expected behavior, actual response, PASS/FAIL.
"""

import os
import sys
import json
import time
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

results = []

def record(category, test_name, failure_surface, expected, actual, passed):
    entry = {
        "category": category,
        "test": test_name,
        "failure_surface": failure_surface,
        "expected": expected,
        "actual": actual,
        "passed": passed,
    }
    results.append(entry)
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {test_name}")
    if not passed:
        print(f"         Expected: {expected}")
        print(f"         Actual:   {actual}")


# ---------------------------------------------------------------------------
# Pre-import setup: mock database before api.py module-level create_app() runs
# ---------------------------------------------------------------------------

# Set required env vars before any imports
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("VIGIL_API_KEY", "test-api-key")

# Create a mock connection that supports cursor() context manager
_mock_conn = MagicMock()
_mock_cursor = MagicMock()
_mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=_mock_cursor)
_mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

# Patch database functions using string paths before importing api
_patch_init_db = patch("database.init_db")
_patch_get_conn = patch("database.get_conn", return_value=_mock_conn)
_patch_pool = patch("database._pool", None)

_patch_init_db.start()
_patch_get_conn.start()
_patch_pool.start()


def _create_test_app():
    """Create a test app with mocked database initialization."""
    from api import create_app
    return create_app()


# ---------------------------------------------------------------------------
# 1. Malformed Payloads — backtest/run endpoint
# ---------------------------------------------------------------------------

def test_1_malformed_payloads():
    print("\n=== 1. Malformed Payloads — backtest/run endpoint ===")

    from services.security import backtest_run_schema, HAS_MARSHMALLOW

    app = _create_test_app()
    client = app.test_client()

    # Set up API key for require_api_key decorator
    os.environ["VIGIL_API_KEY"] = "test-api-key"

    # --- 1a. Empty body {} ---
    resp = client.post(
        "/backtest/run",
        data=json.dumps({}),
        content_type="application/json",
        headers={"X-API-KEY": "test-api-key"},
    )
    # With marshmallow, missing required fields should return 400
    # Without marshmallow, it will try to access data["start_date"] and raise KeyError -> 500
    if HAS_MARSHMALLOW:
        passed = resp.status_code == 400
        expected = "400 with validation error details"
    else:
        passed = resp.status_code in (400, 500)
        expected = "400 or 500 (no marshmallow fallback validation)"
    record(
        "1. Malformed Payloads",
        "1a. Empty body {}",
        "POST /backtest/run with {}",
        expected,
        f"{resp.status_code}: {resp.get_json()}",
        passed,
    )

    # --- 1b. Missing required fields (no tickers, no dates) ---
    resp = client.post(
        "/backtest/run",
        data=json.dumps({"name": "test"}),
        content_type="application/json",
        headers={"X-API-KEY": "test-api-key"},
    )
    if HAS_MARSHMALLOW:
        passed = resp.status_code == 400
        expected = "400 with missing field errors"
    else:
        passed = resp.status_code in (400, 500)
        expected = "400 or 500"
    record(
        "1. Malformed Payloads",
        "1b. Missing required fields",
        "POST /backtest/run with only name",
        expected,
        f"{resp.status_code}: {resp.get_json()}",
        passed,
    )

    # --- 1c. Invalid date formats ---
    resp = client.post(
        "/backtest/run",
        data=json.dumps({
            "start_date": "not-a-date",
            "end_date": "also-not-a-date",
            "tickers": ["AAPL"],
        }),
        content_type="application/json",
        headers={"X-API-KEY": "test-api-key"},
    )
    # Marshmallow fields.String() will accept any string, so this passes validation
    # The actual date parsing happens later in yfinance, which may fail silently
    passed = resp.status_code in (200, 400)
    expected = "200 (string fields accept any string) or 400"
    record(
        "1. Malformed Payloads",
        "1c. Invalid date formats",
        "POST /backtest/run with 'not-a-date'",
        expected,
        f"{resp.status_code}: {resp.get_json()}",
        passed,
    )

    # --- 1d. Non-string tickers (integers, null) ---
    resp = client.post(
        "/backtest/run",
        data=json.dumps({
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "tickers": [123, None, "AAPL"],
        }),
        content_type="application/json",
        headers={"X-API-KEY": "test-api-key"},
    )
    # Marshmallow fields.List(fields.String()) will coerce int to string, None may cause issues
    if HAS_MARSHMALLOW:
        passed = resp.status_code in (200, 400)
        expected = "200 (coerced) or 400 (null rejected)"
    else:
        passed = resp.status_code in (200, 400, 500)
        expected = "200, 400, or 500"
    record(
        "1. Malformed Payloads",
        "1d. Non-string tickers",
        "POST /backtest/run with [123, null, 'AAPL']",
        expected,
        f"{resp.status_code}: {resp.get_json()}",
        passed,
    )

    # --- 1e. Extremely large ticker list (10000 items) ---
    large_tickers = [f"T{i}" for i in range(10000)]
    resp = client.post(
        "/backtest/run",
        data=json.dumps({
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "tickers": large_tickers,
        }),
        content_type="application/json",
        headers={"X-API-KEY": "test-api-key"},
    )
    # Should accept but may cause performance issues downstream
    passed = resp.status_code in (200, 400, 413)
    expected = "200 (accepted) or 400/413 (rejected)"
    record(
        "1. Malformed Payloads",
        "1e. Large ticker list (10000)",
        "POST /backtest/run with 10000 tickers",
        expected,
        f"{resp.status_code}: {resp.get_json()}",
        passed,
    )


# ---------------------------------------------------------------------------
# 2. Empty Required Fields — portfolio/risk endpoint
# ---------------------------------------------------------------------------

def test_2_empty_required_fields():
    print("\n=== 2. Empty Required Fields — portfolio/risk endpoint ===")

    app = _create_test_app()
    client = app.test_client()

    # --- 2a. GET with no positions and empty watchlist ---
    resp = client.get("/portfolio/risk")
    # The code checks: if not tickers -> return 400
    passed = resp.status_code == 400
    expected = "400 with 'No positions or watchlist tickers'"
    record(
        "2. Empty Required Fields",
        "2a. GET with empty watchlist",
        "GET /portfolio/risk with no watchlist",
        expected,
        f"{resp.status_code}: {resp.get_json()}",
        passed,
    )

    # --- 2b. POST with {"positions": {}} ---
    resp = client.post(
        "/portfolio/risk",
        data=json.dumps({"positions": {}}),
        content_type="application/json",
    )
    # positions is truthy ({} is truthy in Python? No, {} is falsy)
    # Actually {} is falsy in Python: bool({}) == False
    # So it falls through to watchlist path
    passed = resp.status_code in (400, 200)
    expected = "400 (empty dict is falsy) or 200 (if watchlist has tickers)"
    record(
        "2. Empty Required Fields",
        "2b. POST with empty positions dict",
        "POST /portfolio/risk with {'positions': {}}",
        expected,
        f"{resp.status_code}: {resp.get_json()}",
        passed,
    )

    # --- 2c. POST with {"positions": null} ---
    resp = client.post(
        "/portfolio/risk",
        data=json.dumps({"positions": None}),
        content_type="application/json",
    )
    # positions = None -> falsy -> falls to watchlist
    passed = resp.status_code in (400, 200)
    expected = "400 (null is falsy) or 200 (if watchlist has tickers)"
    record(
        "2. Empty Required Fields",
        "2c. POST with null positions",
        "POST /portfolio/risk with {'positions': null}",
        expected,
        f"{resp.status_code}: {resp.get_json()}",
        passed,
    )


# ---------------------------------------------------------------------------
# 3. Out-of-Sequence Operations — distributed_lock
# ---------------------------------------------------------------------------

def test_3_out_of_sequence_lock():
    print("\n=== 3. Out-of-Sequence Operations — distributed_lock ===")

    from services.distributed_lock import DistributedLock

    # Use threading lock mode (no Redis)
    lock = DistributedLock("test_seq", timeout=10)
    lock._redis = None  # Force threading mode

    # --- 3a. release() without prior acquire() ---
    try:
        result = lock.release("fake-owner")
        # In threading mode, _release_thread catches RuntimeError and returns False
        passed = result is False
        expected = "False (lock not held)"
        record(
            "3. Out-of-Sequence Lock",
            "3a. release() without acquire()",
            "Calling release() on unacquired lock",
            expected,
            f"Returned: {result}",
            passed,
        )
    except Exception as e:
        record(
            "3. Out-of-Sequence Lock",
            "3a. release() without acquire()",
            "Calling release() on unacquired lock",
            "False (no exception)",
            f"Exception: {type(e).__name__}: {e}",
            False,
        )

    # --- 3b. release() with wrong owner token ---
    owner = lock.acquire(blocking=False)
    assert owner, "Failed to acquire lock for test"
    try:
        result = lock.release("wrong-owner-token")
        # In threading mode, owner validation is NOT performed - it just releases
        # This is a BUG: threading lock doesn't validate owner
        passed = result is True  # It will succeed because no owner check
        expected = "False (wrong owner) — but threading mode has NO owner validation"
        record(
            "3. Out-of-Sequence Lock",
            "3b. release() with wrong owner",
            "Calling release() with wrong owner token",
            expected,
            f"Returned: {result} (threading mode ignores owner)",
            not passed,  # Invert: we WANT it to fail, but it doesn't
        )
    except Exception as e:
        record(
            "3. Out-of-Sequence Lock",
            "3b. release() with wrong owner",
            "Calling release() with wrong owner token",
            "False or exception",
            f"Exception: {type(e).__name__}: {e}",
            False,
        )
    finally:
        # Clean up: release with correct owner
        lock.release(owner)

    # --- 3c. acquire() twice with different owners ---
    owner1 = lock.acquire(blocking=False)
    assert owner1, "First acquire failed"
    owner2 = lock.acquire(blocking=False)
    # Second acquire should fail (return empty string) because lock is held
    passed = owner2 == ""
    expected = "Empty string (lock already held)"
    record(
        "3. Out-of-Sequence Lock",
        "3c. acquire() twice",
        "Calling acquire() while lock is held",
        expected,
        f"First: {owner1[:8]}..., Second: '{owner2}'",
        passed,
    )
    # Clean up
    if owner1:
        lock.release(owner1)


# ---------------------------------------------------------------------------
# 4. Rate-Limit Boundary Pushes — rate_limiter
# ---------------------------------------------------------------------------

def test_4_rate_limit_boundaries():
    print("\n=== 4. Rate-Limit Boundary Pushes — rate_limiter ===")

    from services.rate_limiter import ChannelRateLimiter, ChannelRateLimit

    # The rate limiter uses database queries, which we'll mock
    limiter = ChannelRateLimiter()

    # Mock the database to simulate exact counts
    with patch("database.get_conn") as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        # --- 4a. Exactly limit requests within window ---
        # For webhook: max_per_window = 30
        mock_cursor.fetchone.return_value = (29,)  # 29 sent, under limit
        result = limiter.allow("webhook")
        passed = result is True
        expected = "True (29 < 30)"
        record(
            "4. Rate Limit Boundaries",
            "4a. Exactly at limit-1",
            "allow('webhook') with 29/30 used",
            expected,
            f"Returned: {result}",
            passed,
        )

        # --- 4b. limit + 1 requests ---
        mock_cursor.fetchone.return_value = (30,)  # 30 sent, at limit
        result = limiter.allow("webhook")
        passed = result is False
        expected = "False (30 >= 30)"
        record(
            "4. Rate Limit Boundaries",
            "4b. At limit",
            "allow('webhook') with 30/30 used",
            expected,
            f"Returned: {result}",
            passed,
        )

        # --- 4c. Over limit ---
        mock_cursor.fetchone.return_value = (31,)  # 31 sent, over limit
        result = limiter.allow("webhook")
        passed = result is False
        expected = "False (31 >= 30)"
        record(
            "4. Rate Limit Boundaries",
            "4c. Over limit",
            "allow('webhook') with 31/30 used",
            expected,
            f"Returned: {result}",
            passed,
        )

    # --- 4d. Database error during rate check ---
    with patch("database.get_conn", side_effect=Exception("DB down")):
        result = limiter.allow("webhook")
        # The code returns True on exception (fail-open!)
        passed = result is True
        expected = "True (fail-open on DB error)"
        record(
            "4. Rate Limit Boundaries",
            "4d. DB error during check",
            "allow() when DB throws exception",
            expected,
            f"Returned: {result} (fail-open!)",
            passed,
        )


# ---------------------------------------------------------------------------
# 5. Rapid Concurrent Requests — cache and observability
# ---------------------------------------------------------------------------

def test_5_concurrent_requests():
    print("\n=== 5. Rapid Concurrent Requests — cache & observability ===")

    from services.cache import MemoryCache, get_cache, invalidate_cache, _memory_cache
    from services.observability import MetricsCollector

    # --- 5a. Cache prefix invalidation race ---
    cache = MemoryCache()
    num_threads = 100

    # Populate cache
    for i in range(num_threads):
        cache.set(f"test:key:{i}", f"value_{i}", ttl=300)

    errors = []

    def invalidate_and_read(idx):
        try:
            if idx % 2 == 0:
                invalidate_cache("test:key:")
            else:
                cache.get(f"test:key:{idx}")
        except Exception as e:
            errors.append((idx, str(e)))

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(invalidate_and_read, i) for i in range(num_threads)]
        for f in as_completed(futures):
            f.result()  # Raise any exceptions

    passed = len(errors) == 0
    expected = "No exceptions during concurrent invalidation"
    record(
        "5. Concurrent Requests",
        "5a. Cache prefix invalidation race",
        f"{num_threads} concurrent invalidate/get calls",
        expected,
        f"Errors: {len(errors)}",
        passed,
    )

    # --- 5b. Observability _latencies concurrent appends ---
    mc = MetricsCollector()
    latency_errors = []

    def record_latency(idx):
        try:
            mc.observe_latency("GET", "/test", 200, 0.01 * idx)
        except Exception as e:
            latency_errors.append((idx, str(e)))

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(record_latency, i) for i in range(num_threads)]
        for f in as_completed(futures):
            f.result()

    # Check that we have approximately num_threads entries
    # Note: list.append is thread-safe in CPython due to GIL, but slicing isn't atomic
    actual_count = len(mc._latencies)
    passed = len(latency_errors) == 0 and actual_count > 0
    expected = f"No exceptions, ~{num_threads} entries"
    record(
        "5. Concurrent Requests",
        "5b. Observability concurrent appends",
        f"{num_threads} concurrent observe_latency calls",
        expected,
        f"Errors: {len(latency_errors)}, Entries: {actual_count}",
        passed,
    )

    # --- 5c. Active request counter race ---
    mc2 = MetricsCollector()
    counter_errors = []

    def inc_dec(idx):
        try:
            mc2.inc_active()
            mc2.dec_active()
        except Exception as e:
            counter_errors.append((idx, str(e)))

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(inc_dec, i) for i in range(num_threads)]
        for f in as_completed(futures):
            f.result()

    # Due to lack of locking, _active_requests may not be 0 after balanced inc/dec
    final_active = mc2._active_requests
    passed = len(counter_errors) == 0 and final_active == 0
    expected = "No exceptions, active=0 after balanced inc/dec"
    record(
        "5. Concurrent Requests",
        "5c. Active request counter race",
        f"{num_threads} concurrent inc/dec pairs",
        expected,
        f"Errors: {len(counter_errors)}, Final active: {final_active}",
        passed,
    )


# ---------------------------------------------------------------------------
# 6. DB Connection Failure — services/health.py
# ---------------------------------------------------------------------------

def test_6_db_connection_failure():
    print("\n=== 6. DB Connection Failure — services/health.py ===")

    app = _create_test_app()
    client = app.test_client()

    # --- 6a. Mock get_conn() to throw an exception, call /health/ready ---
    with patch("services.health.get_conn", side_effect=Exception("DB connection refused")):
        resp = client.get("/health/ready")
        data = resp.get_json()

        # The endpoint should catch the exception and mark database as unhealthy
        # It should return 503 with database listed as unhealthy
        db_status = data.get("checks", {}).get("database", "")
        passed = (
            resp.status_code == 503
            and "unhealthy" in db_status
        )
        expected = "503 with database=unhealthy"
        record(
            "6. DB Connection Failure",
            "6a. /health/ready with DB down",
            "GET /health/ready when get_conn() raises Exception",
            expected,
            f"{resp.status_code}: checks.database='{db_status}'",
            passed,
        )

    # --- 6b. Verify no NameError in finally block of _get_last_detection_time() ---
    # The finally block references `conn` which could be None if get_conn() fails
    # before assignment. The code initializes conn = None at the top, so it should
    # be safe. We verify by checking the response doesn't contain a NameError.
    with patch("services.health.get_conn", side_effect=Exception("DB connection refused")):
        resp = client.get("/health/ready")
        data = resp.get_json()
        detection_status = data.get("checks", {}).get("detection", "")
        # _get_last_detection_time catches exceptions internally, so detection
        # should show "no data" or "error:" but NOT a NameError
        has_name_error = "NameError" in detection_status
        passed = not has_name_error
        expected = "No NameError in _get_last_detection_time() finally block"
        record(
            "6. DB Connection Failure",
            "6b. No NameError in finally block",
            "_get_last_detection_time() when get_conn() raises",
            expected,
            f"detection='{detection_status}'",
            passed,
        )


# ---------------------------------------------------------------------------
# 7. Missing Env Vars — api.py require_api_key, services/security.py JWT
# ---------------------------------------------------------------------------

def test_7_missing_env_vars():
    print("\n=== 7. Missing Env Vars — require_api_key & JWT ===")

    # --- 7a. Unset VIGIL_API_KEY, call a @require_api_key protected endpoint ---
    # Save original value
    original_api_key = os.environ.get("VIGIL_API_KEY")

    # Remove VIGIL_API_KEY
    if "VIGIL_API_KEY" in os.environ:
        del os.environ["VIGIL_API_KEY"]

    try:
        # We need to re-create the app so it picks up the missing env var
        # But require_api_key is defined inside create_app(), so we need a fresh app
        app = _create_test_app()
        client = app.test_client()

        resp = client.post(
            "/backtest/run",
            data=json.dumps({
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "tickers": ["AAPL"],
            }),
            content_type="application/json",
            headers={"X-API-KEY": "some-key"},
        )
        # When VIGIL_API_KEY is not set, require_api_key returns 500 with
        # {"error": "API key not configured"}
        resp_data = resp.get_json()
        error_msg = resp_data.get("error", "") if resp_data else ""
        passed = resp.status_code == 500 and "API key not configured" in error_msg
        expected = "500 with 'API key not configured' (fail-closed)"
        record(
            "7. Missing Env Vars",
            "7a. Unset VIGIL_API_KEY",
            "POST /backtest/run without VIGIL_API_KEY set",
            expected,
            f"{resp.status_code}: {error_msg}",
            passed,
        )
    finally:
        # Restore original value
        if original_api_key is not None:
            os.environ["VIGIL_API_KEY"] = original_api_key

    # --- 7b. Unset JWT_SECRET — security module raises RuntimeError at import ---
    original_jwt_secret = os.environ.get("JWT_SECRET")
    original_secret_key = os.environ.get("SECRET_KEY")

    # Remove both env vars
    if "JWT_SECRET" in os.environ:
        del os.environ["JWT_SECRET"]
    if "SECRET_KEY" in os.environ:
        del os.environ["SECRET_KEY"]

    try:
        # Remove the module from sys.modules so it re-imports
        import sys
        modules_to_remove = [k for k in sys.modules if k.startswith("services.security")]
        for mod in modules_to_remove:
            del sys.modules[mod]

        raised_runtime_error = False
        actual_exception = None
        try:
            import services.security  # noqa: F401
        except RuntimeError as e:
            raised_runtime_error = True
            actual_exception = str(e)

        passed = raised_runtime_error
        expected = "RuntimeError at import time (fail-closed at startup)"
        record(
            "7. Missing Env Vars",
            "7b. Unset JWT_SECRET",
            "import services.security without JWT_SECRET",
            expected,
            f"RuntimeError raised: {raised_runtime_error}, msg: '{actual_exception}'",
            passed,
        )
    finally:
        # Restore original values
        if original_jwt_secret is not None:
            os.environ["JWT_SECRET"] = original_jwt_secret
        if original_secret_key is not None:
            os.environ["SECRET_KEY"] = original_secret_key

        # Re-import to restore module state
        import sys
        modules_to_remove = [k for k in sys.modules if k.startswith("services.security")]
        for mod in modules_to_remove:
            del sys.modules[mod]
        import services.security  # noqa: F401


# ---------------------------------------------------------------------------
# 8. Socket.IO Edge Cases
# ---------------------------------------------------------------------------

def test_8_socketio_edge_cases():
    print("\n=== 8. Socket.IO Edge Cases ===")

    # --- 8a. Flask app WITHOUT SocketIO initialized, try to call emit_alert ---
    from flask import Flask
    app_no_socketio = Flask(__name__)
    app_no_socketio.config['SECRET_KEY'] = 'test'

    # The app doesn't have emit_alert attribute since it was never set
    has_emit_alert = hasattr(app_no_socketio, "emit_alert")
    passed = not has_emit_alert
    expected = "No emit_alert attribute (graceful absence)"
    record(
        "8. Socket.IO Edge Cases",
        "8a. App without SocketIO",
        "Flask app without SocketIO, check for emit_alert",
        expected,
        f"hasattr(app, 'emit_alert'): {has_emit_alert}",
        passed,
    )


# ---------------------------------------------------------------------------
# Main entry point — run all tests and print summary
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Vigil Adversarial Edge Case Simulation")
    print("=" * 60)

    test_functions = [
        test_1_malformed_payloads,
        test_2_empty_required_fields,
        test_3_out_of_sequence_lock,
        test_4_rate_limit_boundaries,
        test_5_concurrent_requests,
        test_6_db_connection_failure,
        test_7_missing_env_vars,
        test_8_socketio_edge_cases,
    ]

    failures = []

    for test_fn in test_functions:
        try:
            test_fn()
        except Exception as e:
            print(f"  [ERROR] {test_fn.__name__} raised: {type(e).__name__}: {e}")
            traceback.print_exc()
            failures.append({
                "category": "SETUP ERROR",
                "test": test_fn.__name__,
                "failure_surface": "Test function execution",
                "expected": "No exception",
                "actual": f"{type(e).__name__}: {e}",
                "passed": False,
            })

    # Summary report
    print("\n" + "=" * 60)
    print("SUMMARY REPORT")
    print("=" * 60)

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = total - passed_count

    print(f"Total tests: {total}")
    print(f"PASS: {passed_count}")
    print(f"FAIL: {failed_count}")

    if failures:
        print(f"\n--- Additional failures ({len(failures)}) ---")
        for f in failures:
            print(f"  [FAIL] {f['test']}: {f['actual']}")

    if failed_count > 0:
        print("\n--- Failed Tests ---")
        for r in results:
            if not r["passed"]:
                print(f"  [FAIL] {r['test']}")
                print(f"         Surface: {r['failure_surface']}")
                print(f"         Expected: {r['expected']}")
                print(f"         Actual:   {r['actual']}")

    print("\n" + "=" * 60)
    if failed_count == 0:
        print("ALL TESTS PASSED")
    else:
        print(f"{failed_count} TEST(S) FAILED")
    print("=" * 60)

    # --- 8b. With SocketIO initialized but no connected clients, call emit_alert() ---
    app = _create_test_app()
    client = app.test_client()

    # emit_alert is attached to the app by create_app()
    # With no WebSocket clients connected, socketio.emit() should be a no-op
    emit_error = None
    try:
        app.emit_alert({
            "ticker": "TEST",
            "signal_type": "VOLUME_SPIKE_UP",
            "state": "BREAKOUT",
        })
    except Exception as e:
        emit_error = f"{type(e).__name__}: {e}"

    passed = emit_error is None
    expected = "No exception (emit with no clients is a no-op)"
    record(
        "8. Socket.IO Edge Cases",
        "8b. emit_alert with no clients",
        "app.emit_alert() with no connected WebSocket clients",
        expected,
        f"Error: {emit_error}" if emit_error else "No error",
        passed,
    )