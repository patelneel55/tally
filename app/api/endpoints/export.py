"""
Financial Data Export Endpoints
-----------------------------

This module provides API endpoints for exporting financial data to Excel files.

What this file does:
1. Exposes endpoints for downloading financial statements as Excel files
2. Handles parameter parsing for financial periods and data filters
3. Coordinates between the financial data services and Excel exporter
4. Serves downloadable files via FastAPI's response system

How it fits in the architecture:
- Part of the API layer, providing export functionality
- Consumes data from financial_statement_extractor service
- Uses excel_exporter service to generate formatted files
- Provides an interface for frontend download buttons
"""

import logging
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

from app.services.financial_statement_extractor import extract_financial_statements
from app.services.sec_fetcher import sec_fetcher
from app.services.excel_exporter import export_financial_statements_to_excel, excel_exporter
from app.models.financial_statements import FinancialStatementType, FilingType
from app.core.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.get("/{symbol}", summary="Export financial statements to Excel")
async def export_financials(
    symbol: str,
    fiscal_year: Optional[int] = None,
    fiscal_period: Optional[str] = None,
    filing_type: str = "10-K",
    statements: Optional[List[str]] = Query(None, description="Statement types to include (income_statement, balance_sheet, cash_flow). If empty, all are included.")
):
    """
    Export financial statements to an Excel file.
    
    This endpoint:
    1. Retrieves financial statements for the specified company and period
    2. Converts them to a formatted Excel file with calculations
    3. Returns the file as a downloadable response
    
    Parameters:
    - **symbol**: Stock symbol of the company (e.g., AAPL, MSFT)
    - **fiscal_year**: Fiscal year (e.g., 2023). Defaults to most recent.
    - **fiscal_period**: Fiscal period (e.g., Q1, Q2, FY). For 10-K, use FY.
    - **filing_type**: SEC filing type (10-K or 10-Q)
    - **statements**: List of statement types to include
    
    Returns:
    - Excel file with financial statements
    """
    logger.info(f"Exporting financial statements for {symbol} {fiscal_year} {fiscal_period}")
    
    try:
        # Convert filing_type string to enum
        if filing_type == "10-K":
            filing_type_enum = FilingType.FORM_10K
        elif filing_type == "10-Q":
            filing_type_enum = FilingType.FORM_10Q
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported filing type: {filing_type}")
            
        # If fiscal_year is not provided, use current year
        if not fiscal_year:
            fiscal_year = datetime.now().year
            
        # Fetch the filing
        filing = sec_filing_fetcher.get_filing(
            ticker=symbol,
            filing_type=filing_type_enum,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period
        )
        
        if not filing:
            raise HTTPException(
                status_code=404, 
                detail=f"No {filing_type} filing found for {symbol} (fiscal year: {fiscal_year}, period: {fiscal_period})"
            )
            
        # Extract financial statements
        all_statements = extract_financial_statements(filing)
        
        if not all_statements:
            raise HTTPException(
                status_code=404,
                detail=f"No financial statements found in the filing for {symbol}"
            )
            
        # Filter statements if requested
        if statements:
            filtered_statements = {}
            for statement_name in statements:
                try:
                    statement_type = FinancialStatementType(statement_name)
                    if statement_type in all_statements:
                        filtered_statements[statement_type] = all_statements[statement_type]
                except ValueError:
                    logger.warning(f"Invalid statement type: {statement_name}")
                    
            if filtered_statements:
                all_statements = filtered_statements
        
        # Generate Excel file
        excel_buffer = export_financial_statements_to_excel(
            statements=all_statements,
            ticker=symbol,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period
        )
        
        # Determine filename
        period_str = f"_{fiscal_period}" if fiscal_period else ""
        filename = f"{symbol}_{fiscal_year}{period_str}_financials.xlsx"
        
        # Return the Excel file as a downloadable response
        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting financial statements: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export financial statements: {str(e)}")
        

@router.get("/{symbol}/multi-period", summary="Export multi-period financial statements to Excel")
async def export_multi_period_financials(
    symbol: str,
    years: int = Query(3, description="Number of years of data to include"),
    quarterly: bool = Query(False, description="Include quarterly data if available"),
    filing_type: str = "10-K"
):
    """
    Export financial statements for multiple periods to an Excel file.
    
    This endpoint:
    1. Retrieves financial statements for multiple years/quarters
    2. Combines them into a single dataset
    3. Generates an Excel file with trend analysis
    
    Parameters:
    - **symbol**: Stock symbol of the company (e.g., AAPL, MSFT)
    - **years**: Number of years of data to include (default: 3)
    - **quarterly**: Whether to include quarterly data (default: false)
    - **filing_type**: SEC filing type (10-K or 10-Q)
    
    Returns:
    - Excel file with financial statements and trend analysis
    """
    logger.info(f"Exporting multi-period financial statements for {symbol} (years: {years}, quarterly: {quarterly})")
    
    try:
        # Convert filing_type string to enum
        if filing_type == "10-K":
            filing_type_enum = FilingType.FORM_10K
        elif filing_type == "10-Q":
            filing_type_enum = FilingType.FORM_10Q
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported filing type: {filing_type}")
            
        # Determine the years to fetch
        current_year = datetime.now().year
        target_years = list(range(current_year - years + 1, current_year + 1))
        
        # Fetch filings for each year
        all_statements = {}
        latest_filing = None
        
        for year in reversed(target_years):  # Start with most recent for latest_filing
            try:
                filing = sec_filing_fetcher.get_filing(
                    ticker=symbol,
                    filing_type=filing_type_enum,
                    fiscal_year=year
                )
                
                if filing:
                    if not latest_filing:
                        latest_filing = filing
                        
                    statements = extract_financial_statements(filing)
                    if statements:
                        # Use the year as the key to combine statements
                        all_statements[year] = statements
            except Exception as e:
                logger.warning(f"Error fetching {filing_type} for {symbol} in {year}: {str(e)}")
                
        if not all_statements:
            raise HTTPException(
                status_code=404,
                detail=f"No financial statements found for {symbol} in the requested period"
            )
            
        # Combine statements across periods
        combined_statements = {}
        
        # Process each statement type separately
        for statement_type in FinancialStatementType:
            combined_metrics = {}
            
            # Collect metrics from each year
            for year, statements in all_statements.items():
                if statement_type in statements:
                    statement = statements[statement_type]
                    
                    # Use year as the period identifier
                    year_str = str(year)
                    
                    # Add each metric with the year as the period
                    for metric_name, values in statement.metrics.items():
                        if metric_name not in combined_metrics:
                            combined_metrics[metric_name] = {}
                            
                        # Get the most recent period value if multiple periods exist
                        if values:
                            # For simplicity, just use the first value
                            # In a real implementation, you might want to be more selective
                            first_key = next(iter(values))
                            combined_metrics[metric_name][year_str] = values[first_key]
            
            if combined_metrics:
                # Create a combined statement using the latest filing as a template
                if latest_filing and statement_type in all_statements.get(target_years[-1], {}):
                    template = all_statements[target_years[-1]][statement_type]
                    
                    combined_statements[statement_type] = type(template)(
                        statement_type=statement_type,
                        company_ticker=symbol,
                        period=template.period,
                        fiscal_year=target_years[-1],
                        fiscal_period=template.fiscal_period,
                        filing_date=template.filing_date,
                        currency=template.currency,
                        units=template.units,
                        metrics=combined_metrics,
                        source_filing_id=template.source_filing_id
                    )
        
        if not combined_statements:
            raise HTTPException(
                status_code=404,
                detail=f"No financial statements could be combined for {symbol}"
            )
        
        # Generate Excel file
        excel_buffer = export_financial_statements_to_excel(
            statements=combined_statements,
            ticker=symbol,
            fiscal_year=target_years[-1],
            fiscal_period="FY"
        )
        
        # Determine filename
        period_range = f"{target_years[0]}-{target_years[-1]}"
        filename = f"{symbol}_{period_range}_financials.xlsx"
        
        # Return the Excel file as a downloadable response
        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting multi-period financial statements: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export financial statements: {str(e)}") 