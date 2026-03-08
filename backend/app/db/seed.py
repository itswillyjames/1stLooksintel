"""Seed fixtures for golden records.

10 permits across 3 cities (Chicago, Seattle, Cincinnati).
Includes intentional entity name variations for entity resolution testing.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Dict, Any
from app.services.permit_service import create_permit
import logging

logger = logging.getLogger(__name__)

# Golden record fixtures
GOLDEN_PERMITS = [
    # Chicago (4 permits)
    {
        "city": "Chicago",
        "source_permit_id": "CHI-2024-00123",
        "filed_date": "2024-01-15T00:00:00Z",
        "issued_date": "2024-02-01T00:00:00Z",
        "address_raw": "500 W Madison St",
        "work_type": "new_construction_commercial",
        "description_raw": "New construction of 12-story mixed-use building with retail and office space",
        "valuation": 2500000,
        "applicant_raw": "Madison Development LLC",
        "contractor_raw": "Reliable Builders Inc",  # Entity variation test 1
        "owner_raw": "Madison Development LLC",
    },
    {
        "city": "Chicago",
        "source_permit_id": "CHI-2024-00456",
        "filed_date": "2024-01-20T00:00:00Z",
        "address_raw": "750 N Clark St",
        "work_type": "renovation_mixed_use",
        "description_raw": "Mixed-use renovation: ground floor retail and 3 floors residential",
        "valuation": 850000,
        "applicant_raw": "Clark Street Properties",
        "contractor_raw": "Reliable Builders, Inc.",  # Entity variation test 2 (same contractor, different formatting)
        "owner_raw": "Clark Street Properties",
    },
    {
        "city": "Chicago",
        "source_permit_id": "CHI-2024-00789",
        "filed_date": "2024-02-01T00:00:00Z",
        "address_raw": "1234 W Elm St",
        "work_type": "residential_addition",
        "description_raw": "Single family home addition - kitchen expansion",
        "valuation": 45000,
        "applicant_raw": "John Smith",
        "contractor_raw": "ABC Home Improvements",
        "owner_raw": "John Smith",
    },
    {
        "city": "Chicago",
        "source_permit_id": "CHI-2024-01011",
        "filed_date": "2024-02-10T00:00:00Z",
        "issued_date": "2024-02-25T00:00:00Z",
        "address_raw": "2100 S Western Ave",
        "work_type": "industrial_buildout",
        "description_raw": "Industrial warehouse build-out with office space and loading docks",
        "valuation": 1200000,
        "applicant_raw": "Western Industrial Partners",
        "contractor_raw": "BuildRight Construction",
        "owner_raw": "Western Industrial Partners",
    },
    
    # Seattle (3 permits)
    {
        "city": "Seattle",
        "source_permit_id": "SEA-2024-5678",
        "filed_date": "2024-01-25T00:00:00Z",
        "issued_date": "2024-02-15T00:00:00Z",
        "address_raw": "400 Pine St",
        "work_type": "commercial_tenant_improvement",
        "description_raw": "Commercial tenant improvement for tech office space - open floor plan",
        "valuation": 950000,
        "applicant_raw": "Pine Street Tech LLC",
        "contractor_raw": "Pacific Northwest Builders",
        "owner_raw": "Pine Street Properties",
    },
    {
        "city": "Seattle",
        "source_permit_id": "SEA-2024-6789",
        "filed_date": "2024-02-05T00:00:00Z",
        "address_raw": "1500 N 45th St",
        "work_type": "institutional_renovation",
        "description_raw": "School renovation including new HVAC, electrical, and classroom expansion",
        "valuation": 3100000,
        "applicant_raw": "Seattle Public Schools",
        "contractor_raw": "Educational Facilities Group",
        "owner_raw": "Seattle Public Schools",
    },
    {
        "city": "Seattle",
        "source_permit_id": "SEA-2024-7890",
        "filed_date": "2024-02-12T00:00:00Z",
        "address_raw": "823 E Lake St",
        "work_type": "residential_adu",
        "description_raw": "Accessory dwelling unit (ADU) construction in backyard",
        "valuation": 75000,
        "applicant_raw": "Emily Johnson",
        "contractor_raw": "Lake City Contractors",
        "owner_raw": "Emily Johnson",
    },
    
    # Cincinnati (3 permits)
    {
        "city": "Cincinnati",
        "source_permit_id": "CIN-2024-9876",
        "filed_date": "2024-01-30T00:00:00Z",
        "issued_date": "2024-02-20T00:00:00Z",
        "address_raw": "600 Vine St",
        "work_type": "commercial_retail_buildout",
        "description_raw": "Commercial retail build-out for restaurant and bar - full kitchen installation",
        "valuation": 780000,
        "applicant_raw": "Vine Street Hospitality",
        "contractor_raw": "Queen City Builders",
        "owner_raw": "Vine Street Hospitality",
    },
    {
        "city": "Cincinnati",
        "source_permit_id": "CIN-2024-8765",
        "filed_date": "2024-02-08T00:00:00Z",
        "address_raw": "3400 Madison Rd",
        "work_type": "industrial_expansion",
        "description_raw": "Industrial manufacturing expansion - new production line and equipment installation",
        "valuation": 1800000,
        "applicant_raw": "Madison Manufacturing Corp",
        "contractor_raw": "Industrial Solutions LLC",
        "owner_raw": "Madison Manufacturing Corp",
    },
    {
        "city": "Cincinnati",
        "source_permit_id": "CIN-2024-7654",
        "filed_date": "2024-02-15T00:00:00Z",
        "address_raw": "1122 Hill Ave",
        "work_type": "residential_deck",
        "description_raw": "Residential deck addition - 200 sq ft rear deck",
        "valuation": 12000,
        "applicant_raw": "Michael Brown",
        "contractor_raw": "Hill Decks & Patios",
        "owner_raw": "Michael Brown",
    },
]


async def seed_permits(
    db: AsyncIOMotorDatabase,
    force: bool = False
) -> Dict[str, Any]:
    """Seed permits idempotently.
    
    Args:
        db: MongoDB database instance
        force: If True, delete existing permits and reseed
    
    Returns:
        Dict with message, permits_created, already_existed counts
    """
    if force:
        # Delete all existing permits
        delete_result = await db.permits.delete_many({})
        logger.info(f"Force seed: deleted {delete_result.deleted_count} existing permits")
    
    permits_created = 0
    already_existed = 0
    
    for permit_data in GOLDEN_PERMITS:
        # Check if permit already exists before creating
        existing = await db.permits.find_one({
            "city": permit_data["city"],
            "source_permit_id": permit_data["source_permit_id"]
        })
        
        if existing:
            already_existed += 1
            continue
        
        try:
            # create_permit handles duplicate detection via unique index
            result = await create_permit(db, permit_data.copy())
            permits_created += 1
        except Exception as e:
            if "duplicate" in str(e).lower():
                already_existed += 1
            else:
                logger.error(f"Error seeding permit: {e}")
                raise
    
    message = f"Seeded {permits_created} permits" if permits_created > 0 else "All permits already exist"
    
    return {
        "message": message,
        "permits_created": permits_created,
        "already_existed": already_existed
    }
