"""
SEC Filing Analysis API Endpoints
--------------------------------

This module provides API endpoints for analyzing SEC filings using AI.
It allows users to request AI-powered analysis of complete SEC filings
for any publicly traded company.

Endpoints:
- GET /api/v1/sec/{symbol}/analyze: Analyze the latest filing of a specific type
- GET /api/v1/sec/{symbol}/analyze/{filing_id}: Analyze a specific filing by ID

The analysis includes:
- Executive summaries
- Key financial metrics extraction
- Risk factor identification
- Management discussion analysis
- Future outlook assessment
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, Query, Path, status, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.models.financial_statements import FilingType
from app.services.sec_fetcher import sec_fetcher
from app.services.sec_analyzer import sec_filing_analyzer, SECFilingAnalysisResult
from app.core.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Response models
class SECFilingAnalysisResponse(BaseModel):
    """Response model for SEC filing analysis."""
    symbol: str
    filing_type: str
    filing_date: datetime
    document_url: str
    summary: str
    analysis: Dict[str, Any]
    analysis_date: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "symbol": "AAPL",
                "filing_type": "10-K",
                "filing_date": "2023-10-27T00:00:00",
                "document_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm",
                "summary": "Apple Inc. reported strong financial performance for fiscal year 2023 with revenue of $383.3 billion and net income of $97.0 billion. The company maintains a robust balance sheet with $162.1 billion in cash and investments.",
                "analysis": {
                    "EXECUTIVE SUMMARY": "Apple Inc. demonstrated resilient financial performance in fiscal year 2023..."
                },
                "analysis_date": "2023-11-10T12:34:56"
            }
        }
    }

@router.get(
    "/{symbol}/analyze",
    response_model=SECFilingAnalysisResponse,
    summary="Analyze the latest SEC filing for a company",
    description="Retrieves and analyzes the latest SEC filing of a specified type for a company using AI."
)
async def analyze_latest_filing(
    symbol: str = Path(..., description="Stock symbol of the company"),
    filing_type: FilingType = Query(FilingType.FORM_10K, description="Type of SEC filing to analyze"),
    limit: int = Query(1, description="Number of filings to retrieve (only the most recent will be analyzed)")
):
    """
    Analyze the latest SEC filing of a specified type for a company.
    
    This endpoint:
    1. Retrieves the latest filing of the specified type
    2. Downloads the complete filing as PDF
    3. Analyzes the filing using AI models
    4. Returns structured insights and summaries
    
    Args:
        symbol: Stock ticker symbol (e.g., AAPL, MSFT)
        filing_type: Type of filing to analyze (10-K, 10-Q, 8-K, etc.)
        limit: Number of filings to retrieve (only the most recent will be analyzed)
        
    Returns:
        Structured analysis of the SEC filing with insights and summaries
    """
    try:
        # Convert symbol to uppercase
        symbol = symbol.upper()
        logger.info(f"Analyzing latest {filing_type} filing for {symbol}")
        
        # Fetch the latest filings of the specified type
        filings = await sec_fetcher.get_sec_filings(
            symbol=symbol,
            filing_type=filing_type,
            limit=limit
        )
        
        if not filings or not filings.filings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No {filing_type} filings found for {symbol}"
            )
        
        # Get the most recent filing
        latest_filing = filings.filings[0]
        
        # Analyze the filing
        analysis_result = await sec_filing_analyzer.analyze_filing(latest_filing)
        
        if not analysis_result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to analyze {filing_type} filing for {symbol}"
            )
        
        # Convert to response model
        return SECFilingAnalysisResponse(
            symbol=analysis_result.filing.symbol,
            filing_type=analysis_result.filing.filing_type,
            filing_date=analysis_result.filing.filing_date,
            document_url=analysis_result.filing.document_url,
            summary=analysis_result.summary,
            analysis=analysis_result.analysis,
            analysis_date=analysis_result.analysis_date
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error analyzing latest filing for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while analyzing the filing: {str(e)}"
        )

@router.get(
    "/{symbol}/analyze/{filing_id}",
    response_model=SECFilingAnalysisResponse,
    summary="Analyze a specific SEC filing by ID",
    description="Retrieves and analyzes a specific SEC filing by its ID using AI."
)
async def analyze_specific_filing(
    symbol: str = Path(..., description="Stock symbol of the company"),
    filing_id: str = Path(..., description="ID of the specific filing to analyze")
):
    """
    Analyze a specific SEC filing by its ID.
    
    This endpoint:
    1. Retrieves the specified filing by ID
    2. Downloads the complete filing as PDF
    3. Analyzes the filing using AI models
    4. Returns structured insights and summaries
    
    Args:
        symbol: Stock ticker symbol (e.g., AAPL, MSFT)
        filing_id: Unique identifier for the specific filing
        
    Returns:
        Structured analysis of the SEC filing with insights and summaries
    """
    try:
        # Convert symbol to uppercase
        symbol = symbol.upper()
        logger.info(f"Analyzing filing {filing_id} for {symbol}")
        
        # Fetch the specific filing by ID
        filing = await sec_fetcher.get_sec_filing_by_id(symbol, filing_id)
        
        if not filing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Filing with ID {filing_id} not found for {symbol}"
            )
        
        # Analyze the filing
        analysis_result = await sec_filing_analyzer.analyze_filing(filing)
        
        if not analysis_result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to analyze filing {filing_id} for {symbol}"
            )
        
        # Convert to response model
        return SECFilingAnalysisResponse(
            symbol=analysis_result.filing.symbol,
            filing_type=analysis_result.filing.filing_type,
            filing_date=analysis_result.filing.filing_date,
            document_url=analysis_result.filing.document_url,
            summary=analysis_result.summary,
            analysis=analysis_result.analysis,
            analysis_date=analysis_result.analysis_date
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error analyzing filing {filing_id} for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while analyzing the filing: {str(e)}"
        )

@router.get(
    "/{symbol}/filings",
    summary="[DEPRECATED] Retrieve SEC filings for a company",
    description="This endpoint is deprecated. Please use /sec-data/{symbol}/filings instead."
)
async def legacy_sec_filings_redirect(
    request: Request,
    symbol: str = Path(..., description="Stock symbol of the company")
):
    """
    Legacy endpoint that redirects to the new /sec-data/{symbol}/filings endpoint.
    
    This endpoint exists to support clients using the old URL pattern during transition.
    It will redirect to the new endpoint with the appropriate query parameters.
    
    Args:
        request: The incoming request object
        symbol: Stock ticker symbol (e.g., AAPL, MSFT)
    """
    # Extract query parameters to preserve them in the redirect
    query_string = request.url.query
    redirect_url = f"/api/v1/sec-data/{symbol}/filings"
    
    # Add query parameters if they exist
    if query_string:
        redirect_url = f"{redirect_url}?{query_string}"
    
    logger.info(f"Redirecting legacy SEC filings request for {symbol} to {redirect_url}")
    
    # Return a redirect response
    return RedirectResponse(
        url=redirect_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT
    ) 