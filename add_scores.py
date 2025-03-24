def create_events(self, article, analysis_results):
    """Create events for categorized articles with persistence tracking"""
    for category_id, severity in analysis_results['categories'].items():
        # Only create events for non-green categories
        if severity == 'green':
            continue
                
        # Calculate score based on severity
        severity_scores = {
            'yellow': 25,
            'orange': 65,
            'red': 90
        }
        base_score = severity_scores.get(severity, 0)
        
        # Add variation based on keyword matches or Claude confidence
        variation = 0
        if 'match_count' in analysis_results:
            variation = min(15, analysis_results['match_count'] * 3)
        
        # Adjust score based on Claude's explanation if available
        claude_confidence = 0
        if 'claude_explanation' in analysis_results and 'claude' in analysis_results.get('methods', []):
            # Extract confidence indicators from Claude's explanation
            explanation = analysis_results['claude_explanation'].lower()
            if 'high confidence' in explanation or 'strong evidence' in explanation:
                claude_confidence = 10
            elif 'moderate confidence' in explanation or 'some evidence' in explanation:
                claude_confidence = 5
                
        # Final score calculation
        final_score = min(100, base_score + variation + claude_confidence)
        
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
        
        # Create the event
        event = {
            'article_id': article['_id'],
            'title': article.get('title', 'No title'),
            'url': article.get('url', ''),
            'source': article.get('source', 'Unknown'),
            'published_date': article.get('published_date', ''),
            'category': category_id,
            'severity': severity,
            'score': final_score,  # Add score to the event
            'detected_date': datetime.datetime.now().isoformat(),
            'methods': analysis_results.get('methods', ['keyword']),
            'explanation': analysis_results.get('claude_explanation', ''),
            
            # Persistence tracking fields
            'start_date': start_date,
            'previous_severity': previous_severity,
            'severity_change_date': datetime.datetime.now().isoformat() if previous_severity != severity else None,
        }
        
        self.events_collection.insert_one(event)
        logger.info(f"Created {severity} event (score: {final_score}) for category {category_id}: {article.get('title', 'No title')}")