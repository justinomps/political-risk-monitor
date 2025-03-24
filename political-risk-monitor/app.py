from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import pymongo
import datetime
import logging
import json
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash

from config import (
    SECRET_KEY, 
    MONGODB_URI, 
    DATABASE_NAME,
    COLLECTION_ARTICLES,
    COLLECTION_EVENTS,
    COLLECTION_SUMMARIES,
    COLLECTION_USERS,
    CATEGORIES
)
from modules.tracker import IndicatorTracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('app')

# Initialize Flask app
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Custom filter for datetime formatting
@app.template_filter('datetime')
def format_datetime(value, format='%Y-%m-%d %H:%M'):
    if isinstance(value, str):
        try:
            value = datetime.datetime.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime(format)

# JSON encoder for MongoDB ObjectId
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)

app.json_encoder = JSONEncoder

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database connection
mongo_client = pymongo.MongoClient(MONGODB_URI)
db = mongo_client[DATABASE_NAME]
logger.info("Database connection initialized")

# User model
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.email = user_data.get('email', '')
        self.name = user_data.get('name', 'User')
        self.subscription_level = user_data.get('subscription_level', 'free')
        self.preferences = user_data.get('preferences', {})

@login_manager.user_loader
def load_user(user_id):
    user_data = db[COLLECTION_USERS].find_one({'_id': user_id})
    if not user_data:
        return None
    return User(user_data)

# Clean up when app shuts down
@app.teardown_appcontext
def cleanup(exception=None):
    # Don't close the connection here 
    # Only log that this function was called
    logger.debug("Teardown appcontext called")

# Routes
@app.route('/')
def index():
    # Get the most recent summary
    summary = db[COLLECTION_SUMMARIES].find_one(sort=[('date', pymongo.DESCENDING)])
    
    # If no summary exists yet, create a minimal default one
    if not summary:
        summary = {
            'date': datetime.datetime.now().isoformat(),
            'overall_status': 'green',
            'yellow_count': 0,
            'orange_count': 0,
            'red_count': 0,
            'alert_level': 1,
            'alert_recommendations': "Normal monitoring, no action required.",
            'categories': {},
            'thresholds': {
                'orange_threshold': 3,
                'red_threshold': 1,
                'orange_threshold_crossed': False,
                'red_threshold_crossed': False
            }
        }
        # Initialize empty categories
        for cat_id in CATEGORIES:
            summary['categories'][cat_id] = {
                'green': 0,
                'yellow': 0,
                'orange': 0,
                'red': 0,
                'current_severity': 'green',
                'duration_days': 0,
                'confirmed': False
            }
    
    # Get recent events
    recent_events = list(db[COLLECTION_EVENTS].find().sort('detected_date', pymongo.DESCENDING).limit(5))
    
    # Create timeline data (last 7 days)
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=7)
    
    # Generate date labels
    dates = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date.strftime('%Y-%m-%d'))
        current_date += datetime.timedelta(days=1)
    
    # Initialize counts
    yellow_counts = [0] * len(dates)
    orange_counts = [0] * len(dates)
    red_counts = [0] * len(dates)
    
    # Get events for the date range
    events_in_range = list(db[COLLECTION_EVENTS].find({
        'detected_date': {
            '$gte': start_date.isoformat(),
            '$lte': end_date.isoformat()
        }
    }))
    
    # Count events by date and severity
    for event in events_in_range:
        try:
            event_date = datetime.datetime.fromisoformat(event['detected_date']).strftime('%Y-%m-%d')
            if event_date in dates:
                idx = dates.index(event_date)
                severity = event['severity']
                if severity == 'yellow':
                    yellow_counts[idx] += 1
                elif severity == 'orange':
                    orange_counts[idx] += 1
                elif severity == 'red':
                    red_counts[idx] += 1
        except (ValueError, KeyError):
            continue
    
    timeline_data = {
        'dates': dates,
        'yellow': yellow_counts,
        'orange': orange_counts,
        'red': red_counts
    }
    
    return render_template(
        'dashboard.html',
        summary=summary,
        recent_events=recent_events,
        categories=CATEGORIES,
        timeline_data=timeline_data
    )

@app.route('/events')
def events():
    # Get category filter if provided
    category = request.args.get('category')
    severity = request.args.get('severity')
    
    # Build query
    query = {}
    if category:
        query['category'] = category
    if severity:
        query['severity'] = severity
    
    # Get events
    events = list(db[COLLECTION_EVENTS].find(query).sort('detected_date', pymongo.DESCENDING).limit(50))
    
    return render_template(
        'events.html',
        events=events,
        categories=CATEGORIES,
        selected_category=category,
        selected_severity=severity
    )

@app.route('/event/<event_id>')
def event_detail(event_id):
    # Find event
    event = db[COLLECTION_EVENTS].find_one({'_id': ObjectId(event_id)})
    if not event:
        flash('Event not found', 'danger')
        return redirect(url_for('events'))
    
    # Find related article
    article = None
    if 'article_id' in event:
        article = db[COLLECTION_ARTICLES].find_one({'_id': event['article_id']})
    
    return render_template(
        'event_detail.html',
        event=event,
        article=article,
        categories=CATEGORIES
    )

@app.route('/trends')
def trends():
    """Display trend analysis and visualization"""
    # Initialize tracker
    tracker = IndicatorTracker()
    
    # Get trends for all categories
    category_trends = {}
    for cat_id in CATEGORIES:
        trend_data = tracker.get_category_trends(cat_id)
        
        # Get current status from most recent history point
        current_status = trend_data['history'][-1][1] if trend_data['history'] else 'green'
        
        # Determine if indicator is confirmed based on persistence rules
        confirmed = False
        days = trend_data['days_at_current_level']
        
        if current_status == 'yellow' and days >= 30:
            confirmed = True
        elif current_status == 'orange' and days >= 14:
            confirmed = True
        elif current_status == 'red':
            confirmed = True
            
        # Add to category trends
        category_trends[cat_id] = {
            'trend': trend_data['trend'],
            'days_at_current_level': trend_data['days_at_current_level'],
            'history': trend_data['history'],
            'current_status': current_status,
            'confirmed': confirmed
        }
    
    # Get threshold history
    threshold_history = tracker.get_threshold_history()
    
    # Get confirmed indicators count
    confirmed_counts = tracker.get_confirmed_indicators_count()
    
    # Get accelerating categories
    accelerating_categories = tracker.get_accelerating_categories()
    
    # Get alert level statistics
    alert_statistics = tracker.get_alert_level_statistics()
    
    # Get current alert level
    current_alert_level = alert_statistics['current_level']
    
    return render_template(
        'trends.html',
        category_trends=category_trends,
        threshold_history=threshold_history,
        confirmed_counts=confirmed_counts,
        accelerating_categories=accelerating_categories,
        alert_statistics=alert_statistics,
        current_alert_level=current_alert_level,
        categories=CATEGORIES
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user_data = db[COLLECTION_USERS].find_one({'email': email})
        
        if user_data and check_password_hash(user_data['password'], password):
            user = User(user_data)
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        
        flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        
        # Check if user already exists
        existing_user = db[COLLECTION_USERS].find_one({'email': email})
        if existing_user:
            flash('Email already registered', 'danger')
            return render_template('register.html')
        
        # Create new user
        user_id = ObjectId()
        user_data = {
            '_id': user_id,
            'email': email,
            'password': generate_password_hash(password),
            'name': name,
            'subscription_level': 'free',
            'created_at': datetime.datetime.now().isoformat(),
            'preferences': {
                'alerts_enabled': True,
                'alert_threshold': 'orange'
            }
        }
        
        db[COLLECTION_USERS].insert_one(user_data)
        
        # Log in the new user
        user = User(user_data)
        login_user(user)
        
        flash('Account created successfully', 'success')
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/api/summary')
def api_summary():
    """API endpoint to get the current summary"""
    summary = db[COLLECTION_SUMMARIES].find_one(sort=[('date', pymongo.DESCENDING)])
    if not summary:
        return jsonify({'error': 'No summary available'}), 404
    
    # Convert ObjectId to string
    summary['_id'] = str(summary['_id'])
    
    return jsonify(summary)

@app.route('/api/events')
def api_events():
    """API endpoint to get recent events"""
    limit = int(request.args.get('limit', 10))
    category = request.args.get('category')
    severity = request.args.get('severity')
    
    query = {}
    if category:
        query['category'] = category
    if severity:
        query['severity'] = severity
    
    events = list(db[COLLECTION_EVENTS].find(query).sort('detected_date', pymongo.DESCENDING).limit(limit))
    
    # Convert ObjectId to string
    for event in events:
        event['_id'] = str(event['_id'])
        if 'article_id' in event:
            event['article_id'] = str(event['article_id'])
    
    return jsonify(events)

# For application shutdown handling
def close_mongo_connection():
    if mongo_client:
        mongo_client.close()
        logger.info("MongoDB connection closed")

# For development only - remove in production
if __name__ == '__main__':
    try:
        app.run(debug=True)
    finally:
        # Make sure to close the MongoDB connection when the app shuts down
        close_mongo_connection()