# SEC Filing Analysis

## Overview

The SEC Filing Analysis feature provides AI-powered analysis of complete SEC filings (10-K, 10-Q, 8-K) for any publicly traded company. This feature leverages advanced AI models to analyze entire PDF documents directly, ensuring comprehensive financial analysis with no information loss.

## Key Features

- **Complete Document Analysis**: Processes entire SEC filings as PDFs, ensuring no information is lost
- **Direct PDF Processing**: Sends the complete PDF directly to AI models without text extraction
- **AI-Powered Insights**: Uses GPT-4 Vision to extract meaningful insights from complex financial documents
- **Structured Results**: Organizes analysis into consistent sections for easy consumption
- **Caching System**: Efficiently stores both downloaded filings and analysis results

## Architecture

The SEC Filing Analysis feature consists of three main components:

1. **SEC Filing Fetcher (`sec_fetcher.py`)**: 
   - Downloads complete SEC filings as PDFs
   - Handles API rate limits and retries
   - Implements caching to avoid redundant downloads

2. **SEC Filing Analyzer (`sec_analyzer.py`)**: 
   - Sends complete PDF documents directly to AI models
   - Uses OpenAI's Files API for efficient PDF handling
   - Parses AI responses into structured formats
   - Caches analysis results for efficiency

3. **SEC Analysis API Endpoints (`sec_analysis.py`)**: 
   - Provides REST API endpoints for accessing SEC filing analysis
   - Supports analyzing latest filings or specific filings by ID
   - Handles error cases and provides appropriate responses

## API Endpoints

### Analyze Latest Filing

```
GET /api/v1/sec/{symbol}/analyze
```

Analyzes the latest SEC filing of a specified type for a company.

**Parameters:**
- `symbol` (path): Stock ticker symbol (e.g., AAPL, MSFT)
- `filing_type` (query, optional): Type of SEC filing to analyze (default: 10-K)
- `limit` (query, optional): Number of filings to retrieve (default: 1)

### Analyze Specific Filing

```
GET /api/v1/sec/{symbol}/analyze/{filing_id}
```

Analyzes a specific SEC filing by its ID.

**Parameters:**
- `symbol` (path): Stock ticker symbol (e.g., AAPL, MSFT)
- `filing_id` (path): Unique identifier for the specific filing

## Analysis Content

The analysis includes:

- **Executive Summary**: Concise overview of the filing's key points
- **Key Financial Metrics**: Extraction and analysis of important financial data
- **Business Segments**: Breakdown of company's business units and their performance
- **Risk Factors**: Identification of top risks mentioned in the filing
- **Management Discussion**: Summary of management's commentary
- **Notable Changes**: Significant changes in operations, strategy, or financial position
- **Red Flags**: Concerning issues that investors should be aware of
- **Future Outlook**: Company's outlook based on the filing

## Implementation Details

### PDF Processing

The system uses an efficient two-tier approach for PDF analysis:
1. **Primary Method**: OpenAI Files API
   - Uploads the PDF file once and references it by ID
   - More efficient for large documents
   - Avoids size limitations of base64 encoding
   - Supports up to 100 pages and 32MB per file

2. **Fallback Method**: Base64 Encoding
   - Used if the Files API approach fails
   - Encodes the PDF directly in the API request
   - Works well for smaller documents

### AI Models

The system uses advanced AI models with PDF processing capabilities:
- **OpenAI GPT-4o/GPT-4 Vision**: Primary models for direct PDF analysis
- **File ID Caching**: Stores file IDs to avoid redundant uploads

### Caching

Three levels of caching are implemented:
1. **Filing Cache**: Stores downloaded PDF files
2. **File ID Cache**: Stores OpenAI file IDs to avoid redundant uploads
3. **Analysis Cache**: Stores completed analyses to avoid redundant processing

## Configuration

The following settings can be configured in `config.py`:

- `SEC_FILING_CACHE_DIR`: Directory to store downloaded filings
- `SEC_ANALYSIS_CACHE_DIR`: Directory to store analysis results
- `SEC_FILING_MAX_RETRIES`: Maximum number of retries for SEC API requests
- `SEC_FILING_RETRY_DELAY`: Delay between retries in seconds
- `SEC_ANALYSIS_MODEL`: AI model for SEC filing analysis
- `SEC_ANALYSIS_MAX_TOKENS`: Maximum tokens for AI analysis response
- `SEC_ANALYSIS_PDF_DETAIL`: Detail level for PDF analysis (high/low)

## Dependencies

- `sec-api`: For accessing SEC filings
- `openai>=1.3.0`: For GPT-4 Vision API access with PDF support
- `anthropic`: For Claude API access (optional)
- `aiohttp`: For async HTTP requests

## Example Usage

```python
import requests

# Analyze the latest 10-K filing for Apple
response = requests.get(
    "http://localhost:8000/api/v1/sec/AAPL/analyze",
    params={"filing_type": "10-K"}
)

# Print the executive summary
data = response.json()
print(data["summary"])

# Access specific analysis sections
print(data["analysis"]["KEY FINANCIAL METRICS"])
``` 