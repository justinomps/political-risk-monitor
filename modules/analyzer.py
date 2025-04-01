import datetime
import logging
import time
import json
import os
import requests
from config import (
    ANTHROPIC_API_KEY,
    CATEGORIES,
    COLLECTION_ARTICLES,
    COLLECTION_EVENTS,
    COLLECTION_SUMMARIES
)
from modules.database import get_collection
from modules.tracker import IndicatorTracker

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('analyzer')

class NewsAnalyzer:
    """
    Analyzes news articles and categorizes them according to the 
    Despotism Readiness Framework.
    """
    
    def __init__(self):
        # Connect to collections
        self.articles_collection = get_collection(COLLECTION_ARTICLES)
        self.events_collection = get_collection(COLLECTION_EVENTS)
        self.summaries_collection = get_collection(COLLECTION_SUMMARIES)
        
        # Initialize tracker for trend analysis
        self.tracker = IndicatorTracker()
        
        # Load category definitions from config
        self.categories = CATEGORIES
    
    def analyze_recent_articles(self, days=1, limit=20):
        """Analyze articles collected in the past specified days"""
        # Set whether to use Claude API for analysis - can be toggled
        self.USE_CLAUDE_ANALYSIS = True
        
        # Set keyword match threshold for Claude analysis
        self.CLAUDE_MATCH_THRESHOLD = 1
        
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        cutoff_date_str = cutoff_date.isoformat()
        
        # Get unanalyzed articles
        query = {
            'collected_at': {'$gte': cutoff_date_str},
            'analyzed': False
        }
        
        articles = list(self.articles_collection.find(query).limit(limit))
        logger.info(f"Found {len(articles)} unanalyzed recent articles")
        
        if not articles:
            logger.info("No articles to analyze")
            return 0
        
        analyzed_count = 0
        
        for article in articles:
            try:
                logger.info(f"Analyzing article: {article.get('title', 'No title')}")
                
                # First stage: keyword-based analysis
                keyword_results = self._keyword_analysis(article)
                
                # Second stage: Claude analysis for articles that matched keywords
                claude_results = None
                if keyword_results['categorized'] and self.USE_CLAUDE_ANALYSIS and keyword_results.get('should_use_claude', False):
                    claude_results = self._claude_analysis(article, keyword_results)
                
                # Combine results
                analysis_results = self._combine_analysis_results(keyword_results, claude_results)
                
                # Update article with analysis results
                self.articles_collection.update_one(
                    {'_id': article['_id']},
                    {'$set': {
                        'analyzed': True,
                        'analysis_date': datetime.datetime.now().isoformat(),
                        'analysis_results': analysis_results
                    }}
                )
                
                # For categorized articles, create events
                if analysis_results['categorized']:
                    self._create_events(article, analysis_results)
                
                analyzed_count += 1
                
                # Slight delay to avoid overwhelming Claude API
                if claude_results:
                    time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error analyzing article {article.get('_id')}: {str(e)}")
        
        # Generate summary after analysis
        if analyzed_count > 0:
            self._generate_summary()
        
        logger.info(f"Completed analysis of {analyzed_count} articles")
        return analyzed_count
    
def _keyword_analysis(self, article):
    """Perform first-stage keyword-based analysis with scoring for Claude decision"""
    # Combine title and content for analysis
    text = f"{article.get('title', '')} {article.get('content', '')}".lower()
    
    results = {
        'categorized': False,
        'categories': {},
        'method': 'keyword',
        'should_use_claude': False,
        'match_count': 0
    }
    
    # Check each category
    for category_id, category_data in self.categories.items():
        # Default to 'green' (no concern)
        severity = 'green'
        category_match_count = 0
        
        # Check for keyword matches of increasing severity
        for keyword in category_data.get('keywords', []):
            if keyword.lower() in text:
                severity = 'yellow'  # Base match moves to yellow
                category_match_count += 1
                break
        
        # Only check higher levels if already at yellow
        if severity == 'yellow':
            for indicator in category_data.get('orange_indicators', []):
                if indicator.lower() in text:
                    severity = 'orange'
                    category_match_count += 2  # Orange matches count more
                    break
            
            if severity == 'orange':
                for indicator in category_data.get('red_indicators', []):
                    if indicator.lower() in text:
                        severity = 'red'
                        category_match_count += 3  # Red matches count even more
                        break
        
        # Record the result
        results['categories'][category_id] = severity
        results['match_count'] += category_match_count
        
        # If any category is not green, mark as categorized
        if severity != 'green':
            results['categorized'] = True
            # Set should_use_claude to True whenever any category is yellow or above
            results['should_use_claude'] = True
    
    return results
    
    def _claude_analysis(self, article, keyword_results):
        """Perform second-stage Claude-based analysis for more nuanced understanding"""
        try:
            # Only analyze articles that were flagged in keyword analysis
            if not keyword_results['categorized']:
                return None
            
            # Get categories that were flagged
            flagged_categories = [
                cat_id for cat_id, severity in keyword_results['categories'].items()
                if severity != 'green'
            ]
            
            # Construct the prompt for Claude
            prompt = self._construct_claude_prompt(article, flagged_categories)
            
            # Call Claude API
            response = self._call_claude_api(prompt)
            
            # Parse Claude's response
            claude_results = self._parse_claude_response(response, flagged_categories)
            claude_results['method'] = 'claude'
            
            return claude_results
            
        except Exception as e:
            logger.error(f"Error in Claude analysis: {str(e)}")
            return None
    
def _construct_claude_prompt(self, article, flagged_categories):
    """Construct a prompt for Claude to analyze the article"""
    # Base prompt with article content
    prompt = f"""
    As a political analyst, I need you to analyze the following news article according to 
    the "Despotism Readiness Framework" which tracks indicators of democratic backsliding.
    
    Please provide the following analysis in a structured JSON format:
    
    1. Is this article about the United States? (True/False)
    2. For each of these categories: {', '.join(flagged_categories)}, provide:
       - Severity level (GREEN, YELLOW, ORANGE, RED)
       - Justification for this rating (list key evidence from the article)
       - Confidence level (1-5, where 5 is highest confidence)
    3. A summary of why this article is relevant to the framework
    
    Rate each category on a four-level scale:
    - GREEN: No concerning indicators
    - YELLOW: Early warning signs
    - ORANGE: Significant concerns
    - RED: Critical threat to democratic governance
    
    Article Title: {article.get('title', 'No title')}
    
    Article Content:
    {article.get('content', 'No content')}
    
    Source: {article.get('source', 'Unknown')}
    Date: {article.get('published_date', 'Unknown')}
    
    Please respond in JSON format like this:
    {{
        "is_us_based": true/false,
        "categories": {{
            "category_id": {{
                "severity": "GREEN/YELLOW/ORANGE/RED",
                "evidence": ["evidence1", "evidence2", ...],
                "confidence": 1-5
            }}
        }},
        "summary": "Your analysis of why this article is relevant to the framework",
        "reasoning": "Your step-by-step reasoning process for arriving at these ratings"
    }}
    
    Only include the categories I've asked about, and use only GREEN, YELLOW, ORANGE, or RED as severity levels.
    """
    
    return prompt    
    def _call_claude_api(self, prompt):
        """Call Claude API with the given prompt"""
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        data = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 1000,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                logger.error(f"Claude API error: {response.status_code}, {response.text}")
                return None
            
            result = response.json()
            return result.get('content', [{}])[0].get('text', '')
            
        except Exception as e:
            logger.error(f"Error calling Claude API: {str(e)}")
            return None
    
def _parse_claude_response(self, response, flagged_categories):
    """Parse Claude's response to extract ratings, explanations, and confidence"""
    if not response:
        logger.warning("Empty response from Claude")
        return {'categorized': False, 'categories': {}}
    
    try:
        # Extract JSON from response
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        
        if json_start == -1 or json_end == 0:
            logger.warning("No JSON found in Claude response")
            return {'categorized': False, 'categories': {}}
        
        json_str = response[json_start:json_end]
        result = json.loads(json_str)
        
        # Normalize the response
        is_us_based = result.get('is_us_based', True)
        categories_data = result.get('categories', {})
        summary = result.get('summary', 'No summary provided')
        reasoning = result.get('reasoning', 'No reasoning provided')
        
        normalized_categories = {}
        category_evidence = {}
        category_confidence = {}
        
        for cat_id in flagged_categories:
            if cat_id in categories_data:
                cat_data = categories_data[cat_id]
                
                # Handle both string and object formats
                if isinstance(cat_data, str):
                    severity = cat_data.lower()
                    evidence = []
                    confidence = 3  # Default confidence
                else:
                    severity = cat_data.get('severity', '').lower()
                    evidence = cat_data.get('evidence', [])
                    confidence = cat_data.get('confidence', 3)
                
                # Validate severity level
                if severity in ['green', 'yellow', 'orange', 'red']:
                    normalized_categories[cat_id] = severity
                    category_evidence[cat_id] = evidence
                    category_confidence[cat_id] = confidence
                else:
                    # Default to yellow if invalid severity but was flagged
                    normalized_categories[cat_id] = 'yellow'
                    category_evidence[cat_id] = []
                    category_confidence[cat_id] = 2
        
        # Determine if any categories have concerns
        categorized = any(sev != 'green' for sev in normalized_categories.values())
        
        return {
            'categorized': categorized,
            'is_us_based': is_us_based,
            'categories': normalized_categories,
            'evidence': category_evidence,
            'confidence': category_confidence,
            'explanation': summary,
            'reasoning': reasoning
        }
        
    except Exception as e:
        logger.error(f"Error parsing Claude response: {str(e)}")
        return {'categorized': False, 'categories': {}}
        
    def _combine_analysis_results(self, keyword_results, claude_results=None):
        """Combine results from keyword and Claude analysis"""
        # If Claude analysis is disabled or no Claude results, just use keyword results
        if not getattr(self, 'USE_CLAUDE_ANALYSIS', False) or not claude_results:
            return keyword_results

        # The rest of your existing method
        combined_results = {
            'categorized': keyword_results['categorized'] or claude_results['categorized'],
            'categories': {},
            'methods': ['keyword']
        }
        
        if claude_results:
            combined_results['methods'].append('claude')
            combined_results['claude_explanation'] = claude_results.get('explanation', '')
        
        # Combine categories, using Claude's assessment when available
        all_categories = set(list(keyword_results['categories'].keys()) + 
                            (list(claude_results['categories'].keys()) if claude_results else []))
        
        for cat_id in all_categories:
            keyword_severity = keyword_results['categories'].get(cat_id, 'green')
            claude_severity = claude_results['categories'].get(cat_id, keyword_severity) if claude_results else keyword_severity
            
            # Use the higher severity between keyword and Claude
            severity_order = {'green': 0, 'yellow': 1, 'orange': 2, 'red': 3}
            if severity_order.get(claude_severity, 0) >= severity_order.get(keyword_severity, 0):
                combined_results['categories'][cat_id] = claude_severity
            else:
                combined_results['categories'][cat_id] = keyword_severity
        
        return combined_results
    
def _create_events(self, article, analysis_results):
    """Create events for categorized articles with persistence tracking"""
    for category_id, severity in analysis_results['categories'].items():
        # Only create events for non-green categories
        if severity == 'green':
            continue
            
        # Check if there's an existing event for this category
        existing_events = list(self.events_collection.find({
            'category': category_id,
            'detected_date': {'$gte': (datetime.datetime.now() - datetime.timedelta(days=90)).isoformat()}
        }).sort('detected_date', -1))
        
        # Set start date for persistence tracking
        start_date = datetime.datetime.now().isoformat()
        previous_severity = None
        
        # If we have a previous event, track persistence
        if existing_events:
            latest_event = existing_events[0]
            
            # If severity hasn't changed, keep the original start date
            if latest_event.get('severity') == severity:
                start_date = latest_event.get('start_date', latest_event['detected_date'])
            
            # Track previous severity for detecting rapid escalation
            previous_severity = latest_event.get('severity')
            
        # Get evidence and confidence if available
        evidence = analysis_results.get('evidence', {}).get(category_id, [])
        confidence = analysis_results.get('confidence', {}).get(category_id, 3)
        is_us_based = analysis_results.get('is_us_based', True)
        reasoning = analysis_results.get('reasoning', '')
        
        # Format evidence as HTML list if available
        evidence_html = ""
        if evidence:
            evidence_html = "<ul>"
            for item in evidence:
                evidence_html += f"<li>{item}</li>"
            evidence_html += "</ul>"
        
        # Create the event with new fields
        event = {
            'article_id': article['_id'],
            'title': article.get('title', 'No title'),
            'url': article.get('url', ''),
            'source': article.get('source', 'Unknown'),
            'published_date': article.get('published_date', ''),
            'category': category_id,
            'severity': severity,
            'detected_date': datetime.datetime.now().isoformat(),
            'methods': analysis_results.get('methods', ['keyword']),
            'explanation': analysis_results.get('explanation', ''),
            'evidence': evidence,
            'evidence_html': evidence_html,
            'confidence': confidence,
            'is_us_based': is_us_based,
            'reasoning': reasoning,
            
            # Persistence tracking fields
            'start_date': start_date,
            'previous_severity': previous_severity,
            'severity_change_date': datetime.datetime.now().isoformat() if previous_severity != severity else None,
            'duration_days': 0,  # Will be calculated in summary generation
            'confirmed': False   # Will be updated in summary generation
        }
        
        self.events_collection.insert_one(event)
        logger.info(f"Created {severity} event for category {category_id}: {article.get('title', 'No title')}")        
    def _generate_summary(self):
        """Generate a summary of the current state based on recent events with persistence tracking"""
        # Get events from the past 7 days
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=7)
        cutoff_date_str = cutoff_date.isoformat()
        
        query = {
            'detected_date': {'$gte': cutoff_date_str}
        }
        
        events = list(self.events_collection.find(query))
        logger.info(f"Generating summary from {len(events)} recent events")
        
        # Count flags by category and severity
        summary = {
            'date': datetime.datetime.now().isoformat(),
            'total_events': len(events),
            'green_count': 0,
            'yellow_count': 0,
            'orange_count': 0,
            'red_count': 0,
            'categories': {}
        }
        
        # Initialize category counts
        for category_id in self.categories.keys():
            summary['categories'][category_id] = {
                'green': 0,
                'yellow': 0,
                'orange': 0,
                'red': 0,
                'current_severity': 'green'
            }
        
        # Count events by category and severity
        for event in events:
            category = event.get('category')
            severity = event.get('severity')
            
            if category and severity:
                # Increment overall counts
                summary[f'{severity}_count'] = summary.get(f'{severity}_count', 0) + 1
                
                # Increment category-specific counts
                if category in summary['categories']:
                    summary['categories'][category][severity] = summary['categories'][category].get(severity, 0) + 1
        
        # Apply persistence rules to each category
        for category_id in self.categories.keys():
            # Get events for this category
            category_events = [e for e in events if e.get('category') == category_id]
            
            # Check persistence
            if category_events:
                persistence_data = self.tracker.check_category_persistence(category_id, category_events)
                
                # Update category data with persistence info
                summary['categories'][category_id].update(persistence_data)
        
        # Determine current severity level for each category
        for category_id, counts in summary['categories'].items():
            if counts['red'] > 0:
                counts['current_severity'] = 'red'
            elif counts['orange'] > 0:
                counts['current_severity'] = 'orange'
            elif counts['yellow'] > 0:
                counts['current_severity'] = 'yellow'
            else:
                counts['current_severity'] = 'green'
        
        # Calculate alert level based on tiered approach
        alert_level, recommendations = self.tracker.calculate_alert_level(summary)
        summary['alert_level'] = alert_level
        summary['alert_recommendations'] = recommendations
        
        # Determine threshold status
        summary['thresholds'] = {
            'orange_threshold': 3,  # Number of orange flags to trigger alert
            'red_threshold': 1,     # Number of red flags to trigger alert
            'orange_threshold_crossed': False,
            'red_threshold_crossed': False
        }
        
        # Count how many categories are at orange or red level (only if confirmed)
        orange_categories = sum(1 for cat in summary['categories'].values() 
                              if cat['current_severity'] == 'orange' and cat.get('confirmed', False))
        red_categories = sum(1 for cat in summary['categories'].values() 
                           if cat['current_severity'] == 'red' and cat.get('confirmed', False))
        
        summary['thresholds']['orange_threshold_crossed'] = orange_categories >= summary['thresholds']['orange_threshold']
        summary['thresholds']['red_threshold_crossed'] = red_categories >= summary['thresholds']['red_threshold']
        
        # Overall status based on thresholds
        if summary['thresholds']['red_threshold_crossed']:
            summary['overall_status'] = 'red'
        elif summary['thresholds']['orange_threshold_crossed']:
            summary['overall_status'] = 'orange'
        elif summary['yellow_count'] > 0:
            summary['overall_status'] = 'yellow'
        else:
            summary['overall_status'] = 'green'
        
        # Save the summary
        self.summaries_collection.insert_one(summary)
        logger.info(f"Generated summary with overall status: {summary['overall_status']}, alert level: {summary['alert_level']}")
        
        return summary


# For testing
if __name__ == "__main__":
    analyzer = NewsAnalyzer()
    count = analyzer.analyze_recent_articles()
    print(f"Analyzed {count} articles")