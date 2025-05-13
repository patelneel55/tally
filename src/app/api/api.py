"""
API Router
----------

This module configures the main API router for the Analyst AI application.
It serves as a central hub that organizes all API endpoints into logical groups.

What this file does:
1. Creates a main router that will handle all API requests
2. Organizes endpoints by feature/functionality (e.g., company data)
3. Attaches prefixes and tags to help organize the API structure

How it fits in the architecture:
- Acts as the "traffic controller" for API requests
- Keeps endpoints organized by domain/feature
- Allows for modular development where new features can be easily added

For end users:
- Creates a logical, hierarchical API structure
- Makes the API documentation more organized and easier to navigate
- Allows for versioning and consistent URL patterns
"""

from fastapi import APIRouter

from app.api.endpoints import (
    export,
    financial_modeling,
    sec_analysis,
    sec_routes,
    utilities,
)


# Create the main API router
# This router will include all other routers and be included in the main app
api_router = APIRouter()

# Include SEC analysis endpoints
api_router.include_router(
    sec_analysis.router,
    prefix="/sec",  # All SEC analysis endpoints will start with /sec
    tags=["sec"],  # In the docs, these endpoints will be under "sec" section
)

# Include SEC historical analysis endpoints
api_router.include_router(
    sec_routes.router,
    prefix="/sec-data",  # Change prefix to /sec-data to avoid conflict with /sec
    tags=["sec-data"],  # In the docs, these endpoints will be under "sec-data" section
)

# Include Excel export endpoints
api_router.include_router(
    export.router,
    prefix="/export",  # All export endpoints will start with /export
    tags=["export"],  # In the docs, these endpoints will be under "export" section
)

# Include Financial Modeling endpoints
api_router.include_router(
    financial_modeling.router,
    prefix="/financial-modeling",  # Fixed: Changed from "/modeling" to "/financial-modeling" to match client requests
    tags=[
        "financial-modeling"
    ],  # In the docs, these endpoints will be under "financial-modeling" section
)

# Include Utilities endpoints
api_router.include_router(
    utilities.router,
    prefix="/utilities",  # Fixed: Changed from "/modeling" to "/utilities" to match client requests
    tags=[
        "utilities"
    ],  # In the docs, these endpoints will be under "utilities" section
)


# Root API endpoint
@api_router.get("/")
async def api_root():
    """
    Root API endpoint that provides basic information about the API.
    """
    return {
        "name": "Analyst AI API",
        "version": "0.1.0",
        "description": "AI-powered financial research assistant",
        "endpoints": {
            "sec_analysis": "/sec/{symbol}/analyze",
            "sec_data": "/sec-data/{symbol}/filings",
            "financial_modeling": "/financial-modeling/{symbol}/quick-model",
            "utilities": "/utilities/cache/{symbol}",
        },
    }


# Test endpoint to verify server reloading
@api_router.get("/test-reload")
async def test_reload():
    """
    Test endpoint to verify server reloading.
    """
    return {"message": "Server reloaded successfully", "time": "2025-03-21"}


# As the application grows, we can add more feature routers here:
# api_router.include_router(valuation.router, prefix="/valuation", tags=["valuation"])
# api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
# etc.
