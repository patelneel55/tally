"""
Financial Data Aggregator
------------------------

This module aggregates comprehensive financial data for a company from multiple sources,
creating a complete dataset for AI-driven financial modeling.

What this file does:
1. Collects financial statement data from multiple sources (Polygon.io, SEC filings)
2. Aggregates data across multiple periods (quarterly and annual)
3. Extracts accounting policies and footnotes
4. Standardizes data format for AI consumption
5. Provides a unified interface for the AI modeling engine

How it fits in the architecture:
- Sits between the data extraction layers (Polygon, SEC fetcher, etc.)
  and the AI modeling engine
- Aggregates data from multiple sources into a unified format
- Enriches financial data with contextual information from footnotes and MD&A

Financial importance:
- Creates a comprehensive financial dataset spanning multiple years and quarters
- Includes accounting policy information needed for accurate interpretation
- Provides the foundation for AI-driven financial modeling
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, date
import pandas as pd

from ai_analyst.app.core.config import settings
from ai_analyst.app.models.financial_statements import FilingType
from ai_analyst.app.services.sec_fetcher import SECFiling, sec_fetcher
from ai_analyst.app.models.financial_statements import (
    FinancialStatement,
    FinancialStatementType,
    FinancialStatementPeriod
)
from ai_analyst.app.services.polygon_financials import polygon_financials
from ai_analyst.app.services.financial_statement_extractor import extract_financial_statements
from ai_analyst.app.services.sec_analyzer import sec_filing_analyzer

# Set up logging
logger = logging.getLogger(__name__)

class FinancialDataAggregator:
    """
    Aggregates comprehensive financial data for a company from multiple sources.
    Prepares a complete dataset for AI-driven financial modeling.
    """
    
    def __init__(self):
        """Initialize the financial data aggregator."""
        self.cache_dir = Path(settings.DATA_DIR) / "aggregated_data"
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def get_comprehensive_financial_data(
        self,
        ticker: str,
        years: int = 5,
        include_quarterly: bool = True,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Retrieve comprehensive financial data for a company.
        
        Args:
            ticker: Company ticker symbol
            years: Number of years of historical data to include
            include_quarterly: Whether to include quarterly data
            force_refresh: Whether to force refresh from source
            
        Returns:
            Dictionary containing comprehensive financial data
        """
        cache_file = self.cache_dir / f"{ticker}_comprehensive_data.json"
        
        # Check cache if not forcing refresh
        if not force_refresh and cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    cached_data = json.load(f)
                    
                # Check if cache is recent (within 7 days)
                cache_date = datetime.fromisoformat(cached_data.get("aggregated_at", "2000-01-01"))
                if (datetime.now() - cache_date).days < 7:
                    logger.info(f"Using cached comprehensive data for {ticker}")
                    return cached_data
            except Exception as e:
                logger.warning(f"Error reading cached data: {e}")
        
        # 1. Get financial statements from Polygon.io (primary source)
        logger.info(f"Fetching financial statements from Polygon.io for {ticker}")
        try:
            financial_statements = polygon_financials.get_financial_statements_by_type(
                ticker=ticker,
                statement_type="all",
                years=years,
                include_quarterly=include_quarterly,
                force_refresh=force_refresh
            )
            
            # Check if we have data
            if not financial_statements or not any(financial_statements.values()):
                logger.warning(f"No financial statements found for {ticker} from Polygon.io")
                financial_statements = {"income_statements": [], "balance_sheets": [], "cash_flow_statements": []}
        except Exception as e:
            logger.error(f"Error fetching financial statements from Polygon.io: {e}")
            financial_statements = {"income_statements": [], "balance_sheets": [], "cash_flow_statements": []}
            
        # 2. Get common financial metrics (pre-processed for easier consumption)
        logger.info(f"Fetching common financial metrics for {ticker}")
        try:
            financial_metrics = polygon_financials.get_common_financial_metrics(
                ticker=ticker,
                years=years,
                include_quarterly=include_quarterly,
                force_refresh=force_refresh
            )
            
            if not financial_metrics:
                logger.warning(f"No financial metrics found for {ticker}")
                financial_metrics = {"income": {}, "balance": {}, "cash_flow": {}, "ratios": {}}
        except Exception as e:
            logger.error(f"Error fetching financial metrics: {e}")
            financial_metrics = {"income": {}, "balance": {}, "cash_flow": {}, "ratios": {}}
        
        # 3. Try to get SEC filings for accounting policies and footnotes
        accounting_policies = {}
        footnotes = {}
        
        try:
            # Find a recent 10-K filing
            filings = []
            try:
                # Use query API to find filings
                current_year = datetime.now().year
                for year in range(current_year, current_year - years, -1):
                    try:
                        filing = self._get_latest_10k(ticker, year)
                        if filing:
                            filings.append((year, filing))
                            if len(filings) >= 2:  # Get at least 2 years if available
                                break
                    except Exception as e:
                        logger.warning(f"Error fetching 10-K for {ticker} for year {year}: {e}")
            except Exception as e:
                logger.warning(f"Error in filing search: {e}")
            
            # Extract accounting policies and footnotes from the filings
            for year, filing in filings:
                try:
                    # Analyze filing to extract accounting policies
                    analysis_result = sec_filing_analyzer.analyze_filing(filing)
                    
                    if analysis_result:
                        # Extract accounting policies and footnotes
                        accounting_policies[year] = self._extract_accounting_policies(filing, analysis_result)
                        footnotes[year] = self._extract_footnotes(filing, analysis_result)
                except Exception as e:
                    logger.warning(f"Error extracting policies for {ticker} for year {year}: {e}")
        except Exception as e:
            logger.warning(f"Error processing SEC filings for accounting policies: {e}")
        
        # 4. Organize financial data by year and period
        annual_data = self._organize_statements_by_year(financial_statements, "annual")
        quarterly_data = self._organize_statements_by_year(financial_statements, "quarterly")
        
        # 5. Create time series data for key metrics
        time_series = self._create_time_series(financial_metrics)
        
        # 6. Aggregate all the financial data
        comprehensive_data = {
            "ticker": ticker,
            "aggregated_at": datetime.now().isoformat(),
            "annual_data": annual_data,
            "quarterly_data": quarterly_data, 
            "metrics": financial_metrics,
            "accounting_policies": accounting_policies,
            "footnotes": footnotes,
            "time_series": time_series,
            "metadata": {
                "years_available": sorted(list(annual_data.keys())),
                "quarters_available": sorted(list(quarterly_data.keys()))
            }
        }
        
        # 7. Cache the results
        try:
            with open(cache_file, "w") as f:
                json.dump(comprehensive_data, f, indent=2, default=str)
            logger.info(f"Cached comprehensive data for {ticker}")
        except Exception as e:
            logger.warning(f"Error caching data: {e}")
            
        return comprehensive_data
    
    def _get_latest_10k(self, ticker: str, year: int) -> Optional[SECFiling]:
        """
        Get the latest 10-K filing for a specific year.
        
        Args:
            ticker: Company ticker symbol
            year: Year to fetch
            
        Returns:
            SECFiling object or None if not found
        """
        try:
            # Try different approaches to get a 10-K filing
            
            # First approach: Search using _query_sec_filings if available
            try:
                # This is an asynchronous method, we can't call it directly
                # filings = sec_filing_fetcher.query_sec_filings(
                #     symbol=ticker,
                #     form_type="10-K",
                #     year=year,
                #     limit=1
                # )
                pass
            except Exception as e:
                logger.debug(f"Query approach failed: {e}")
            
            # Second approach: Try batch_download_filings if available
            try:
                filings = sec_filing_fetcher.batch_download_filings(
                    ticker=ticker,
                    filing_types=[FilingType.FORM_10K],
                    start_year=year,
                    end_year=year,
                    limit=1
                )
                
                if filings and FilingType.FORM_10K in filings and len(filings[FilingType.FORM_10K]) > 0:
                    return filings[FilingType.FORM_10K][0]
            except Exception as e:
                logger.debug(f"Batch download approach failed: {e}")
            
            # Third approach: Try direct methods if available
            try:
                # Try to get filing directly if method exists
                filing = sec_filing_fetcher.get_10k(
                    ticker=ticker,
                    year=year
                )
                
                if filing:
                    return filing
            except Exception as e:
                logger.debug(f"Direct approach failed: {e}")
                
        except Exception as e:
            logger.warning(f"Error in _get_latest_10k: {e}")
            
        return None
    
    def _extract_accounting_policies(self, filing: SECFiling, analysis_result: Any) -> Dict[str, Any]:
        """
        Extract accounting policies from a filing and its analysis.
        
        Args:
            filing: SEC filing
            analysis_result: Analysis result for the filing
            
        Returns:
            Dictionary of accounting policies
        """
        accounting_policies = {}
        
        try:
            # Extract accounting policies section (typically in 10-K Item 7)
            if hasattr(analysis_result, 'significant_accounting_policies'):
                accounting_policies['significant_policies'] = analysis_result.significant_accounting_policies
                
            # Extract specific accounting policies of interest
            for policy_name in [
                "revenue_recognition", "inventory", "intangible_assets", 
                "property_plant_equipment", "leases", "investments"
            ]:
                if hasattr(analysis_result, f"{policy_name}_policy"):
                    accounting_policies[policy_name] = getattr(analysis_result, f"{policy_name}_policy")
        except Exception as e:
            logger.warning(f"Error extracting accounting policies: {e}")
            
        return accounting_policies
    
    def _extract_footnotes(self, filing: SECFiling, analysis_result: Any) -> Dict[str, Any]:
        """
        Extract footnotes from a filing and its analysis.
        
        Args:
            filing: SEC filing
            analysis_result: Analysis result for the filing
            
        Returns:
            Dictionary of footnotes
        """
        footnotes = {}
        
        try:
            # Extract footnotes section if available in analysis
            if hasattr(analysis_result, 'footnotes'):
                return analysis_result.footnotes
                
            # If not available as a structured field, we can try to extract them
            # from the raw text (more complex implementation would be needed here)
        except Exception as e:
            logger.warning(f"Error extracting footnotes: {e}")
            
        return footnotes
    
    def _organize_statements_by_year(
        self, 
        statements: Dict[str, List[Dict[str, Any]]],
        period_type: str
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Organize financial statements by year and statement type.
        
        Args:
            statements: Dictionary mapping statement types to lists of statements
            period_type: "annual" or "quarterly"
            
        Returns:
            Dictionary mapping years to statement types to statement data
        """
        organized_data = {}
        
        # Process each statement type
        for statement_type, statement_list in statements.items():
            for statement in statement_list:
                # Skip statements that don't match the period type
                if statement.get("period_type") != period_type:
                    continue
                    
                # For annual data, use fiscal_year as the key
                if period_type == "annual":
                    year_key = statement.get("fiscal_year")
                    if not year_key:
                        continue
                        
                    if year_key not in organized_data:
                        organized_data[year_key] = {}
                        
                    # Map statement type to appropriate category
                    if statement_type == "income_statements":
                        organized_data[year_key]["income_statement"] = statement
                    elif statement_type == "balance_sheets":
                        organized_data[year_key]["balance_sheet"] = statement
                    elif statement_type == "cash_flow_statements":
                        organized_data[year_key]["cash_flow"] = statement
                
                # For quarterly data, use fiscal_year-fiscal_period as the key
                elif period_type == "quarterly":
                    year = statement.get("fiscal_year")
                    period = statement.get("fiscal_period")
                    if not year or not period:
                        continue
                        
                    quarter_key = f"{year}-{period}"
                    
                    if quarter_key not in organized_data:
                        organized_data[quarter_key] = {}
                        
                    # Map statement type to appropriate category
                    if statement_type == "income_statements":
                        organized_data[quarter_key]["income_statement"] = statement
                    elif statement_type == "balance_sheets":
                        organized_data[quarter_key]["balance_sheet"] = statement
                    elif statement_type == "cash_flow_statements":
                        organized_data[quarter_key]["cash_flow"] = statement
        
        return organized_data
    
    def _create_time_series(self, metrics: Dict[str, Dict[str, List[Dict[str, Any]]]]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        Create time series data for key financial metrics.
        
        Args:
            metrics: Dictionary of financial metrics by category
            
        Returns:
            Dictionary of time series data
        """
        time_series = {
            "annual": {},
            "quarterly": {}
        }
        
        # Define key metrics to track
        key_metrics = {
            "income": ["revenues", "operating_income", "net_income"],
            "balance": ["total_assets", "total_liabilities", "total_equity"],
            "cash_flow": ["operating_cash_flow", "free_cash_flow"]
        }
        
        # Process each category of metrics
        for category, metric_names in key_metrics.items():
            for metric_name in metric_names:
                if category in metrics and metric_name in metrics[category]:
                    # Initialize the metric in time series if needed
                    if metric_name not in time_series["annual"]:
                        time_series["annual"][metric_name] = []
                    if metric_name not in time_series["quarterly"]:
                        time_series["quarterly"][metric_name] = []
                    
                    # Add each metric value to the appropriate time series
                    for value in metrics[category][metric_name]:
                        if value.get("period_type") == "annual":
                            time_series["annual"][metric_name].append({
                                "year": value.get("fiscal_year"),
                                "value": value.get("value")
                            })
                        elif value.get("period_type") == "quarterly":
                            time_series["quarterly"][metric_name].append({
                                "year": value.get("fiscal_year"),
                                "quarter": value.get("fiscal_period"),
                                "value": value.get("value")
                            })
        
        # Sort each time series by year/quarter
        for metric_name in time_series["annual"]:
            time_series["annual"][metric_name].sort(key=lambda x: x.get("year", ""))
            
        for metric_name in time_series["quarterly"]:
            time_series["quarterly"][metric_name].sort(key=lambda x: (x.get("year", ""), x.get("quarter", "")))
        
        return time_series

# Create a singleton instance
financial_data_aggregator = FinancialDataAggregator() 