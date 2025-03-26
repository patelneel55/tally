"""
SEC Filing Analyzer
------------------

This module processes SEC filings and analyzes them using AI models.
It extracts insights, summaries, and key information from complete
filing documents to provide comprehensive financial analysis.

What this file does:
1. Processes PDF filings to extract structured text
2. Sends the text to AI models (Claude/GPT-4) for analysis
3. Extracts key insights, risks, and financial information
4. Generates comprehensive summaries of the filings

How it fits in the architecture:
- Sits between the data acquisition layer (sec_fetcher) and the API layer
- Provides high-level analysis of SEC filings
- Leverages AI models to extract insights from unstructured text

Financial importance:
- Enables deep analysis of complete SEC filings, not just predefined sections
- Identifies risks, opportunities, and trends that might be missed in summary data
- Provides context and narrative understanding of financial information
"""

import os
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

import aiohttp
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
import base64
import tiktoken

from app.core.config import settings
from app.models.financial_statements import FilingType
from app.services.sec_fetcher import SECFiling, sec_fetcher
from tools.sec_preprocessor import extract_text_from_pdf

# Set up logging
logger = logging.getLogger(__name__)

# Analysis prompts for different filing types
ANALYSIS_PROMPTS = {
    FilingType.FORM_10K: """
    You are a financial analyst specializing in SEC filings analysis. 
    I'm providing you with the complete text of a 10-K annual report filing.
    
    Please analyze this filing and provide a comprehensive analysis with the following sections:
    
    1. EXECUTIVE SUMMARY: A brief overview of the company's performance and key highlights
    2. FINANCIAL METRICS: Key financial metrics and their trends
    3. RISK FACTORS: Major risks identified in the filing
    4. BUSINESS OPERATIONS: Overview of the company's business operations
    5. FUTURE OUTLOOK: The company's future plans and outlook
    
    Format your response with clear section headers using either:
    1. Markdown headers (# SECTION NAME), or
    2. ALL CAPS followed by a colon (SECTION NAME:)
    
    Be thorough but concise in your analysis.
    """,
    
    FilingType.FORM_10Q: """
    You are a financial analyst specializing in SEC filings analysis. 
    I'm providing you with the complete text of a 10-Q quarterly report filing.
    
    Please analyze this filing and provide a comprehensive analysis with the following sections:
    
    1. EXECUTIVE SUMMARY: A concise summary of the company's quarterly performance
    2. FINANCIAL METRICS: Key quarterly financial metrics and their trends
    3. QUARTERLY TRENDS: Notable trends compared to previous quarters
    4. RISK UPDATES: New or updated risk factors
    5. MANAGEMENT INSIGHTS: Key points from management's commentary
    6. FUTURE OUTLOOK: The company's outlook for upcoming quarters
    
    Format your response with clear section headers using either:
    1. Markdown headers (# SECTION NAME), or
    2. ALL CAPS followed by a colon (SECTION NAME:)
    
    Be thorough but concise in your analysis.
    """,
    
    FilingType.FORM_8K: """
    You are a financial analyst specializing in SEC filings analysis. 
    I'm providing you with the complete text of an 8-K current report filing.
    
    Please analyze this filing and provide a comprehensive analysis with the following sections:
    
    1. EVENT SUMMARY: A concise summary of the material event being reported
    2. FINANCIAL IMPACT: Potential financial implications of the event
    3. STRATEGIC IMPLICATIONS: How this event affects the company's strategy
    4. MARKET REACTION: Potential market reaction to this news
    5. FUTURE IMPLICATIONS: Long-term implications of this event
    
    Format your response with clear section headers using either:
    1. Markdown headers (# SECTION NAME), or
    2. ALL CAPS followed by a colon (SECTION NAME:)
    
    Be thorough but concise in your analysis.
    """,
    
    FilingType.OTHER: """
    You are a financial analyst specializing in SEC filings analysis. 
    I'm providing you with the complete text of an SEC filing.
    
    Please analyze this document thoroughly and provide:
    
    1. FILING SUMMARY: A concise 2-paragraph summary of the filing's purpose and key information.
    
    2. KEY POINTS: Extract and analyze the most important information contained in this filing.
    
    3. FINANCIAL IMPLICATIONS: If applicable, what are the financial implications of this filing for the company?
    
    4. STRATEGIC IMPLICATIONS: How might the information in this filing impact the company's strategy or operations?
    
    5. INVESTOR RELEVANCE: Why should investors care about this filing? What is its significance?
    
    Your analysis should be concise, insightful, and focused on information that would be most valuable to investors.
    """
}

class SECFilingAnalysisResult:
    """
    Container for SEC filing analysis results.
    
    This class stores the results of AI-powered analysis of SEC filings,
    including summaries, extracted metrics, and key insights.
    """
    
    def __init__(
        self,
        filing: SECFiling,
        summary: str,
        analysis: Dict[str, Any],
        analysis_date: datetime = None
    ):
        self.filing = filing
        self.summary = summary
        self.analysis = analysis
        self.analysis_date = analysis_date or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the analysis result to a dictionary."""
        return {
            "symbol": self.filing.symbol,
            "filing_type": self.filing.filing_type,
            "filing_date": self.filing.filing_date.isoformat(),
            "document_url": self.filing.document_url,
            "summary": self.summary,
            "analysis": self.analysis,
            "analysis_date": self.analysis_date.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], filing: SECFiling) -> 'SECFilingAnalysisResult':
        """Create an analysis result from a dictionary."""
        return cls(
            filing=filing,
            summary=data.get("summary", ""),
            analysis=data.get("analysis", {}),
            analysis_date=datetime.fromisoformat(data.get("analysis_date", datetime.now().isoformat()))
        )


class SECFilingAnalyzer:
    """
    Service for analyzing SEC filings using AI models.
    
    This class processes SEC filings and extracts insights using
    advanced AI models like Claude or GPT-4. It handles the entire
    pipeline from text extraction to AI analysis and result formatting.
    """
    
    def __init__(self):
        """
        Initialize the SEC filing analyzer with AI model clients.
        
        Sets up connections to AI models (Claude/GPT-4) and creates
        cache directories for storing analysis results.
        """
        # Initialize AI model clients
        self.anthropic_client = None
        self.openai_client = None
        
        if settings.OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("OpenAI client initialized for SEC filing analysis")
        
        # Create cache directory for storing analysis results
        self.cache_dir = Path("cache/sec_analysis")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    async def analyze_filing(self, filing: SECFiling) -> Optional[SECFilingAnalysisResult]:
        """
        Analyze a SEC filing using AI models.
        
        This function orchestrates the entire analysis process:
        1. Fetches the filing PDF
        2. Sends the complete PDF directly to an AI model for analysis
        3. Processes and structures the analysis results
        
        Args:
            filing: SECFiling object containing metadata about the filing
            
        Returns:
            SECFilingAnalysisResult object if successful, None otherwise
        """
        logger.info(f"Analyzing {filing.filing_type} filing for {filing.symbol} from {filing.filing_date}")
        
        # Check if we already have cached analysis
        cache_path = self._get_cache_path(filing)
        if cache_path.exists() and settings.ENABLE_CACHE:
            logger.info(f"Using cached analysis for {filing.symbol} {filing.filing_type} from {filing.filing_date}")
            try:
                with open(cache_path, 'r') as f:
                    analysis_data = json.load(f)
                return SECFilingAnalysisResult.from_dict(analysis_data, filing)
            except Exception as e:
                logger.error(f"Error loading cached analysis: {e}")
                # Continue with fresh analysis if cache loading fails
        
        try:
            # 1. If we don't have a PDF path, download the PDF
            pdf_path = None
            if filing.document_url:
                logger.info(f"Downloading SEC filing PDF for {filing.symbol} {filing.filing_type} from {filing.filing_date}")
                try:
                    pdf_path = await sec_fetcher.get_filing_pdf(filing)
                except Exception as e:
                    logger.error(f"Error downloading SEC filing PDF: {e}")
                    return SECFilingAnalysisResult(
                        filing=filing,
                        summary=f"Error: Failed to download SEC filing PDF. Please check logs for details.",
                        analysis={"ERROR": f"Failed to download SEC filing PDF: {str(e)}"}
                    )
            
            # Step 2: Analyze the filing directly using AI
            analysis_result = await self._analyze_with_ai(filing, pdf_path)
            if not analysis_result:
                logger.error(f"Failed to analyze filing for {filing.symbol} {filing.filing_type}")
                return SECFilingAnalysisResult(
                    filing=filing,
                    summary=f"Error: Failed to analyze SEC filing for {filing.symbol}",
                    analysis={"ERROR": "Analysis process failed. Please check logs for details."}
                )
            
            # Step 3: Cache the analysis result
            try:
                with open(cache_path, 'w') as f:
                    json.dump(analysis_result.to_dict(), f, indent=2)
                logger.info(f"Successfully cached analysis for {filing.symbol} {filing.filing_type}")
            except Exception as cache_error:
                logger.error(f"Error caching analysis: {cache_error}")
                # Continue even if caching fails
            
            logger.info(f"Successfully analyzed filing for {filing.symbol} {filing.filing_type}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error analyzing filing for {filing.symbol} {filing.filing_type}: {e}")
            return SECFilingAnalysisResult(
                filing=filing,
                summary=f"Error analyzing SEC filing: {str(e)}",
                analysis={"ERROR": f"An unexpected error occurred: {str(e)}"}
            )
    
    async def _analyze_with_ai(self, filing: SECFiling, pdf_path: Path) -> Optional[SECFilingAnalysisResult]:
        """
        Analyze filing using an AI model.
        
        This function sends the filing document URL to an AI model (Claude/GPT-4)
        for analysis and processes the response into a structured format.
        
        Args:
            filing: SECFiling object
            pdf_path: Path to the PDF file
            
        Returns:
            SECFilingAnalysisResult if successful, None otherwise
        """
        # Get the appropriate analysis prompt for this filing type
        prompt = ANALYSIS_PROMPTS.get(filing.filing_type, ANALYSIS_PROMPTS[FilingType.OTHER])
        
        try:
            # Check if OpenAI API key is properly configured
            if not self.openai_client:
                logger.error("OpenAI client not initialized. Check if OPENAI_API_KEY is properly set in .env file.")
                return None
                
            logger.info(f"Analyzing filing using OpenAI with model: {settings.SEC_ANALYSIS_MODEL}")
            return await self._analyze_with_openai_text(filing, prompt, pdf_path)
                
        except Exception as e:
            logger.error(f"Error during AI analysis: {e}")
            # Return a default analysis result with error information
            return SECFilingAnalysisResult(
                filing=filing,
                summary=f"Error analyzing SEC filing: {str(e)}",
                analysis={
                    "ERROR": f"Failed to analyze filing due to: {str(e)}. Please check API keys and configuration."
                }
            )
    
    async def _analyze_with_openai_text(self, filing: SECFiling, prompt: str, pdf_path: Path) -> Optional[SECFilingAnalysisResult]:
        """
        Analyze filing using OpenAI's GPT-4 model with plain text extraction.
        
        This method extracts text from the PDF and sends it directly to the API.
        
        Args:
            filing: SECFiling object
            prompt: Analysis prompt for the specific filing type
            pdf_path: Path to the PDF file
            
        Returns:
            SECFilingAnalysisResult if successful, None otherwise
        """
        try:
            logger.info(f"Reading text from filing: {pdf_path}")
            
            # Read text from file (treat as text file)
            try:
                filing_text = extract_text_from_pdf(pdf_path)
                with open(pdf_path, 'r', encoding='utf-8', errors='ignore') as f:
                    filing_text = f.read()
                
                # Truncate if too long
                max_chars = 32000  # Safe limit for context window
                if len(filing_text) > max_chars:
                    logger.warning(f"Filing text too long ({len(filing_text)} chars), truncating to {max_chars} chars")
                    filing_text = filing_text[:max_chars] + "\n\n[Content truncated due to length]"
                
                logger.info(f"Successfully read {len(filing_text)} chars from filing")
            except Exception as read_error:
                logger.error(f"Error reading text from filing: {read_error}")
                return SECFilingAnalysisResult(
                    filing=filing,
                    summary=f"Error reading SEC filing text: {str(read_error)}",
                    analysis={"ERROR": f"Failed to read filing text: {str(read_error)}"}
                )
            
            # Send to OpenAI API as normal text
            logger.info(f"Sending filing text to OpenAI API")
            logger.setLevel(logging.INFO)
            response = await self.openai_client.chat.completions.create(
                model=settings.SEC_ANALYSIS_MODEL,
                messages=[
                    {"role": "system", "content": "You are a financial analyst specializing in SEC filings analysis."},
                    {"role": "user", "content": f"{prompt}\n\n{filing_text}"}
                ],
                temperature=0.2,  # Low temperature for more factual responses
                max_tokens=settings.SEC_ANALYSIS_MAX_TOKENS
            )
            logger.setLevel(logging.INFO)
            
            analysis_text = response.choices[0].message.content
            logger.info(f"Received analysis response of length: {len(analysis_text)}")
            
            # Extract summary (first paragraph) and detailed analysis
            parts = analysis_text.split("\n\n", 1)
            summary = parts[0] if parts else ""
            
            # Parse the structured analysis sections
            analysis = self._parse_analysis_sections(analysis_text)
            
            # Validate that we have at least some analysis sections
            if not analysis:
                logger.warning("No analysis sections were parsed from the response")
                # Create a default section with the raw response
                analysis = {"RAW_RESPONSE": analysis_text}
            
            return SECFilingAnalysisResult(
                filing=filing,
                summary=summary,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Error analyzing with OpenAI text approach: {e}")
            # If all methods fail, return a default result with error information
            return SECFilingAnalysisResult(
                filing=filing,
                summary=f"Error analyzing SEC filing: {str(e)}",
                analysis={
                    "ERROR": f"Failed to analyze filing due to: {str(e)}. Please check API keys and configuration."
                }
            )
    
    def _parse_analysis_sections(self, analysis_text: str) -> Dict[str, Any]:
        """
        Parse the AI model's response into structured sections.
        
        This function extracts the different sections from the AI's
        analysis text and organizes them into a structured dictionary.
        
        Args:
            analysis_text: Raw text response from the AI model
            
        Returns:
            Dictionary with structured analysis sections
        """
        sections = {}
        current_section = None
        current_content = []
        
        # Parse sections - handle both # headers and ALL CAPS: headers
        for line in analysis_text.split('\n'):
            # Check if this line is a section header with # prefix
            if line.startswith('# '):
                # If we were already building a section, save it
                if current_section:
                    sections[current_section.replace('#', '').strip()] = '\n'.join(current_content).strip()
                
                # Start a new section
                current_section = line.strip()
                current_content = []
            # Check if this line is a section header (all caps with colon)
            elif ':' in line and line.split(':')[0].isupper() and len(line.split(':')[0]) > 3:
                # If we were already building a section, save it
                if current_section:
                    sections[current_section.replace('#', '').strip()] = '\n'.join(current_content).strip()
                
                # Start a new section
                parts = line.split(':', 1)
                current_section = parts[0].strip()
                current_content = [parts[1].strip()] if len(parts) > 1 and parts[1].strip() else []
            elif current_section:
                # Continue building the current section
                current_content.append(line)
        
        # Save the last section
        if current_section and current_content:
            sections[current_section.replace('#', '').strip()] = '\n'.join(current_content).strip()
        
        # Clean up section names (remove # and extra spaces)
        cleaned_sections = {}
        for section, content in sections.items():
            cleaned_section = section.replace('#', '').strip()
            cleaned_sections[cleaned_section] = content
        
        return cleaned_sections
    
    def _get_cache_path(self, filing: SECFiling) -> Path:
        """
        Generate a cache file path for analysis results.
        
        Creates a unique file path for caching the analysis of a filing
        based on its symbol, type, and date.
        
        Args:
            filing: SECFiling object
            
        Returns:
            Path object for the cache file location
        """
        # Create a unique filename based on filing metadata
        filename = f"{filing.symbol}_{filing.filing_type}_{filing.filing_date.isoformat()}_analysis.json"
        
        # Sanitize filename to remove any invalid characters
        filename = "".join(c for c in filename if c.isalnum() or c in "._-")
        
        return self.cache_dir / filename

# Create a singleton instance
sec_filing_analyzer = SECFilingAnalyzer() 