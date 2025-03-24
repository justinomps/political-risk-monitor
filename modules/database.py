import pymongo
from config import MONGODB_URI, DATABASE_NAME

client = None
db = None

def connect():
    """Connect to MongoDB database"""
    global client, db
    client = pymongo.MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    return db

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