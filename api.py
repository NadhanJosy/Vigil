"""
Vigil API — Flask application with SocketIO, observability, and security.

Phase 1 changes:
- Removed BackgroundScheduler (competing with scheduler.py)
- Added structured JSON logging
- Added request latency tracking middleware
- Added health check blueprint
- Added input validation via Marshmallow schemas
- Added rate limiting via Flask-Limiter
- Added JWT authentication endpoint
- Restricted CORS origins via environment variable
"""

import os
import json
import logging
import threading
from datetime import datetime, timezone
from flask import Flask, jsonify, send_from_directory, request, abort
from flask_socketio import SocketIO, emit

from database import (init_db, get_alerts, save_alert,
                      add_to_watchlist, remove_from_watchlist, get_watchlist, get_system_metrics,
                      save_backtest_run, save_backtest_results, get_backtest_runs, get_backtest_results)
from data import run_detection, run_backfill, compute_regime
from services.observability import (
    configure_structured_logging,
    register_metrics_middleware,
    metrics,
)
from services.health import health_bp
from services.security import (
    alert_query_schema,
    watchlist_schema,
    validate_query_params,
    validate_json_body,
    require_jwt,
    generate_jwt,
    get_allowed_origins,
    get_rate_limits,
)

# ---------------------------------------------------------------------------
# Application Factory
# ---------------------------------------------------------------------------

def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "vigil-secret-dev")

    # Structured JSON logging
    configure_structured_logging()

    # SocketIO with restricted CORS
    allowed_origins = get_allowed_origins()
    socketio = SocketIO(app, cors_allowed_origins=allowed_origins)

    # Initialize database
    init_db()

    # Register metrics middleware
    register_metrics_middleware(app)

    # Register health check blueprint
    app.register_blueprint(health_bp)

    # -----------------------------------------------------------------------
    # Rate Limiting (Flask-Limiter)
    # -----------------------------------------------------------------------
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
        limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=["200 per day", "50 per hour"],
            storage_uri=os.environ.get("REDIS_URL", "memory://"),
        )
    except ImportError:
        limiter = None  # Graceful degradation if flask-limiter not installed

    def _limit(spec: str):
        """Apply rate limit if limiter is available."""
        if limiter:
            return limiter.limit(spec)
        return lambda f: f  # No-op decorator

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def require_api_key(f):
        """Decorator to protect sensitive management endpoints."""
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            api_key = os.environ.get("VIGIL_API_KEY")
            if api_key and request.headers.get('X-API-KEY') != api_key:
                abort(401)
            return f(*args, **kwargs)
        return decorated_function

    DECAY_PROFILES = {
        "VOLUME_SPIKE_UP":       (8,  10),
        "VOLUME_SPIKE_DOWN":     (8,  10),
        "ACCUMULATION_DETECTED": (36, 20),
    }

    def compute_decay(signal_type, created_at):
        if created_at is None:
            return {"pct": 50, "status": "UNKNOWN", "hours_old": 0, "half_life": 8}
        half_life, min_strength = DECAY_PROFILES.get(signal_type, (8, 10))
        now       = datetime.now(timezone.utc)
        hours_old = (now - created_at).total_seconds() / 3600
        strength  = max(min_strength, int((0.5 ** (hours_old / half_life)) * 100))
        if strength < 15:
            status = "EXPIRED"
        elif hours_old < half_life * 0.5:
            status = "FRESH"
        elif hours_old < half_life:
            status = "DECAYING"
        else:
            status = "DETERIORATING"
        return {"pct": strength, "status": status,
                "hours_old": round(hours_old, 1), "half_life": half_life}

    # -----------------------------------------------------------------------
    # Routes
    # -----------------------------------------------------------------------

    @app.route("/")
    def index():
        return send_from_directory("templates", "dashboard.html")

    @app.route("/legacy")
    def legacy():
        return send_from_directory("templates", "index.html")

    @app.route("/alerts")
    @_limit("30 per minute")
    @validate_query_params(alert_query_schema)
    def alerts():
        params = getattr(request, 'validated_args', {})
        ticker      = params.get("ticker") or request.args.get("ticker")
        signal_type = params.get("signal_type") or request.args.get("signal_type")
        state       = params.get("state") or request.args.get("state")
        limit       = params.get("limit", request.args.get("limit", 50, type=int))
        offset      = params.get("offset", request.args.get("offset", 0, type=int))

        data   = get_alerts(ticker=ticker, signal_type=signal_type, state=state, limit=limit, offset=offset)
        result = []
        for row in data:
            decay = compute_decay(row[5], row[19])
            result.append({
                "id":                    row[0],
                "ticker":                row[1],
                "date":                  row[2],
                "volume_ratio":          round(float(row[3]), 2) if row[3] is not None else None,
                "change_pct":            round(float(row[4]), 2) if row[4] is not None else None,
                "signal_type":           row[5],
                "state":                 row[6],
                "outcome_pct":           round(float(row[7]), 2) if row[7] is not None else None,
                "outcome_result":        row[8],
                "trap_conviction":       row[9],
                "trap_type":             row[10],
                "trap_reasons":          json.loads(row[11]) if row[11] else [],
                "accum_conviction":      row[12],
                "accum_days":            row[13],
                "accum_price_range_pct": row[14],
                "mtf_weekly":            row[15],
                "mtf_daily":             row[16],
                "mtf_recent":            row[17],
                "mtf_alignment":         row[18],
                "decay":                 decay,
                "signal_combination":    row[20],
                "edge_score":            row[21],
                "days_in_state":         row[22],
                "adx_strength":          row[23],
                "momentum_score":        row[24],
                "volatility_desc":       row[25],
                "sector_gate":           row[26],
                "prev_state":            row[27],
                "regime":                row[28],
                "action":                row[29],
                "summary":               row[30],
            })
        return jsonify(result)

    @app.route("/regime")
    @_limit("10 per minute")
    def regime():
        import yfinance as yf
        try:
            spy_history = yf.Ticker("SPY").history(period="60d")
            current_regime = compute_regime(spy_history)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        return jsonify({"regime": current_regime})

    @app.route("/trigger")
    @_limit("5 per hour")
    @require_api_key
    def trigger():
        threading.Thread(target=run_detection).start()
        return jsonify({"status": "detection started in background"})

    @app.route("/backfill")
    @_limit("2 per hour")
    @require_api_key
    def backfill():
        threading.Thread(target=run_backfill).start()
        return jsonify({"status": "backfill started in background"})

    @app.route("/stats")
    @_limit("10 per minute")
    def stats():
        return jsonify(get_system_metrics())

    @app.route("/evaluate")
    @_limit("5 per hour")
    def evaluate():
        from database import evaluate_outcomes
        evaluate_outcomes()
        return jsonify({"status": "outcomes evaluated"})

    @app.route("/watchlist", methods=["GET", "POST", "DELETE"])
    @_limit("20 per minute")
    def watchlist():
        if request.method == "POST":
            ticker = request.json.get("ticker") if request.json else None
            if ticker:
                add_to_watchlist(ticker)
            return jsonify({"status": "added"})
        elif request.method == "DELETE":
            ticker = request.args.get("ticker")
            if ticker:
                remove_from_watchlist(ticker)
            return jsonify({"status": "removed"})
        else:
            return jsonify(get_watchlist())

    # -----------------------------------------------------------------------
    # Backtesting Endpoints
    # -----------------------------------------------------------------------

    @app.route("/backtest/runs", methods=["GET"])
    @_limit("10 per minute")
    def backtest_runs():
        """List historical backtest runs."""
        runs = get_backtest_runs()
        return jsonify(runs)

    @app.route("/backtest/results", methods=["GET"])
    @_limit("10 per minute")
    def backtest_results():
        """Get results for a specific backtest run."""
        run_id = request.args.get("run_id", type=int)
        if run_id is None:
            return jsonify({"error": "Missing run_id parameter"}), 400
        results = get_backtest_results(run_id)
        return jsonify(results)

    @app.route("/backtest/run", methods=["POST"])
    @_limit("2 per hour")
    @require_api_key
    @validate_json_body({
        "name": {"type": "string", "required": False},
        "start_date": {"type": "string", "required": True},
        "end_date": {"type": "string", "required": True},
        "tickers": {"type": "list", "required": True},
        "capital": {"type": "number", "required": False, "default": 100000},
        "slippage_bps": {"type": "number", "required": False, "default": 5},
        "commission_bps": {"type": "number", "required": False, "default": 10},
    })
    def backtest_run():
        """Start a backtest run asynchronously."""
        from backtest import BacktestEngine, BacktestConfig, compute_metrics
        from datetime import datetime as dt

        data = request.get_json(silent=True) or {}
        config = BacktestConfig(
            name=data.get("name", f"backtest_{dt.now().strftime('%Y%m%d_%H%M%S')}"),
            start_date=data["start_date"],
            end_date=data["end_date"],
            tickers=data["tickers"],
            capital=data.get("capital", 100000),
            slippage_bps=data.get("slippage_bps", 5),
            commission_bps=data.get("commission_bps", 10),
        )

        def _run_backtest(cfg: BacktestConfig):
            engine = BacktestEngine(cfg)
            result = engine.run()
            save_backtest_run(
                name=cfg.name,
                config=cfg.to_dict(),
                start_date=cfg.start_date,
                end_date=cfg.end_date,
                tickers=cfg.tickers,
            )
            # Note: run_id would be returned by save_backtest_run in a full implementation
            save_backtest_results(
                run_id=1,  # Placeholder - would be actual run_id from above
                results=[t.__dict__ for t in result.trades],
                metrics=result.metrics.__dict__ if result.metrics else {},
            )

        threading.Thread(target=_run_backtest, args=(config,)).start()
        return jsonify({"status": "backtest started", "config": config.to_dict()})

    @app.route("/auth/token", methods=["POST"])
    @_limit("10 per hour")
    def auth_token():
        """Generate JWT token for API access."""
        data = request.get_json(silent=True) or {}
        api_key = data.get("api_key")
        if not api_key:
            return jsonify({"error": "Missing api_key"}), 400
        token = generate_jwt(api_key)
        if token is None:
            return jsonify({"error": "Invalid API key"}), 401
        return jsonify({"token": token})

    # -----------------------------------------------------------------------
    # SocketIO Event Handlers
    # -----------------------------------------------------------------------

    @socketio.on("connect")
    def handle_connect():
        emit("connected", {"message": "Connected to Vigil"})

    @socketio.on("disconnect")
    def handle_disconnect():
        pass

    def emit_alert(alert_data: dict) -> None:
        from config.events import build_alert_payload
        socketio.emit("new_alert", build_alert_payload(alert_data), namespace="/alerts")

    def emit_regime_shift(old_regime: str, new_regime: str) -> None:
        from config.events import build_regime_payload
        socketio.emit("regime_shift", build_regime_payload(old_regime, new_regime), namespace="/regime")

    app.emit_alert = emit_alert
    app.emit_regime_shift = emit_regime_shift

    # Store socketio on app for access by other modules
    app.socketio = socketio
    return app


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

app = create_app()
socketio = app.socketio

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, debug=False, host="0.0.0.0", port=port)
