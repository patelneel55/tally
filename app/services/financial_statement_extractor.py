"""
Financial Statement Extractor
----------------------------

This module extracts structured financial statement data from SEC filings.
It parses the HTML/XML content of financial statements in 10-K and 10-Q filings
and converts them into structured data for analysis.

What this file does:
1. Extracts balance sheets, income statements, and cash flow statements
2. Handles different filing formats and company-specific variations
3. Normalizes data into consistent structures for comparison and analysis
4. Provides both simple and detailed extraction modes

How it fits in the architecture:
- Financial statement data is fundamental to valuation and analysis
- Provides structured data that feeds into financial modeling
- Enables comparisons across companies and time periods
"""

import os
import re
import json
import logging
import pandas as pd
from typing import Dict, List, Optional, Union, Any, Tuple
from pathlib import Path
from datetime import datetime, date
from bs4 import BeautifulSoup
import numpy as np

from app.core.config import settings
from app.models.financial_statements import FilingType, FinancialStatement, FinancialStatementType, FinancialStatementPeriod
from app.services.sec_fetcher import SECFiling, sec_fetcher

from app.core.config import settings
from app.models.financial_statements import (
    FinancialStatement,
    FinancialStatementType,
    FinancialStatementPeriod,
    FinancialMetric
)

# Set up logging
logger = logging.getLogger(__name__)

class FinancialStatementExtractor:
    """
    Extracts structured financial statements from SEC filings.
    
    This class provides methods to identify, extract, and normalize
    financial statements from SEC filing text, converting them into
    standardized, comparable formats.
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the financial statement extractor.
        
        Args:
            cache_dir: Directory to cache extracted financial statements.
                       If None, uses the default cache directory.
        """
        # Handle case where settings.DATA_DIR might not be available
        try:
            data_dir = getattr(settings, 'DATA_DIR', 'data')
        except AttributeError:
            data_dir = 'data'
            
        self.cache_dir = cache_dir or os.path.join(
            data_dir, "financial_statements_cache"
        )
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Load financial statement templates and mapping dictionaries
        self._load_templates()
    
    def _load_templates(self):
        """
        Load templates and mappings for financial statement extraction.
        
        This includes:
        - Standard line item names and their variations
        - Regex patterns for identifying financial tables
        - Structural templates for different statement types
        """
        # Common line item variations (different companies use different terms)
        self.income_statement_items = {
            "revenue": ["revenue", "net sales", "total revenue", "net revenue", "sales"],
            "cost_of_revenue": ["cost of revenue", "cost of sales", "cost of goods sold", "cogs"],
            "gross_profit": ["gross profit", "gross margin"],
            "operating_expenses": ["operating expenses", "total operating expenses"],
            "operating_income": ["operating income", "operating profit", "income from operations"],
            "net_income": ["net income", "net earnings", "net profit"],
            "eps_basic": ["basic eps", "basic earnings per share", "earnings per share basic"],
            "eps_diluted": ["diluted eps", "diluted earnings per share", "earnings per share diluted"]
        }
        
        self.balance_sheet_items = {
            "total_assets": ["total assets", "assets total"],
            "total_liabilities": ["total liabilities", "liabilities total"],
            "total_equity": ["total equity", "total stockholders' equity", "shareholders' equity"],
            "cash_and_equivalents": ["cash and cash equivalents", "cash and equivalents"],
            "short_term_investments": ["short term investments", "short-term investments"],
            "accounts_receivable": ["accounts receivable", "receivables"],
            "inventory": ["inventory", "inventories"],
            "long_term_debt": ["long term debt", "long-term debt"]
        }
        
        self.cash_flow_items = {
            "operating_cash_flow": ["cash flow from operations", "net cash provided by operating activities"],
            "investing_cash_flow": ["cash flow from investing", "net cash used in investing activities"],
            "financing_cash_flow": ["cash flow from financing", "net cash used in financing activities"],
            "free_cash_flow": ["free cash flow"],
            "capital_expenditures": ["capital expenditures", "purchases of property and equipment"]
        }
        
        # Regex patterns for identifying statement sections in filings
        self.statement_patterns = {
            FinancialStatementType.INCOME_STATEMENT: [
                r"(?i)consolidated\s+statements?\s+of\s+(?:operations|income|earnings)",
                r"(?i)statements?\s+of\s+(?:operations|income|earnings)",
                r"(?i)(?:operations|income|earnings)\s+statements?"
            ],
            FinancialStatementType.BALANCE_SHEET: [
                r"(?i)consolidated\s+balance\s+sheets?",
                r"(?i)balance\s+sheets?",
                r"(?i)statements?\s+of\s+financial\s+position"
            ],
            FinancialStatementType.CASH_FLOW: [
                r"(?i)consolidated\s+statements?\s+of\s+cash\s+flows?",
                r"(?i)statements?\s+of\s+cash\s+flows?",
                r"(?i)cash\s+flows?\s+statements?"
            ]
        }
    
    def extract_financial_statements(self, filing: SECFiling) -> Dict[str, FinancialStatement]:
        """
        Extract all financial statements from an SEC filing.
        
        Args:
            filing: SECFiling object containing the filing data
            
        Returns:
            Dictionary mapping statement types to FinancialStatement objects
        """
        logger.info(f"Extracting financial statements from {filing.filing_type} for {filing.ticker}")
        
        # Check cache first
        cache_key = self._generate_cache_key(filing)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            logger.info(f"Retrieved financial statements from cache for {filing.ticker}")
            return cached_result
        
        # Get filing content
        content = self._get_filing_content(filing)
        if not content:
            logger.warning(f"No content found for {filing.filing_type} filing {filing.ticker}")
            return {}
        
        # Extract each statement type
        statements = {}
        for statement_type in FinancialStatementType:
            try:
                statement = self._extract_statement(content, statement_type, filing)
                if statement:
                    statements[statement_type] = statement
            except Exception as e:
                logger.error(f"Error extracting {statement_type} for {filing.ticker}: {str(e)}")
        
        # Cache the results
        self._save_to_cache(cache_key, statements)
        
        return statements
    
    def _extract_statement(
        self, content: str, statement_type: FinancialStatementType, filing: SECFiling
    ) -> Optional[FinancialStatement]:
        """
        Extract a specific financial statement from filing content.
        
        Args:
            content: The filing content (text or HTML)
            statement_type: Type of financial statement to extract
            filing: Original SECFiling metadata
            
        Returns:
            FinancialStatement object or None if not found
        """
        # First, try to find the section containing the statement
        section = self._find_statement_section(content, statement_type)
        if not section:
            logger.warning(f"Could not find {statement_type} section in {filing.ticker} filing")
            return None
        
        # Parse the section into a structured format
        try:
            if self._is_html_content(content):
                data = self._parse_html_table(section, statement_type)
            else:
                data = self._parse_text_table(section, statement_type)
                
            if not data or not data.get('metrics'):
                logger.warning(f"Failed to extract metrics from {statement_type} for {filing.ticker}")
                return None
                
            # Determine the reporting period
            period = self._determine_period(filing, data)
            
            # Create and return the financial statement object
            return FinancialStatement(
                statement_type=statement_type,
                company_ticker=filing.ticker,
                period=period,
                fiscal_year=filing.fiscal_year,
                fiscal_period=filing.fiscal_period,
                filing_date=filing.filing_date,
                currency="USD",  # Default, could be extracted from the filing
                metrics=data['metrics'],
                units=data.get('units', 'thousands'),
                source_filing_id=filing.id
            )
        except Exception as e:
            logger.error(f"Error parsing {statement_type} table: {str(e)}")
            return None
    
    def _find_statement_section(
        self, content: str, statement_type: FinancialStatementType
    ) -> Optional[str]:
        """
        Find the section containing a specific financial statement.
        
        Args:
            content: Full filing content
            statement_type: Type of statement to locate
            
        Returns:
            The extracted section as string, or None if not found
        """
        patterns = self.statement_patterns[statement_type]
        
        for pattern in patterns:
            # First, try to find the section header
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                # Extract a reasonable chunk after the match (adjust size as needed)
                start_idx = match.start()
                
                # Find a potential end marker (next statement or end of document)
                end_markers = []
                for st_type in FinancialStatementType:
                    if st_type != statement_type:
                        end_markers.extend(self.statement_patterns[st_type])
                
                # Add some generic section end markers
                end_markers.extend([
                    r"(?i)notes\s+to\s+(?:consolidated\s+)?financial\s+statements",
                    r"(?i)management's\s+discussion\s+and\s+analysis",
                    r"(?i)item\s+[0-9]+"
                ])
                
                # Try to find the end of the section
                end_idx = len(content)
                for end_pattern in end_markers:
                    end_match = re.search(end_pattern, content[start_idx:start_idx + 50000])
                    if end_match:
                        potential_end = start_idx + end_match.start()
                        if potential_end < end_idx:
                            end_idx = potential_end
                
                # Limit to a reasonable chunk size if no end marker found
                max_chunk = 50000  # Adjust based on typical statement size
                if end_idx - start_idx > max_chunk:
                    end_idx = start_idx + max_chunk
                
                return content[start_idx:end_idx]
        
        return None
    
    def _parse_html_table(
        self, section: str, statement_type: FinancialStatementType
    ) -> Dict[str, Any]:
        """
        Parse an HTML table into structured financial data.
        
        Args:
            section: HTML section containing the table
            statement_type: Type of financial statement
            
        Returns:
            Dictionary with parsed metrics and metadata
        """
        soup = BeautifulSoup(section, 'html.parser')
        tables = soup.find_all('table')
        
        if not tables:
            return {}
        
        # Find the most likely financial table (usually the largest)
        target_table = max(tables, key=lambda t: len(t.find_all('tr')))
        
        # Extract headers (column names)
        headers = []
        header_row = target_table.find('tr')
        if header_row:
            headers = [th.get_text().strip() for th in header_row.find_all(['th', 'td'])]
        
        # Map columns to time periods
        time_periods = self._identify_time_periods(headers)
        
        # Extract data rows
        metrics = {}
        for row in target_table.find_all('tr')[1:]:  # Skip header row
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue
                
            # Try to identify what metric this row represents
            metric_name = cells[0].get_text().strip().lower()
            standardized_name = self._standardize_metric_name(metric_name, statement_type)
            
            if not standardized_name:
                continue  # Skip rows we can't identify
                
            # Extract values for each time period
            values = {}
            for i, cell in enumerate(cells[1:]):
                if i >= len(time_periods):
                    break
                    
                period = time_periods[i]
                value_text = cell.get_text().strip()
                value = self._parse_numeric_value(value_text)
                
                if value is not None:
                    values[period] = value
            
            if values:
                metrics[standardized_name] = values
        
        return {
            'metrics': metrics,
            'units': self._determine_units(section)
        }
    
    def _parse_text_table(
        self, section: str, statement_type: FinancialStatementType
    ) -> Dict[str, Any]:
        """
        Parse a text-based table into structured financial data.
        
        Args:
            section: Text section containing the table
            statement_type: Type of financial statement
            
        Returns:
            Dictionary with parsed metrics and metadata
        """
        # Split into lines and clean
        lines = [line.strip() for line in section.split('\n') if line.strip()]
        
        # Identify table header line (contains years)
        header_line = None
        for i, line in enumerate(lines[:20]):  # Check first 20 lines for header
            if re.search(r'\b20\d\d\b', line) and ('year' in line.lower() or 'period' in line.lower() or len(re.findall(r'\b20\d\d\b', line)) >= 2):
                header_line = i
                break
        
        if header_line is None:
            return {}
            
        # Extract column headers (years/periods)
        header = lines[header_line]
        time_periods = self._extract_time_periods_from_text(header)
        
        if not time_periods:
            return {}
            
        # Process data rows
        metrics = {}
        current_section = None
        
        for line in lines[header_line+1:]:
            # Skip lines without numbers (likely headers or notes)
            if not re.search(r'\d', line):
                current_section = line.lower()
                continue
                
            # Try to identify the metric from this line
            parts = re.split(r'\s{2,}', line)
            if len(parts) < 2:
                continue
                
            metric_name = parts[0].lower().strip()
            standardized_name = self._standardize_metric_name(metric_name, statement_type)
            
            if not standardized_name:
                continue
                
            # Extract values
            values = {}
            numeric_values = [self._parse_numeric_value(p) for p in parts[1:]]
            
            for i, value in enumerate(numeric_values):
                if i >= len(time_periods) or value is None:
                    continue
                values[time_periods[i]] = value
            
            if values:
                metrics[standardized_name] = values
        
        return {
            'metrics': metrics,
            'units': self._determine_units(section)
        }
    
    def _standardize_metric_name(
        self, raw_name: str, statement_type: FinancialStatementType
    ) -> Optional[str]:
        """
        Convert a raw line item name to a standardized metric name.
        
        Args:
            raw_name: Raw text of the line item
            statement_type: Type of financial statement
            
        Returns:
            Standardized metric name or None if no match found
        """
        # Remove common prefixes/suffixes and clean the raw name
        clean_name = raw_name.lower().strip()
        clean_name = re.sub(r'^total\s+', '', clean_name)
        clean_name = re.sub(r'\s+\([^)]*\)$', '', clean_name)
        clean_name = re.sub(r'[\(\)]', '', clean_name)
        
        # Select the appropriate mapping dictionary based on statement type
        if statement_type == FinancialStatementType.INCOME_STATEMENT:
            mapping_dict = self.income_statement_items
        elif statement_type == FinancialStatementType.BALANCE_SHEET:
            mapping_dict = self.balance_sheet_items
        elif statement_type == FinancialStatementType.CASH_FLOW:
            mapping_dict = self.cash_flow_items
        else:
            return None
            
        # Try to match the clean name to standardized metrics
        for std_name, variations in mapping_dict.items():
            if any(var in clean_name for var in variations):
                return std_name
                
        # Return the clean name as-is if it doesn't match any standard metric
        return clean_name
    
    def _identify_time_periods(self, headers: List[str]) -> List[str]:
        """
        Identify time periods from table headers.
        
        Args:
            headers: List of column headers from the table
            
        Returns:
            List of standardized time period strings
        """
        time_periods = []
        
        for header in headers[1:]:  # Skip the first header (usually line item name)
            # Look for years in the format "YYYY" or "FY YYYY"
            year_match = re.search(r'\b(20\d\d)\b', header)
            if year_match:
                year = year_match.group(1)
                
                # Check if it specifies a quarter
                quarter_match = re.search(r'\bQ([1-4])\b', header, re.IGNORECASE)
                if quarter_match:
                    quarter = quarter_match.group(1)
                    time_periods.append(f"{year}Q{quarter}")
                else:
                    time_periods.append(year)
            elif "months" in header.lower():
                # Handle periods like "Three Months Ended June 30, 2023"
                months_match = re.search(r'(\w+)\s+months', header.lower())
                date_match = re.search(r'(\w+\s+\d+,\s+20\d\d)', header)
                
                if months_match and date_match:
                    months_text = months_match.group(1).lower()
                    date_text = date_match.group(1)
                    
                    months_map = {"three": "Q1", "six": "Q2", "nine": "Q3", "twelve": "FY"}
                    period = months_map.get(months_text, "")
                    
                    year_match = re.search(r'20\d\d', date_text)
                    if year_match and period:
                        year = year_match.group(0)
                        time_periods.append(f"{year}{period}")
                    else:
                        time_periods.append(date_text)
                else:
                    time_periods.append(header)
            else:
                time_periods.append(header)
                
        return time_periods
    
    def _extract_time_periods_from_text(self, header_line: str) -> List[str]:
        """
        Extract time periods from a text table header line.
        
        Args:
            header_line: The header line containing period information
            
        Returns:
            List of standardized time period strings
        """
        # Look for years in format YYYY
        years = re.findall(r'\b(20\d\d)\b', header_line)
        
        # If we found years, use them as periods
        if years:
            # Check if there are quarter indicators
            quarters = re.findall(r'\bQ([1-4])\b', header_line, re.IGNORECASE)
            
            if len(quarters) == len(years):
                return [f"{year}Q{quarter}" for year, quarter in zip(years, quarters)]
            else:
                return years
                
        # If no years found, try to extract date ranges
        date_ranges = re.findall(r'(\w+\s+\d+,\s+20\d\d)', header_line)
        if date_ranges:
            return date_ranges
            
        # Last resort: split by multiple spaces and filter for items with numbers
        parts = re.split(r'\s{2,}', header_line)
        return [p for p in parts if re.search(r'\d', p)]
    
    def _parse_numeric_value(self, value_text: str) -> Optional[float]:
        """
        Parse a numeric value from text, handling formatting and units.
        
        Args:
            value_text: Text containing the numeric value
            
        Returns:
            Parsed float value or None if parsing fails
        """
        if not value_text or value_text.lower() in ['', '-', 'n/a', 'na', 'nil']:
            return None
            
        # Remove currency symbols, commas, and other non-numeric characters
        clean_text = re.sub(r'[^0-9\.\-\(\)]', '', value_text)
        
        # Handle parentheses notation for negative numbers: (123) -> -123
        if clean_text.startswith('(') and clean_text.endswith(')'):
            clean_text = '-' + clean_text[1:-1]
            
        try:
            return float(clean_text)
        except ValueError:
            return None
    
    def _determine_units(self, text: str) -> str:
        """
        Determine the units used in the financial statement.
        
        Args:
            text: The financial statement text
            
        Returns:
            Unit string ('thousands', 'millions', etc.)
        """
        text_lower = text.lower()
        
        if 'in thousands' in text_lower or '(in thousands)' in text_lower:
            return 'thousands'
        elif 'in millions' in text_lower or '(in millions)' in text_lower:
            return 'millions'
        elif 'in billions' in text_lower or '(in billions)' in text_lower:
            return 'billions'
        else:
            return 'thousands'  # Default assumption
    
    def _determine_period(self, filing: SECFiling, data: Dict[str, Any]) -> FinancialStatementPeriod:
        """
        Determine the reporting period of the financial statement.
        
        Args:
            filing: SECFiling metadata
            data: Extracted statement data
            
        Returns:
            FinancialStatementPeriod enum value
        """
        if filing.filing_type == FilingType.FORM_10K:
            return FinancialStatementPeriod.ANNUAL
        elif filing.filing_type == FilingType.FORM_10Q:
            return FinancialStatementPeriod.QUARTERLY
        
        # If filing type doesn't directly indicate period, infer from data
        metrics = data.get('metrics', {})
        
        # Check column headers for quarter indicators
        has_quarterly = False
        for metric_name, periods in metrics.items():
            for period in periods.keys():
                if 'Q' in period or 'quarter' in period.lower():
                    has_quarterly = True
                    break
            if has_quarterly:
                break
                
        return FinancialStatementPeriod.QUARTERLY if has_quarterly else FinancialStatementPeriod.ANNUAL
    
    def _is_html_content(self, content: str) -> bool:
        """
        Check if content is HTML or plain text.
        
        Args:
            content: Filing content to check
            
        Returns:
            True if content appears to be HTML, False otherwise
        """
        return '<html' in content.lower() or '<table' in content.lower() or '<tr' in content.lower()
    
    def _get_filing_content(self, filing: SECFiling) -> Optional[str]:
        """
        Get the content of a filing, either from the filing object or by fetching it.
        
        Args:
            filing: SECFiling object
            
        Returns:
            Filing content as string or None if not available
        """
        if hasattr(filing, 'content') and filing.content:
            return filing.content
            
        # If content not available in filing object, try to fetch it
        try:
            return sec_fetcher.get_filing_text(filing)
        except Exception as e:
            logger.error(f"Error fetching filing content for {filing.ticker}: {str(e)}")
            return None
    
    def _generate_cache_key(self, filing: SECFiling) -> str:
        """
        Generate a cache key for a filing.
        
        Args:
            filing: SECFiling object
            
        Returns:
            Cache key string
        """
        key_parts = [
            filing.ticker,
            filing.filing_type,
            str(filing.fiscal_year),
            filing.fiscal_period if filing.fiscal_period else ''
        ]
        return "_".join(key_parts)
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, FinancialStatement]]:
        """
        Retrieve financial statements from cache.
        
        Args:
            cache_key: Cache key string
            
        Returns:
            Dictionary of financial statements or None if not in cache
        """
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                
                # Convert JSON data back to FinancialStatement objects
                return {
                    statement_type: FinancialStatement(**statement_data)
                    for statement_type, statement_data in data.items()
                }
            except Exception as e:
                logger.error(f"Error loading cache file {cache_file}: {str(e)}")
                return None
        return None
    
    def _save_to_cache(self, cache_key: str, statements: Dict[str, FinancialStatement]):
        """
        Save financial statements to cache.
        
        Args:
            cache_key: Cache key string
            statements: Dictionary of financial statements
        """
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        try:
            # Convert FinancialStatement objects to dictionaries
            data = {
                statement_type: statement.dict()
                for statement_type, statement in statements.items()
            }
            
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
                
            logger.info(f"Saved financial statements to cache: {cache_file}")
        except Exception as e:
            logger.error(f"Error saving to cache file {cache_file}: {str(e)}")

# Convenience function for external use
financial_statement_extractor = FinancialStatementExtractor()

def extract_financial_statements(filing: SECFiling) -> Dict[str, FinancialStatement]:
    """
    Extract financial statements from an SEC filing.
    
    Args:
        filing: SECFiling object
        
    Returns:
        Dictionary mapping statement types to FinancialStatement objects
    """
    return financial_statement_extractor.extract_financial_statements(filing) 