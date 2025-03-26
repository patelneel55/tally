"""
SEC Filing Retrieval Tool

This module provides functionality to fetch SEC filings for companies using the SEC-API.io service.
It allows retrieving the latest filings for a given ticker and form type, with caching to minimize API usage.

What this file does:
1. Fetches SEC filing metadata via SEC-API.io
2. Caches results to avoid redundant API calls
3. Provides easy access to latest SEC filings for financial analysis
4. Downloads and saves PDF versions of filings using SEC-API PDF Generator
"""

import os
import json
import httpx
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.core.config import settings

# Configure logger
logger = logging.getLogger(__name__)


def get_sec_filing(ticker: str, form_type: str = "10-K") -> dict:
    """
    Fetch the latest SEC filing of specified type for a company.
    
    Args:
        ticker: Stock ticker symbol of the company (e.g., 'AAPL')
        form_type: SEC form type to retrieve (e.g., '10-K', '10-Q', '8-K')
        
    Returns:
        dict: On success, returns:
            {
                "ticker": ticker,
                "form_type": form_type,
                "filing_date": filing_date,
                "company_name": company_name,
                "cik": cik,
                "filing_text": filing_text,
                "pdf_path": path to the PDF file (if successful)
            }
            
            On failure, returns:
            {
                "ticker": ticker,
                "form_type": form_type,
                "error": "Error message with details",
                "filing_text": None,
                "pdf_path": None
            }
    """
    # Ensure the SEC filings directory exists
    os.makedirs("sec_data/filings", exist_ok=True)
    
    # Get API key from settings
    SEC_API_KEY = settings.SEC_API_KEY
    
    # Initialize error response structure
    error_response = {
        "ticker": ticker,
        "form_type": form_type,
        "error": "No filing found or unable to download",
        "filing_text": None,
        "pdf_path": None
    }
    
    try:
        # Construct the API endpoint URL
        url = "https://api.sec-api.io"
        
        # Prepare the query payload according to SEC API documentation
        payload = {
            "query": f'ticker:"{ticker}" AND formType:"{form_type}"',
            "from": "0",
            "size": "1",
            "sort": [{"filedAt": {"order": "desc"}}]
        }
        
        # Set up headers with authorization
        headers = {
            "Authorization": SEC_API_KEY,
            "Content-Type": "application/json"
        }
        
        # Make the HTTP POST request with JSON payload
        with httpx.Client() as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()  # Raise exception for 4XX/5XX responses
        
        # Parse the JSON response
        data = response.json()
        
        # Check if any filings were found
        if data.get("total", 0) == 0 or not data.get("filings"):
            error_response["error"] = f"No {form_type} filings found for {ticker}"
            return error_response
        
        # Extract the first (most recent) filing
        filing = data["filings"][0]
        
        # Get filing date and format it
        filing_date = filing.get("filedAt", "")
        formatted_date = filing_date.split("T")[0] if "T" in filing_date else filing_date
        filename_date = formatted_date.replace("-", "")
        
        # Create the filenames for caching
        txt_filename = f"sec_data/filings/{ticker}_{form_type}_{filename_date}.txt"
        pdf_filename = f"sec_data/filings/{ticker}_{form_type}_{filename_date}.pdf"
        
        # Initialize success response structure
        success_response = {
            "ticker": ticker,
            "form_type": form_type,
            "filing_date": formatted_date,
            "company_name": filing.get("companyName", ""),
            "cik": filing.get("cik", ""),
            "filing_text": None,
            "pdf_path": None
        }
        
        # Check if the text file already exists
        if os.path.exists(txt_filename):
            # Load the filing text from disk
            with open(txt_filename, "r", encoding="utf-8") as file:
                filing_text = file.read()
            success_response["filing_text"] = filing_text
            
            # Check if the PDF file exists
            if os.path.exists(pdf_filename):
                success_response["pdf_path"] = pdf_filename
                
            return success_response
            
        # Check if only the PDF file exists
        if os.path.exists(pdf_filename):
            success_response["pdf_path"] = pdf_filename
            success_response["filing_text"] = "PDF file available but text not extracted yet."
            return success_response
        
        # Get the filing URL - prefer linkToFiling but fallback to linkToTxt
        original_filing_url = filing.get("linkToFiling") or filing.get("linkToHtml") or filing.get("linkToTxt", "")
        if not original_filing_url:
            error_response["error"] = "No filing URL available"
            return error_response
        
        # First attempt to generate and download the PDF version
        pdf_generated = False
        pdf_api_url = (
            f"https://api.sec-api.io/filing-reader?"
            f"token={SEC_API_KEY}&"
            f"url={original_filing_url}"
        )
        
        try:
            logger.info(f"Downloading PDF via SEC-API PDF Generator: {pdf_api_url}")
            with httpx.Client() as client:
                pdf_response = client.get(pdf_api_url)
                if pdf_response.status_code == 200:
                    with open(pdf_filename, "wb") as f:
                        f.write(pdf_response.content)
                    success_response["pdf_path"] = pdf_filename
                    pdf_generated = True
                elif pdf_response.status_code == 202:
                    logger.warning("SEC-API PDF Generator returned 202 Accepted — PDF is being generated. Try again in a few seconds or fallback to text.")
                    # 202 means the request was accepted but processing is not complete
                    # We'll fall back to text mode for now
                else:
                    logger.warning(f"PDF download failed with status code: {pdf_response.status_code}. Falling back to text mode.")
        except Exception as e:
            logger.warning(f"PDF download failed. Falling back to text mode. Error: {str(e)}")
        
        # Download the text version of the filing if PDF generation failed or as a backup
        filing_url = filing.get("linkToTxt", "")
        if not filing_url:
            if pdf_generated:
                # If we have the PDF but no text URL, return what we have
                success_response["filing_text"] = "PDF file available but text not extracted yet."
                return success_response
            else:
                error_response["error"] = "No filing text URL available"
                return error_response
            
        try:
            # SEC requires a User-Agent header
            sec_headers = {
                "User-Agent": "AnalystAI research.bot@example.com",
                "Accept-Encoding": "gzip, deflate",
                "Host": "www.sec.gov"
            }
            
            with httpx.Client() as client:
                text_response = client.get(filing_url, headers=sec_headers)
                text_response.raise_for_status()
                filing_text = text_response.text
            
            # Save the filing text to disk
            with open(txt_filename, "w", encoding="utf-8") as file:
                file.write(filing_text)
            
            # Add the filing text to the result
            success_response["filing_text"] = filing_text
            return success_response
            
        except Exception as e:
            if pdf_generated:
                # If we have the PDF but text download failed, return what we have
                success_response["filing_text"] = "PDF file available but text download failed."
                return success_response
            else:
                error_response["error"] = f"Error downloading filing text: {str(e)}"
                return error_response
    
    except httpx.RequestError as e:
        error_response["error"] = f"Network error when fetching SEC filing: {str(e)}"
        return error_response
    
    except httpx.HTTPStatusError as e:
        error_response["error"] = f"HTTP error when fetching SEC filing: {e.response.status_code}"
        return error_response
    
    except KeyError as e:
        error_response["error"] = f"Missing expected data in SEC API response: {str(e)}"
        return error_response
    
    except Exception as e:
        error_response["error"] = f"Error fetching SEC filing: {str(e)}"
        return error_response 