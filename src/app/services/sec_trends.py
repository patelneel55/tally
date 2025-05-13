"""
SEC Filing Trends Analyzer
-------------------------

This module analyzes trends and changes across multiple SEC filings for a company.
It leverages AI models to identify patterns, compare key metrics, and extract
insights from historical filings.

What this file does:
1. Processes multiple SEC filings (10-K, 10-Q) for a single company
2. Compares key sections and metrics across filings
3. Identifies trends, changes, and notable developments
4. Generates comprehensive multi-period analysis

How it fits in the architecture:
- Builds on top of the sec_fetcher and sec_analyzer modules
- Provides higher-level insights across multiple time periods
- Feeds into the API layer for historical SEC analysis

Financial importance:
- Enables trend analysis across multiple reporting periods
- Identifies changes in risk factors, business operations, and financial metrics
- Provides context for understanding company performance over time
- Highlights emerging opportunities or challenges
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import aiohttp
from openai import AsyncOpenAI

from app.core.config import settings
from app.models.financial_statements import FilingType
from app.services.sec_analyzer import SECFilingAnalysisResult, sec_filing_analyzer
from app.services.sec_fetcher import SECFiling, sec_fetcher


# Set up logging
logger = logging.getLogger(__name__)

# Multi-period analysis prompt
MULTI_PERIOD_ANALYSIS_PROMPT = """
You are a financial analyst specializing in SEC filings analysis.
I'm providing you with analyses of multiple SEC filings for the same company across different time periods.

Please analyze these filings collectively and provide a comprehensive multi-period analysis with the following sections:

1. EXECUTIVE SUMMARY: A concise overview of the company's performance and key trends across the analyzed periods.

2. FINANCIAL TRENDS:
   - Revenue trends and growth rates
   - Profit margin evolution
   - EPS progression
   - Cash flow patterns
   - Balance sheet changes

3. BUSINESS EVOLUTION:
   - Changes in business segments or product lines
   - Geographic expansion or contraction
   - Strategic shifts or new initiatives

4. RISK FACTOR CHANGES:
   - New risks that have emerged
   - Risks that have been mitigated or removed
   - Changes in emphasis or language around persistent risks

5. MANAGEMENT COMMENTARY EVOLUTION:
   - Changes in tone or focus in management's discussion
   - Consistency or inconsistency in forward-looking statements
   - Shifts in strategic priorities

6. KEY PERFORMANCE INDICATORS:
   - Track important KPIs across periods
   - Identify positive or negative trends
   - Compare against management's previous guidance

7. NOTABLE DEVELOPMENTS:
   - Significant events or changes across periods
   - Acquisitions, divestitures, or restructuring
   - Leadership changes or organizational shifts

8. FORWARD OUTLOOK:
   - Synthesize management's guidance across periods
   - Identify potential future challenges or opportunities
   - Assess the company's trajectory based on historical performance

Format your response with clear section headers using markdown (# for main sections, ## for subsections).
Be thorough but concise in your analysis, focusing on meaningful trends rather than isolated events.
"""


class SECTrendsAnalysisResult:
    """
    Container for SEC multi-period trends analysis results.

    This class stores the results of AI-powered analysis of multiple
    SEC filings across different time periods, including trend analysis,
    comparative insights, and key developments.
    """

    def __init__(
        self,
        symbol: str,
        filings: Dict[str, List[SECFiling]],
        summary: str,
        trends_analysis: Dict[str, Any],
        analysis_date: datetime = None,
    ):
        self.symbol = symbol
        self.filings = filings
        self.summary = summary
        self.trends_analysis = trends_analysis
        self.analysis_date = analysis_date or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert the trends analysis result to a dictionary."""
        return {
            "symbol": self.symbol,
            "filings": {
                filing_type: [filing.filing_id for filing in filings]
                for filing_type, filings in self.filings.items()
            },
            "filing_dates": {
                filing_type: [filing.filing_date.isoformat() for filing in filings]
                for filing_type, filings in self.filings.items()
            },
            "summary": self.summary,
            "trends_analysis": self.trends_analysis,
            "analysis_date": self.analysis_date.isoformat(),
        }

    @classmethod
    def from_dict(
        cls, data: Dict[str, Any], filings: Dict[str, List[SECFiling]]
    ) -> "SECTrendsAnalysisResult":
        """Create a trends analysis result from a dictionary."""
        return cls(
            symbol=data.get("symbol", ""),
            filings=filings,
            summary=data.get("summary", ""),
            trends_analysis=data.get("trends_analysis", {}),
            analysis_date=datetime.fromisoformat(
                data.get("analysis_date", datetime.now().isoformat())
            ),
        )


class SECTrendsAnalyzer:
    """
    Service for analyzing trends across multiple SEC filings.

    This class processes multiple SEC filings for a company and identifies
    trends, changes, and notable developments across different time periods.
    It leverages AI models to generate comprehensive multi-period analysis.
    """

    def __init__(self):
        """
        Initialize the SEC trends analyzer with AI model clients.

        Sets up connections to AI models and creates cache directories
        for storing trends analysis results.
        """
        # Initialize AI model client
        self.openai_client = None

        if settings.OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("OpenAI client initialized for SEC trends analysis")

        # Create cache directory for storing trends analysis results
        self.cache_dir = Path("cache/sec_trends")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def analyze_historical_filings(
        self, symbol: str
    ) -> Optional[SECTrendsAnalysisResult]:
        """
        Analyze historical SEC filings for a company.

        This function orchestrates the entire trends analysis process:
        1. Fetches historical filings (last 4 10-Qs + latest 10-K)
        2. Analyzes each filing individually
        3. Performs a comparative analysis across all filings
        4. Generates a comprehensive trends analysis

        Args:
            symbol: Company ticker symbol

        Returns:
            SECTrendsAnalysisResult object if successful, None otherwise
        """
        logger.info(f"Analyzing historical filings for {symbol}")

        # Check if we already have cached analysis
        cache_path = self._get_cache_path(symbol)
        if cache_path.exists() and settings.ENABLE_CACHE:
            logger.info(f"Using cached trends analysis for {symbol}")
            try:
                with open(cache_path) as f:
                    analysis_data = json.load(f)

                # We need to fetch the filings again to reconstruct the result object
                historical_filings = await sec_fetcher.get_historical_filings(symbol)
                return SECTrendsAnalysisResult.from_dict(
                    analysis_data, historical_filings
                )
            except Exception as e:
                logger.error(f"Error loading cached trends analysis: {e}")
                # Continue with fresh analysis if cache loading fails

        try:
            # Step 1: Fetch historical filings
            historical_filings = await sec_fetcher.get_historical_filings(symbol)

            # Check if we have any filings to analyze
            all_filings = historical_filings.get("10-K", []) + historical_filings.get(
                "10-Q", []
            )
            if not all_filings:
                logger.error(f"No historical filings found for {symbol}")
                return None

            # Step 2: Analyze each filing individually
            filing_analyses = {}
            for filing_type, filings in historical_filings.items():
                filing_analyses[filing_type] = []
                for filing in filings:
                    analysis = await sec_filing_analyzer.analyze_filing(filing)
                    if analysis:
                        filing_analyses[filing_type].append(analysis)

            # Step 3: Perform comparative analysis across all filings
            trends_analysis = await self._analyze_trends(symbol, filing_analyses)
            if not trends_analysis:
                logger.error(f"Failed to analyze trends for {symbol}")
                return None

            # Step 4: Cache the trends analysis result
            with open(cache_path, "w") as f:
                json.dump(trends_analysis.to_dict(), f, indent=2)

            logger.info(f"Successfully analyzed and cached trends for {symbol}")
            return trends_analysis

        except Exception as e:
            logger.error(f"Error analyzing historical filings for {symbol}: {e}")
            return None

    async def _analyze_trends(
        self, symbol: str, filing_analyses: Dict[str, List[SECFilingAnalysisResult]]
    ) -> Optional[SECTrendsAnalysisResult]:
        """
        Analyze trends across multiple filing analyses.

        This function uses an AI model to identify trends, changes, and
        notable developments across multiple SEC filings for a company.

        Args:
            symbol: Company ticker symbol
            filing_analyses: Dictionary mapping filing types to lists of analysis results

        Returns:
            SECTrendsAnalysisResult if successful, None otherwise
        """
        if not self.openai_client:
            logger.error("OpenAI client not available for trends analysis")
            return None

        try:
            # Prepare the input for the AI model
            input_text = self._prepare_trends_input(symbol, filing_analyses)

            # Call the OpenAI API for trends analysis
            response = await self.openai_client.chat.completions.create(
                model=settings.SEC_ANALYSIS_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a financial analyst specializing in SEC filings analysis.",
                    },
                    {"role": "user", "content": input_text},
                ],
                temperature=0.2,  # Low temperature for more factual responses
                max_tokens=settings.SEC_ANALYSIS_MAX_TOKENS,
            )

            analysis_text = response.choices[0].message.content

            # Extract summary (first paragraph) and detailed analysis
            parts = analysis_text.split("\n\n", 1)
            summary = parts[0] if parts else ""

            # Parse the structured analysis sections
            trends_analysis = self._parse_trends_sections(analysis_text)

            # Create filings dictionary for the result object
            filings = {}
            for filing_type, analyses in filing_analyses.items():
                filings[filing_type] = [analysis.filing for analysis in analyses]

            return SECTrendsAnalysisResult(
                symbol=symbol,
                filings=filings,
                summary=summary,
                trends_analysis=trends_analysis,
            )

        except Exception as e:
            logger.error(f"Error analyzing trends with OpenAI: {e}")
            return None

    def _prepare_trends_input(
        self, symbol: str, filing_analyses: Dict[str, List[SECFilingAnalysisResult]]
    ) -> str:
        """
        Prepare the input text for trends analysis.

        This function formats the individual filing analyses into a structured
        input for the AI model to perform trends analysis.

        Args:
            symbol: Company ticker symbol
            filing_analyses: Dictionary mapping filing types to lists of analysis results

        Returns:
            Formatted input text for the AI model
        """
        input_parts = [MULTI_PERIOD_ANALYSIS_PROMPT, f"\n\nCompany: {symbol}\n\n"]

        # Add 10-K filings first (usually more comprehensive)
        if "10-K" in filing_analyses and filing_analyses["10-K"]:
            input_parts.append("## 10-K Filings\n\n")
            for analysis in sorted(
                filing_analyses["10-K"],
                key=lambda x: x.filing.filing_date,
                reverse=True,
            ):
                input_parts.append(
                    f"### 10-K Filing Date: {analysis.filing.filing_date.isoformat()}\n\n"
                )
                input_parts.append(f"Summary: {analysis.summary}\n\n")
                for section, content in analysis.analysis.items():
                    input_parts.append(f"#### {section}\n{content}\n\n")

        # Add 10-Q filings
        if "10-Q" in filing_analyses and filing_analyses["10-Q"]:
            input_parts.append("## 10-Q Filings\n\n")
            for analysis in sorted(
                filing_analyses["10-Q"],
                key=lambda x: x.filing.filing_date,
                reverse=True,
            ):
                input_parts.append(
                    f"### 10-Q Filing Date: {analysis.filing.filing_date.isoformat()}\n\n"
                )
                input_parts.append(f"Summary: {analysis.summary}\n\n")
                for section, content in analysis.analysis.items():
                    input_parts.append(f"#### {section}\n{content}\n\n")

        input_parts.append(
            "\nBased on the above filing analyses, please provide a comprehensive multi-period analysis that identifies trends, changes, and notable developments across these filings."
        )

        return "".join(input_parts)

    def _parse_trends_sections(self, analysis_text: str) -> Dict[str, Any]:
        """
        Parse the AI model's response into structured sections.

        This function extracts the different sections from the AI's
        trends analysis text and organizes them into a structured dictionary.

        Args:
            analysis_text: Raw text response from the AI model

        Returns:
            Dictionary with structured trends analysis sections
        """
        sections = {}
        current_section = None
        current_subsection = None
        current_content = []

        # Parse sections - handle markdown headers (# and ##)
        for line in analysis_text.split("\n"):
            # Check if this line is a main section header (# Header)
            if line.startswith("# "):
                # If we were already building a section, save it
                if current_section and current_content:
                    if current_subsection:
                        if current_section not in sections:
                            sections[current_section] = {}
                        sections[current_section][current_subsection] = "\n".join(
                            current_content
                        ).strip()
                        current_subsection = None
                    else:
                        sections[current_section] = "\n".join(current_content).strip()

                # Start a new main section
                current_section = line.replace("#", "").strip()
                current_subsection = None
                current_content = []

            # Check if this line is a subsection header (## Header)
            elif line.startswith("## ") and current_section:
                # If we were already building a subsection, save it
                if current_subsection and current_content:
                    if current_section not in sections:
                        sections[current_section] = {}
                    sections[current_section][current_subsection] = "\n".join(
                        current_content
                    ).strip()

                # Start a new subsection
                current_subsection = line.replace("#", "").strip()
                current_content = []

            # Otherwise, add the line to the current content
            elif current_section:
                current_content.append(line)

        # Save the last section/subsection
        if current_section and current_content:
            if current_subsection:
                if current_section not in sections:
                    sections[current_section] = {}
                sections[current_section][current_subsection] = "\n".join(
                    current_content
                ).strip()
            else:
                sections[current_section] = "\n".join(current_content).strip()

        return sections

    def _get_cache_path(self, symbol: str) -> Path:
        """
        Generate a cache file path for trends analysis results.

        Creates a unique file path for caching the trends analysis of a company
        based on its symbol.

        Args:
            symbol: Company ticker symbol

        Returns:
            Path object for the cache file location
        """
        # Create a unique filename based on the symbol
        filename = f"{symbol}_trends_analysis.json"

        # Sanitize filename to remove any invalid characters
        filename = "".join(c for c in filename if c.isalnum() or c in "._-")

        return self.cache_dir / filename


# Create a singleton instance of the trends analyzer
sec_trends_analyzer = SECTrendsAnalyzer()
