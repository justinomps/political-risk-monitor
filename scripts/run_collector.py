#!/usr/bin/env python
"""
Collector Runner - Runs the news collection process
Can be scheduled with cron or Windows Task Scheduler
"""

import logging
import sys
import os
from dotenv import load_dotenv

# Make sure we can import from our module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

from modules.collector import NewsCollector

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("collector.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('collector_runner')

def main():
    """Run the news collector"""
    try:
        logger.info("Starting news collection")
        collector = NewsCollector()
        new_count = collector.collect_all()
        logger.info(f"News collection complete. {new_count} new articles collected.")
        return True
    except Exception as e:
        logger.error(f"Error in news collection: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)