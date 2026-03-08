from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path

# Import app modules
from app.db import init_db
from app.db.collections import create_indexes
from app.api.permits import router as permits_router
from app.api.reports import router as reports_router

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize MongoDB
mongo_url = os.environ['MONGO_URL']
db_name = os.environ['DB_NAME']
db = init_db(mongo_url, db_name)

# Create the main app
app = FastAPI(
    title="Permit Intel API",
    description="Single-operator permit intelligence workbench",
    version="1.0.0-milestone-1"
)

# Create API router with /api prefix
api_router = APIRouter(prefix="/api")

# Health check
@api_router.get("/")
async def root():
    return {
        "message": "Permit Intel API - Milestone 1",
        "status": "operational",
        "milestone": "1 - Data Model + Persistence + Seed"
    }

# Include sub-routers
api_router.include_router(permits_router)
api_router.include_router(reports_router)

# Include the API router in the main app
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Create indexes on startup."""
    logger.info("Starting Permit Intel API...")
    logger.info(f"Connected to MongoDB: {db_name}")
    
    # Create all indexes
    await create_indexes(db)
    logger.info("Indexes created successfully")
    logger.info("API ready for requests")


@app.on_event("shutdown")
async def shutdown_event():
    """Close MongoDB connection on shutdown."""
    from app.db import client
    if client:
        client.close()
        logger.info("MongoDB connection closed")
