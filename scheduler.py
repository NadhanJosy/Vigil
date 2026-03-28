from apscheduler.schedulers.blocking import BlockingScheduler
import subprocess
import datetime

scheduler = BlockingScheduler()

@scheduler.scheduled_job("cron", hour=21, minute=0, timezone="America/New_York")
def run_detection():
    print(f"Running detection at {datetime.datetime.now()}")
    subprocess.run(["python", "data.py"])

print("Scheduler started — detection runs daily at 21:00 ET")
scheduler.start()


