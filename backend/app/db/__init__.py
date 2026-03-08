from motor.motor_asyncio import AsyncIOMotorClient
import os

# MongoDB client (initialized in server.py)
client = None
db = None

def init_db(mongo_url: str, db_name: str):
    global client, db
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    return db

def get_db():
    if db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return db
