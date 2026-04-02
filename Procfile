web: gunicorn --bind 0.0.0.0:$PORT --workers 2 --worker-class eventlet --timeout 120 --access-logfile - api:app
scheduler: python3 scheduler.py
