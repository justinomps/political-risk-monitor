import datetime
import logging
import time
import json
import os
import re
import requests
import html # <--- IMPORT ADDED HERE

# --- Define Mock Classes First ---
# These will always be defined, but only used if imports fail.

class MockCollection:
    """Mock database collection for testing when real DB is unavailable."""
    def __init__(self, name):
        self.name = name
        self._data = {} # Use a dictionary to simulate data store
        self._id_counter = 0
        logger.debug(f"Initialized MockCollection: {name}")

    def find(self, query=None, limit=None, sort=None): # Added sort parameter
        """Very basic mock find."""
        logger.debug(f"Mock find in '{self.name}' with query: {query}, limit: {limit}, sort: {sort}")
        results = []
        count = 0
        now = datetime.datetime.now()
        # Handle potential None query
        query = query or {}

        # Extract query parameters safely
        analyzed_filter = query.get('analyzed')
        date_filter = query.get('collected_at', {}).get('$gte')
        category_filter = query.get('category') # Added for event filtering
        detected_date_filter = query.get('detected_date', {}).get('$gte') # Added for event filtering

        cutoff_dt = None
        if date_filter:
            try:
                cutoff_dt = datetime.datetime.fromisoformat(date_filter)
            except (ValueError, TypeError):
                logger.warning(f"Invalid date format in query: {date_filter}")
                cutoff_dt = None

        detected_cutoff_dt = None
        if detected_date_filter:
             try:
                  detected_cutoff_dt = datetime.datetime.fromisoformat(detected_date_filter)
             except (ValueError, TypeError):
                  logger.warning(f"Invalid detected_date format in query: {detected_date_filter}")
                  detected_cutoff_dt = None


        # Iterate through a copy of items to avoid runtime errors if data changes
        temp_results = []
        for doc_id, doc in list(self._data.items()):
            match = True # Assume match initially

            # Check analyzed status if filter exists
            if analyzed_filter is not None:
                is_analyzed = doc.get('analyzed', False) # Default to False if not present for filtering
                if is_analyzed != analyzed_filter:
                    match = False

            # Check date cutoff if filter exists and valid
            if match and cutoff_dt:
                collected_at_str = doc.get('collected_at')
                if collected_at_str:
                    try:
                        collected_dt = datetime.datetime.fromisoformat(collected_at_str)
                        if collected_dt < cutoff_dt:
                            match = False
                    except (ValueError, TypeError):
                         match = False # Treat invalid date as non-matching
                else:
                    match = False # No date, cannot match date filter

            # Check category if filter exists
            if match and category_filter is not None:
                 if doc.get('category') != category_filter:
                      match = False

            # Check detected date if filter exists and valid
            if match and detected_cutoff_dt:
                detected_at_str = doc.get('detected_date')
                if detected_at_str:
                    try:
                        detected_dt = datetime.datetime.fromisoformat(detected_at_str)
                        if detected_dt < detected_cutoff_dt:
                            match = False
                    except (ValueError, TypeError):
                         match = False # Treat invalid date as non-matching
                else:
                    match = False # No date, cannot match date filter


            # If all filters passed
            if match:
                # Add _id if it's not already part of the doc (it should be key)
                doc_with_id = doc.copy()
                doc_with_id['_id'] = doc_id
                temp_results.append(doc_with_id) # Add to temp list for sorting

        # --- Mock Sorting ---
        if sort and isinstance(sort, list) and len(sort) > 0:
             sort_key, sort_order = sort[0] # Assumes simple sort like [('date', -1)]
             reverse = (sort_order == -1) # pymongo.DESCENDING is -1
             try:
                  # Attempt to sort; handle potential missing keys or type errors gracefully
                  temp_results.sort(key=lambda x: x.get(sort_key, None), reverse=reverse)
                  logger.debug(f"Mock sorting by {sort_key} {'DESC' if reverse else 'ASC'}")
             except TypeError:
                  logger.warning(f"Mock sort failed on key '{sort_key}'. Returning unsorted results.")
             except Exception as e:
                  logger.warning(f"Mock sort encountered an unexpected error: {e}. Returning unsorted results.")


        # --- Mock Limiting ---
        if limit is not None:
            results = temp_results[:limit]
            logger.debug(f"Mock limiting to {limit} results.")
        else:
             results = temp_results


        logger.debug(f"Mock find completed. Returning {len(results)} results.")
        # Return list directly, mimicking list(cursor) or cursor iteration
        return results

    def update_one(self, query, update):
        """Mock update_one operation."""
        doc_id = query.get('_id')
        logger.debug(f"Mock update_one in '{self.name}' for ID: {doc_id}")
        if doc_id in self._data:
            set_data = update.get('$set', {})
            self._data[doc_id].update(set_data)
            logger.debug(f"Mock Updated doc {doc_id}")
        else:
             logger.warning(f"Mock Update failed: Doc {doc_id} not found.")

    def insert_one(self, document):
        """Mock insert_one operation."""
        self._id_counter += 1
        doc_id = document.get('_id', f"mock_id_{self.name}_{self._id_counter}") # Use provided _id or generate one

        if doc_id in self._data:
             logger.warning(f"Mock Insert Warning: Document with _id {doc_id} already exists in '{self.name}'. Overwriting.")

        # Ensure document has _id field before inserting
        document['_id'] = doc_id
        self._data[doc_id] = document.copy() # Store a copy
        logger.debug(f"Mock Inserted doc {doc_id} into '{self.name}'")
        # Return a mock result object mimicking pymongo's InsertOneResult
        return type('obj', (object,), {'inserted_id': doc_id})()

    # --- Mock data insertion helper for testing ---
    def insert_mock_article(self, title, content, analyzed=False, days_ago=0):
         """Helper to add mock articles to the collection."""
         doc = {
             'title': title,
             'content': content,
             'collected_at': (datetime.datetime.now() - datetime.timedelta(days=days_ago, hours=1)).isoformat(),
             'analyzed': analyzed,
             'url': f'http://example.com/{title.replace(" ", "-").lower()}',
             'source': 'Mock Source',
             'published_date': (datetime.datetime.now() - datetime.timedelta(days=days_ago, hours=2)).isoformat()
         }
         self.insert_one(doc)
         logger.debug(f"Inserted mock article: {title}")

# Global store for mock collections
_mock_collections_store = {}

def mock_get_collection(collection_name):
    """Returns a mock collection instance."""
    if collection_name not in _mock_collections_store:
        _mock_collections_store[collection_name] = MockCollection(collection_name)
    return _mock_collections_store[collection_name]

class MockIndicatorTracker:
    """Mock IndicatorTracker for testing."""
    def __init__(self):
         self.category_state = {} # Optional: maintain state across calls if needed
         logger.debug("Initialized MockIndicatorTracker")


    def check_category_persistence(self, category_id, category_events):
        """Basic mock persistence check."""
        logger.debug(f"Mock checking persistence for category '{category_id}' with {len(category_events)} events.")
        if not category_events:
             return {
                 'is_persistent': False, 'duration_days': 0, 'confirmed': False,
                 'current_severity': 'green', 'start_date': None,
             }

        # Simple logic: persistent if > 1 event, confirmed if persistent
        is_persistent = len(category_events) > 1
        confirmed = is_persistent # Simple confirmation logic for mock
        latest_event = max(category_events, key=lambda e: e['detected_date'])
        current_severity = latest_event['severity']
        start_date = None
        duration = 0

        if is_persistent:
            # Find the event marking the start of the current streak (same severity)
            # This requires looking back through the events sorted by date
            sorted_events = sorted(category_events, key=lambda e: e['detected_date'])
            streak_start_event = latest_event
            for i in range(len(sorted_events) - 2, -1, -1):
                 # Check if the previous event had the same severity to continue the streak start date
                 if sorted_events[i]['severity'] == current_severity:
                      # Use the start_date of the previous event in the streak
                      streak_start_event = sorted_events[i]
                 else:
                      break # Streak broken

            # Use the start_date field from the actual start of the streak
            start_date = streak_start_event.get('start_date', streak_start_event['detected_date'])

            try:
                 start_dt = datetime.datetime.fromisoformat(start_date)
                 end_dt = datetime.datetime.fromisoformat(latest_event['detected_date'])
                 duration = max(0, (end_dt - start_dt).days) # Ensure non-negative
            except (ValueError, TypeError):
                 logger.warning(f"Could not calculate duration for category '{category_id}' due to invalid date format.")
                 duration = 0
                 start_date = latest_event['detected_date'] # Fallback start date


        logger.debug(f"Mock persistence result for '{category_id}': Persistent={is_persistent}, Confirmed={confirmed}, Severity={current_severity}, Duration={duration}, Start={start_date}")
        return {
            'is_persistent': is_persistent,
            'duration_days': duration,
            'confirmed': confirmed,
            'current_severity': current_severity,
            'start_date': start_date,
        }

    def calculate_alert_level(self, summary):
        """Basic mock alert level calculation."""
        overall_status = summary.get('overall_status', 'green')
        logger.debug(f"Mock calculating alert level for overall status: {overall_status}")
        # Return string levels for consistency
        if overall_status == 'red':
            return 'High', ["Mock: Immediate action required."]
        elif overall_status == 'orange':
            return 'Medium', ["Mock: Monitor closely."]
        elif overall_status == 'yellow':
            return 'Low', ["Mock: Continue monitoring."]
        else:
            return 'None', ["Mock: No immediate concerns."]

# --- Set up logging ---
logging.basicConfig(
    level=logging.INFO, # Change to DEBUG for more verbose mock output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('analyzer_script') # Changed logger name slightly

# --- Try importing real modules, fall back to mocks ---
try:
    # Try importing real config
    from config import (
        ANTHROPIC_API_KEY,
        CATEGORIES,
        COLLECTION_ARTICLES,
        COLLECTION_EVENTS,
        COLLECTION_SUMMARIES
    )
    logger.info("Successfully imported configuration from config.py")
except ImportError:
    logger.warning("config.py not found or incomplete. Using dummy configuration values.")
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "dummy_key") # Allow override via env var
    CATEGORIES = {
        "example_cat": {"keywords": ["keyword1"], "orange_indicators": ["orange_indicator"], "red_indicators": ["red_indicator"]},
        "another_cat": {"keywords": ["test", "policy"], "orange_indicators": [], "red_indicators": []}
        }
    COLLECTION_ARTICLES = "articles_dummy"
    COLLECTION_EVENTS = "events_dummy"
    COLLECTION_SUMMARIES = "summaries_dummy"
    if ANTHROPIC_API_KEY == "dummy_key":
         logger.warning("ANTHROPIC_API_KEY not found in config.py or environment variables. Claude analysis will be disabled.")


try:
    # Attempt to import the real implementations
    # Use pymongo directly for type checking if needed
    import pymongo
    from modules.database import get_collection
    from modules.tracker import IndicatorTracker
    logger.info("Successfully imported 'get_collection' and 'IndicatorTracker' from modules.")
    # More robust check if mocks might be imported accidentally
    if get_collection == mock_get_collection:
         raise ImportError("Imported 'get_collection' is the mock version.")
    if IndicatorTracker == MockIndicatorTracker:
         raise ImportError("Imported 'IndicatorTracker' is the mock version.")
    is_mock_db = False

except ImportError as e:
    logger.warning(f"Could not import real database/tracker modules ({e}). Falling back to mock implementations.")
    # Assign the mock functions/classes to the names expected by NewsAnalyzer
    get_collection = mock_get_collection
    IndicatorTracker = MockIndicatorTracker
    is_mock_db = True # Flag to indicate mocks are in use


# --- Main Analyzer Class ---

class NewsAnalyzer:
    """
    Analyzes news articles and categorizes them according to the
    Despotism Readiness Framework. Uses real or mock components based on imports.
    """

    def __init__(self):
        logger.info("Initializing NewsAnalyzer...")
        # Connect to collections (will use real or mock get_collection)
        self.articles_collection = get_collection(COLLECTION_ARTICLES)
        self.events_collection = get_collection(COLLECTION_EVENTS)
        self.summaries_collection = get_collection(COLLECTION_SUMMARIES)
        logger.info(f"Using Article Collection: {getattr(self.articles_collection, 'name', 'N/A')} ({type(self.articles_collection).__name__})")
        logger.info(f"Using Event Collection: {getattr(self.events_collection, 'name', 'N/A')} ({type(self.events_collection).__name__})")
        logger.info(f"Using Summary Collection: {getattr(self.summaries_collection, 'name', 'N/A')} ({type(self.summaries_collection).__name__})")


        # Initialize tracker (will use real or mock IndicatorTracker)
        self.tracker = IndicatorTracker()
        logger.info(f"Using Indicator Tracker: {type(self.tracker).__name__}")


        # Load category definitions from config
        self.categories = CATEGORIES
        logger.info(f"Loaded {len(self.categories)} categories.")


        # --- Add mock data for testing ONLY if using mock collections ---
        # Check using the flag set during import fallback
        if is_mock_db:
             logger.info("Running with Mock DB. Adding mock articles...")
             # Add mock articles only if the collection is empty to avoid duplicates on re-runs
             if not self.articles_collection.find(limit=1): # Check if collection has any data
                 self.articles_collection.insert_mock_article("Test Article 1", "This article contains keyword1.", analyzed=False, days_ago=0)
                 self.articles_collection.insert_mock_article("Test Article 2", "This one has an orange_indicator.", analyzed=False, days_ago=1)
                 self.articles_collection.insert_mock_article("Test Article 3", "A red_indicator is mentioned here.", analyzed=False, days_ago=0)
                 self.articles_collection.insert_mock_article("Test Article 4", "Nothing relevant here.", analyzed=False, days_ago=2)
                 self.articles_collection.insert_mock_article("Old Article", "This is too old.", analyzed=False, days_ago=10)
                 self.articles_collection.insert_mock_article("Analyzed Article", "This was already done.", analyzed=True, days_ago=0)
                 self.articles_collection.insert_mock_article("Another Keyword1 Article", "More keyword1 content.", analyzed=False, days_ago=0)
             else:
                  logger.info("Mock Article Collection already contains data. Skipping mock data insertion.")


        logger.info("NewsAnalyzer initialized.")


    def analyze_recent_articles(self, days=1, limit=20):
        """Analyze articles collected in the past specified days"""
        logger.info(f"Starting analysis for articles from the last {days} day(s), limit {limit}.")
        # Set whether to use Claude API for analysis - can be toggled
        # Set to False if ANTHROPIC_API_KEY is dummy or missing
        self.USE_CLAUDE_ANALYSIS = ANTHROPIC_API_KEY != "dummy_key"
        if not self.USE_CLAUDE_ANALYSIS:
             logger.warning("Claude analysis is disabled (ANTHROPIC_API_KEY is 'dummy_key' or missing).")

        # Set keyword match threshold for Claude analysis (currently not used, but kept for potential future use)
        self.CLAUDE_MATCH_THRESHOLD = 1

        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        cutoff_date_str = cutoff_date.isoformat()
        logger.info(f"Analysis cutoff date: {cutoff_date_str}")

        # Get unanalyzed articles
        query = {
            'collected_at': {'$gte': cutoff_date_str},
            'analyzed': False
        }

        try:
            # Use sort argument for pymongo, mock handles it internally
            sort_order = [('collected_at', pymongo.ASCENDING if not is_mock_db else 1)] # Process oldest first within the window
            if is_mock_db:
                 # Mock find directly accepts sort list
                 articles_cursor_or_list = self.articles_collection.find(query, limit=limit, sort=sort_order)
                 articles = articles_cursor_or_list # Mock returns a list
            else:
                 # Real pymongo uses cursor methods
                 articles_cursor_or_list = self.articles_collection.find(query).sort(sort_order).limit(limit)
                 articles = list(articles_cursor_or_list)


        except Exception as e:
             logger.exception(f"Error fetching articles from database: {e}")
             articles = []


        logger.info(f"Found {len(articles)} unanalyzed recent articles matching criteria.")

        if not articles:
            logger.info("No articles to analyze in this run.")
            # Still generate a summary even if no articles analyzed, to update status based on existing events
            self._generate_summary()
            return 0

        analyzed_count = 0
        processed_ids = set() # Keep track of processed articles in this run

        for article in articles:
            try:
                # Ensure article has an _id
                article_id = article.get('_id')
                if not article_id:
                     logger.error(f"Article missing _id: {article.get('title', 'No title')}")
                     continue # Skip this article

                # Avoid reprocessing if somehow fetched twice (shouldn't happen with correct query)
                if article_id in processed_ids:
                     logger.warning(f"Attempted to reprocess article ID {article_id}. Skipping.")
                     continue
                processed_ids.add(article_id)


                logger.info(f"Analyzing article: {article.get('title', 'No title')} (ID: {article_id})")

                # First stage: keyword-based analysis
                keyword_results = self._keyword_analysis(article)
                logger.debug(f"Keyword analysis result for {article_id}: {keyword_results}")


                # Second stage: Claude analysis for articles that matched keywords
                claude_results = None
                should_try_claude = keyword_results['categorized'] and self.USE_CLAUDE_ANALYSIS and keyword_results.get('should_use_claude', False)

                if should_try_claude:
                    logger.info(f"Attempting Claude analysis for article ID: {article_id}")
                    claude_results = self._claude_analysis(article, keyword_results)
                    if claude_results:
                         logger.debug(f"Claude analysis result for {article_id}: {claude_results}")
                    else:
                         logger.warning(f"Claude analysis failed or returned no result for article ID: {article_id}")
                elif not self.USE_CLAUDE_ANALYSIS and keyword_results.get('should_use_claude', False):
                    logger.info(f"Skipping Claude analysis (globally disabled) for article ID: {article_id}")
                elif not keyword_results['categorized']:
                     logger.debug(f"Skipping Claude analysis (not categorized by keywords) for article ID: {article_id}")


                # Combine results
                analysis_results = self._combine_analysis_results(keyword_results, claude_results)
                logger.debug(f"Combined analysis result for {article_id}: {analysis_results}")


                # Update article with analysis results in the database
                self.articles_collection.update_one(
                    {'_id': article_id},
                    {'$set': {
                        'analyzed': True,
                        'analysis_date': datetime.datetime.now().isoformat(),
                        'analysis_results': analysis_results
                    }}
                )
                logger.info(f"Marked article {article_id} as analyzed.")


                # For categorized articles, create events
                if analysis_results.get('categorized', False):
                    self._create_events(article, analysis_results)
                else:
                     logger.debug(f"Article {article_id} not categorized, no event created.")


                analyzed_count += 1

                # Slight delay to avoid overwhelming Claude API if it was used
                if claude_results:
                    time.sleep(1) # Consider making delay configurable

            except Exception as e:
                # Log the full traceback for better debugging
                logger.exception(f"Error analyzing article {article.get('_id', 'Unknown ID')}: {str(e)}")
                # Optionally, mark article as failed analysis?
                # try:
                #     self.articles_collection.update_one({'_id': article_id}, {'$set': {'analyzed': True, 'analysis_failed': True, 'error': str(e)}})
                # except Exception as update_err:
                #      logger.error(f"Failed to mark article {article_id} as failed: {update_err}")


        # Generate summary after analysis run completes
        logger.info("Analysis loop finished.")
        self._generate_summary()


        logger.info(f"Completed analysis run. Processed {analyzed_count} articles.")
        return analyzed_count

    # --- Analysis Helper Methods ---

    def _keyword_analysis(self, article):
        """Perform first-stage keyword-based analysis."""
        # Combine title and content for analysis, handle None values
        title = article.get('title', '') or ''
        content = article.get('content', '') or ''
        text = f"{title} {content}".lower()

        results = {
            'categorized': False,
            'categories': {},
            'method': 'keyword',
            'should_use_claude': False,
            'match_count': 0
        }

        # Initialize all categories to green first
        for category_id in self.categories.keys():
             results['categories'][category_id] = 'green'


        # Check each category for keyword matches
        for category_id, category_data in self.categories.items():
            if not isinstance(category_data, dict):
                 logger.warning(f"Skipping category '{category_id}': Invalid data format in CATEGORIES config.")
                 continue

            severity = 'green' # Start at green for this category
            category_match_count = 0

            # Ensure keywords/indicators are lists and handle potential None values inside lists
            base_keywords = [kw.lower() for kw in category_data.get('keywords', []) if kw]
            orange_indicators = [ind.lower() for ind in category_data.get('orange_indicators', []) if ind]
            red_indicators = [ind.lower() for ind in category_data.get('red_indicators', []) if ind]


            # Check base keywords -> Yellow
            for keyword in base_keywords:
                if keyword in text:
                    severity = 'yellow'
                    category_match_count += 1
                    break # Found yellow, move to check orange

            # Check orange indicators -> Orange (only if already yellow or higher)
            if severity != 'green':
                for indicator in orange_indicators:
                    if indicator in text:
                        severity = 'orange'
                        category_match_count += 2
                        break # Found orange, move to check red

            # Check red indicators -> Red (only if already orange or higher)
            # Corrected logic: Check only if orange was reached
            if severity == 'orange': # Check specifically if orange was reached
                 for indicator in red_indicators:
                     if indicator in text:
                         severity = 'red'
                         category_match_count += 3
                         break # Found red, stop checking for this category


            # Update results for this category
            results['categories'][category_id] = severity
            results['match_count'] += category_match_count


            # If this category triggered a non-green status, mark for potential Claude use
            if severity != 'green':
                results['categorized'] = True # Mark overall as categorized
                results['should_use_claude'] = True # Mark that Claude might be useful


        return results

    def _claude_analysis(self, article, keyword_results):
        """Perform second-stage Claude-based analysis."""
        article_id = article.get('_id', 'Unknown ID')
        try:
            # Get categories that were flagged yellow or higher by keywords
            flagged_categories = [
                cat_id for cat_id, severity in keyword_results.get('categories', {}).items()
                if severity != 'green'
            ]

            if not flagged_categories:
                 logger.debug(f"Skipping Claude analysis for {article_id}: No categories flagged >= yellow by keywords.")
                 return None # No categories need Claude's review


            logger.info(f"Requesting Claude analysis for categories: {flagged_categories} in article {article_id}")
            # Construct the prompt for Claude
            prompt = self._construct_claude_prompt(article, flagged_categories)
            # logger.debug(f"Claude prompt for {article_id}:\n{prompt}") # Be careful logging full prompts/content

            # Call Claude API
            response_text = self._call_claude_api(prompt)

            if response_text is None:
                 logger.error(f"Claude API call failed or returned None for article {article_id}")
                 return None # Indicate failure


            # Parse Claude's response
            # logger.debug(f"Raw Claude response for {article_id}: {response_text}") # Be careful logging full responses
            claude_results = self._parse_claude_response(response_text, flagged_categories)

            # Add method indicator if parsing was successful (check for key keys)
            if claude_results and 'categories' in claude_results:
                 claude_results['method'] = 'claude'
                 # Log success only if parsing didn't return the error structure
                 if 'Parsing failed' not in claude_results.get('explanation', ''):
                      logger.info(f"Claude analysis and parsing successful for article {article_id}")
                 else:
                      logger.warning(f"Claude analysis successful but parsing failed for article {article_id}")
                 return claude_results
            else:
                 # This case might occur if _parse_claude_response returned None directly
                 logger.error(f"Failed to parse Claude response or parser returned None for article {article_id}")
                 return None


        except Exception as e:
            logger.exception(f"Error during Claude analysis pipeline for article {article_id}: {str(e)}")
            return None # Indicate failure

    def _construct_claude_prompt(self, article, flagged_categories):
        """Construct a prompt for Claude to analyze the article."""
        # Ensure content is not excessively long - consider truncation if necessary
        max_content_length = 10000 # Example limit (adjust based on model context window and cost)
        content = article.get('content', 'No content') or 'No content'
        if len(content) > max_content_length:
             logger.warning(f"Article content truncated for Claude prompt (ID: {article.get('_id')})")
             content = content[:max_content_length] + "... (truncated)"


        # Improved prompt clarity and structure
        prompt = f"""
        Analyze the news article provided below according to the "Despotism Readiness Framework".
        Focus *only* on the following categories: {', '.join(flagged_categories)}.

        **Article Details:**
        Title: {article.get('title', 'No title')}
        Source: {article.get('source', 'Unknown')}
        Date: {article.get('published_date', 'Unknown')}

        **Article Content:**
        --- START ARTICLE ---
        {content}
        --- END ARTICLE ---

        **Analysis Instructions:**
        1.  **US Focus:** Determine if the article's primary subject matter concerns events, policies, or political discourse within the United States. Respond with `true` or `false`.
        2.  **Category Assessment:** For EACH category listed [{', '.join(flagged_categories)}]:
            a.  **Severity:** Assign **one** severity level: `GREEN`, `YELLOW`, `ORANGE`, or `RED`. Use these definitions:
                - `GREEN`: No concerning indicators relevant to this category found in the text.
                - `YELLOW`: Potential early warning signs, minor issues, or ambiguous indicators relevant to this category.
                - `ORANGE`: Significant concerns, clear problems, or substantial indicators relevant to this category.
                - `RED`: Critical threat, severe problem, or major negative indicators relevant to this category.
            b.  **Evidence:** Provide a JSON list of **direct quotes** (strings) from the article text that **specifically justify** your assigned severity level for this category. If `GREEN`, provide an empty list `[]`. Aim for 1-3 key quotes per category if not GREEN. Ensure quotes are properly escaped JSON strings.
            c.  **Confidence:** Provide a confidence score as an **integer** from 1 (low) to 5 (high) reflecting your certainty in the severity assessment for this category based *only* on the provided text.
        3.  **Relevance Summary:** Write a brief (1-3 sentences) overall summary explaining *why* the article is relevant (or not relevant) to the specified framework categories, based on your analysis.
        4.  **Reasoning:** Briefly explain your step-by-step reasoning for assigning the severity levels to each category, referencing the evidence found.

        **Output Format:**
        Respond **only** with a single, valid JSON object. Do not include any text before or after the JSON object. Ensure all strings within the JSON are properly escaped (e.g., quotes within evidence strings). Follow this exact structure:

        ```json
        {{
          "is_us_based": <true_or_false>,
          "categories": {{
            "category_id_1": {{
              "severity": "GREEN | YELLOW | ORANGE | RED",
              "evidence": ["quote1", "quote2", ...],
              "confidence": <integer_1_to_5>
            }},
            "category_id_2": {{
              "severity": "GREEN | YELLOW | ORANGE | RED",
              "evidence": ["quote1", ...],
              "confidence": <integer_1_to_5>
            }}
            // ... include ALL requested categories ...
          }},
          "summary": "Brief relevance summary text...",
          "reasoning": "Step-by-step reasoning text..."
        }}
        ```
        """
        return prompt

    def _call_claude_api(self, prompt):
        """Call Claude API with the given prompt."""
        # API Key check moved to analyze_recent_articles to avoid repeated checks
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        data = {
            "model": "claude-3-haiku-20240307", # Fast and capable model
            "max_tokens": 2500, # Increased slightly more, maybe helps with truncation?
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1 # Very low temp for consistent JSON
        }

        try:
            logger.debug("Sending request to Claude API...")
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data,
                timeout=90 # Increased timeout for potentially longer analysis
            )
            logger.debug(f"Claude API response status code: {response.status_code}")
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            result = response.json()

            # Extract text content safely
            if result.get('content') and isinstance(result['content'], list) and result['content'][0].get('text'):
                 response_text = result['content'][0]['text']
                 logger.debug("Successfully received text content from Claude API.")
                 return response_text
            else:
                 # Log the problematic structure if text is missing
                 logger.error(f"Unexpected Claude API response structure - missing text: {result}")
                 return None

        except requests.exceptions.Timeout:
             logger.error("Claude API request timed out.")
             return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Claude API: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                 logger.error(f"Claude API Response Status: {e.response.status_code}")
                 # Log response body only for non-200 status if needed for debugging API errors
                 # Be cautious logging full bodies in production
                 # if response.status_code != 200:
                 #    logger.error(f"Claude API Response Body: {e.response.text}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error during Claude API call: {str(e)}")
            return None

    def _parse_claude_response(self, response_text, flagged_categories):
        """Parse Claude's JSON response robustly."""
        if not response_text:
            logger.warning("Cannot parse empty response from Claude.")
            return None # Indicate parsing failure

        # Default structure for error cases, helps in combining results later
        error_result = {
            'categorized': False, 'is_us_based': None,
            'categories': {cat_id: 'green' for cat_id in flagged_categories},
            'evidence': {cat_id: [] for cat_id in flagged_categories},
            'confidence': {cat_id: 0 for cat_id in flagged_categories},
            'explanation': 'Parsing failed', 'reasoning': 'Parsing failed'
        }

        try:
            logger.debug("Attempting to parse Claude JSON response.")
            # Attempt to find JSON block, handling potential markdown fences ```json ... ```
            json_str = None
            # Handle potential leading/trailing whitespace and markdown fences
            response_text_cleaned = response_text.strip()
            if response_text_cleaned.startswith('```json') and response_text_cleaned.endswith('```'):
                 json_str = response_text_cleaned[7:-3].strip() # Extract content within ```json ... ```
            elif response_text_cleaned.startswith('{') and response_text_cleaned.endswith('}'):
                 json_str = response_text_cleaned # Assume it's just the JSON object
            else:
                 # Fallback: find first '{' and last '}' as a last resort
                 json_start = response_text.find('{')
                 json_end = response_text.rfind('}') + 1
                 if json_start != -1 and json_end > json_start: # Ensure valid range
                     json_str = response_text[json_start:json_end]

            if not json_str:
                 logger.warning(f"Could not extract JSON object from Claude response. Response start: {response_text[:200]}...")
                 error_result['explanation'] = 'Parsing failed: No JSON object found.'
                 error_result['reasoning'] = 'Parsing failed: No JSON object found.'
                 return error_result # Return error structure

            # Attempt to decode the extracted JSON string
            result = json.loads(json_str)
            logger.debug("Successfully decoded JSON from Claude response.")


            # --- Data Validation and Normalization ---
            is_us_based = result.get('is_us_based')
            if not isinstance(is_us_based, bool):
                 logger.warning(f"Invalid 'is_us_based' value: {is_us_based}. Defaulting to True.")
                 is_us_based = True

            categories_data = result.get('categories', {})
            if not isinstance(categories_data, dict):
                 logger.warning(f"Invalid 'categories' format: Expected dict, got {type(categories_data)}. Defaulting to empty.")
                 categories_data = {}

            summary = result.get('summary', 'No summary provided by Claude.')
            reasoning = result.get('reasoning', 'No reasoning provided by Claude.')

            normalized_categories = {}
            category_evidence = {}
            category_confidence = {}
            valid_severities = {'green', 'yellow', 'orange', 'red'}

            # Ensure all flagged categories are present in the output, defaulting if necessary
            for cat_id in flagged_categories:
                if cat_id in categories_data:
                    cat_data = categories_data[cat_id]
                    if isinstance(cat_data, dict):
                        # Normalize severity: lowercase string, default GREEN
                        severity = str(cat_data.get('severity', 'GREEN')).lower()
                        if severity not in valid_severities:
                             logger.warning(f"Invalid severity '{cat_data.get('severity')}' for category '{cat_id}'. Defaulting to 'green'.")
                             severity = 'green'

                        # Normalize evidence: list of strings, default empty
                        evidence = cat_data.get('evidence', [])
                        if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
                             logger.warning(f"Invalid evidence format for category '{cat_id}'. Defaulting to empty list.")
                             evidence = []

                        # Normalize confidence: integer 1-5, default 3
                        confidence_raw = cat_data.get('confidence', 3)
                        try:
                            confidence = int(confidence_raw)
                            if not 1 <= confidence <= 5:
                                logger.warning(f"Confidence {confidence} out of range (1-5) for '{cat_id}'. Clamping to 3.")
                                confidence = 3
                        except (ValueError, TypeError):
                             logger.warning(f"Invalid confidence value '{confidence_raw}' for '{cat_id}'. Defaulting to 3.")
                             confidence = 3

                        normalized_categories[cat_id] = severity
                        category_evidence[cat_id] = evidence
                        category_confidence[cat_id] = confidence
                    else:
                        logger.warning(f"Unexpected data format for category '{cat_id}': {cat_data}. Defaulting to 'green'.")
                        normalized_categories[cat_id] = 'green'
                        category_evidence[cat_id] = []
                        category_confidence[cat_id] = 1
                else:
                    logger.warning(f"Category '{cat_id}' was expected but missing in Claude's response. Defaulting to 'green'.")
                    normalized_categories[cat_id] = 'green'
                    category_evidence[cat_id] = []
                    category_confidence[cat_id] = 1

            # Determine overall categorization based on Claude's results
            categorized = any(sev != 'green' for sev in normalized_categories.values())

            logger.debug(f"Parsed Claude results: US={is_us_based}, Categorized={categorized}, Categories={normalized_categories}")
            return {
                'categorized': categorized,
                'is_us_based': is_us_based,
                'categories': normalized_categories,
                'evidence': category_evidence,
                'confidence': category_confidence,
                'explanation': summary,
                'reasoning': reasoning
            }

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from Claude response: {str(e)}")
            # Log more context around the error position
            error_pos = e.pos
            context_window = 50 # Characters before and after error position
            start = max(0, error_pos - context_window)
            end = min(len(json_str), error_pos + context_window)
            logger.error(f"Context around error position {error_pos}: ...{json_str[start:end]}...")
            error_result['explanation'] = f'Parsing failed: JSONDecodeError - {e}'
            error_result['reasoning'] = f'Parsing failed: JSONDecodeError - {e}'
            return error_result # Return error structure
        except Exception as e:
            logger.exception(f"Unexpected error parsing Claude response: {str(e)}")
            error_result['explanation'] = f'Parsing failed: Unexpected error - {e}'
            error_result['reasoning'] = f'Parsing failed: Unexpected error - {e}'
            return error_result # Return error structure

    def _combine_analysis_results(self, keyword_results, claude_results=None):
        """Combine keyword and Claude results, prioritizing Claude's non-green assessments."""
        # Start with a deep copy of keyword results to avoid modifying the original
        combined_results = {
            'categorized': keyword_results.get('categorized', False),
            'categories': (keyword_results.get('categories') or {}).copy(),
            'methods': ['keyword'],
            'keyword_match_count': keyword_results.get('match_count', 0),
            'claude_explanation': None,
            'claude_reasoning': None,
            'is_us_based': None,
            'evidence': {},
            'confidence': {}
        }

        # If Claude analysis provided valid results (check for categories dict)
        if claude_results and isinstance(claude_results.get('categories'), dict):
            logger.debug("Combining Claude results with keyword results.")
            combined_results['methods'].append('claude')
            combined_results['claude_explanation'] = claude_results.get('explanation')
            combined_results['claude_reasoning'] = claude_results.get('reasoning')
            combined_results['is_us_based'] = claude_results.get('is_us_based')
            combined_results['evidence'] = claude_results.get('evidence', {})
            combined_results['confidence'] = claude_results.get('confidence', {})

            claude_analyzed_categories = claude_results['categories']
            severity_order = {'green': 0, 'yellow': 1, 'orange': 2, 'red': 3}

            # Iterate through categories assessed by Claude
            for cat_id, claude_severity in claude_analyzed_categories.items():
                 # Get the keyword severity for comparison (default to green if somehow missing)
                 keyword_severity = combined_results['categories'].get(cat_id, 'green')

                 # --- Decision Logic ---
                 # 1. If Claude provides a non-green assessment, use Claude's severity.
                 if claude_severity != 'green':
                      final_severity = claude_severity
                      logger.debug(f"Combine '{cat_id}': Using Claude's '{claude_severity}' (non-green).")
                 # 2. If Claude says green, but keywords flagged higher, keep the higher keyword severity.
                 elif severity_order.get(keyword_severity, 0) > severity_order.get(claude_severity, 0):
                      final_severity = keyword_severity
                      logger.debug(f"Combine '{cat_id}': Using Keyword's '{keyword_severity}' (higher than Claude's 'green').")
                 # 3. Otherwise (both green, or keyword <= Claude's green), use Claude's assessment (which is green).
                 else:
                      final_severity = claude_severity # Which is 'green' in this case
                      logger.debug(f"Combine '{cat_id}': Using 'green' (both methods agree or Claude is green).")

                 combined_results['categories'][cat_id] = final_severity

            # Ensure all categories from the config are present in the final result
            for cat_id in self.categories.keys():
                 if cat_id not in combined_results['categories']:
                      logger.warning(f"Category '{cat_id}' from config missing in combined results. Adding as 'green'.")
                      combined_results['categories'][cat_id] = 'green'


            # Recalculate overall 'categorized' status based on the final combined severities
            combined_results['categorized'] = any(sev != 'green' for sev in combined_results['categories'].values())
            logger.debug(f"Final combined categorization status: {combined_results['categorized']}")

        else:
             logger.debug("No valid Claude results to combine, using only keyword results.")
             # Ensure all categories from config are present even if only using keywords
             for cat_id in self.categories.keys():
                  if cat_id not in combined_results['categories']:
                       combined_results['categories'][cat_id] = 'green'


        return combined_results

    def _create_events(self, article, analysis_results):
        """Create event documents in the database for categorized articles."""
        now_iso = datetime.datetime.now().isoformat()
        article_id = article.get('_id')
        logger.debug(f"Checking for events to create from article {article_id}")

        for category_id, severity in analysis_results.get('categories', {}).items():
            # Only create events for non-green categories identified in the combined analysis
            if severity == 'green':
                continue

            logger.info(f"Creating '{severity}' event for category '{category_id}' from article {article_id}")

            # Retrieve details from the combined analysis results safely
            evidence = analysis_results.get('evidence', {}).get(category_id, [])
            confidence = analysis_results.get('confidence', {}).get(category_id, 3) # Default confidence
            is_us_based = analysis_results.get('is_us_based', True) # Default US-based
            explanation = analysis_results.get('claude_explanation', '') # Use Claude's explanation if available
            reasoning = analysis_results.get('claude_reasoning', '') # Use Claude's reasoning if available
            methods = analysis_results.get('methods', ['keyword'])

            # Format evidence as HTML list
            evidence_html = ""
            try:
                if evidence and isinstance(evidence, list):
                    # Use html.escape for safety
                    evidence_html = "<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in evidence if item) + "</ul>"
                elif isinstance(evidence, str) and evidence:
                     evidence_html = f"<p>{html.escape(evidence)}</p>"
            except Exception as escape_err:
                 logger.error(f"Error escaping HTML for event evidence (Article: {article_id}, Category: {category_id}): {escape_err}")
                 evidence_html = "<p>Error formatting evidence.</p>" # Fallback


            # --- Persistence Logic: Find most recent event for this category ---
            # Look back further (e.g., 180 days) for persistence check than summary generation
            persistence_lookback_days = 180
            lookback_date = (datetime.datetime.now() - datetime.timedelta(days=persistence_lookback_days)).isoformat()

            try:
                # Define sort order based on whether using mock or real pymongo
                sort_field = 'detected_date'
                sort_direction = pymongo.DESCENDING if not is_mock_db else -1
                sort_spec = [(sort_field, sort_direction)]

                if is_mock_db:
                     # Mock find handles sort directly
                     latest_event_cursor_or_list = self.events_collection.find(
                          {'category': category_id, 'detected_date': {'$gte': lookback_date}},
                          sort=sort_spec,
                          limit=1
                     )
                     latest_event_list = latest_event_cursor_or_list # Mock returns list
                else:
                     # Real pymongo uses cursor methods
                     latest_event_cursor_or_list = self.events_collection.find(
                          {'category': category_id, 'detected_date': {'$gte': lookback_date}}
                     ).sort(sort_spec).limit(1)
                     latest_event_list = list(latest_event_cursor_or_list)


            except Exception as e:
                 logger.exception(f"Error querying latest event for category {category_id}: {e}")
                 latest_event_list = []


            start_date = now_iso # Default: start of a new streak
            previous_severity = None
            severity_change_date = None


            if latest_event_list:
                latest_event = latest_event_list[0]
                previous_severity = latest_event.get('severity')
                logger.debug(f"Found previous event for '{category_id}': Severity '{previous_severity}' on {latest_event.get('detected_date')}")

                # If severity is the same, continue the streak
                if previous_severity == severity:
                    # Use the start_date of the previous event in the streak
                    start_date = latest_event.get('start_date', latest_event['detected_date'])
                    logger.debug(f"Severity unchanged for '{category_id}', continuing streak from {start_date}")
                else:
                    # Severity changed, record the date of change (new streak starts now)
                    severity_change_date = now_iso
                    logger.debug(f"Severity changed for '{category_id}' from '{previous_severity}' to '{severity}'. New streak starts {start_date}.")
            else:
                 logger.debug(f"No recent previous event found for '{category_id}'. Starting new streak {start_date}.")


            # Create the event document
            event = {
                'article_id': article_id,
                'title': article.get('title', 'No title'),
                'url': article.get('url', ''),
                'source': article.get('source', 'Unknown'),
                'published_date': article.get('published_date', ''),
                'category': category_id,
                'severity': severity,
                'detected_date': now_iso, # Timestamp of this specific event detection
                'methods': methods,
                'explanation': explanation,
                'evidence': evidence,
                'evidence_html': evidence_html,
                'confidence': confidence,
                'is_us_based': is_us_based,
                'reasoning': reasoning,

                # Persistence tracking fields
                'start_date': start_date, # Start date of the current severity streak
                'previous_severity': previous_severity, # Severity of the preceding event (if any)
                'severity_change_date': severity_change_date, # Date severity changed (if applicable)

                # Fields calculated/updated by summary/tracker (initialize)
                'duration_days': 0,
                'confirmed': False
            }

            try:
                 self.events_collection.insert_one(event)
                 logger.info(f"Successfully created '{severity}' event for category '{category_id}' (Article: {article_id})")
            except Exception as e:
                 logger.exception(f"Failed to insert event into database for category '{category_id}', article {article_id}: {e}")


    def _generate_summary(self):
        """Generate and save a summary of the current system state."""
        logger.info("Generating analysis summary...")
        summary_lookback_days = 7 # How far back the summary counts events
        now = datetime.datetime.now()
        now_iso = now.isoformat()
        cutoff_date = now - datetime.timedelta(days=summary_lookback_days)
        cutoff_date_str = cutoff_date.isoformat()

        # Query for all events within the lookback period for counting
        try:
             query = {'detected_date': {'$gte': cutoff_date_str}}
             # No sort needed here, just fetching all within period
             recent_events_cursor = self.events_collection.find(query)
             recent_events = list(recent_events_cursor)
             logger.info(f"Found {len(recent_events)} events within the {summary_lookback_days}-day summary period.")
        except Exception as e:
             logger.exception(f"Error fetching recent events for summary: {e}")
             recent_events = []


        # Initialize summary structure
        summary = {
            'date': now_iso,
            'summary_period_days': summary_lookback_days,
            'total_events_in_period': len(recent_events),
            'severity_counts_in_period': {'green': 0, 'yellow': 0, 'orange': 0, 'red': 0},
            'categories': {},
            'overall_status': 'green', # Default
            'alert_level': 'None',     # Default
            'alert_recommendations': [], # Default
            'thresholds': {}           # Populated later
        }

        # Initialize category details
        for category_id in self.categories.keys():
            summary['categories'][category_id] = {
                'event_count_in_period': 0,
                'severity_counts_in_period': {'green': 0, 'yellow': 0, 'orange': 0, 'red': 0},
                'current_severity': 'green', # Determined by tracker based on persistence
                'is_persistent': False,
                'duration_days': 0,
                'confirmed': False,
                'start_date': None, # Start date of the current confirmed streak
                'latest_event_date_in_period': None,
                # 'recent_events_details': [] # Optional: Can make summary very large
            }

        # Process recent events to populate period counts
        for event in recent_events:
            category = event.get('category')
            severity = event.get('severity')
            if category in summary['categories'] and severity in summary['categories'][category]['severity_counts_in_period']:
                cat_summary = summary['categories'][category]
                cat_summary['event_count_in_period'] += 1
                cat_summary['severity_counts_in_period'][severity] += 1
                summary['severity_counts_in_period'][severity] += 1 # Update overall period count

                detected_date = event.get('detected_date')
                if detected_date and (cat_summary['latest_event_date_in_period'] is None or detected_date > cat_summary['latest_event_date_in_period']):
                     cat_summary['latest_event_date_in_period'] = detected_date


        # --- Apply Persistence and Confirmation using IndicatorTracker ---
        logger.info("Checking category persistence and confirmation using tracker...")
        for category_id, cat_summary in summary['categories'].items():
            # Fetch events needed for the tracker's persistence check (might need longer lookback)
            # For simplicity, we'll reuse the recent_events list here, assuming the mock tracker
            # logic is sufficient or a real tracker manages its own state/longer lookback.
            # A real implementation might query events specifically for the tracker's needs.
            category_events_for_tracker = [e for e in recent_events if e.get('category') == category_id] # Using period events for mock/simple tracker

            try:
                 # Call the tracker (real or mock)
                 persistence_data = self.tracker.check_category_persistence(category_id, category_events_for_tracker)
                 # Update summary with tracker results, ensuring keys exist
                 cat_summary['current_severity'] = persistence_data.get('current_severity', 'green')
                 cat_summary['is_persistent'] = persistence_data.get('is_persistent', False)
                 cat_summary['duration_days'] = persistence_data.get('duration_days', 0)
                 cat_summary['confirmed'] = persistence_data.get('confirmed', False)
                 cat_summary['start_date'] = persistence_data.get('start_date')

                 if cat_summary['is_persistent']:
                      logger.info(f"Tracker confirmation for '{category_id}': Severity={cat_summary['current_severity']}, Confirmed={cat_summary['confirmed']}, Duration={cat_summary['duration_days']}d")
            except Exception as e:
                 logger.exception(f"Error checking persistence for category {category_id}: {e}")
                 # Keep defaults (green, not persistent, etc.)


        # --- Calculate Overall Status and Alert Level ---
        logger.info("Calculating overall status and alert level based on confirmed categories...")
        # Configurable thresholds (could be moved to config.py)
        ORANGE_THRESHOLD_COUNT = 3 # Min number of distinct categories at confirmed orange/red
        RED_THRESHOLD_COUNT = 1    # Min number of distinct categories at confirmed red

        confirmed_orange_or_red_count = 0
        confirmed_red_count = 0

        for cat_id, cat_summary in summary['categories'].items():
            # Crucially, use the 'confirmed' status from the tracker
            if cat_summary.get('confirmed', False):
                 current_sev = cat_summary.get('current_severity', 'green')
                 if current_sev == 'red':
                     confirmed_red_count += 1
                     confirmed_orange_or_red_count += 1
                 elif current_sev == 'orange':
                     confirmed_orange_or_red_count += 1

        # Determine overall status based on confirmed counts crossing thresholds
        if confirmed_red_count >= RED_THRESHOLD_COUNT:
            summary['overall_status'] = 'red'
        elif confirmed_orange_or_red_count >= ORANGE_THRESHOLD_COUNT:
            summary['overall_status'] = 'orange'
        # If no thresholds crossed, check if there were *any* yellow/orange/red events in the period
        elif summary['severity_counts_in_period']['yellow'] > 0 or \
             summary['severity_counts_in_period']['orange'] > 0 or \
             summary['severity_counts_in_period']['red'] > 0:
             summary['overall_status'] = 'yellow'
        else:
            summary['overall_status'] = 'green'

        summary['thresholds'] = {
            'orange_alert_threshold': ORANGE_THRESHOLD_COUNT,
            'red_alert_threshold': RED_THRESHOLD_COUNT,
            'confirmed_orange_or_red_count': confirmed_orange_or_red_count,
            'confirmed_red_count': confirmed_red_count,
            'orange_threshold_crossed': confirmed_orange_or_red_count >= ORANGE_THRESHOLD_COUNT,
            'red_threshold_crossed': confirmed_red_count >= RED_THRESHOLD_COUNT
        }
        logger.info(f"Overall Status determined: {summary['overall_status']} (Confirmed Red: {confirmed_red_count}, Confirmed Orange/Red: {confirmed_orange_or_red_count})")


        # Use tracker to get alert level and recommendations based on the calculated summary
        try:
             # Call the tracker (real or mock)
             alert_level, recommendations = self.tracker.calculate_alert_level(summary)
             summary['alert_level'] = alert_level
             summary['alert_recommendations'] = recommendations
             logger.info(f"Alert Level determined: {alert_level}")
        except Exception as e:
             logger.exception(f"Error calculating alert level: {e}")
             summary['alert_level'] = 'Error'
             summary['alert_recommendations'] = ['Error calculating alert level.']


        # Save the summary
        try:
             insert_result = self.summaries_collection.insert_one(summary)
             logger.info(f"Generated and saved summary (ID: {insert_result.inserted_id})")
        except Exception as e:
             logger.exception(f"Failed to save summary to database: {e}")

        return summary


# --- Main execution block ---
if __name__ == "__main__":
    # Import pymongo here only if needed for constants like DESCENDING
    # It's already imported above in the try/except block for type checking
    # import pymongo

    print("\n" + "="*30 + " Starting News Analyzer Script " + "="*30)
    analyzer = NewsAnalyzer()

    print("\n" + "="*30 + " Analyzing Recent Articles " + "="*30)
    # Pass days=7 for a wider initial test, adjust as needed
    # Set limit high enough to process all mock articles if needed
    count = analyzer.analyze_recent_articles(days=1, limit=50) # Changed days back to 1 for typical run

    print(f"\n--- Analysis Complete ---")
    print(f"Analyzed {count} articles.")

    # Optional: Fetch and print the latest summary
    print("\n" + "="*30 + " Fetching Latest Summary " + "="*30)
    try:
        # Fetch latest summary (mock or real) using appropriate sorting
        sort_field = 'date'
        sort_direction = pymongo.DESCENDING if not is_mock_db else -1
        sort_spec = [(sort_field, sort_direction)]
        latest_summary = None

        if is_mock_db:
             summary_list = analyzer.summaries_collection.find(sort=sort_spec, limit=1)
             if summary_list:
                  latest_summary = summary_list[0]
        else:
             summary_cursor = analyzer.summaries_collection.find().sort(sort_spec).limit(1)
             latest_summary_list = list(summary_cursor)
             if latest_summary_list:
                  latest_summary = latest_summary_list[0]


        # Print summary details
        if latest_summary:
            print("\n--- Latest Summary ---")
            print(f"Summary ID: {latest_summary.get('_id')}") # Show ID
            print(f"Date Generated: {latest_summary.get('date')}")
            print(f"Summary Period: {latest_summary.get('summary_period_days')} days")
            print(f"Events in Period: {latest_summary.get('total_events_in_period')}")
            print(f"Overall Status: {latest_summary.get('overall_status', 'N/A')}")
            print(f"Alert Level: {latest_summary.get('alert_level', 'N/A')}")
            # print(f"Recommendations: {latest_summary.get('alert_recommendations', [])}") # Keep concise for now
            print(f"Thresholds Crossed: Orange={latest_summary.get('thresholds', {}).get('orange_threshold_crossed')}, Red={latest_summary.get('thresholds', {}).get('red_threshold_crossed')}")
            print(f"Confirmed Counts: Red={latest_summary.get('thresholds', {}).get('confirmed_red_count')}, Orange/Red={latest_summary.get('thresholds', {}).get('confirmed_orange_or_red_count')}")

            print("\nCategory Status (Confirmed Non-Green):")
            has_confirmed_issues = False
            # Sort categories for consistent output
            sorted_categories = sorted(latest_summary.get('categories', {}).items())
            for cat_id, data in sorted_categories:
                 if data.get('confirmed') and data.get('current_severity') != 'green':
                      has_confirmed_issues = True
                      print(f"  - {cat_id}: {data.get('current_severity','N/A').upper()} (Duration: {data.get('duration_days','N/A')}d, Start: {data.get('start_date','N/A')})")
            if not has_confirmed_issues:
                 print("  No categories currently confirmed at Yellow, Orange, or Red severity.")

        else:
            print("\nNo summary found in the database.")
    except Exception as e:
        logger.exception(f"Error fetching or printing latest summary: {e}")

    print("\n" + "="*30 + " Analyzer Script Finished " + "="*30)
