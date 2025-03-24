"""
Tracker module - Provides time-series analysis of political risk indicators
"""

import datetime
import logging
import pymongo
from config import (
    COLLECTION_EVENTS,
    COLLECTION_SUMMARIES,
    CATEGORIES
)
from modules.database import get_collection

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('tracker')

class IndicatorTracker:
    """
    Tracks political risk indicators over time and provides trend analysis.
    """
    
    def __init__(self):
        # Connect to collections
        self.events_collection = get_collection(COLLECTION_EVENTS)
        self.summaries_collection = get_collection(COLLECTION_SUMMARIES)
        
        # Cache for category history
        self.category_history_cache = {}
        
    def get_category_trends(self, category_id, days=90):
        """
        Get trend data for a specific category over time.
        
        Args:
            category_id: The category identifier
            days: Number of days to look back
            
        Returns:
            Dictionary with trend data
        """
        # Get historical status
        history = self.get_category_history(category_id, days)
        
        if not history:
            return {
                'trend': 'stable',
                'days_at_current_level': 0,
                'history': []
            }
            
        # Get current status (most recent)
        current_status = history[-1][1] if history else 'green'
        
        # Count days at current level
        days_at_current_level = 0
        for i in range(len(history) - 1, -1, -1):
            if history[i][1] == current_status:
                days_at_current_level += 1
            else:
                break
                
        # Determine trend
        trend = 'stable'  # Default
        if len(history) >= 2:
            # Compare first and last status
            first_status = history[0][1]
            last_status = history[-1][1]
            
            severity_levels = {'green': 0, 'yellow': 1, 'orange': 2, 'red': 3}
            
            if severity_levels.get(last_status, 0) > severity_levels.get(first_status, 0):
                trend = 'deteriorating'
            elif severity_levels.get(last_status, 0) < severity_levels.get(first_status, 0):
                trend = 'improving'
                
            # Check for acceleration patterns
            if trend == 'deteriorating':
                # Count status changes
                changes = 0
                for i in range(1, len(history)):
                    if history[i][1] != history[i-1][1]:
                        changes += 1
                        
                # If many changes in short period, flag as rapid
                if changes >= 2 and days <= 30:
                    trend = 'rapidly_deteriorating'
                    
        return {
            'trend': trend,
            'days_at_current_level': days_at_current_level,
            'history': history
        }
    
    def get_category_history(self, category_id, days=90):
        """
        Get historical status data for a category
        
        Args:
            category_id: Category identifier
            days: Number of days of history to retrieve
        
        Returns:
            List of [date, severity] pairs
        """
        # Check cache first
        cache_key = f"{category_id}_{days}"
        if cache_key in self.category_history_cache:
            # Check if cache is still fresh (less than 1 hour old)
            if datetime.datetime.now() - self.category_history_cache[cache_key]['timestamp'] < datetime.timedelta(hours=1):
                return self.category_history_cache[cache_key]['data']
        
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        cutoff_date_str = cutoff_date.isoformat()
        
        # Get past summaries
        past_summaries = list(self.summaries_collection.find(
            {'date': {'$gte': cutoff_date_str}},
            {'date': 1, f'categories.{category_id}.current_severity': 1}
        ).sort('date', 1))
        
        history = []
        for summary in past_summaries:
            try:
                date = datetime.datetime.fromisoformat(summary.get('date', ''))
                severity = summary.get('categories', {}).get(category_id, {}).get('current_severity', 'green')
                history.append([date.strftime('%Y-%m-%d'), severity])
            except:
                continue
                
        # Update cache
        self.category_history_cache[cache_key] = {
            'data': history,
            'timestamp': datetime.datetime.now()
        }
            
        return history
    
    def get_threshold_history(self, days=90):
        """
        Get the history of threshold crossings
        
        Args:
            days: Number of days to look back
            
        Returns:
            Dictionary with threshold history data
        """
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        cutoff_date_str = cutoff_date.isoformat()
        
        # Get past summaries
        past_summaries = list(self.summaries_collection.find(
            {'date': {'$gte': cutoff_date_str}},
            {
                'date': 1, 
                'thresholds.orange_threshold_crossed': 1,
                'thresholds.red_threshold_crossed': 1,
                'alert_level': 1
            }
        ).sort('date', 1))
        
        # Extract history data
        dates = []
        orange_threshold = []
        red_threshold = []
        alert_levels = []
        
        for summary in past_summaries:
            try:
                date = datetime.datetime.fromisoformat(summary.get('date', ''))
                dates.append(date.strftime('%Y-%m-%d'))
                
                # Get threshold status
                thresholds = summary.get('thresholds', {})
                orange_threshold.append(thresholds.get('orange_threshold_crossed', False))
                red_threshold.append(thresholds.get('red_threshold_crossed', False))
                
                # Get alert level
                alert_levels.append(summary.get('alert_level', 1))
            except:
                continue
                
        return {
            'dates': dates,
            'orange_threshold': orange_threshold,
            'red_threshold': red_threshold,
            'alert_levels': alert_levels
        }
    
    def get_confirmed_indicators_count(self):
        """
        Get count of confirmed indicators by severity
        
        Returns:
            Dictionary with counts
        """
        # Get the most recent summary
        latest_summary = self.summaries_collection.find_one(sort=[('date', pymongo.DESCENDING)])
        
        if not latest_summary:
            return {
                'yellow': 0,
                'orange': 0,
                'red': 0
            }
            
        # Count confirmed indicators by severity
        yellow_count = 0
        orange_count = 0
        red_count = 0
        
        for cat_id, cat_data in latest_summary.get('categories', {}).items():
            severity = cat_data.get('current_severity', 'green')
            confirmed = cat_data.get('confirmed', False)
            
            if confirmed:
                if severity == 'yellow':
                    yellow_count += 1
                elif severity == 'orange':
                    orange_count += 1
                elif severity == 'red':
                    red_count += 1
                    
        return {
            'yellow': yellow_count,
            'orange': orange_count,
            'red': red_count
        }
    
    def get_accelerating_categories(self):
        """
        Get list of categories with rapid acceleration patterns
        
        Returns:
            List of category information
        """
        accelerating = []
        
        # Check each category
        for category_id in CATEGORIES.keys():
            trend_data = self.get_category_trends(category_id, days=60)
            
            if trend_data['trend'] == 'rapidly_deteriorating':
                accelerating.append({
                    'category_id': category_id,
                    'name': CATEGORIES[category_id]['name'],
                    'current_status': trend_data['history'][-1][1] if trend_data['history'] else 'green',
                    'days_at_current_level': trend_data['days_at_current_level']
                })
                
        return accelerating
    
    def get_alert_level_statistics(self, days=90):
        """
        Get statistics about alert levels over time
        
        Args:
            days: Number of days to look back
            
        Returns:
            Dictionary with alert level statistics
        """
        threshold_history = self.get_threshold_history(days)
        
        # Count days at each alert level
        alert_level_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        
        for level in threshold_history.get('alert_levels', []):
            if level in alert_level_counts:
                alert_level_counts[level] += 1
                
        # Get current alert level
        current_level = threshold_history.get('alert_levels', [1])[-1] if threshold_history.get('alert_levels') else 1
        
        # Count consecutive days at current level
        consecutive_days = 0
        for i in range(len(threshold_history.get('alert_levels', [])) - 1, -1, -1):
            if threshold_history['alert_levels'][i] == current_level:
                consecutive_days += 1
            else:
                break
                
        return {
            'level_counts': alert_level_counts,
            'current_level': current_level,
            'consecutive_days': consecutive_days
        }
    
    def check_category_persistence(self, category_id, events):
        """
        Check if a category status has persisted long enough to be confirmed
        
        Args:
            category_id: Category identifier
            events: List of events for this category
        
        Returns:
            Dictionary with persistence data
        """
        persistence_data = {
            'confirmed': False,
            'duration_days': 0,
            'rapid_escalation': False
        }
        
        if not events:
            return persistence_data
            
        # Sort events by detected date (newest first)
        sorted_events = sorted(events, key=lambda e: e.get('detected_date', ''), reverse=True)
        
        # Get the newest event
        newest_event = sorted_events[0]
        severity = newest_event.get('severity')
        
        # Calculate duration
        start_date_str = newest_event.get('start_date', newest_event.get('detected_date'))
        if start_date_str:
            start_date = datetime.datetime.fromisoformat(start_date_str)
            duration_days = (datetime.datetime.now() - start_date).days
            persistence_data['duration_days'] = duration_days
            
            # Apply persistence thresholds
            if severity == 'yellow' and duration_days >= 30:
                persistence_data['confirmed'] = True
            elif severity == 'orange' and duration_days >= 14:
                persistence_data['confirmed'] = True
            elif severity == 'red':
                # Red status is immediately confirmed
                persistence_data['confirmed'] = True
                
        # Check for rapid escalation (green to orange/red within 60 days)
        if len(sorted_events) >= 2:
            # Get previous status
            previous_event = sorted_events[1]
            prev_severity = previous_event.get('severity')
            
            if prev_severity == 'green' and severity in ['orange', 'red']:
                # Check how quickly it escalated
                prev_date = datetime.datetime.fromisoformat(previous_event.get('detected_date', ''))
                current_date = datetime.datetime.fromisoformat(newest_event.get('detected_date', ''))
                
                if (current_date - prev_date).days <= 60:
                    persistence_data['rapid_escalation'] = True
                    
        return persistence_data
    
    def calculate_alert_level(self, summary):
        """
        Calculate the tiered alert level based on current status
        
        Args:
            summary: Current summary data
            
        Returns:
            Alert level (1-5) and recommendations
        """
        # Count confirmed events by severity
        yellow_count = 0
        orange_count = 0
        red_count = 0
        
        for cat_id, cat_data in summary['categories'].items():
            severity = cat_data['current_severity']
            # Only count confirmed events
            if cat_data.get('confirmed', False):
                if severity == 'yellow':
                    yellow_count += 1
                elif severity == 'orange':
                    orange_count += 1
                elif severity == 'red':
                    red_count += 1
                    
        # Count rapid escalations as an additional orange
        rapid_escalation_count = sum(1 for cat_data in summary['categories'].values() 
                                    if cat_data.get('rapid_escalation', False))
        
        effective_orange_count = orange_count + rapid_escalation_count
        
        # Determine alert level using tiered approach
        alert_level = 1  # Default level
        recommendations = "Normal monitoring, no action required."
        
        if yellow_count >= 3 or (yellow_count >= 1 and orange_count >= 1):
            alert_level = 2
            recommendations = "Review financial portability, organize documents, research exit options."
            
        if effective_orange_count >= 3:
            alert_level = 3
            recommendations = "Transfer some assets abroad, obtain second residency options, prepare property for potential sale."
            
        if effective_orange_count >= 4 or red_count >= 1:
            alert_level = 4
            recommendations = "Move liquid assets offshore, send family members ahead for 'extended visits,' prepare property for immediate sale."
            
        if red_count >= 2:
            alert_level = 5
            recommendations = "Execute departure plan immediately, activate emergency protocols."
            
        return alert_level, recommendations

# For testing
if __name__ == "__main__":
    tracker = IndicatorTracker()
    for category_id in CATEGORIES.keys():
        trend = tracker.get_category_trends(category_id)
        print(f"Category {category_id}: {trend['trend']} for {trend['days_at_current_level']} days")