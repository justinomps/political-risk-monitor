# clear_db.py
import pymongo
from config import MONGODB_URI, DATABASE_NAME, COLLECTION_ARTICLES, COLLECTION_EVENTS, COLLECTION_SUMMARIES

def clear_database():
    # Connect to MongoDB
    client = pymongo.MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    
    # Clear each collection
    articles_deleted = db[COLLECTION_ARTICLES].delete_many({})
    events_deleted = db[COLLECTION_EVENTS].delete_many({})
    summaries_deleted = db[COLLECTION_SUMMARIES].delete_many({})
    
    # Print results
    print(f"Deleted {articles_deleted.deleted_count} articles")
    print(f"Deleted {events_deleted.deleted_count} events")
    print(f"Deleted {summaries_deleted.deleted_count} summaries")
    
    client.close()
    print("Database cleared successfully")

if __name__ == "__main__":
    # Confirm before deleting
    confirm = input("Are you sure you want to delete ALL data? (yes/no): ")
    if confirm.lower() == 'yes':
        clear_database()
    else:
        print("Operation cancelled")