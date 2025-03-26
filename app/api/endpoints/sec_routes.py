"""
SEC Analysis API Routes
---------------------

This module provides API endpoints for SEC filing analysis, including
historical analysis across multiple filings.

What this file does:
1. Defines API endpoints for SEC filing analysis
2. Handles request validation and error responses
3. Connects the API layer to the SEC analysis services

How it fits in the architecture:
- Provides the interface between clients and the SEC analysis services
- Handles HTTP-specific concerns (status codes, headers, etc.)
- Implements proper error handling and response formatting

Financial importance:
- Enables programmatic access to SEC filing analysis
- Supports integration with other financial analysis tools
- Provides a consistent interface for accessing SEC insights
"""

import logging
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, Query, Path, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services.sec_fetcher import sec_fetcher
from app.services.sec_analyzer import sec_filing_analyzer
from app.services.sec_trends import sec_trends_analyzer
from app.models.financial_statements import FilingType
from app.core.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["SEC Filings"])

# Add a diagnostic endpoint
@router.get("")
async def sec_api_root():
    """
    SEC API Root endpoint.
    
    This is a diagnostic endpoint that confirms the SEC API routes are properly configured.
    
    Returns:
        A simple message confirming the SEC API is available
    """
    logger.info("SEC API root endpoint called")
    return {"message": "SEC API is available"}

# Response models
class SECFilingAnalysisResponse(BaseModel):
    """Response model for SEC filing analysis."""
    symbol: str
    filing_type: str
    filing_date: str
    summary: str
    analysis: Dict[str, Any]
    analysis_date: str

class SECTrendsAnalysisResponse(BaseModel):
    """Response model for SEC trends analysis."""
    symbol: str
    filing_dates: Dict[str, List[str]]
    summary: str
    trends_analysis: Dict[str, Any]
    analysis_date: str

@router.get("/{symbol}/filing/{filing_type}", response_model=SECFilingAnalysisResponse)
async def analyze_sec_filing(
    symbol: str = Path(..., description="Company ticker symbol"),
    filing_type: str = Path(..., description="Filing type (10-K, 10-Q, 8-K)"),
    filing_date: Optional[str] = Query(None, description="Filing date in ISO format (YYYY-MM-DD)")
):
    """
    Analyze a specific SEC filing.
    
    This endpoint retrieves and analyzes a specific SEC filing for a company.
    If no filing date is provided, it will analyze the most recent filing of the specified type.
    
    Args:
        symbol: Company ticker symbol
        filing_type: Filing type (10-K, 10-Q, 8-K)
        filing_date: Filing date in ISO format (YYYY-MM-DD)
        
    Returns:
        Analysis of the SEC filing
    """
    try:
        # Convert filing type string to enum
        filing_type_enum = None
        if filing_type == "10-K":
            filing_type_enum = FilingType.FORM_10K
        elif filing_type == "10-Q":
            filing_type_enum = FilingType.FORM_10Q
        elif filing_type == "8-K":
            filing_type_enum = FilingType.FORM_8K
        else:
            filing_type_enum = FilingType.OTHER
        
        # Query for the filing
        filings = await sec_fetcher._query_sec_filings(
            symbol=symbol,
            form_type=filing_type,
            limit=1
        )
        
        if not filings:
            raise HTTPException(status_code=404, detail=f"No {filing_type} filings found for {symbol}")
        
        # Convert to SECFiling object
        filing = sec_fetcher._convert_api_result_to_filing(
            filings[0], symbol, filing_type_enum
        )
        
        if not filing:
            raise HTTPException(status_code=404, detail=f"Failed to process {filing_type} filing for {symbol}")
        
        # Analyze the filing
        analysis_result = await sec_filing_analyzer.analyze_filing(filing)
        
        if not analysis_result:
            raise HTTPException(status_code=500, detail=f"Failed to analyze {filing_type} filing for {symbol}")
        
        # Return the analysis
        return SECFilingAnalysisResponse(
            symbol=symbol,
            filing_type=filing_type,
            filing_date=filing.filing_date.isoformat(),
            summary=analysis_result.summary,
            analysis=analysis_result.analysis,
            analysis_date=analysis_result.analysis_date.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error analyzing SEC filing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{symbol}/historical/analyze", response_model=SECTrendsAnalysisResponse)
async def analyze_historical_filings(
    symbol: str = Path(..., description="Company ticker symbol"),
    background_tasks: BackgroundTasks = None
):
    """
    Analyze historical SEC filings for a company.
    
    This endpoint retrieves and analyzes multiple SEC filings for a company,
    including the latest 10-K and the last four 10-Q filings. It identifies
    trends, changes, and notable developments across these filings.
    
    Args:
        symbol: Company ticker symbol
        
    Returns:
        Comprehensive analysis of trends across multiple filings
    """
    try:
        # Analyze historical filings
        trends_analysis = await sec_trends_analyzer.analyze_historical_filings(symbol)
        
        if not trends_analysis:
            raise HTTPException(status_code=500, detail=f"Failed to analyze historical filings for {symbol}")
        
        # Return the analysis
        return SECTrendsAnalysisResponse(
            symbol=symbol,
            filing_dates={
                filing_type: [filing.filing_date.isoformat() for filing in filings]
                for filing_type, filings in trends_analysis.filings.items()
            },
            summary=trends_analysis.summary,
            trends_analysis=trends_analysis.trends_analysis,
            analysis_date=trends_analysis.analysis_date.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error analyzing historical filings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{symbol}/historical/filings")
async def get_historical_filings(
    symbol: str = Path(..., description="Company ticker symbol")
):
    """
    Retrieve historical SEC filings for a company.
    
    This endpoint retrieves the latest 10-K and the last four 10-Q filings
    for a company, without performing analysis.
    
    Args:
        symbol: Company ticker symbol
        
    Returns:
        Dictionary of historical filings by type
    """
    try:
        # Fetch historical filings
        historical_filings = await sec_fetcher.get_historical_filings(symbol)
        
        if not historical_filings or not any(historical_filings.values()):
            raise HTTPException(status_code=404, detail=f"No historical filings found for {symbol}")
        
        # Convert to response format
        response = {
            "symbol": symbol,
            "filings": {}
        }
        
        for filing_type, filings in historical_filings.items():
            response["filings"][filing_type] = [
                {
                    "filing_date": filing.filing_date.isoformat(),
                    "document_url": filing.document_url,
                    "filing_id": filing.filing_id
                }
                for filing in filings
            ]
        
        return response
        
    except Exception as e:
        logger.error(f"Error retrieving historical filings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{symbol}/filings")
async def get_sec_filings(
    symbol: str = Path(..., description="Company ticker symbol"),
    filing_type: Optional[str] = Query(None, description="Type of filing to filter by (e.g., 10-K, 10-Q, 8-K)"),
    limit: Optional[int] = Query(20, ge=1, le=100, description="Maximum number of filings to retrieve")
):
    """
    Retrieve SEC filings for a company.
    
    This endpoint provides access to official regulatory filings that public companies
    must submit to the Securities and Exchange Commission (SEC).
    
    Args:
        symbol: Stock ticker symbol (e.g., AAPL for Apple Inc.)
        filing_type: Optional filter for specific filing type (10-K, 10-Q, 8-K)
        limit: Maximum number of filings to retrieve (default: 20, max: 100)
        
    Returns:
        Dictionary containing the list of SEC filings
    """
    logger.info(f"Retrieving SEC filings for {symbol}, filing_type={filing_type}, limit={limit}")
    try:
        # Convert symbol to uppercase
        symbol = symbol.upper()
        
        # Debug info: API key status
        api_key = settings.SEC_API_KEY
        has_api_key = bool(api_key)
        logger.info(f"SEC API key available: {has_api_key}")
        
        # Convert filing type string to enum if provided
        filing_type_enum = None
        if filing_type:
            if filing_type == "10-K":
                filing_type_enum = FilingType.FORM_10K
            elif filing_type == "10-Q":
                filing_type_enum = FilingType.FORM_10Q
            elif filing_type == "8-K":
                filing_type_enum = FilingType.FORM_8K
            else:
                filing_type_enum = FilingType.OTHER
        
        # Query for filings
        logger.info(f"Calling _query_sec_filings for {symbol}")
        filings = await sec_fetcher._query_sec_filings(
            symbol=symbol,
            form_type=filing_type,
            limit=limit
        )
        logger.info(f"Received response from _query_sec_filings: {len(filings) if filings else 0} filings")
        
        if not filings:
            debug_info = {
                "api_key_available": has_api_key,
                "query_params": {
                    "symbol": symbol,
                    "form_type": filing_type,
                    "limit": limit
                }
            }
            logger.warning(f"No SEC filings found for {symbol}. Debug info: {debug_info}")
            return {
                "symbol": symbol,
                "filings": [],
                "total": 0,
                "message": f"No SEC filings found for {symbol}",
                "debug_info": debug_info
            }
        
        # Convert to response format
        formatted_filings = []
        for filing in filings:
            try:
                filing_data = {
                    "filing_id": filing.get("id"),
                    "filing_type": filing.get("formType"),
                    "filing_date": filing.get("filedAt"),
                    "company_name": filing.get("companyName"),
                    "document_url": None
                }
                
                # Retrieve documentUrl from documentFormatFiles if available and matches filing_type
                doc_format_files = filing.get("documentFormatFiles")
                if doc_format_files and isinstance(doc_format_files, list):
                    for doc in doc_format_files:
                        if doc.get("type") == filing_type:
                            filing_data["document_url"] = doc.get("documentUrl")
                            break
                
                formatted_filings.append(filing_data)
            except Exception as e:
                logger.error(f"Error processing filing: {e}, filing data: {filing}")
                continue
        
        response = {
            "symbol": symbol,
            "filings": formatted_filings,
            "total": len(formatted_filings)
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Error retrieving SEC filings: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error retrieving SEC filings: {str(e)}")

# Add a legacy support endpoint to help clients transition
@router.get("/legacy/{symbol}/filings")
async def legacy_get_sec_filings(
    symbol: str = Path(..., description="Company ticker symbol"),
    filing_type: Optional[str] = Query(None, description="Type of filing to filter by (e.g., 10-K, 10-Q, 8-K)"),
    limit: Optional[int] = Query(20, ge=1, le=100, description="Maximum number of filings to retrieve")
):
    """
    Legacy endpoint for SEC filings - redirects to the new endpoint structure.
    
    This endpoint exists to support clients using the old URL pattern during transition.
    It will return the same data as the standard endpoint but also includes a message
    about the endpoint change.
    
    Args:
        symbol: Stock ticker symbol (e.g., AAPL for Apple Inc.)
        filing_type: Optional filter for specific filing type (10-K, 10-Q, 8-K)
        limit: Maximum number of filings to retrieve (default: 20, max: 100)
        
    Returns:
        Dictionary containing the list of SEC filings with a notification about the endpoint change
    """
    logger.info(f"Legacy SEC filings endpoint called for {symbol}")
    
    # Get the data from the standard endpoint function
    result = await get_sec_filings(symbol, filing_type, limit)
    
    # Add a message about the endpoint change
    if isinstance(result, dict):
        result["notice"] = "This endpoint is deprecated. Please update your client to use /sec-data/{symbol}/filings instead."
    
    return result 