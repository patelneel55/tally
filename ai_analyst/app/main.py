"""
Analyst AI - Main Application
-----------------------------

This module serves as the entry point for the Analyst AI application, which is a financial 
research assistant designed to automate stock research and analysis tasks.

What this file does:
1. Sets up the FastAPI web server that will handle incoming requests
2. Configures logging to track system activities and errors
3. Sets up Cross-Origin Resource Sharing (CORS) to allow web browsers to safely request data
4. Registers all the API endpoints that users can access

How it fits in the architecture:
- This is the starting point of the entire application
- It connects all components together and makes them accessible via HTTP endpoints
"""

import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ai_analyst.app.api.api import api_router
from ai_analyst.app.core.config import settings

# Configure logging - this helps us track what happens in the application
# It's like having a diary of everything that happens, which is useful for debugging
logging.basicConfig(
    level=logging.INFO,  # Only log messages that are "INFO" level or higher (ignores DEBUG)
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Format: Time - Module - Level - Message
)
logger = logging.getLogger(__name__)  # Get a logger specific to this file

# Create the main FastAPI application
# FastAPI is chosen because it's modern, fast, and has built-in documentation
app = FastAPI(
    title=settings.PROJECT_NAME,  # The name shown in the API docs
    description=settings.PROJECT_DESCRIPTION,  # Description of what the API does
    version=settings.VERSION,  # Current version of the API
    openapi_url=f"{settings.API_V1_STR}/openapi.json",  # URL to access API documentation
)

# Set up CORS middleware
# This is a security feature that controls which websites can access our API
# Without this, web browsers would block requests from frontend applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # List of allowed origins (websites)
    allow_credentials=True,  # Allow cookies and authentication
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all HTTP headers
)

# Include API router - this connects all our API endpoints
# The router organizes endpoints by feature (company data, financials, etc.)
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    """
    Root endpoint that provides basic information about the API.
    
    This is the landing page users see when they first access the API without specifying
    any particular endpoint.
    
    Returns:
        A welcome message with API version and where to find documentation
    """
    return {
        "message": "Welcome to Analyst AI API",
        "version": settings.VERSION,
        "documentation": "/docs",  # Points users to the auto-generated documentation
    }


# This code only runs if we execute this file directly
# (not when it's imported by another module)
if __name__ == "__main__":
    import uvicorn

    # Start the web server using uvicorn
    # Uvicorn is a lightning-fast ASGI server that powers FastAPI
    uvicorn.run("ai_analyst.app.main:app", host="0.0.0.0", port=8001, reload=True) 