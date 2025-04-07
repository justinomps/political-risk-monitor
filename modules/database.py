import pymongo
from config import MONGODB_URI, DATABASE_NAME

client = None
db = None

def connect():
    """Connect to MongoDB database"""
    global client, db
    
    # Extract the tlsCAFile parameter if it exists in the URI
    uri = MONGODB_URI
    
    try:
        client = pymongo.MongoClient(uri)
        db = client[DATABASE_NAME]
        # Test the connection
        client.admin.command('ping')
        return db
    except Exception as e:
        print(f"Connection error: {e}")
        raise
    
def get_db():
    """Get database connection"""
    global db
    if db is None:
        db = connect()
    return db

def close():
    """Close database connection"""
    global client
    if client is not None:
        client.close()
        client = None

def get_collection(collection_name):
    """Get a specific collection"""
    db = get_db()
    return db[collection_name]