"""
Polygon.io Financials API Client
-------------------------------

This module provides direct access to financial data from the Polygon.io Financials API,
retrieving structured financial statements from SEC filings.

What this file does:
1. Retrieves financial statement data directly from Polygon.io's Financials API
2. Provides access to income statements, balance sheets, and cash flow statements
3. Handles API pagination, error handling, and rate limiting
4. Standardizes financial data into a consistent format

How it fits in the architecture:
- Acts as a primary data source for financial statement data
- Works alongside the sec_fetcher module to provide comprehensive financial data
- Feeds standardized financial data to the financial_data_aggregator

Financial importance:
- Provides immediate access to structured financial data without parsing raw filings
- Enables consistent financial analysis across companies and time periods
- Supports fundamental financial modeling with reliable data sources
"""

import os
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
import requests

from ai_analyst.app.core.config import settings

# Set up logging
logger = logging.getLogger(__name__)

class PolygonFinancialsClient:
    """
    Client for retrieving financial data from Polygon.io Financials API.
    """
    
    def __init__(self, api_key: Optional[str] = None, cache_dir: Optional[str] = None):
        """
        Initialize the Polygon Financials client.
        
        Args:
            api_key: Polygon API key (defaults to settings.POLYGON_API_KEY)
            cache_dir: Directory for caching API responses
        """
        self.api_key = api_key or settings.POLYGON_API_KEY
        
        if not self.api_key:
            raise ValueError("Polygon API key is required")
            
        self.base_url = "https://api.polygon.io/vX/reference/financials"
        self.cache_dir = Path(cache_dir or (settings.DATA_DIR + "/polygon_cache"))
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Rate limiting settings - Polygon has 5 requests per minute for free tier
        self.rate_limit_per_minute = 5
        self.request_timestamps = []
        
    def get_financial_statements(
        self,
        ticker: str,
        timeframe: str = "annual",
        limit: int = 5,
        filing_date_gte: Optional[str] = None,
        filing_date_lt: Optional[str] = None,
        include_sources: bool = False,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Retrieve financial statements for a company.
        
        Args:
            ticker: Company ticker symbol
            timeframe: Financial reporting period ("annual", "quarterly", or "ttm")
            limit: Maximum number of results to return
            filing_date_gte: Filter by filing date >= this date (YYYY-MM-DD)
            filing_date_lt: Filter by filing date < this date (YYYY-MM-DD)
            include_sources: Whether to include xpath and formula attributes
            force_refresh: Whether to force refresh from source
            
        Returns:
            Dictionary containing financial statements data
        """
        cache_key = f"{ticker}_{timeframe}_{limit}_{filing_date_gte}_{filing_date_lt}_{include_sources}"
        cache_key = cache_key.replace("-", "_").replace("/", "_")
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        # Check cache if not forcing refresh
        if not force_refresh and cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    cached_data = json.load(f)
                    
                # Check if cache is recent (within 7 days)
                cache_date = datetime.fromisoformat(cached_data.get("fetched_at", "2000-01-01"))
                if (datetime.now() - cache_date).days < 7:
                    logger.info(f"Using cached financial data for {ticker}")
                    return cached_data
            except Exception as e:
                logger.warning(f"Error reading cached data: {e}")
        
        # Build query parameters
        params = {
            "ticker": ticker,
            "timeframe": timeframe,
            "limit": min(limit, 100),  # API max is 100
            "include_sources": str(include_sources).lower(),
            "apiKey": self.api_key
        }
        
        # Add optional date filters
        if filing_date_gte:
            params["filing_date.gte"] = filing_date_gte
        if filing_date_lt:
            params["filing_date.lt"] = filing_date_lt
            
        # Make request with rate limiting
        self._apply_rate_limiting()
        
        try:
            response = requests.get(self.base_url, params=params)
            self.request_timestamps.append(time.time())
            
            # Check for errors
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            
            # Check for pagination
            results = data.get("results", [])
            next_url = data.get("next_url")
            
            # Fetch additional pages if needed and if limit hasn't been reached
            while next_url and len(results) < limit:
                # Apply rate limiting
                self._apply_rate_limiting()
                
                # Make request for next page
                next_url_with_key = f"{next_url}&apiKey={self.api_key}"
                response = requests.get(next_url_with_key)
                self.request_timestamps.append(time.time())
                
                # Check for errors
                response.raise_for_status()
                
                # Parse response
                next_data = response.json()
                
                # Add results and update next_url
                next_results = next_data.get("results", [])
                results.extend(next_results)
                next_url = next_data.get("next_url")
                
            # Trim to requested limit
            results = results[:limit]
            
            # Add metadata
            result_data = {
                "ticker": ticker,
                "timeframe": timeframe,
                "fetched_at": datetime.now().isoformat(),
                "results": results
            }
            
            # Cache the results
            try:
                with open(cache_file, "w") as f:
                    json.dump(result_data, f, indent=2)
                logger.info(f"Cached financial data for {ticker}")
            except Exception as e:
                logger.warning(f"Error caching data: {e}")
                
            return result_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching financial data from Polygon: {e}")
            raise
    
    def get_financial_statements_by_type(
        self,
        ticker: str,
        statement_type: str = "all",
        years: int = 3,
        include_quarterly: bool = False,
        force_refresh: bool = False
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve financial statements organized by statement type.
        
        Args:
            ticker: Company ticker symbol
            statement_type: Type of financial statement ("income", "balance", "cash", "all")
            years: Number of years of historical data
            include_quarterly: Whether to include quarterly data
            force_refresh: Whether to force refresh from source
            
        Returns:
            Dictionary mapping statement types to lists of statements
        """
        # Convert years to date range (approx.)
        current_year = datetime.now().year
        filing_date_gte = f"{current_year - years}-01-01"
        
        # Fetch annual statements
        annual_data = self.get_financial_statements(
            ticker=ticker,
            timeframe="annual",
            limit=years,
            filing_date_gte=filing_date_gte,
            include_sources=False,
            force_refresh=force_refresh
        )
        
        # Fetch quarterly statements if requested
        quarterly_data = None
        if include_quarterly:
            quarterly_data = self.get_financial_statements(
                ticker=ticker,
                timeframe="quarterly",
                limit=years * 4,  # Approx. 4 quarters per year
                filing_date_gte=filing_date_gte,
                include_sources=False,
                force_refresh=force_refresh
            )
        
        # Organize by statement type
        result = {
            "income_statements": [],
            "balance_sheets": [],
            "cash_flow_statements": []
        }
        
        # Process annual data
        for filing in annual_data.get("results", []):
            financials = filing.get("financials", {})
            
            # Get fiscal period info
            fiscal_year = filing.get("fiscal_year")
            fiscal_period = filing.get("fiscal_period")
            filing_date = filing.get("filing_date")
            end_date = filing.get("end_date")
            
            # Extract income statement
            if statement_type in ["income", "all"] and "income_statement" in financials:
                income_statement = {
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "fiscal_period": fiscal_period,
                    "filing_date": filing_date,
                    "end_date": end_date,
                    "period_type": "annual",
                    "metrics": financials.get("income_statement", {})
                }
                result["income_statements"].append(income_statement)
            
            # Extract balance sheet
            if statement_type in ["balance", "all"] and "balance_sheet" in financials:
                balance_sheet = {
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "fiscal_period": fiscal_period,
                    "filing_date": filing_date,
                    "end_date": end_date,
                    "period_type": "annual",
                    "metrics": financials.get("balance_sheet", {})
                }
                result["balance_sheets"].append(balance_sheet)
            
            # Extract cash flow statement
            if statement_type in ["cash", "all"] and "cash_flow_statement" in financials:
                cash_flow = {
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "fiscal_period": fiscal_period,
                    "filing_date": filing_date,
                    "end_date": end_date,
                    "period_type": "annual",
                    "metrics": financials.get("cash_flow_statement", {})
                }
                result["cash_flow_statements"].append(cash_flow)
        
        # Process quarterly data if available
        if quarterly_data:
            for filing in quarterly_data.get("results", []):
                financials = filing.get("financials", {})
                
                # Get fiscal period info
                fiscal_year = filing.get("fiscal_year")
                fiscal_period = filing.get("fiscal_period")
                filing_date = filing.get("filing_date")
                end_date = filing.get("end_date")
                
                # Extract income statement
                if statement_type in ["income", "all"] and "income_statement" in financials:
                    income_statement = {
                        "ticker": ticker,
                        "fiscal_year": fiscal_year,
                        "fiscal_period": fiscal_period,
                        "filing_date": filing_date,
                        "end_date": end_date,
                        "period_type": "quarterly",
                        "metrics": financials.get("income_statement", {})
                    }
                    result["income_statements"].append(income_statement)
                
                # Extract balance sheet
                if statement_type in ["balance", "all"] and "balance_sheet" in financials:
                    balance_sheet = {
                        "ticker": ticker,
                        "fiscal_year": fiscal_year,
                        "fiscal_period": fiscal_period,
                        "filing_date": filing_date,
                        "end_date": end_date,
                        "period_type": "quarterly",
                        "metrics": financials.get("balance_sheet", {})
                    }
                    result["balance_sheets"].append(balance_sheet)
                
                # Extract cash flow statement
                if statement_type in ["cash", "all"] and "cash_flow_statement" in financials:
                    cash_flow = {
                        "ticker": ticker,
                        "fiscal_year": fiscal_year,
                        "fiscal_period": fiscal_period,
                        "filing_date": filing_date,
                        "end_date": end_date,
                        "period_type": "quarterly",
                        "metrics": financials.get("cash_flow_statement", {})
                    }
                    result["cash_flow_statements"].append(cash_flow)
        
        return result
    
    def get_common_financial_metrics(
        self,
        ticker: str,
        years: int = 3,
        include_quarterly: bool = False,
        force_refresh: bool = False
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        Retrieve common financial metrics organized by category.
        
        Args:
            ticker: Company ticker symbol
            years: Number of years of historical data
            include_quarterly: Whether to include quarterly data
            force_refresh: Whether to force refresh from source
            
        Returns:
            Dictionary mapping metric categories to metrics to lists of values
        """
        # Fetch financial statements
        statements = self.get_financial_statements_by_type(
            ticker=ticker,
            statement_type="all",
            years=years,
            include_quarterly=include_quarterly,
            force_refresh=force_refresh
        )
        
        # Organize metrics by category
        result = {
            "income": {},
            "balance": {},
            "cash_flow": {},
            "ratios": {}
        }
        
        # Helper function to extract a specific metric from a statement
        def extract_metric(statement, metric_name):
            if metric_name in statement.get("metrics", {}):
                metric_value = statement["metrics"][metric_name]
                
                # Only include value if it's a number
                if not isinstance(metric_value, dict):
                    value = metric_value
                else:
                    value = metric_value.get("value")
                
                if value is not None:
                    return {
                        "value": value,
                        "fiscal_year": statement.get("fiscal_year"),
                        "fiscal_period": statement.get("fiscal_period"),
                        "period_type": statement.get("period_type"),
                        "filing_date": statement.get("filing_date"),
                        "end_date": statement.get("end_date")
                    }
            return None
        
        # Extract key income statement metrics
        income_metrics = [
            "revenues", "cost_of_revenue", "gross_profit", "operating_expenses",
            "operating_income", "interest_expense", "income_tax_expense", "net_income"
        ]
        
        for metric_name in income_metrics:
            result["income"][metric_name] = []
            for statement in statements["income_statements"]:
                metric = extract_metric(statement, metric_name)
                if metric:
                    result["income"][metric_name].append(metric)
        
        # Extract key balance sheet metrics
        balance_metrics = [
            "current_assets", "cash_and_equivalents", "inventory", "accounts_receivable",
            "total_assets", "current_liabilities", "accounts_payable", "long_term_debt",
            "total_liabilities", "total_equity", "retained_earnings"
        ]
        
        for metric_name in balance_metrics:
            result["balance"][metric_name] = []
            for statement in statements["balance_sheets"]:
                metric = extract_metric(statement, metric_name)
                if metric:
                    result["balance"][metric_name].append(metric)
        
        # Extract key cash flow metrics
        cash_flow_metrics = [
            "operating_cash_flow", "capital_expenditure", "free_cash_flow", 
            "dividend_payments", "net_cash_flow"
        ]
        
        for metric_name in cash_flow_metrics:
            result["cash_flow"][metric_name] = []
            for statement in statements["cash_flow_statements"]:
                metric = extract_metric(statement, metric_name)
                if metric:
                    result["cash_flow"][metric_name].append(metric)
        
        # Calculate financial ratios where we have enough data
        # Will be implemented in more detail as needed
        
        return result
    
    def _apply_rate_limiting(self):
        """Apply rate limiting to API requests."""
        # Remove timestamps older than 1 minute
        current_time = time.time()
        self.request_timestamps = [ts for ts in self.request_timestamps 
                                  if current_time - ts < 60]
        
        # If we've hit the rate limit, wait
        if len(self.request_timestamps) >= self.rate_limit_per_minute:
            oldest_timestamp = min(self.request_timestamps)
            sleep_time = 60 - (current_time - oldest_timestamp)
            
            if sleep_time > 0:
                logger.info(f"Rate limiting in effect, waiting {sleep_time:.2f} seconds")
                time.sleep(sleep_time)

# Create singleton instance
polygon_financials = PolygonFinancialsClient() 