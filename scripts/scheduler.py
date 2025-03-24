#!/usr/bin/env python
"""
Scheduler - Runs collection and analysis processes at scheduled intervals
Use this instead of cron/task scheduler for simple deployment
"""

import time
import logging
import threading
import schedule
from modules.collector import NewsCollector
from modules.analyzer import NewsAnalyzer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('scheduler')

def run_collection():
    """Run the news collection process"""
    try:
        logger.info("Starting scheduled news collection")
        collector = NewsCollector()
        new_count = collector.collect_all()
        logger.info(f"Scheduled collection complete. {new_count} new articles collected.")
    except Exception as e:
        logger.error(f"Error in scheduled collection: {str(e)}")

def run_analysis():
    """Run the news analysis process"""
    try:
        logger.info("Starting scheduled news analysis")
        analyzer = NewsAnalyzer()
        count = analyzer.analyze_recent_articles()
        logger.info(f"Scheduled analysis complete. {count} articles analyzed.")
    except Exception as e:
        logger.error(f"Error in scheduled analysis: {str(e)}")

def run_threaded(job_func):
    """Run a function in a thread"""
    job_thread = threading.Thread(target=job_func)
    job_thread.start()

def main():
    """Set up and run the scheduler"""
    # Schedule collection to run every 3 hours
    schedule.every(3).hours.do(run_threaded, run_collection)
    
    # Schedule analysis to run every 6 hours
    schedule.every(6).hours.do(run_threaded, run_analysis)
    
    # Also schedule analysis to run 15 minutes after each collection
    # This ensures new articles get analyzed soon after collection
    schedule.every(3).hours.do(lambda: schedule.every(15).minutes.do(run_threaded, run_analysis).tag('one-time')).tag('collection-trigger')
    
    # Run collection immediately on startup
    run_threaded(run_collection)
    
    # Run analysis 15 minutes after startup
    schedule.every(15).minutes.do(run_threaded, run_analysis).tag('one-time')
    
    logger.info("Scheduler started. Press Ctrl+C to exit.")
    
    # Run the scheduler loop
    while True:
        try:
            # Run pending scheduled tasks
            schedule.run_pending()
            
            # Clear one-time tasks that have run
            for job in schedule.get_jobs('one-time'):
                if job.last_run is not None:
                    schedule.cancel_job(job)
            
            # Wait before checking again
            time.sleep(60)  # Check every minute
            
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user.")
            break
        except Exception as e:
            logger.error(f"Error in scheduler: {str(e)}")
            time.sleep(60)  # Wait a minute and try again

if __name__ == "__main__":
    main()