from apscheduler.schedulers.blocking import BlockingScheduler
import subprocess
import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
scheduler = BlockingScheduler()

@scheduler.scheduled_job("cron", hour=21, minute=0, timezone="America/New_York")
def run_detection():
    logger.info(f"Triggering detection job via subprocess...")
    subprocess.run(["python", "data.py"])

logger.info("Scheduler started — detection runs daily at 21:00 ET")
scheduler.start()
