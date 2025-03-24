import requests
import feedparser
import datetime
import time
import logging
from config import (
    GUARDIAN_API_KEY, 
    NEWS_API_KEY,
    NEWS_SOURCES,
    COLLECTION_ARTICLES,
    NEWSDATA_API_KEY,
    THENEWSAPI_KEY
)
from modules.database import get_collection

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('collector')

class NewsCollector:
    """
    Collects news from multiple sources using free APIs and RSS feeds.
    Filters for political news and stores in the database.
    """
    
    def __init__(self):
        try:
            self.articles_collection = get_collection(COLLECTION_ARTICLES)
            logger.info("Successfully connected to database")
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            raise
        
        # Configure news sources with updated URLs
        self.sources = {
            # The Guardian API
            'guardian': {
                'type': 'api',
                'url': 'https://content.guardianapis.com/search',
                'params': {
                    'api-key': GUARDIAN_API_KEY,
                    'section': 'us-news,politics',
                    'show-fields': 'headline,body,byline,publication',
                    'page-size': 10  # Reduced for testing
                }
            },
            # NewsAPI for multiple sources
            'newsapi': {
                'type': 'api',
                'url': 'https://newsapi.org/v2/top-headlines',
                'params': {
                    'apiKey': NEWS_API_KEY,
                    'country': 'us',
                    'category': 'politics',
                    'pageSize': 10  # Reduced for testing
                }
            },
            # NewsData.io API
            'newsdata': {
                'type': 'custom',
                'processor': '_collect_from_newsdata'
            },
            # TheNewsAPI
            'thenewsapi': {
                'type': 'custom',
                'processor': '_collect_from_thenewsapi'
            },
            # Updated and expanded RSS feeds
            'ap_politics': {
                'type': 'rss',
                'url': 'https://feeds.apnews.com/apnews/politics'
            },
            'reuters_politics': {
                'type': 'rss',
                'url': 'https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best&best-topic=political-general'
            },
            'npr_politics': {
                'type': 'rss',
                'url': 'https://feeds.npr.org/1014/rss.xml'
            },
            'bbc_world': {
                'type': 'rss',
                'url': 'http://feeds.bbci.co.uk/news/world/rss.xml'
            },
            'nyt_politics': {
                'type': 'rss',
                'url': 'https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml'
            },
            'wapo_politics': {
                'type': 'rss',
                'url': 'https://feeds.washingtonpost.com/rss/politics'
            },
            'politico': {
                'type': 'rss',
                'url': 'https://www.politico.com/rss/politicopicks.xml'
            },
            'the_hill': {
                'type': 'rss',
                'url': 'https://thehill.com/homenews/feed/'
            },
            'propublica': {
                'type': 'rss',
                'url': 'https://feeds.propublica.org/propublica/main'
            },
            'democracy_now': {
                'type': 'rss',
                'url': 'https://www.democracynow.org/democracynow.rss'
            },
            'the_intercept': {
                'type': 'rss',
                'url': 'https://theintercept.com/feed/?lang=en'
            },
            'vox_policy': {
                'type': 'rss',
                'url': 'https://www.vox.com/rss/policy-and-politics/index.xml'
            },
            'reason': {
                'type': 'rss',
                'url': 'https://reason.com/feed/'
            },
            'the_nation': {
                'type': 'rss',
                'url': 'https://www.thenation.com/feed/?post_type=article'
            },
            'national_review': {
                'type': 'rss',
                'url': 'https://www.nationalreview.com/feed/'
            }
        }
        
        # Comprehensive keywords for the expanded framework
        self.political_keywords = [
            # Electoral integrity
            'democracy', 'election', 'voter', 'voting', 'ballot', 'congress',
            'supreme court', 'constitution', 'president', 'rights', 'protest',
            'executive order', 'justice department', 'civil liberties',
            'free speech', 'censorship', 'military', 'detention', 'surveillance',
            'security clearance', 'opposition', 'investigation', 'impeach',
            'authoritarian', 'media freedom', 'journalist', 'corruption',
            'rule of law', 'checks and balances', 'power grab',
            # Judicial independence
            'court packing', 'judge removal', 'judicial independence',
            'supreme court', 'constitutional court', 'judicial review',
            # Information manipulation
            'disinformation', 'fake news', 'propaganda', 'fact check',
            'social media manipulation', 'troll farm', 'bot network',
            # Institutional erosion
            'electoral commission', 'oversight body', 'inspector general',
            'term limits', 'civil service', 'bureaucracy', 'career official'
        ]
    
    def collect_all(self):
        """Collect news from all configured sources"""
        new_articles_count = 0
        logger.info("Starting news collection cycle")
        
        # For testing, try using a dummy article if no real ones are found
        added_dummy = False
        
        for source_name, config in self.sources.items():
            try:
                logger.info(f"Collecting from {source_name}")
                
                if config['type'] == 'api':
                    articles = self._collect_from_api(source_name, config)
                elif config['type'] == 'rss':
                    articles = self._collect_from_rss(source_name, config)
                elif config['type'] == 'custom':
                    # Call the custom processor method
                    processor_method = getattr(self, config['processor'], None)
                    if processor_method and callable(processor_method):
                        articles = processor_method()
                    else:
                        logger.warning(f"Unknown processor method for {source_name}")
                        continue
                else:
                    logger.warning(f"Unknown source type for {source_name}")
                    continue
                
                # Add debugging info
                logger.info(f"Initial collection from {source_name}: {len(articles)} articles")
                
                # MODIFY THIS SECTION to add US filtering:
                logger.info(f"Initial collection from {source_name}: {len(articles)} articles")

                # First filter to only US content
                articles = self._filter_us_content(articles) 
                logger.info(f"After US filtering from {source_name}: {len(articles)} articles")
                # Filter for political content
                filtered_articles = self._filter_political_content(articles)
                
                logger.info(f"After filtering from {source_name}: {len(filtered_articles)} articles")
                
                # Store articles in database
                try:
                    new_count = self._store_articles(filtered_articles)
                    new_articles_count += new_count
                    logger.info(f"Stored {new_count} new articles from {source_name}")
                except Exception as e:
                    logger.error(f"Error storing articles from {source_name}: {str(e)}")
                
                # Sleep between API calls to avoid rate limiting
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error collecting from {source_name}: {str(e)}")
        
        # If no articles were collected, add a dummy article for testing
        if new_articles_count == 0 and not added_dummy:
            try:
                logger.info("Adding dummy article for testing purposes")
                dummy_article = {
                    'source': 'Test Source',
                    'title': 'Test Political Article',
                    'url': 'https://example.com/test-article',
                    'published_date': datetime.datetime.now().isoformat(),
                    'content': 'This is a test article about voter suppression and election integrity concerns.',
                    'collected_at': datetime.datetime.now().isoformat(),
                    'analyzed': False
                }
                self.articles_collection.insert_one(dummy_article)
                new_articles_count += 1
                added_dummy = True
            except Exception as e:
                logger.error(f"Error adding dummy article: {str(e)}")
        
        logger.info(f"Collection cycle complete. Total new articles: {new_articles_count}")
        return new_articles_count
    
    def _collect_from_api(self, source_name, config):
        """Collect news from an API source"""
        articles = []
        
        try:
            # Log the request we're about to make
            logger.info(f"Making request to {config['url']} with params: {config['params']}")
            
            # Add user agent to avoid some blocks
            headers = {
                'User-Agent': 'Political Risk Monitor/1.0'
            }
            
            response = requests.get(
                config['url'], 
                params=config['params'],
                headers=headers,
                timeout=10  # Add timeout
            )
            
            # Log response status
            logger.info(f"Response from {source_name}: Status {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"API error {response.status_code} from {source_name}: {response.text}")
                return articles
            
            # Log successful response
            logger.info(f"Successfully got response from {source_name}")
            
            data = response.json()
            logger.info(f"Response data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            # Parse according to the specific API format
            if source_name == 'guardian':
                results = data.get('response', {}).get('results', [])
                logger.info(f"Guardian results count: {len(results)}")
                
                for item in results:
                    article = {
                        'source': 'The Guardian',
                        'title': item.get('webTitle', ''),
                        'url': item.get('webUrl', ''),
                        'published_date': item.get('webPublicationDate', ''),
                        'content': item.get('fields', {}).get('body', ''),
                        'section': item.get('sectionName', ''),
                        'collected_at': datetime.datetime.now().isoformat()
                    }
                    articles.append(article)
                    
            elif source_name == 'newsapi':
                articles_data = data.get('articles', [])
                logger.info(f"NewsAPI articles count: {len(articles_data)}")
                
                for item in articles_data:
                    source_name = item.get('source', {}).get('name', 'Unknown')
                    
                    article = {
                        'source': source_name,
                        'title': item.get('title', ''),
                        'url': item.get('url', ''),
                        'published_date': item.get('publishedAt', ''),
                        'content': item.get('content', item.get('description', '')),
                        'author': item.get('author', ''),
                        'collected_at': datetime.datetime.now().isoformat()
                    }
                    articles.append(article)
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception in API collection from {source_name}: {str(e)}")
        except ValueError as e:
            logger.error(f"JSON parsing error from {source_name}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in API collection from {source_name}: {str(e)}")
        
        # Debug info
        if len(articles) == 0:
            if 'response' in locals():
                logger.info(f"Empty results debug for {source_name}. Response preview: {response.text[:300]}...")
        
        return articles
    
    def _collect_from_rss(self, source_name, config):
        """Collect news from an RSS feed with improved content extraction"""
        articles = []
        
        try:
            # Log the request
            logger.info(f"Fetching RSS feed from {config['url']}")
            
            # Add user agent to avoid some feed blocks
            user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            feed = feedparser.parse(config['url'], agent=user_agent)
            
            # Log feed info
            logger.info(f"Feed info - version: {feed.get('version', 'unknown')}, " 
                       f"encoding: {feed.get('encoding', 'unknown')}")
            logger.info(f"Feed entries count: {len(feed.entries) if hasattr(feed, 'entries') else 0}")
            
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                logger.warning(f"No entries found in RSS feed from {source_name}")
                # Log feed bozo status (indicates feed parsing issues)
                if hasattr(feed, 'bozo') and feed.bozo:
                    logger.warning(f"Feed from {source_name} has bozo bit set: {feed.bozo_exception}")
                return articles
            
            for entry in feed.entries:
                # Extract the best possible content
                content = ''
                
                # Try to get content from various possible fields
                if 'content' in entry and len(entry.content) > 0:
                    content = entry.content[0].value
                elif 'summary_detail' in entry and entry.summary_detail.get('value'):
                    content = entry.summary_detail.value
                elif 'summary' in entry:
                    content = entry.summary
                elif 'description' in entry:
                    content = entry.description
                
                # Try to get the publication date in various formats
                published_date = None
                for date_field in ['published', 'pubDate', 'updated', 'created', 'date']:
                    if date_field in entry:
                        published_date = entry[date_field]
                        break
                
                # If we couldn't find a date, use current time
                if not published_date:
                    published_date = datetime.datetime.now().isoformat()
                
                # Create the article object
                article = {
                    'source': feed.feed.title if hasattr(feed, 'feed') and hasattr(feed.feed, 'title') else source_name,
                    'title': entry.get('title', ''),
                    'url': entry.get('link', ''),
                    'published_date': published_date,
                    'content': content,
                    'author': entry.get('author', entry.get('creator', '')),
                    'collected_at': datetime.datetime.now().isoformat(),
                    'analyzed': False
                }
                
                # Add any tags/categories if available
                if 'tags' in entry and len(entry.tags) > 0:
                    article['categories'] = [tag.term for tag in entry.tags]
                elif 'category' in entry:
                    article['categories'] = [entry.category]
                
                articles.append(article)
                
        except Exception as e:
            logger.error(f"Exception in RSS collection from {source_name}: {str(e)}")
        
        return articles
    
    def _collect_from_newsdata(self):
        """Collect news from NewsData.io API"""
        articles = []
        
        try:
            # Base URL for NewsData API
            base_url = 'https://newsdata.io/api/1/news'
            
            # Parameters for the API request
            params = {
                'apikey': NEWSDATA_API_KEY,
                'country': 'us',  # Focus on US news, add more as needed
                'category': 'politics',  # Focus on political news
                'language': 'en',  # English language
                'size': 10  # Number of articles to retrieve
            }
            
            # Log the request
            logger.info(f"Making request to NewsData.io API with params: {params}")
            
            # Make the request
            response = requests.get(base_url, params=params, timeout=10)
            
            # Check if the request was successful
            if response.status_code == 200:
                data = response.json()
                
                # Check if we have results
                if 'results' in data and isinstance(data['results'], list):
                    logger.info(f"Retrieved {len(data['results'])} articles from NewsData.io")
                    
                    # Process each article
                    for item in data['results']:
                        article = {
                            'source': item.get('source_id', 'NewsData.io'),
                            'title': item.get('title', ''),
                            'url': item.get('link', ''),
                            'published_date': item.get('pubDate', ''),
                            'content': item.get('content', item.get('description', '')),
                            'author': item.get('creator', [None])[0],
                            'category': ', '.join(item.get('category', [])),
                            'collected_at': datetime.datetime.now().isoformat(),
                            'analyzed': False
                        }
                        articles.append(article)
                else:
                    logger.warning(f"No results found in NewsData.io response: {data}")
            else:
                logger.error(f"NewsData.io API error: Status {response.status_code}, Response: {response.text}")
        
        except Exception as e:
            logger.error(f"Exception in NewsData.io collection: {str(e)}")
        
        return articles
    
    def _collect_from_thenewsapi(self):
        """Collect news from TheNewsAPI"""
        articles = []
        
        try:
            # Base URL for The News API
            base_url = 'https://api.thenewsapi.com/v1/news/all'
            
            # Parameters for the API request
            params = {
                'api_token': THENEWSAPI_KEY,
                'categories': 'politics',
                'language': 'en',
                'limit': 10  # Number of articles to retrieve
            }
            
            # Log the request
            logger.info(f"Making request to TheNewsAPI with params: {params}")
            
            # Make the request
            response = requests.get(base_url, params=params, timeout=10)
            
            # Check if the request was successful
            if response.status_code == 200:
                data = response.json()
                
                # Check if we have results
                if 'data' in data and isinstance(data['data'], list):
                    logger.info(f"Retrieved {len(data['data'])} articles from TheNewsAPI")
                    
                    # Process each article
                    for item in data['data']:
                        article = {
                            'source': item.get('source', 'TheNewsAPI'),
                            'title': item.get('title', ''),
                            'url': item.get('url', ''),
                            'published_date': item.get('published_at', ''),
                            'content': item.get('snippet', item.get('description', '')),
                            'author': '',  # The News API doesn't provide author information in the free tier
                            'category': ', '.join(item.get('categories', [])),
                            'collected_at': datetime.datetime.now().isoformat(),
                            'analyzed': False
                        }
                        articles.append(article)
                else:
                    logger.warning(f"No data found in TheNewsAPI response: {data}")
            else:
                logger.error(f"TheNewsAPI error: Status {response.status_code}, Response: {response.text}")
        
        except Exception as e:
            logger.error(f"Exception in TheNewsAPI collection: {str(e)}")
        
        return articles
    def _filter_us_content(self, articles):
        """Filter articles to only include US-related content"""
        filtered = []
        us_keywords = [
            "united states", "u.s.", "us ", "usa", "american", 
            "biden", "trump", "congress", "white house", "washington",
            "supreme court", "federal", "pentagon", "democrats", "republicans"
        ]
    
        for article in articles:
            # Combine title and content for keyword search
            text = f"{article.get('title', '')} {article.get('content', '')}".lower()
        
            # Check if any US keywords are present
            if any(us_keyword in text for us_keyword in us_keywords):
                filtered.append(article)
    
        logger.info(f"Filtered {len(articles) - len(filtered)} non-US articles")
        return filtered
    def _filter_political_content(self, articles):
        """
        Enhanced filter to identify political content with specific focus on 
        indicators relevant to the Despotism Readiness Framework
        """
        filtered = []
        total_count = len(articles)
        filtered_count = 0
        
        for article in articles:
            # Combine title and content for keyword search
            text = f"{article['title']} {article.get('content', '')}".lower()
            
            # Check if any political keywords are present
            if any(keyword.lower() in text for keyword in self.political_keywords):
                filtered.append(article)
                filtered_count += 1
        
        logger.info(f"Filtered {filtered_count}/{total_count} articles as politically relevant")
        return filtered
    def _store_articles(self, articles):
        """Store articles in the database, avoiding duplicates"""
        new_count = 0
    
        for article in articles:
            # Ensure URL is present
            if not article.get('url'):
                logger.warning(f"Skipping article without URL: {article.get('title', 'No title')}")
                continue
            
            try:
                # Check if article already exists (by URL)
                existing = self.articles_collection.find_one({'url': article['url']})
            
                if not existing:
                    # Add 'analyzed' flag set to False for new articles
                    article['analyzed'] = False
                
                    # Insert the article
                    result = self.articles_collection.insert_one(article)
                    logger.info(f"Inserted article with ID: {result.inserted_id}")
                    new_count += 1
            except Exception as e:
                logger.error(f"Error storing article {article.get('title', 'unknown')}: {str(e)}")
    
        return new_count
    # Find this existing method in collector.py
def _filter_political_content(self, articles):
    """Filter articles to only include political content relevant to the framework"""
    filtered = []
    
    for article in articles:
        # Combine title and content for keyword search
        text = f"{article['title']} {article.get('content', '')}".lower()
        
        # Check if any political keywords are present
        if any(keyword.lower() in text for keyword in self.political_keywords):
            filtered.append(article)
    
    return filtered

# ADD YOUR NEW METHOD HERE, right after the _filter_political_content method:
def _filter_us_content(self, articles):
    """Filter articles to only include US-related content"""
    filtered = []
    us_keywords = [
        "united states", "u.s.", "us ", "usa", "american", 
        "biden", "trump", "congress", "white house", "washington",
        "supreme court", "federal", "pentagon", "democrats", "republicans"
    ]
    
    for article in articles:
        # Combine title and content for keyword search
        text = f"{article['title']} {article.get('content', '')}".lower()
        
        # Check if any US keywords are present
        if any(keyword.lower() in text for keyword in us_keywords):
            filtered.append(article)
    
    logger.info(f"Filtered {len(articles) - len(filtered)} non-US articles")
    return filtered
    def _store_articles(self, articles):
        """Store articles in the database, avoiding duplicates"""
        new_count = 0
        
        for article in articles:
            # Ensure URL is present
            if not article.get('url'):
                logger.warning(f"Skipping article without URL: {article.get('title', 'No title')}")
                continue
                
            try:
                # Check if article already exists (by URL)
                existing = self.articles_collection.find_one({'url': article['url']})
                
                if not existing:
                    # Add 'analyzed' flag set to False for new articles
                    article['analyzed'] = False
                    
                    # Insert the article
                    result = self.articles_collection.insert_one(article)
                    logger.info(f"Inserted article with ID: {result.inserted_id}")
                    new_count += 1
            except Exception as e:
                logger.error(f"Error storing article {article.get('title', 'unknown')}: {str(e)}")
        
        return new_count


# For testing directly
if __name__ == "__main__":
    collector = NewsCollector()
    new_count = collector.collect_all()
    print(f"Collected {new_count} new articles")