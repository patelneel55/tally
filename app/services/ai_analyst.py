"""
AI-Driven Financial Analyst
-------------------------

This module provides comprehensive financial analysis capabilities, leveraging LLMs
to analyze financial data, generate investment recommendations, and provide
detailed qualitative and quantitative assessments of companies.

What this file does:
1. Uses AI to generate detailed financial analysis reports
2. Creates investment recommendations with supporting rationale
3. Provides qualitative assessment of business models and competitive positioning
4. Identifies key risks and opportunities
5. Generates executive summaries for decision makers

How it fits in the architecture:
- Builds on the financial_modeler and financial_data_aggregator modules
- Provides high-level insights based on detailed financial data
- Serves as the primary analysis engine for the system
- Delivers content for client-facing reports and dashboards

Financial importance:
- Automates the investment analysis process
- Identifies potential investment opportunities and risks
- Provides consistent analysis across companies
- Combines quantitative and qualitative factors for holistic assessment
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
import numpy as np
import pandas as pd
from openai import OpenAI

from app.core.config import settings
from app.services.financial_data_aggregator import financial_data_aggregator
from app.services.ai_financial_modeler import AIFinancialModeler

# Set up logging
logger = logging.getLogger(__name__)

# Prompts for AI-driven analysis
INVESTMENT_ANALYSIS_PROMPT = """
You are a senior investment analyst at a top-tier investment bank. 
I'm providing you with comprehensive financial data and a financial model for {ticker}.

Based on this information, please provide a detailed investment analysis with the following components:

1. Executive Summary:
   - Brief overview of the company
   - Key financial highlights with SPECIFIC NUMERICAL VALUES (e.g., "Revenue: $394.33B in FY2022")
   - Investment recommendation (Strong Buy, Buy, Hold, Sell, Strong Sell) with specific price target in dollars
   - Primary investment thesis in 2-3 sentences

2. Financial Performance Analysis:
   - Analysis of recent financial performance using EXACT FIGURES from the data provided
   - Calculate and present key financial ratios with actual values
   - Show specific trends in revenue, profitability, and cash flow with year-over-year growth rates
   - Analyze capital structure with debt-to-equity ratios and actual balance sheet figures

3. Valuation Analysis:
   - DCF valuation with specific growth rate assumptions and resulting price target
   - Comparable company analysis with ACTUAL P/E, EV/EBITDA, and other relevant multiples
   - Discussion of valuation multiples compared to peers with numerical comparisons
   - Justification for price target using specific calculations

4. Growth Opportunities:
   - Analysis of growth vectors and market opportunities
   - Product/service innovation potential
   - Market expansion possibilities with projected growth rates
   - M&A outlook

5. Risk Assessment:
   - Business model risks
   - Competitive threats
   - Regulatory challenges
   - Financial and accounting risks with specific metrics that cause concern
   - Macro factors that could impact performance

6. Conclusion:
   - Recap of investment thesis with key numerical support
   - Specific factors that could change the recommendation
   - Timeline for expected thesis to play out

IMPORTANT: Base ALL your analysis on the ACTUAL NUMERICAL DATA provided. Include SPECIFIC FINANCIAL FIGURES throughout your analysis. Do NOT make up any numbers. Your analysis should reference the exact figures from the provided financial data, including year-over-year comparisons, growth rates, margins, and key financial metrics. Include a financial data table in each section with the relevant numerical data.

Here is the financial data and model: {financial_data_and_model_summary}
"""

EXECUTIVE_SUMMARY_PROMPT = """
You are the Chief Investment Officer at a major asset management firm.
I'm providing you with a detailed investment analysis for {ticker}.

Please write a concise executive summary (500-700 words) that would be suitable for sophisticated investors and portfolio managers.
The summary should:

1. Clearly state the investment recommendation and rationale
2. Highlight the most important financial metrics and trends with SPECIFIC NUMERICAL VALUES (e.g., "Revenue grew 5.2% to $394.33B")
3. Include actual figures for key metrics like revenue, operating margin, EPS, etc.
4. Summarize key risks and opportunities
5. Provide a valuation perspective with a specific price target in dollars
6. Indicate critical factors to monitor going forward

The tone should be professional, balanced, and evidence-based. Focus on the most material information that would drive an investment decision.

IMPORTANT: Base your summary on ACTUAL FINANCIAL FIGURES from the data. Include SPECIFIC NUMBERS throughout your summary. Do not use vague statements like "strong revenue growth" - instead use "revenue growth of X%" with the actual percentage.

Here is the detailed analysis: {detailed_analysis}
"""

COMPETITIVE_ANALYSIS_PROMPT = """
You are a strategic management consultant specializing in competitive analysis.
I'm providing you with financial data and analysis for {ticker}.

Please create a detailed competitive positioning analysis that covers:

1. Industry Structure:
   - Key players and market shares
   - Industry concentration and dynamics
   - Barriers to entry and competitive intensity

2. Competitive Advantages:
   - Core competitive advantages of {ticker}
   - Sustainability of these advantages
   - Areas of competitive weakness

3. Peer Comparison:
   - Relative financial performance vs. peers
   - Operational efficiency comparison
   - Growth trajectory differences

4. Strategic Positioning:
   - Product/market positioning
   - Pricing power and margin potential
   - Technology and innovation positioning

5. Future Competitive Landscape:
   - Emerging competitive threats
   - Potential industry disruption
   - How {ticker} is positioned for future industry evolution

Base your analysis on the financial data provided, industry knowledge, and logical inferences from the company's financial performance.

Here is the financial data and analysis: {financial_and_competitor_data}
"""

class AIAnalyst:
    """
    AI-driven financial analyst service that uses LLMs to generate
    comprehensive investment analysis and recommendations.
    """
    
    def __init__(self):
        """Initialize the AI analyst."""
        self.cache_dir = Path(settings.DATA_DIR) / "financial_analysis"
        os.makedirs(self.cache_dir, exist_ok=True)
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.financial_modeler = AIFinancialModeler()
        
    def generate_investment_analysis(
        self,
        ticker: str,
        years_historical: int = 5,
        include_peers: bool = True,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive investment analysis for a company.
        
        Args:
            ticker: Company ticker symbol
            years_historical: Number of years of historical data to include
            include_peers: Whether to include peer comparison
            force_refresh: Whether to force refresh the analysis
            
        Returns:
            Dictionary containing the investment analysis
        """
        cache_file = self.cache_dir / f"{ticker}_investment_analysis.json"
        
        # Check cache if not forcing refresh
        if not force_refresh and cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    cached_data = json.load(f)
                    
                # Check if cache is recent (within 3 days)
                cache_date = datetime.fromisoformat(cached_data.get("generated_at", "2000-01-01"))
                if (datetime.now() - cache_date).days < 3:
                    logger.info(f"Using cached investment analysis for {ticker}")
                    return cached_data
            except Exception as e:
                logger.warning(f"Error reading cached analysis: {e}")
        
        # 1. Build financial model
        logger.info(f"Building financial model for {ticker}")
        financial_model = self.financial_modeler.build_financial_model(
            ticker=ticker,
            years_historical=years_historical,
            force_refresh=force_refresh
        )
        
        if not financial_model:
            raise ValueError(f"Failed to build financial model for {ticker}")
        
        # 2. Fetch peer data if requested
        peer_data = {}
        if include_peers:
            logger.info(f"Gathering peer data for {ticker}")
            peer_data = self._gather_peer_data(ticker)
        
        # 3. Generate investment analysis
        logger.info(f"Generating investment analysis for {ticker}")
        analysis = self._generate_analysis_with_ai(ticker, financial_model, peer_data)
        
        # 4. Generate executive summary
        logger.info(f"Creating executive summary for {ticker}")
        executive_summary = self._generate_executive_summary(ticker, analysis)
        analysis["executive_summary"] = executive_summary
        
        # 5. Generate competitive analysis if peers included
        if include_peers and peer_data:
            logger.info(f"Creating competitive analysis for {ticker}")
            competitive_analysis = self._generate_competitive_analysis(ticker, analysis, peer_data)
            analysis["competitive_analysis"] = competitive_analysis
        
        # 6. Add metadata
        analysis["metadata"] = {
            "ticker": ticker,
            "generated_at": datetime.now().isoformat(),
            "years_historical": years_historical,
            "model_version": "1.0"
        }
        
        # 7. Cache the results
        try:
            with open(cache_file, "w") as f:
                json.dump(analysis, f, indent=2, default=str)
            logger.info(f"Cached investment analysis for {ticker}")
        except Exception as e:
            logger.warning(f"Error caching investment analysis: {e}")
            
        return analysis
    
    def _gather_peer_data(self, ticker: str) -> Dict[str, Any]:
        """
        Gather financial data for peers of the specified company.
        
        Args:
            ticker: Company ticker symbol
            
        Returns:
            Dictionary with peer financial data
        """
        try:
            # This would normally query a database or service to get peer companies
            # For now we'll use a simplified approach with predefined peers
            
            peer_map = {
                "AAPL": ["MSFT", "GOOGL", "AMZN", "META"],
                "MSFT": ["AAPL", "GOOGL", "AMZN", "ORCL"],
                "GOOGL": ["MSFT", "META", "AMZN", "AAPL"],
                "AMZN": ["MSFT", "GOOGL", "AAPL", "WMT"],
                "META": ["GOOGL", "SNAP", "PINS", "TWTR"],
                # Add more mappings as needed
            }
            
            peers = peer_map.get(ticker, [])
            
            if not peers:
                logger.warning(f"No peers defined for {ticker}")
                return {}
            
            # Limit to top 3 peers to avoid excessive API calls
            peers = peers[:3]
            logger.info(f"Gathering data for peers of {ticker}: {', '.join(peers)}")
            
            peer_data = {}
            for peer in peers:
                try:
                    # Get financial data for peer
                    peer_financial_data = financial_data_aggregator.get_comprehensive_financial_data(
                        ticker=peer,
                        years=3,  # Limit to 3 years for peers
                        include_quarterly=False
                    )
                    
                    if peer_financial_data:
                        # Extract key metrics for comparison
                        peer_data[peer] = self._extract_peer_metrics(peer_financial_data)
                except Exception as e:
                    logger.warning(f"Error gathering data for peer {peer}: {e}")
            
            return {
                "peers": list(peer_data.keys()),
                "peer_data": peer_data
            }
            
        except Exception as e:
            logger.error(f"Error gathering peer data: {e}")
            return {}
    
    def _extract_peer_metrics(self, financial_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract key metrics from peer financial data for comparison.
        
        Args:
            financial_data: Comprehensive financial data for a peer
            
        Returns:
            Dictionary with key metrics
        """
        metrics = {}
        
        try:
            # Use time series data if available
            if "time_series" in financial_data and "annual" in financial_data["time_series"]:
                annual_metrics = financial_data["time_series"]["annual"]
                
                # Helper function to get latest value
                def get_latest_value(metric_name):
                    if metric_name in annual_metrics and annual_metrics[metric_name]:
                        for item in annual_metrics[metric_name]:
                            if "value" in item:
                                return item["value"]
                    return None
                
                # Extract key metrics
                metrics["revenue"] = get_latest_value("revenues")
                metrics["operating_income"] = get_latest_value("operating_income")
                metrics["net_income"] = get_latest_value("net_income")
                metrics["total_assets"] = get_latest_value("total_assets")
                metrics["total_liabilities"] = get_latest_value("total_liabilities")
                metrics["total_equity"] = get_latest_value("total_equity")
                
                # Calculate ratios
                if metrics["revenue"] and metrics["net_income"]:
                    metrics["net_margin"] = metrics["net_income"] / metrics["revenue"]
                    
                if metrics["total_assets"] and metrics["net_income"]:
                    metrics["roa"] = metrics["net_income"] / metrics["total_assets"]
                    
                if metrics["total_equity"] and metrics["net_income"]:
                    metrics["roe"] = metrics["net_income"] / metrics["total_equity"]
                    
                # Get time series data for growth calculations
                if "revenues" in annual_metrics and len(annual_metrics["revenues"]) >= 2:
                    # Calculate 1-year revenue growth
                    current = annual_metrics["revenues"][0]["value"]
                    previous = annual_metrics["revenues"][1]["value"]
                    
                    if previous and previous != 0:
                        metrics["revenue_growth"] = (current - previous) / previous
            
            return metrics
            
        except Exception as e:
            logger.warning(f"Error extracting peer metrics: {e}")
            return metrics
    
    def _generate_analysis_with_ai(
        self, 
        ticker: str, 
        financial_model: Dict[str, Any],
        peer_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate investment analysis using AI.
        
        Args:
            ticker: Company ticker symbol
            financial_model: Financial model data
            peer_data: Peer company data
            
        Returns:
            Dictionary with investment analysis
        """
        try:
            # Prepare the data summary for the AI prompt
            data_summary = self._create_data_summary(ticker, financial_model, peer_data)
            
            # Prepare the prompt
            prompt = INVESTMENT_ANALYSIS_PROMPT.format(
                ticker=ticker,
                financial_data_and_model_summary=data_summary
            )
            
            # Call the OpenAI API
            response = self.openai_client.chat.completions.create(
                model=settings.FINANCIAL_ANALYSIS_MODEL,
                messages=[
                    {"role": "system", "content": "You are a senior investment analyst at a top-tier investment bank."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=4000
            )
            
            # Extract the analysis from the response
            analysis_text = response.choices[0].message.content.strip()
            
            # Process the AI response into structured format
            analysis = self._process_ai_analysis_response(analysis_text)
            
            # Add the raw response
            analysis["raw_analysis"] = analysis_text
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error generating investment analysis: {e}")
            return {"error": str(e)}
    
    def _create_data_summary(
        self, 
        ticker: str, 
        financial_model: Dict[str, Any],
        peer_data: Dict[str, Any]
    ) -> str:
        """
        Create a summary of financial data and model for the AI prompt.
        
        Args:
            ticker: Company ticker symbol
            financial_model: Financial model data
            peer_data: Peer company data
            
        Returns:
            String with data summary
        """
        summary = []
        
        try:
            # Get raw financial data directly from the financial_data_aggregator
            financial_data = financial_data_aggregator.get_comprehensive_financial_data(
                ticker=ticker,
                force_refresh=False
            )
            
            # Start with a clear section for raw financial data
            summary.append(f"# {ticker} RAW FINANCIAL DATA")
            
            # First, display a summary of key financial metrics from time series
            if financial_data and "time_series" in financial_data and "annual" in financial_data["time_series"]:
                summary.append("\n## Key Financial Metrics Summary")
                annual_metrics = financial_data["time_series"]["annual"]
                
                # Create a summary table of the most important metrics
                summary_table = ["| Metric | 2024 | 2023 | 2022 | 3-Year CAGR |"]
                summary_table.append("| --- | --- | --- | --- | --- |")
                
                # Helper function to extract values
                def get_metric_values(metric_name):
                    values = {}
                    if metric_name in annual_metrics and annual_metrics[metric_name]:
                        for item in annual_metrics[metric_name]:
                            if "year" in item and "value" in item:
                                values[item["year"]] = item["value"]
                    return values
                
                # Key metrics to display
                key_metrics = [
                    ("revenues", "Revenue (USD)"),
                    ("operating_income", "Operating Income (USD)"),
                    ("net_income", "Net Income (USD)"),
                    ("total_assets", "Total Assets (USD)"),
                    ("total_liabilities", "Total Liabilities (USD)"),
                    ("total_equity", "Total Equity (USD)"),
                    ("operating_cash_flow", "Operating Cash Flow (USD)"),
                    ("free_cash_flow", "Free Cash Flow (USD)")
                ]
                
                for metric_key, metric_name in key_metrics:
                    values = get_metric_values(metric_key)
                    if values and "2024" in values and "2022" in values:
                        row = f"| {metric_name} | "
                        
                        # Add values for each year
                        for year in ["2024", "2023", "2022"]:
                            if year in values:
                                row += f"{values[year]:,.2f} | "
                            else:
                                row += "N/A | "
                        
                        # Calculate 3-year CAGR if we have both start and end values
                        if "2024" in values and "2022" in values and values["2022"] != 0:
                            cagr = ((values["2024"] / values["2022"]) ** (1/2)) - 1
                            row += f"{cagr:.2%} |"
                        else:
                            row += "N/A |"
                        
                        summary_table.append(row)
                
                summary.append("\n".join(summary_table))
                
                # Add calculated key ratios
                summary.append("\n## Key Financial Ratios")
                ratio_table = ["| Ratio | 2024 | 2023 | 2022 |"]
                ratio_table.append("| --- | --- | --- | --- |")
                
                # Get values for ratio calculations
                revenue_values = get_metric_values("revenues")
                net_income_values = get_metric_values("net_income")
                operating_income_values = get_metric_values("operating_income")
                total_assets_values = get_metric_values("total_assets")
                total_equity_values = get_metric_values("total_equity")
                
                # Calculate and add profitability ratios
                for year in ["2024", "2023", "2022"]:
                    # Net Margin
                    if year not in revenue_values or year not in net_income_values or revenue_values[year] == 0:
                        continue
                        
                    net_margin = net_income_values[year] / revenue_values[year]
                    operating_margin = operating_income_values.get(year, 0) / revenue_values[year] if year in operating_income_values else 0
                    roa = net_income_values[year] / total_assets_values.get(year, 0) if year in total_assets_values and total_assets_values[year] != 0 else 0
                    roe = net_income_values[year] / total_equity_values.get(year, 0) if year in total_equity_values and total_equity_values[year] != 0 else 0
                    
                    # Add ratio rows
                    if "Net Margin" not in [row.split("|")[1].strip() for row in ratio_table]:
                        row = "| Net Margin | "
                        for y in ["2024", "2023", "2022"]:
                            if y == year:
                                row += f"{net_margin:.2%} | "
                            else:
                                row += "- | "
                        ratio_table.append(row)
                    
                    if "Operating Margin" not in [row.split("|")[1].strip() for row in ratio_table]:
                        row = "| Operating Margin | "
                        for y in ["2024", "2023", "2022"]:
                            if y == year:
                                row += f"{operating_margin:.2%} | "
                            else:
                                row += "- | "
                        ratio_table.append(row)
                    
                    if "Return on Assets" not in [row.split("|")[1].strip() for row in ratio_table]:
                        row = "| Return on Assets | "
                        for y in ["2024", "2023", "2022"]:
                            if y == year:
                                row += f"{roa:.2%} | "
                            else:
                                row += "- | "
                        ratio_table.append(row)
                    
                    if "Return on Equity" not in [row.split("|")[1].strip() for row in ratio_table]:
                        row = "| Return on Equity | "
                        for y in ["2024", "2023", "2022"]:
                            if y == year:
                                row += f"{roe:.2%} | "
                            else:
                                row += "- | "
                        ratio_table.append(row)
                
                summary.append("\n".join(ratio_table))
            
            # Add annual financial data in a clear tabular format
            if financial_data and "annual_data" in financial_data:
                annual_data = financial_data["annual_data"]
                years = sorted(annual_data.keys(), reverse=True)
                
                if years:
                    # Income Statement Data
                    summary.append("\n## Income Statement Data (in USD)")
                    
                    # Create a table header with years
                    income_table = ["| Metric | " + " | ".join(years) + " |"]
                    income_table.append("| --- | " + " | ".join(["---"] * len(years)) + " |")
                    
                    # Common income statement metrics to extract
                    income_metrics = [
                        ("revenues", "Revenue"),
                        ("gross_profit", "Gross Profit"),
                        ("operating_income_loss", "Operating Income"),
                        ("net_income_loss", "Net Income"),
                        ("basic_earnings_per_share", "EPS (Basic)"),
                        ("diluted_earnings_per_share", "EPS (Diluted)")
                    ]
                    
                    # Add each metric to the table
                    for metric_key, metric_name in income_metrics:
                        row = f"| {metric_name} | "
                        for year in years:
                            if year in annual_data and "income_statement" in annual_data[year]:
                                income_stmt = annual_data[year]["income_statement"]
                                if metric_key in income_stmt and "value" in income_stmt[metric_key]:
                                    value = income_stmt[metric_key]["value"]
                                    row += f"{value:,.2f} | "
                                else:
                                    row += "N/A | "
                            else:
                                row += "N/A | "
                        income_table.append(row)
                    
                    summary.append("\n".join(income_table))
                    
                    # Balance Sheet Data
                    summary.append("\n## Balance Sheet Data (in USD)")
                    
                    # Create a table header with years
                    balance_table = ["| Metric | " + " | ".join(years) + " |"]
                    balance_table.append("| --- | " + " | ".join(["---"] * len(years)) + " |")
                    
                    # Common balance sheet metrics to extract
                    balance_metrics = [
                        ("assets", "Total Assets"),
                        ("current_assets", "Current Assets"),
                        ("noncurrent_assets", "Non-Current Assets"),
                        ("liabilities", "Total Liabilities"),
                        ("current_liabilities", "Current Liabilities"),
                        ("noncurrent_liabilities", "Non-Current Liabilities"),
                        ("equity", "Total Equity")
                    ]
                    
                    # Add each metric to the table
                    for metric_key, metric_name in balance_metrics:
                        row = f"| {metric_name} | "
                        for year in years:
                            if year in annual_data and "balance_sheet" in annual_data[year]:
                                balance_sheet = annual_data[year]["balance_sheet"]
                                if metric_key in balance_sheet and "value" in balance_sheet[metric_key]:
                                    value = balance_sheet[metric_key]["value"]
                                    row += f"{value:,.2f} | "
                                else:
                                    row += "N/A | "
                            else:
                                row += "N/A | "
                        balance_table.append(row)
                    
                    summary.append("\n".join(balance_table))
                    
                    # Cash Flow Data
                    summary.append("\n## Cash Flow Data (in USD)")
                    
                    # Create a table header with years
                    cash_flow_table = ["| Metric | " + " | ".join(years) + " |"]
                    cash_flow_table.append("| --- | " + " | ".join(["---"] * len(years)) + " |")
                    
                    # Common cash flow metrics to extract
                    cash_flow_metrics = [
                        ("net_cash_flow_from_operating_activities", "Operating Cash Flow"),
                        ("net_cash_flow_from_investing_activities", "Investing Cash Flow"),
                        ("net_cash_flow_from_financing_activities", "Financing Cash Flow"),
                        ("net_change_in_cash", "Net Change in Cash")
                    ]
                    
                    # Add each metric to the table
                    for metric_key, metric_name in cash_flow_metrics:
                        row = f"| {metric_name} | "
                        for year in years:
                            if year in annual_data and "cash_flow_statement" in annual_data[year]:
                                cash_flow = annual_data[year]["cash_flow_statement"]
                                if metric_key in cash_flow and "value" in cash_flow[metric_key]:
                                    value = cash_flow[metric_key]["value"]
                                    row += f"{value:,.2f} | "
                                else:
                                    row += "N/A | "
                            else:
                                row += "N/A | "
                        cash_flow_table.append(row)
                    
                    summary.append("\n".join(cash_flow_table))
                    
                    # Calculate and add key financial ratios
                    summary.append("\n## Key Financial Ratios")
                    
                    # Create a table header with years
                    ratio_table = ["| Ratio | " + " | ".join(years) + " |"]
                    ratio_table.append("| --- | " + " | ".join(["---"] * len(years)) + " |")
                    
                    # Calculate common ratios
                    ratios = []
                    
                    # Profitability Ratios
                    for year in years:
                        if year in annual_data:
                            year_data = annual_data[year]
                            income_stmt = year_data.get("income_statement", {})
                            balance_sheet = year_data.get("balance_sheet", {})
                            
                            # Get necessary values
                            revenue = income_stmt.get("revenues", {}).get("value")
                            net_income = income_stmt.get("net_income_loss", {}).get("value")
                            operating_income = income_stmt.get("operating_income_loss", {}).get("value")
                            total_assets = balance_sheet.get("assets", {}).get("value")
                            total_equity = balance_sheet.get("equity", {}).get("value")
                            
                            # Calculate ratios
                            if revenue and revenue != 0:
                                if net_income:
                                    if "net_margin" not in ratios:
                                        ratios.append("net_margin")
                                    net_margin = net_income / revenue
                                    row = f"| Net Margin | "
                                    for y in years:
                                        if y == year:
                                            row += f"{net_margin:.2%} | "
                                        else:
                                            row += "- | "
                                
                                if operating_income:
                                    if "operating_margin" not in ratios:
                                        ratios.append("operating_margin")
                                    operating_margin = operating_income / revenue
                                    row = f"| Operating Margin | "
                                    for y in years:
                                        if y == year:
                                            row += f"{operating_margin:.2%} | "
                                        else:
                                            row += "- | "
                            
                            if total_assets and net_income:
                                if "roa" not in ratios:
                                    ratios.append("roa")
                                roa = net_income / total_assets
                                row = f"| Return on Assets | "
                                for y in years:
                                    if y == year:
                                        row += f"{roa:.2%} | "
                                    else:
                                        row += "- | "
                            
                            if total_equity and net_income:
                                if "roe" not in ratios:
                                    ratios.append("roe")
                                roe = net_income / total_equity
                                row = f"| Return on Equity | "
                                for y in years:
                                    if y == year:
                                        row += f"{roe:.2%} | "
                                    else:
                                        row += "- | "
            
            # Add time series data for key metrics
            if financial_data and "time_series" in financial_data:
                time_series = financial_data["time_series"]
                summary.append("\n## Time Series Data")
                
                # Process annual time series
                if "annual" in time_series:
                    summary.append("\n### Annual Time Series")
                    annual_metrics = time_series["annual"]
                    
                    for metric_name, values in annual_metrics.items():
                        if values:
                            summary.append(f"\n#### {metric_name.replace('_', ' ').title()}")
                            
                            # Create a table for time series data
                            ts_table = ["| Year | Value | YoY Change |"]
                            ts_table.append("| --- | --- | --- |")
                            
                            # Add each year's data
                            prev_value = None
                            for i, item in enumerate(values):
                                if "year" in item and "value" in item:
                                    year = item["year"]
                                    value = item["value"]
                                    
                                    if prev_value and prev_value != 0:
                                        yoy_change = (value - prev_value) / prev_value
                                        ts_table.append(f"| {year} | {value:,.2f} | {yoy_change:.2%} |")
                                    else:
                                        ts_table.append(f"| {year} | {value:,.2f} | - |")
                                    
                                    prev_value = value
                            
                            summary.append("\n".join(ts_table))
                
                # Process quarterly time series
                if "quarterly" in time_series:
                    summary.append("\n### Quarterly Time Series")
                    quarterly_metrics = time_series["quarterly"]
                    
                    for metric_name, values in quarterly_metrics.items():
                        if values:
                            summary.append(f"\n#### {metric_name.replace('_', ' ').title()}")
                            
                            # Create a table for time series data
                            ts_table = ["| Quarter | Value | QoQ Change | YoY Change |"]
                            ts_table.append("| --- | --- | --- | --- |")
                            
                            # Add each quarter's data
                            prev_value = None
                            yoy_value = None
                            for i, item in enumerate(values):
                                if "year" in item and "quarter" in item and "value" in item:
                                    year = item["year"]
                                    quarter = item["quarter"]
                                    value = item["value"]
                                    
                                    qoq_change = "-"
                                    if prev_value and prev_value != 0:
                                        qoq_change = f"{(value - prev_value) / prev_value:.2%}"
                                    
                                    yoy_change = "-"
                                    if len(values) > 4 and i + 4 < len(values) and "value" in values[i + 4]:
                                        yoy_comp = values[i + 4]["value"]
                                        if yoy_comp and yoy_comp != 0:
                                            yoy_change = f"{(value - yoy_comp) / yoy_comp:.2%}"
                                    
                                    ts_table.append(f"| Q{quarter} {year} | {value:,.2f} | {qoq_change} | {yoy_change} |")
                                    
                                    prev_value = value
                            
                            summary.append("\n".join(ts_table))
            
            # Now add the AI-generated financial model components
            summary.append("\n# AI-GENERATED FINANCIAL MODEL")
            
            # Add key financial metrics
            if "historical_analysis" in financial_model:
                historical = financial_model["historical_analysis"]
                
                # Revenue and growth
                if "revenue_trends" in historical:
                    summary.append("\n## Revenue Trends")
                    summary.append(json.dumps(historical["revenue_trends"], indent=2))
                
                # Profitability
                if "profitability_metrics" in historical:
                    summary.append("\n## Profitability Metrics")
                    summary.append(json.dumps(historical["profitability_metrics"], indent=2))
                
                # Balance sheet
                if "balance_sheet_metrics" in historical:
                    summary.append("\n## Balance Sheet Metrics")
                    summary.append(json.dumps(historical["balance_sheet_metrics"], indent=2))
            
            # Summary of projections
            if "projections" in financial_model:
                projections = financial_model["projections"]
                summary.append("\n## Financial Projections")
                summary.append(json.dumps(projections, indent=2))
            
            # Summary of valuation
            if "valuation" in financial_model:
                valuation = financial_model["valuation"]
                summary.append("\n## Valuation")
                summary.append(json.dumps(valuation, indent=2))
            
            # Summary of assumptions
            if "assumptions" in financial_model:
                assumptions = financial_model["assumptions"]
                summary.append("\n## Key Assumptions")
                summary.append(json.dumps(assumptions, indent=2))
            
            # Summary of risk factors
            if "risk_factors" in financial_model:
                risks = financial_model["risk_factors"]
                summary.append("\n## Risk Factors")
                summary.append(json.dumps(risks, indent=2))
            
            # Add peer data if available
            if peer_data and "peer_data" in peer_data:
                summary.append("\n# PEER COMPARISON")
                
                peers = peer_data.get("peers", [])
                peer_metrics = peer_data.get("peer_data", {})
                
                if peers and peer_metrics:
                    # Create a comparison table
                    peer_table = [f"| Metric | {ticker} | " + " | ".join(peers) + " |"]
                    peer_table.append("| --- | " + " | ".join(["---"] * (len(peers) + 1)) + " |")
                    
                    # Get the company's metrics
                    company_metrics = {}
                    if financial_data:
                        # Get revenue, income, and other metrics from time series
                        if "time_series" in financial_data and "annual" in financial_data["time_series"]:
                            annual_metrics = financial_data["time_series"]["annual"]
                            
                            # Get the latest values for each metric
                            if "revenues" in annual_metrics and annual_metrics["revenues"]:
                                company_metrics["revenue"] = annual_metrics["revenues"][0]["value"]
                            
                            if "operating_income" in annual_metrics and annual_metrics["operating_income"]:
                                company_metrics["operating_income"] = annual_metrics["operating_income"][0]["value"]
                            
                            if "net_income" in annual_metrics and annual_metrics["net_income"]:
                                company_metrics["net_income"] = annual_metrics["net_income"][0]["value"]
                            
                            if "total_assets" in annual_metrics and annual_metrics["total_assets"]:
                                company_metrics["total_assets"] = annual_metrics["total_assets"][0]["value"]
                            
                            if "total_liabilities" in annual_metrics and annual_metrics["total_liabilities"]:
                                company_metrics["total_liabilities"] = annual_metrics["total_liabilities"][0]["value"]
                            
                            if "total_equity" in annual_metrics and annual_metrics["total_equity"]:
                                company_metrics["total_equity"] = annual_metrics["total_equity"][0]["value"]
                            
                            # Calculate revenue growth if we have enough data
                            if "revenues" in annual_metrics and len(annual_metrics["revenues"]) >= 2:
                                current = annual_metrics["revenues"][0]["value"]
                                previous = annual_metrics["revenues"][1]["value"]
                                
                                if previous and previous != 0:
                                    company_metrics["revenue_growth"] = (current - previous) / previous
                        
                        # Calculate ratios
                        if "revenue" in company_metrics and "net_income" in company_metrics and company_metrics["revenue"]:
                            company_metrics["net_margin"] = company_metrics["net_income"] / company_metrics["revenue"]
                        
                        if "total_assets" in company_metrics and "net_income" in company_metrics and company_metrics["total_assets"]:
                            company_metrics["roa"] = company_metrics["net_income"] / company_metrics["total_assets"]
                        
                        if "total_equity" in company_metrics and "net_income" in company_metrics and company_metrics["total_equity"]:
                            company_metrics["roe"] = company_metrics["net_income"] / company_metrics["total_equity"]
                    
                    # Add rows for each metric
                    metric_names = {
                        "revenue": "Revenue (USD)",
                        "operating_income": "Operating Income (USD)",
                        "net_income": "Net Income (USD)",
                        "total_assets": "Total Assets (USD)",
                        "total_liabilities": "Total Liabilities (USD)",
                        "total_equity": "Total Equity (USD)",
                        "net_margin": "Net Margin (%)",
                        "roa": "Return on Assets (%)",
                        "roe": "Return on Equity (%)",
                        "revenue_growth": "Revenue Growth (%)"
                    }
                    
                    for metric, name in metric_names.items():
                        row = f"| {name} | "
                        
                        # Add the company's value
                        if metric in company_metrics:
                            value = company_metrics[metric]
                            if metric in ["net_margin", "roa", "roe", "revenue_growth"]:
                                row += f"{value:.2%} | " if value else "N/A | "
                            else:
                                row += f"{value:,.2f} | " if value else "N/A | "
                        else:
                            row += "N/A | "
                        
                        # Add each peer's value
                        for peer in peers:
                            if peer in peer_metrics and metric in peer_metrics[peer]:
                                value = peer_metrics[peer][metric]
                                if metric in ["net_margin", "roa", "roe", "revenue_growth"]:
                                    row += f"{value:.2%} | " if value else "N/A | "
                                else:
                                    row += f"{value:,.2f} | " if value else "N/A | "
                            else:
                                row += "N/A | "
                        
                        peer_table.append(row)
                    
                    summary.append("\n".join(peer_table))
                else:
                    summary.append(json.dumps(peer_data, indent=2))
            
            return "\n".join(summary)
            
        except Exception as e:
            logger.warning(f"Error creating data summary: {e}")
            return f"Error creating data summary: {e}"
    
    def _process_ai_analysis_response(self, analysis_text: str) -> Dict[str, Any]:
        """
        Process the AI analysis response into a structured format.
        
        Args:
            analysis_text: Raw analysis text from the AI
            
        Returns:
            Dictionary with structured analysis
        """
        analysis = {}
        
        try:
            # Extract sections based on headings
            sections = self._extract_sections(analysis_text)
            
            # Process each section
            if "Executive Summary" in sections:
                analysis["summary"] = sections["Executive Summary"]
                
                # Extract recommendation from summary
                recommendation = self._extract_recommendation(sections["Executive Summary"])
                if recommendation:
                    analysis["recommendation"] = recommendation
            
            if "Financial Performance Analysis" in sections:
                analysis["financial_performance"] = sections["Financial Performance Analysis"]
            
            if "Valuation Analysis" in sections:
                analysis["valuation_analysis"] = sections["Valuation Analysis"]
                
                # Extract price target
                price_target = self._extract_price_target(sections["Valuation Analysis"])
                if price_target:
                    analysis["price_target"] = price_target
            
            if "Growth Opportunities" in sections:
                analysis["growth_opportunities"] = sections["Growth Opportunities"]
            
            if "Risk Assessment" in sections:
                analysis["risk_assessment"] = sections["Risk Assessment"]
                
                # Extract key risks
                key_risks = self._extract_key_risks(sections["Risk Assessment"])
                if key_risks:
                    analysis["key_risks"] = key_risks
            
            if "Conclusion" in sections:
                analysis["conclusion"] = sections["Conclusion"]
            
            return analysis
            
        except Exception as e:
            logger.warning(f"Error processing AI analysis response: {e}")
            return {"error": str(e), "raw_text": analysis_text}
    
    def _extract_sections(self, text: str) -> Dict[str, str]:
        """
        Extract sections from the analysis text based on headings.
        
        Args:
            text: Raw analysis text
            
        Returns:
            Dictionary with sections
        """
        sections = {}
        lines = text.split("\n")
        
        current_section = None
        current_content = []
        
        for line in lines:
            # Check if line is a heading
            if line.startswith("# "):
                # Save previous section if exists
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                
                # Start new section
                current_section = line.replace("# ", "").strip()
                current_content = []
            
            # Handle secondary heading format
            elif line.startswith("## "):
                # Save previous section if exists
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                
                # Start new section
                current_section = line.replace("## ", "").strip()
                current_content = []
                
            # Check if line contains a section heading without markdown
            elif line and current_section is None and ":" in line and len(line) < 50:
                potential_heading = line.split(":")[0].strip()
                if potential_heading in ["Executive Summary", "Financial Performance Analysis", 
                                        "Valuation Analysis", "Growth Opportunities", 
                                        "Risk Assessment", "Conclusion"]:
                    current_section = potential_heading
                    content_part = line.split(":", 1)[1].strip()
                    if content_part:
                        current_content.append(content_part)
                else:
                    current_content.append(line)
            else:
                # Add to current section content
                current_content.append(line)
        
        # Add the last section
        if current_section:
            sections[current_section] = "\n".join(current_content).strip()
        
        return sections
    
    def _extract_recommendation(self, summary_text: str) -> Dict[str, Any]:
        """
        Extract investment recommendation from the summary text.
        
        Args:
            summary_text: Executive summary text
            
        Returns:
            Dictionary with recommendation details
        """
        recommendations = ["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"]
        recommendation = {}
        
        for rec in recommendations:
            if rec in summary_text:
                recommendation["rating"] = rec
                
                # Try to extract the context around the recommendation
                try:
                    sentences = summary_text.split(". ")
                    for sentence in sentences:
                        if rec in sentence:
                            recommendation["context"] = sentence.strip()
                            break
                except:
                    pass
                
                break
        
        return recommendation
    
    def _extract_price_target(self, valuation_text: str) -> Dict[str, Any]:
        """
        Extract price target from valuation analysis.
        
        Args:
            valuation_text: Valuation analysis text
            
        Returns:
            Dictionary with price target details
        """
        import re
        
        price_target = {}
        
        # Look for price target patterns
        target_patterns = [
            r"price target of \$([0-9]+\.?[0-9]*)",
            r"target price of \$([0-9]+\.?[0-9]*)",
            r"price target: \$([0-9]+\.?[0-9]*)",
            r"target: \$([0-9]+\.?[0-9]*)"
        ]
        
        for pattern in target_patterns:
            matches = re.findall(pattern, valuation_text, re.IGNORECASE)
            if matches:
                price_target["value"] = float(matches[0])
                
                # Try to extract the context around the price target
                try:
                    sentences = valuation_text.split(". ")
                    for sentence in sentences:
                        if f"${matches[0]}" in sentence:
                            price_target["context"] = sentence.strip()
                            break
                except:
                    pass
                
                break
        
        # Look for upside/downside
        if "value" in price_target:
            upside_pattern = r"([0-9]+\.?[0-9]*)% upside"
            downside_pattern = r"([0-9]+\.?[0-9]*)% downside"
            
            upside_matches = re.findall(upside_pattern, valuation_text, re.IGNORECASE)
            if upside_matches:
                price_target["upside"] = float(upside_matches[0])
            
            downside_matches = re.findall(downside_pattern, valuation_text, re.IGNORECASE)
            if downside_matches:
                price_target["downside"] = float(downside_matches[0])
        
        return price_target
    
    def _extract_key_risks(self, risk_text: str) -> List[Dict[str, str]]:
        """
        Extract key risks from risk assessment.
        
        Args:
            risk_text: Risk assessment text
            
        Returns:
            List of risk dictionaries
        """
        key_risks = []
        
        # Split by bullet points or numbered items
        lines = risk_text.split("\n")
        current_risk = None
        
        for line in lines:
            line = line.strip()
            
            # Check if line is a bullet point
            if line.startswith("- ") or line.startswith("* "):
                if current_risk:
                    key_risks.append(current_risk)
                
                current_risk = {
                    "description": line[2:].strip(),
                    "category": "Uncategorized"
                }
            
            # Check if line is a numbered item
            elif re.match(r"^[0-9]+\.", line):
                if current_risk:
                    key_risks.append(current_risk)
                
                current_risk = {
                    "description": re.sub(r"^[0-9]+\.\s*", "", line),
                    "category": "Uncategorized"
                }
            
            # Check if line is a risk category
            elif line.endswith(":") and len(line) < 50:
                current_category = line[:-1].strip()
            
            # Otherwise, append to current risk description
            elif current_risk and line:
                current_risk["description"] += " " + line
                
                # Try to determine risk category
                business_keywords = ["business model", "operations", "strategy", "market share"]
                financial_keywords = ["financial", "liquidity", "debt", "cash flow", "margin"]
                competitive_keywords = ["competition", "competitive", "rivals", "market position"]
                regulatory_keywords = ["regulation", "regulatory", "compliance", "legal"]
                
                description = current_risk["description"].lower()
                
                if any(keyword in description for keyword in business_keywords):
                    current_risk["category"] = "Business Risk"
                elif any(keyword in description for keyword in financial_keywords):
                    current_risk["category"] = "Financial Risk"
                elif any(keyword in description for keyword in competitive_keywords):
                    current_risk["category"] = "Competitive Risk"
                elif any(keyword in description for keyword in regulatory_keywords):
                    current_risk["category"] = "Regulatory Risk"
        
        # Add the last risk
        if current_risk:
            key_risks.append(current_risk)
        
        return key_risks
    
    def _generate_executive_summary(self, ticker: str, analysis: Dict[str, Any]) -> str:
        """
        Generate a concise executive summary using AI.
        
        Args:
            ticker: Company ticker symbol
            analysis: Full investment analysis
            
        Returns:
            Executive summary text
        """
        try:
            # Prepare data for the AI prompt
            detailed_analysis = json.dumps(analysis, indent=2)
            
            # Prepare the prompt
            prompt = EXECUTIVE_SUMMARY_PROMPT.format(
                ticker=ticker,
                detailed_analysis=detailed_analysis
            )
            
            # Call the OpenAI API
            response = self.openai_client.chat.completions.create(
                model=settings.FINANCIAL_ANALYSIS_MODEL,
                messages=[
                    {"role": "system", "content": "You are the Chief Investment Officer at a major asset management firm."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            # Extract the summary from the response
            summary_text = response.choices[0].message.content.strip()
            
            return summary_text
            
        except Exception as e:
            logger.error(f"Error generating executive summary: {e}")
            return f"Error generating executive summary: {e}"
    
    def _generate_competitive_analysis(
        self,
        ticker: str,
        analysis: Dict[str, Any],
        peer_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate competitive analysis using AI.
        
        Args:
            ticker: Company ticker symbol
            analysis: Full investment analysis
            peer_data: Peer company data
            
        Returns:
            Dictionary with competitive analysis
        """
        try:
            # Prepare data for the AI prompt
            financial_and_competitor_data = json.dumps({
                "company_analysis": analysis,
                "peer_data": peer_data
            }, indent=2)
            
            # Prepare the prompt
            prompt = COMPETITIVE_ANALYSIS_PROMPT.format(
                ticker=ticker,
                financial_and_competitor_data=financial_and_competitor_data
            )
            
            # Call the OpenAI API
            response = self.openai_client.chat.completions.create(
                model=settings.FINANCIAL_ANALYSIS_MODEL,
                messages=[
                    {"role": "system", "content": "You are a strategic management consultant specializing in competitive analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            # Extract the analysis from the response
            competitive_analysis_text = response.choices[0].message.content.strip()
            
            # Process the response into structured format
            competitive_analysis = self._extract_sections(competitive_analysis_text)
            
            # Add the raw response
            competitive_analysis["raw_analysis"] = competitive_analysis_text
            
            return competitive_analysis
            
        except Exception as e:
            logger.error(f"Error generating competitive analysis: {e}")
            return {"error": str(e)}

# Create a singleton instance
ai_analyst = AIAnalyst() 