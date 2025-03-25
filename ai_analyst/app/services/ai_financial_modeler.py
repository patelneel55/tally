"""
AI-Driven Financial Modeler
-------------------------

This module provides AI-driven financial modeling capabilities, leveraging LLMs
to build comprehensive financial models from SEC filings and market data.

What this file does:
1. Uses AI to analyze financial data and create projections
2. Generates complete financial models with forecasted statements
3. Builds DCF models and other valuation approaches
4. Handles company-specific accounting policies and nuances
5. Explains model assumptions and rationale

How it fits in the architecture:
- Consumes data from financial_data_aggregator
- Acts as the core modeling engine for the system
- Provides AI-generated financial models for API endpoints
- Creates the foundation for investment analysis

Financial importance:
- Automates the traditionally manual process of financial modeling
- Incorporates qualitative factors from MD&A sections into quantitative models
- Provides consistent, scalable financial analysis across companies
- Handles accounting nuances and company-specific practices
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

from ai_analyst.app.core.config import settings
from ai_analyst.app.services.financial_data_aggregator import financial_data_aggregator

# Set up logging
logger = logging.getLogger(__name__)

# Prompts for AI-driven modeling
FINANCIAL_MODEL_PROMPT_TEMPLATE = """
You are an expert financial analyst specializing in building financial models based on SEC filings data.
I'm providing you with comprehensive financial data for {ticker}, including:

1. Historical financial statements (Income Statement, Balance Sheet, Cash Flow)
2. Accounting policies and footnotes
3. Time series data for key metrics

Based on this data, please create a comprehensive financial model with the following components:

1. Historical Analysis:
   - Calculate key financial ratios and metrics
   - Identify trends and patterns in historical performance
   - Note any accounting policy changes or one-time items

2. Assumptions Development:
   - Revenue growth projections
   - Margin forecasts (gross margin, operating margin, etc.)
   - Working capital assumptions
   - Capital expenditure forecasts
   - Tax rate assumptions

3. Financial Statement Projections (5 years):
   - Income Statement
   - Balance Sheet 
   - Cash Flow Statement

4. Valuation:
   - Discounted Cash Flow (DCF) analysis
   - Comparable company analysis (if applicable)
   - Key valuation metrics

5. Risk Factors:
   - Key sensitivities in the model
   - Potential accounting or financial reporting concerns
   - Business risks based on qualitative disclosures

Please provide detailed reasoning for each assumption and projection, explaining how you've accounted for
company-specific accounting policies, industry trends, and any other relevant factors.

Here is the financial data: {financial_data_summary}
"""

ACCOUNTING_POLICY_PROMPT = """
You are an expert in financial accounting and SEC filings analysis.
I'm providing you with accounting policies and footnotes for {ticker} from their SEC filings.

Please analyze these accounting policies and identify any:
1. Unusual or company-specific accounting treatments
2. Changes in accounting policies over time
3. Areas that require special attention in financial modeling
4. Potential red flags or areas of concern

Here are the accounting policies and footnotes: {accounting_policies}

Provide a concise analysis of how these accounting policies should inform our financial model,
including specific adjustments or considerations needed for accurate financial projection.
"""

class AIFinancialModeler:
    """
    AI-driven financial modeling service that uses LLMs to build
    comprehensive financial models from SEC filings and market data.
    """
    
    def __init__(self):
        """Initialize the AI financial modeler."""
        self.cache_dir = Path(settings.DATA_DIR) / "financial_models"
        os.makedirs(self.cache_dir, exist_ok=True)
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
    def build_financial_model(
        self,
        ticker: str,
        years_historical: int = 5,
        years_projection: int = 5,
        include_quarterly: bool = True,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Build a comprehensive financial model for a company using AI.
        
        Args:
            ticker: Company ticker symbol
            years_historical: Number of years of historical data to include
            years_projection: Number of years to project forward
            include_quarterly: Whether to include quarterly data in analysis
            force_refresh: Whether to force refresh the model
            
        Returns:
            Dictionary containing the financial model
        """
        cache_file = self.cache_dir / f"{ticker}_financial_model.json"
        
        # Check cache if not forcing refresh
        if not force_refresh and cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    cached_data = json.load(f)
                    
                # Check if cache is recent (within 7 days)
                cache_date = datetime.fromisoformat(cached_data.get("generated_at", "2000-01-01"))
                if (datetime.now() - cache_date).days < 7:
                    logger.info(f"Using cached financial model for {ticker}")
                    return cached_data
            except Exception as e:
                logger.warning(f"Error reading cached model: {e}")
        
        # 1. Gather comprehensive financial data
        logger.info(f"Gathering comprehensive financial data for {ticker}")
        financial_data = financial_data_aggregator.get_comprehensive_financial_data(
            ticker=ticker,
            years=years_historical,
            include_quarterly=include_quarterly
        )
        
        if not financial_data or not financial_data.get("annual_data"):
            raise ValueError(f"Insufficient financial data available for {ticker}")
        
        # 2. Process accounting policies
        logger.info(f"Analyzing accounting policies for {ticker}")
        accounting_analysis = self._analyze_accounting_policies(ticker, financial_data)
        
        # 3. Create a financial model with AI
        logger.info(f"Building AI-driven financial model for {ticker}")
        model = self._generate_model_with_ai(ticker, financial_data, accounting_analysis)
        
        # 4. Perform validation and sanity checks
        logger.info(f"Validating financial model for {ticker}")
        model = self._validate_model(model)
        
        # 5. Add metadata
        model["metadata"] = {
            "ticker": ticker,
            "generated_at": datetime.now().isoformat(),
            "years_historical": years_historical,
            "years_projection": years_projection,
            "model_version": "1.0"
        }
        
        # 6. Cache the results
        try:
            with open(cache_file, "w") as f:
                json.dump(model, f, indent=2, default=str)
            logger.info(f"Cached financial model for {ticker}")
        except Exception as e:
            logger.warning(f"Error caching financial model: {e}")
            
        return model
    
    def _analyze_accounting_policies(self, ticker: str, financial_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze accounting policies using AI to identify special considerations.
        
        Args:
            ticker: Company ticker symbol
            financial_data: Comprehensive financial data
            
        Returns:
            Dictionary with accounting policy analysis
        """
        try:
            # Extract accounting policies from the financial data
            accounting_policies = financial_data.get("accounting_policies", {})
            if not accounting_policies:
                logger.warning(f"No accounting policies found for {ticker}")
                return {}
            
            # Prepare accounting policies for AI analysis
            policies_text = json.dumps(accounting_policies, indent=2)
            
            # Prepare the prompt
            prompt = ACCOUNTING_POLICY_PROMPT.format(
                ticker=ticker,
                accounting_policies=policies_text
            )
            
            # Call the OpenAI API
            response = self.openai_client.chat.completions.create(
                model=settings.SEC_ANALYSIS_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert financial accounting analyst."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=2000
            )
            
            # Extract the analysis from the response
            analysis_text = response.choices[0].message.content.strip()
            
            # Structure the response
            analysis = {
                "accounting_policy_analysis": analysis_text,
                "special_considerations": self._extract_special_considerations(analysis_text),
                "original_policies": accounting_policies
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing accounting policies: {e}")
            return {"error": str(e)}
    
    def _extract_special_considerations(self, analysis_text: str) -> List[Dict[str, str]]:
        """
        Extract structured special considerations from accounting policy analysis.
        
        Args:
            analysis_text: The AI-generated analysis text
            
        Returns:
            List of special considerations
        """
        # In a more advanced implementation, we would parse the analysis text
        # to extract structured information about special considerations
        # For now, we'll use a simple approach
        
        considerations = []
        sections = analysis_text.split("\n\n")
        
        for section in sections:
            if ":" in section:
                try:
                    title, description = section.split(":", 1)
                    considerations.append({
                        "category": title.strip(),
                        "description": description.strip()
                    })
                except ValueError:
                    # Skip sections that don't fit the expected format
                    pass
        
        return considerations
    
    def _generate_model_with_ai(
        self, 
        ticker: str, 
        financial_data: Dict[str, Any],
        accounting_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a complete financial model using AI.
        
        Args:
            ticker: Company ticker symbol
            financial_data: Comprehensive financial data
            accounting_analysis: Accounting policy analysis
            
        Returns:
            Dictionary containing the financial model
        """
        try:
            # Create a summary of the financial data for the AI
            # We can't send the entire dataset due to token limits,
            # so we create a strategic summary
            financial_summary = self._create_financial_data_summary(financial_data)
            
            # Prepare the prompt
            prompt = FINANCIAL_MODEL_PROMPT_TEMPLATE.format(
                ticker=ticker,
                financial_data_summary=financial_summary
            )
            
            # Call the OpenAI API
            response = self.openai_client.chat.completions.create(
                model=settings.SEC_ANALYSIS_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert financial modeler with deep expertise in SEC filings analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=4000
            )
            
            # Extract the model from the response
            model_text = response.choices[0].message.content.strip()
            
            # Process the AI-generated model into structured data
            structured_model = self._process_ai_model_response(model_text, financial_data)
            
            # Add the accounting analysis
            structured_model["accounting_analysis"] = accounting_analysis
            
            return structured_model
            
        except Exception as e:
            logger.error(f"Error generating financial model: {e}")
            return {"error": str(e)}
    
    def _create_financial_data_summary(self, financial_data: Dict[str, Any]) -> str:
        """
        Create a strategic summary of financial data for the AI prompt.
        
        Args:
            financial_data: Comprehensive financial data
            
        Returns:
            String summary of key financial data
        """
        summary_parts = []
        
        # 1. Available data periods
        years_available = financial_data.get("metadata", {}).get("years_available", [])
        summary_parts.append(f"Years available: {', '.join(map(str, years_available))}")
        
        # 2. Key metrics from most recent year
        if financial_data.get("annual_data") and years_available:
            latest_year = max(years_available)
            latest_data = financial_data["annual_data"].get(str(latest_year), {})
            
            if "income_statement" in latest_data:
                metrics = latest_data["income_statement"].get("metrics", {})
                key_metrics = ["Revenue", "Operating Income", "Net Income"]
                
                summary_parts.append(f"\nKey metrics for {latest_year}:")
                for metric in key_metrics:
                    if metric in metrics:
                        periods = list(metrics[metric].keys())
                        if periods:
                            latest_period = max(periods)
                            value = metrics[metric][latest_period]
                            summary_parts.append(f"- {metric}: {value}")
        
        # 3. Time series data for key metrics
        if "time_series" in financial_data and "annual" in financial_data["time_series"]:
            time_series = financial_data["time_series"]["annual"]
            key_metrics = ["Revenue", "Net Income"]
            
            summary_parts.append("\nHistorical performance:")
            for metric in key_metrics:
                if metric in time_series:
                    values = time_series[metric]
                    series_str = ", ".join([f"{item['year']}: {item['value']}" for item in values])
                    summary_parts.append(f"- {metric} trend: {series_str}")
        
        # 4. Accounting policies summary
        if "accounting_policies" in financial_data and financial_data["accounting_policies"]:
            latest_year = max(financial_data["accounting_policies"].keys())
            policies = financial_data["accounting_policies"][latest_year]
            
            summary_parts.append("\nKey accounting policies:")
            for policy_name, policy in policies.items():
                if isinstance(policy, str):
                    # Truncate long policy descriptions
                    summary = policy[:200] + "..." if len(policy) > 200 else policy
                    summary_parts.append(f"- {policy_name}: {summary}")
        
        return "\n".join(summary_parts)
    
    def _process_ai_model_response(
        self, 
        model_text: str, 
        financial_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process the AI-generated model text into a structured model.
        
        Args:
            model_text: AI-generated model text
            financial_data: Original financial data
            
        Returns:
            Structured financial model
        """
        # In a production system, we would implement sophisticated parsing
        # to extract structured data from the AI response.
        # For this implementation, we'll use a simplified approach
        
        # Split the text into sections based on headings
        sections = {}
        current_section = "overview"
        section_content = []
        
        for line in model_text.split("\n"):
            if line.strip() and line.strip()[0] == "#":
                # Save the previous section if it exists
                if section_content:
                    sections[current_section] = "\n".join(section_content)
                    section_content = []
                
                # Extract the new section name
                current_section = line.strip().split("#", 1)[1].strip().lower().replace(" ", "_")
            else:
                section_content.append(line)
        
        # Save the last section
        if section_content:
            sections[current_section] = "\n".join(section_content)
        
        # Create a structured model based on the sections
        structured_model = {
            "overview": sections.get("overview", ""),
            "historical_analysis": sections.get("historical_analysis", ""),
            "assumptions": self._extract_assumptions(sections.get("assumptions_development", "")),
            "projections": self._extract_projections(sections.get("financial_statement_projections", "")),
            "valuation": self._extract_valuation(sections.get("valuation", "")),
            "risk_factors": self._extract_risk_factors(sections.get("risk_factors", "")),
            "raw_ai_response": model_text
        }
        
        return structured_model
    
    def _extract_assumptions(self, assumptions_text: str) -> Dict[str, Any]:
        """
        Extract structured assumptions from the AI-generated text.
        
        Args:
            assumptions_text: Text containing assumptions
            
        Returns:
            Dictionary of structured assumptions
        """
        # In a production system, this would be more sophisticated
        # For now, we'll do a simple extraction
        assumptions = {
            "revenue_growth": [],
            "margins": {},
            "working_capital": {},
            "capex": {},
            "tax_rate": None,
            "text": assumptions_text
        }
        
        # Look for revenue growth projections
        growth_lines = [line for line in assumptions_text.split("\n") 
                        if "revenue growth" in line.lower() and "%" in line]
        
        for line in growth_lines:
            # Try to extract percentage values
            percents = [float(p.strip(" %")) for p in line.split() if "%" in p]
            if percents:
                assumptions["revenue_growth"] = percents
        
        # Look for margin assumptions
        margin_types = ["gross margin", "operating margin", "profit margin", "ebitda margin"]
        for margin_type in margin_types:
            margin_lines = [line for line in assumptions_text.split("\n") 
                           if margin_type in line.lower() and "%" in line]
            
            for line in margin_lines:
                # Try to extract percentage values
                percents = [float(p.strip(" %")) for p in line.split() if "%" in p]
                if percents:
                    assumptions["margins"][margin_type] = percents[0] if len(percents) == 1 else percents
        
        # Look for tax rate
        tax_lines = [line for line in assumptions_text.split("\n") 
                    if "tax rate" in line.lower() and "%" in line]
        
        if tax_lines:
            # Try to extract percentage value
            percents = [float(p.strip(" %")) for p in tax_lines[0].split() if "%" in p]
            if percents:
                assumptions["tax_rate"] = percents[0]
        
        return assumptions
    
    def _extract_projections(self, projections_text: str) -> Dict[str, Any]:
        """
        Extract structured projections from the AI-generated text.
        
        Args:
            projections_text: Text containing projections
            
        Returns:
            Dictionary of structured projections
        """
        # For simplicity, we're just storing the raw text
        # In a production system, this would parse the projections into structured data
        return {
            "text": projections_text
        }
    
    def _extract_valuation(self, valuation_text: str) -> Dict[str, Any]:
        """
        Extract structured valuation from the AI-generated text.
        
        Args:
            valuation_text: Text containing valuation
            
        Returns:
            Dictionary of structured valuation
        """
        valuation = {
            "dcf_value": None,
            "target_price": None,
            "multiples": {},
            "text": valuation_text
        }
        
        # Look for DCF value
        dcf_lines = [line for line in valuation_text.split("\n") 
                     if "dcf value" in line.lower() or "dcf valuation" in line.lower()]
        
        for line in dcf_lines:
            # Try to extract dollar values
            import re
            dollar_values = re.findall(r'\$[\d,]+(?:\.\d+)?', line)
            if dollar_values:
                # Convert to float (remove $ and commas)
                try:
                    valuation["dcf_value"] = float(dollar_values[0].replace("$", "").replace(",", ""))
                except ValueError:
                    pass
        
        # Look for target price
        target_lines = [line for line in valuation_text.split("\n") 
                       if "target price" in line.lower() or "price target" in line.lower()]
        
        for line in target_lines:
            # Try to extract dollar values
            import re
            dollar_values = re.findall(r'\$[\d,]+(?:\.\d+)?', line)
            if dollar_values:
                # Convert to float (remove $ and commas)
                try:
                    valuation["target_price"] = float(dollar_values[0].replace("$", "").replace(",", ""))
                except ValueError:
                    pass
        
        return valuation
    
    def _extract_risk_factors(self, risk_text: str) -> List[Dict[str, str]]:
        """
        Extract structured risk factors from the AI-generated text.
        
        Args:
            risk_text: Text containing risk factors
            
        Returns:
            List of risk factors
        """
        risk_factors = []
        
        # Split by lines and look for list items
        lines = risk_text.split("\n")
        for line in lines:
            line = line.strip()
            if line and (line.startswith("- ") or line.startswith("* ")):
                risk_factor = line[2:].strip()
                if risk_factor:
                    risk_factors.append({"description": risk_factor})
        
        return risk_factors
    
    def _validate_model(self, model: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform validation and sanity checks on the financial model.
        
        Args:
            model: Financial model to validate
            
        Returns:
            Validated financial model
        """
        # In a production system, this would include comprehensive checks
        # For this implementation, we'll do minimal validation
        
        # Check that all required sections are present
        required_sections = ["historical_analysis", "assumptions", "projections", "valuation"]
        for section in required_sections:
            if section not in model:
                logger.warning(f"Financial model missing required section: {section}")
                model[section] = {}
        
        return model

# Create a singleton instance
ai_financial_modeler = AIFinancialModeler() 