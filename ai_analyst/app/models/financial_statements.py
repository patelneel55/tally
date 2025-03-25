"""
Financial Statements Models - Simple Testing Version
--------------------------------------------------

This is a simplified version of the financial statements model file for testing purposes.
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Union
from datetime import date, datetime
from pydantic import BaseModel, Field


class FilingType(str, Enum):
    """SEC filing types."""
    FORM_10K = "10-K"      # Annual report
    FORM_10Q = "10-Q"      # Quarterly report
    FORM_8K = "8-K"        # Material events report
    FORM_S1 = "S-1"        # Initial registration statement
    FORM_424B = "424B"     # Prospectus
    ALL_FORMS = None       # Represents all forms (for filtering)


class FinancialStatementType(str, Enum):
    """Types of financial statements."""
    INCOME_STATEMENT = "income_statement"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW = "cash_flow"


class FinancialStatementPeriod(str, Enum):
    """Reporting periods for financial statements."""
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class FinancialMetric(BaseModel):
    """A single financial metric or line item from a financial statement."""
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    values: Dict[str, float]
    currency: Optional[str] = "USD"
    units: Optional[str] = "thousands"
    
    model_config = {"extra": "allow"}


class FinancialStatement(BaseModel):
    """A complete financial statement extracted from an SEC filing."""
    statement_type: FinancialStatementType
    company_ticker: str
    period: FinancialStatementPeriod
    fiscal_year: int
    fiscal_period: Optional[str] = None
    filing_date: Optional[date] = None
    currency: str = "USD"
    units: str = "thousands"
    metrics: Dict[str, Dict[str, float]]
    source_filing_id: Optional[str] = None
    extracted_at: datetime = Field(default_factory=datetime.now)
    
    model_config = {"extra": "allow"}


class FinancialStatementComparison(BaseModel):
    """Comparison of financial metrics across multiple periods."""
    statement_type: FinancialStatementType
    company_ticker: str
    comparison_periods: List[str]
    metrics: Dict[str, Dict[str, Any]]
    period_type: FinancialStatementPeriod
    
    model_config = {"extra": "allow"}


class FinancialRatio(BaseModel):
    """Financial ratio calculated from financial statement metrics."""
    name: str
    display_name: str
    description: str
    category: str
    formula: str
    values: Dict[str, float]
    industry_average: Optional[float] = None
    
    model_config = {"extra": "allow"} 