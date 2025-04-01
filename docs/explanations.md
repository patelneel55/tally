# Analyst AI - Code Explanations

This document provides detailed explanations of the Analyst AI codebase structure, functions, and best practices.

## 📁 File Structure

### Main Application Files

- **app/main.py**: Entry point for the FastAPI application
  - Sets up the web server, logging, middleware, and API routing
  - Handles cross-origin resource sharing (CORS) for web security

- **app/core/config.py**: Configuration settings 
  - Centralizes all application settings in one place
  - Loads environment variables for API keys and other sensitive data
  - Sets default values and validates config through Pydantic

- **app/core/cache.py**: Caching utilities
  - Implements in-memory caching for API responses
  - Provides decorators to easily cache function results
  - Manages cache expiration and invalidation

### API and Endpoints

- **app/api/api.py**: Main API router
  - Creates the central router that organizes all endpoints
  - Groups endpoints by feature with appropriate prefixes and tags

- **app/api/endpoints/company.py**: Company data endpoints
  - Implements HTTP endpoints for retrieving company information
  - Handles request validation and error responses
  - Maps HTTP requests to service functions

- **app/api/endpoints/financial_modeling.py**: Financial modeling endpoints
  - Provides AI-driven financial modeling capabilities via API
  - Supports synchronous and asynchronous model generation
  - Returns complete financial models with projections and valuation

### Data Models

- **app/models/company.py**: Pydantic models for company data
  - Defines data structures with validation rules
  - Documents each field and its purpose
  - Provides type safety and automatic API docs

- **app/models/financial_statements.py**: Pydantic models for financial statements
  - Defines structured representations of income statements, balance sheets, and cash flows
  - Standardizes financial metrics and reporting periods
  - Enables consistent comparison of financial data across companies and time

### Service Layer

- **app/services/company_service.py**: Company data service
  - Interfaces with external APIs (yFinance, Alpha Vantage, SEC)
  - Processes raw data into structured formats
  - Handles errors and edge cases
  - Provides a consistent interface for the API endpoints

- **app/services/sec_fetcher.py**: SEC filing fetcher
  - Downloads SEC filings from the SEC API
  - Handles caching to avoid redundant downloads
  - Manages API rate limits and authentication
  - Provides a reliable source of SEC filing data

- **app/services/sec_analyzer.py**: SEC filing analyzer
  - Uses AI models to extract insights from SEC filings
  - Generates summaries and key takeaways from financial reports
  - Identifies risks, opportunities, and significant changes

- **app/services/sec_trends.py**: SEC filing trend analyzer
  - Compares SEC filings across time periods
  - Identifies significant changes in financial metrics
  - Tracks narrative changes and disclosure evolution

- **app/services/financial_statement_extractor.py**: Financial statement extractor
  - Extracts structured financial statements from SEC filings
  - Normalizes financial metrics across different reporting formats
  - Handles both HTML and text-based table parsing
  - Provides standardized financial data for analysis

## 🧩 Key Components Explained

### 1. FastAPI Application Setup

The `app/main.py` file initializes the FastAPI application:

```python
app = FastAPI(
    title=settings.PROJECT_NAME,  # The name shown in the API docs
    description=settings.PROJECT_DESCRIPTION,  # Description of what the API does
    version=settings.VERSION,  # Current version of the API
    openapi_url=f"{settings.API_V1_STR}/openapi.json",  # URL to access API documentation
)
```

This creates the web application with automatic documentation and proper metadata.

### 2. Configuration Management

The `Settings` class in `app/core/config.py` uses Pydantic to define and validate settings:

```python
class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Analyst AI"
    # ... other settings
    
    class Config:
        env_file = ".env"
        case_sensitive = True
```

Benefits of this approach:
- Type validation for all settings
- Automatic loading from environment variables
- Centralized configuration management

### 3. Caching Mechanism

The `cache_response` decorator in `app/core/cache.py` provides an easy way to cache function results:

```python
@cache_response(expiry_minutes=60)
async def get_company_profile(symbol: str) -> CompanyProfile:
    # Function implementation
```

How it works:
1. Creates a unique key based on function name and arguments
2. Checks if there's a valid (not expired) cached result
3. If found, returns cached result; otherwise, calls the original function
4. Stores the new result in cache with expiration time

### 4. API Endpoint Implementation

Each endpoint in `app/api/endpoints/company.py` follows a pattern:

```python
@router.get("/{symbol}", response_model=CompanyProfile)
async def get_company(symbol: str):
    try:
        return await company_service.get_company_profile(symbol.upper())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
```

Key aspects:
- Path parameter validation (symbol)
- Response model specification
- Clear error handling with appropriate HTTP status codes
- Service delegation (separation of concerns)

### 5. Data Models with Validation

Pydantic models in `app/models/company.py` provide validation and documentation:

```python
class CompanyProfile(BaseModel):
    symbol: str = Field(..., description="Stock ticker symbol")
    name: str = Field(..., description="Company name")
    # ... other fields
```

Benefits:
- Automatic validation of incoming/outgoing data
- Self-documenting API (shown in Swagger UI)
- Type safety throughout the application

### 6. Service Layer for Business Logic

The `CompanyDataService` in `app/services/company_service.py` encapsulates data retrieval:

```python
async def get_financial_metrics(self, symbol: str) -> FinancialMetric:
    # Implementation that fetches from multiple sources
    # and combines the results
```

This separation allows:
- Abstracting away the complexity of external APIs
- Combining data from multiple sources
- Handling errors and edge cases consistently
- Testing business logic independently of HTTP concerns

## 📄 SEC Filing Fetcher (Premium API)

### Overview
The enhanced SEC Filing Fetcher module leverages premium API access to efficiently download and process SEC filings. This module is critical for the AI analysis pipeline as it provides the raw data (complete SEC filings as PDFs) that will be analyzed by AI models.

### Files
- **app/services/sec_fetcher.py**: Main module for retrieving SEC filings
  - Downloads complete SEC filings as PDFs
  - Implements robust rate limiting and caching
  - Supports batch downloading of multiple filings in parallel
  - Optimized for premium API access

- **app/core/config.py**: Updated with premium API settings
  - Configures rate limits for premium tier
  - Sets quality settings for PDF generation
  - Controls concurrent request limits

- **test_premium_sec_fetcher.py**: Test script for the enhanced fetcher
  - Verifies single filing downloads
  - Tests batch downloading capabilities
  - Validates caching behavior
  - Measures performance improvements

### Key Enhancements
1. **Improved Rate Limiting**:
   - Uses asyncio semaphores to control concurrent requests
   - Implements time-based rate limiting to stay within API limits
   - Adds exponential backoff for retries

2. **Enhanced Caching**:
   - Organizes cache by company symbol for better file management
   - Stores metadata alongside PDFs for faster lookups
   - Implements cache cleanup functionality

3. **Parallel Processing**:
   - Optimized batch downloading with controlled concurrency
   - Efficient handling of multiple filings
   - Progress tracking and error handling

4. **Premium Features**:
   - Higher quality PDF generation
   - Increased rate limits
   - More reliable API access

### Usage Example
```python
# Download a single filing
filing = SECFiling(
    symbol='AAPL',
    filing_type=FilingType.FORM_10K,
    filing_date=date(2023, 10, 27),
    document_url='https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm',
    filing_id='0000320193-23-000106'
)
pdf_path = await sec_filing_fetcher.get_filing_pdf(filing)

# Batch download multiple filings
filings = [filing1, filing2, filing3]
results = await sec_filing_fetcher.batch_download_filings(filings)
```

### Best Practices
- Always check the cache before making API requests
- Use batch downloading for multiple filings
- Implement proper error handling
- Monitor rate limits to avoid API throttling
- Regularly clean up the cache to manage disk space

### Alternative Approaches
- **Direct HTML/XBRL Parsing**: Instead of using PDFs, we could parse the HTML or XBRL directly. This would be more efficient for targeted data extraction but would lose the document structure that's valuable for AI analysis.
- **Section Extraction**: We could extract specific sections from filings rather than processing the entire document. This would be more efficient but might miss context that spans multiple sections.
- **Database Storage**: For frequently accessed filings, we could store the extracted text in a database rather than re-processing PDFs each time.

### Future Improvements
- Implement automatic CIK lookup from company symbols
- Add support for more filing types
- Integrate with the XBRL-to-JSON Converter API for structured data extraction
- Develop a filing metadata database for faster lookups
- Implement a more sophisticated caching strategy based on access patterns

## 📊 SEC Filing Analysis

The SEC Filing Analysis feature provides AI-powered analysis of complete SEC filings for any publicly traded company.

### Files and Their Purpose

- **app/services/sec_fetcher.py**: Downloads SEC filings as PDFs
  - `SECFilingFetcher` class handles downloading, caching, and API interactions
  - Implements retry mechanisms and rate limiting for API requests
  - Provides a clean interface for retrieving filing PDFs

- **app/services/sec_analyzer.py**: Analyzes SEC filings using AI models
  - `SECFilingAnalyzer` class sends complete PDFs directly to AI models
  - Uses OpenAI's Files API for efficient PDF handling with fallback to base64 encoding
  - Generates structured analysis with executive summaries, financial metrics, risk factors, etc.
  - Implements multi-level caching to avoid redundant processing

- **app/api/endpoints/sec_analysis.py**: Provides API endpoints for SEC filing analysis
  - `/api/v1/sec/{symbol}/analyze`: Analyzes the latest filing of a specific type
  - `/api/v1/sec/{symbol}/analyze/{filing_id}`: Analyzes a specific filing by ID
  - Returns structured analysis results in a consistent format

### Key Functions

#### SEC Filing Fetcher

- `get_filing_pdf(filing)`: Downloads a SEC filing as a PDF
  - Handles caching to avoid redundant downloads
  - Converts SEC.gov URLs to a format suitable for the PDF Generator API
  - Implements retries with exponential backoff

- `find_filing_urls(filing_types, start_year, end_year, save_to_file)`: Finds URLs of SEC filings
  - Uses the SEC-API Query API to search for filings by type and date range
  - Handles pagination through search results (up to 10,000 filings)
  - Saves URLs to a file for later use
  - Respects API rate limits with appropriate delays

- `load_urls_from_file(file_path)`: Loads filing URLs from a file
  - Reads URLs from a text file (one URL per line)
  - Provides a convenient way to reuse previously found URLs

- `download_filings_in_parallel(urls, max_workers, limit)`: Downloads multiple filings concurrently
  - Uses asyncio to download up to 20 filings in parallel
  - Implements a semaphore to control concurrency
  - Handles errors and retries for each download
  - Returns paths to successfully downloaded PDFs

#### SEC Filing Analyzer

- `analyze_filing(filing)`: Orchestrates the entire analysis process
  - Fetches the filing PDF
  - Sends the complete PDF directly to an AI model for analysis
  - Processes and structures the analysis results

- `_analyze_with_openai(filing, prompt, pdf_path)`: Primary analysis method using Files API
  - Uploads the PDF file to OpenAI's Files API
  - Caches the file ID to avoid redundant uploads
  - References the file ID in the analysis request
  - Processes the AI response into structured sections

- `_analyze_with_openai_base64(filing, prompt, pdf_path)`: Fallback analysis method
  - Used if the Files API approach fails
  - Encodes the PDF in base64 format
  - Sends the encoded PDF along with the analysis prompt
  - Provides reliability through redundancy

#### SEC Analysis API

- `analyze_latest_filing(symbol, filing_type, limit)`: Analyzes the latest filing
  - Retrieves the latest filing of the specified type
  - Sends it to the analyzer for processing
  - Returns structured analysis results

- `analyze_specific_filing(symbol, filing_id)`: Analyzes a specific filing by ID
  - Retrieves the specified filing by ID
  - Sends it to the analyzer for processing
  - Returns structured analysis results

### Best Practices and Alternative Approaches

- **Efficient PDF Processing**: The system uses a two-tier approach for PDF analysis
  - Primary: OpenAI Files API for efficient handling of large documents
  - Fallback: Base64 encoding for reliability
  - Advantage: Handles large SEC filings (up to 100 pages and 32MB)
  - Advantage: Preserves document structure, tables, and formatting

- **Multi-level Caching**: The system implements three levels of caching
  - Level 1: Cache downloaded PDF files
  - Level 2: Cache OpenAI file IDs to avoid redundant uploads
  - Level 3: Cache completed analyses
  - Advantage: Minimizes API costs and improves response times

- **Resilient Design**: The system includes fallback mechanisms
  - If Files API fails, falls back to base64 encoding
  - Comprehensive error handling at each step
  - Detailed logging for troubleshooting

## 📄 SEC Filing Trends Analysis

### Overview
The Multi-Period SEC Filing Analysis feature enables comprehensive analysis of a company's SEC filings across multiple time periods. This feature fetches the latest 10-K and the last four 10-Q filings for a company, analyzes each filing individually, and then performs a comparative analysis to identify trends, changes, and notable developments.

### Files
- **app/services/sec_fetcher.py**: Enhanced to support batch downloading of historical filings
  - Added `get_historical_filings()` method to fetch multiple filings for a company
  - Implemented efficient batch downloading with premium API rate limits
  - Added helper methods for querying and converting SEC API results

- **app/services/sec_trends.py**: New module for analyzing trends across multiple filings
  - Implements comparative analysis of filings across different time periods
  - Identifies trends, changes, and notable developments
  - Generates comprehensive multi-period analysis with AI

- **app/api/endpoints/sec_routes.py**: API endpoints for historical SEC analysis
  - Provides `/api/v1/sec/{symbol}/historical/analyze` endpoint for trends analysis
  - Includes endpoints for retrieving and analyzing individual filings
  - Implements proper error handling and response formatting

### Key Features
1. **Historical Filings Retrieval**:
   - Fetches the latest 10-K and the last four 10-Q filings for a company
   - Efficiently downloads multiple filings in parallel
   - Implements caching to avoid redundant downloads

2. **Multi-Period Analysis**:
   - Analyzes each filing individually with AI
   - Performs comparative analysis across all filings
   - Identifies trends, changes, and notable developments

3. **Structured Insights**:
   - Financial trends (revenue, profit margins, EPS)
   - Business evolution (segments, geographic expansion)
   - Risk factor changes (new risks, mitigated risks)
   - Management commentary evolution
   - Key performance indicators
   - Notable developments
   - Forward outlook

### Usage Example
```python
# Fetch and analyze historical filings for a company
trends_analysis = await sec_trends_analyzer.analyze_historical_filings("AAPL")

# Access the analysis results
summary = trends_analysis.summary
financial_trends = trends_analysis.trends_analysis.get("FINANCIAL TRENDS")
risk_changes = trends_analysis.trends_analysis.get("RISK FACTOR CHANGES")
```

### API Endpoints
- **GET /api/v1/sec/{symbol}/historical/analyze**: Analyze historical filings for a company
- **GET /api/v1/sec/{symbol}/historical/filings**: Retrieve historical filings without analysis
- **GET /api/v1/sec/{symbol}/filing/{filing_type}**: Analyze a specific filing

### Best Practices
- Use caching to avoid redundant downloads and analysis
- Implement proper error handling for API requests
- Process filings in parallel for better performance
- Structure the analysis results for easy consumption

### Alternative Approaches
- **Section-by-Section Comparison**: Instead of analyzing entire filings, compare specific sections across filings
- **Quantitative Analysis**: Extract and compare numerical data points across filings
- **Sentiment Analysis**: Analyze the tone and sentiment of management's commentary across filings

### Future Improvements
- Add support for more filing types (8-K, proxy statements)
- Implement more sophisticated trend detection algorithms
- Add visualization of trends and changes
- Enable comparison across multiple companies in the same industry

## 🌟 Best Practices Used

### 1. Modular Architecture

The codebase uses a modular structure with clear separation of concerns:
- API endpoints handle HTTP requests/responses
- Services handle business logic and external API interaction
- Models define and validate data structures
- Core utilities provide shared functionality

### 2. Comprehensive Error Handling

Error handling is implemented at multiple levels:
- Try/except blocks in services catch errors from external APIs
- API endpoints transform errors into appropriate HTTP responses
- Logging provides visibility into what went wrong

### 3. Type Hints and Documentation

The code uses:
- Type hints for all functions and variables
- Detailed docstrings explaining purpose and parameters
- Clear inline comments for complex logic

### 4. Performance Optimization

The application optimizes performance through:
- Caching to reduce redundant API calls
- Asynchronous functions for non-blocking I/O
- Efficient data processing with pandas

## 💡 Alternative Approaches

### Data Retrieval

Current approach: Using yFinance with Alpha Vantage as a supplement.

Alternatives:
- **Direct Yahoo Finance API**: Less stable, requires more maintenance
- **Financial Modeling Prep API**: More comprehensive, but entirely paid
- **Intrinio**: Enterprise-grade, higher cost but better data quality
- **Web scraping**: Customizable but potentially less reliable and legal concerns

### Caching

Current approach: Simple in-memory cache.

Alternatives:
- **Redis**: More scalable, supports distributed systems
- **Database caching**: Persistent across restarts, but slower
- **CDN caching**: For public, rarely changing data

### API Design

Current approach: REST API with clear resource hierarchy.

Alternatives:
- **GraphQL**: More flexible queries, but more complex implementation
- **gRPC**: Better performance, but less client compatibility
- **Webhooks**: Push updates instead of pull, good for real-time data

## SEC API Integration Fix

### Overview
This update fixes the SEC API integration to properly retrieve SEC filings for companies. The previous implementation had issues with the query format that prevented successful retrieval of 10-K and 10-Q filings.

### Files Affected
- `app/services/sec_fetcher.py`: Updated the `_query_sec_filings` method to use the correct query format according to the SEC API documentation.

### Key Changes
1. **Query Format**: Updated the query format to match the SEC API documentation exactly:
   - Used a simpler query format: `ticker:{symbol} AND formType:"{form_type}"`
   - Removed unnecessary exclusions that were causing issues
   - Ensured parameters like "from" and "size" are passed as strings as required by the API

2. **Error Handling**: Improved error handling and logging to provide better visibility into API responses:
   - Added detailed logging of API responses
   - Added traceback information for exceptions
   - Improved error messages for better debugging

3. **Testing**: Created comprehensive test scripts to verify the API integration:
   - Added tests for API key validity
   - Added tests for querying by ticker symbol
   - Added tests for checking form types
   - Added tests for the full historical filings download process

### Usage Example
The SEC API can now be used to retrieve historical filings for a company:

```python
# Get historical filings for Apple
historical_filings = await sec_filing_fetcher.get_historical_filings("AAPL")

# Access the 10-K filings
ten_k_filings = historical_filings["10-K"]

# Access the 10-Q filings
ten_q_filings = historical_filings["10-Q"]
```

### Best Practices
1. Always follow the exact API documentation for query formats and parameter types
2. Implement detailed logging for API requests and responses to aid in debugging
3. Create simple test scripts to verify API functionality before integrating into larger systems
4. Start with simple queries and gradually add complexity as needed

## 📊 Financial Statement Extractor

The Financial Statement Extractor is a sophisticated module that extracts structured financial data from SEC filings. This component is critical for enabling quantitative analysis of financial statements across companies and time periods.

### Purpose and Functionality

**Purpose:** To convert unstructured financial tables in SEC filings into structured, machine-readable formats that can be used for analysis, comparison, and visualization.

**Key Functions:**

1. **extract_financial_statements(filing)**: The main entry point that processes a complete SEC filing and extracts all financial statements.

2. **_extract_statement(content, statement_type, filing)**: Extracts a specific type of financial statement (income statement, balance sheet, or cash flow) from filing content.

3. **_find_statement_section(content, statement_type)**: Identifies the section of a filing that contains a specific financial statement using regex patterns.

4. **_parse_html_table(section, statement_type)** and **_parse_text_table(section, statement_type)**: Parse financial tables in HTML and text formats, respectively.

5. **_standardize_metric_name(raw_name, statement_type)**: Maps company-specific line item names to standardized metric names for consistent analysis.

### How It Works

1. **Section Identification:**
   - Uses regex patterns to locate financial statement sections within the filing
   - Handles different header formats and table structures
   - Extracts the relevant text section for further processing

2. **Format Detection:**
   - Determines if the content is HTML or plain text
   - Applies the appropriate parsing strategy based on the format

3. **Table Parsing:**
   - For HTML: Uses BeautifulSoup to parse table structures
   - For text: Uses regex and text processing to identify tabular data
   - Extracts headers, row labels, and numeric values

4. **Metric Standardization:**
   - Maps company-specific line item names to standard metrics
   - Handles variations in terminology (e.g., "Net Sales" vs "Revenue")
   - Creates a consistent set of metrics across companies

5. **Period Identification:**
   - Detects time periods from column headers
   - Standardizes period formats (e.g., "2023", "2023Q1")
   - Handles fiscal years and calendar years

6. **Value Processing:**
   - Parses numeric values from text
   - Handles different number formats (commas, parentheses for negatives)
   - Detects and applies the correct units (thousands, millions, billions)

7. **Result Formatting:**
   - Creates structured FinancialStatement objects
   - Organizes metrics by statement type
   - Provides standardized access to financial data

### Design Patterns and Best Practices

1. **Caching Strategy:**
   - Implements a file-based cache for extracted statements
   - Uses a deterministic cache key based on ticker, filing type, and period
   - Validates cache entries before using them

2. **Error Handling:**
   - Catches and logs exceptions at multiple levels
   - Provides meaningful error messages for debugging
   - Gracefully handles missing or malformed data

3. **Extensibility:**
   - Uses dictionaries for metric mappings that can be easily expanded
   - Separates format-specific logic from general extraction logic
   - Implements a modular design that can be extended for new statement types

4. **Performance Optimization:**
   - Uses efficient text processing algorithms
   - Limits search scope to relevant sections of filings
   - Implements caching to avoid redundant processing

### Usage Example

```python
from app.services.financial_statement_extractor import extract_financial_statements
from app.services.sec_fetcher import sec_filing_fetcher
from app.models.company import FilingType
from app.models.financial_statements import FinancialStatementType

# Fetch a filing
filing = sec_filing_fetcher.get_filing(
    ticker="AAPL",
    filing_type=FilingType.FORM_10K,
    fiscal_year=2022
)

# Extract all financial statements
statements = extract_financial_statements(filing)

# Access the income statement
income_statement = statements.get(FinancialStatementType.INCOME_STATEMENT)
if income_statement:
    # Get revenue for all available periods
    revenue = income_statement.metrics.get("revenue", {})
    
    # Calculate year-over-year growth
    periods = sorted(revenue.keys())
    for i in range(1, len(periods)):
        current = revenue[periods[i]]
        previous = revenue[periods[i-1]]
        growth = (current / previous - 1) * 100
        print(f"Revenue growth {periods[i-1]} to {periods[i]}: {growth:.2f}%")
```

### Challenges and Solutions

1. **Challenge: Inconsistent formatting across companies**
   - *Solution:* Implemented flexible parsing strategies that adapt to different table formats
   - *Solution:* Created extensive mapping dictionaries for standardizing metrics

2. **Challenge: Mixed HTML and text formats**
   - *Solution:* Built separate parsers for HTML and text with a common output format
   - *Solution:* Implemented format detection to automatically choose the right parser

3. **Challenge: Complex nested tables**
   - *Solution:* Developed heuristics to identify the main financial tables
   - *Solution:* Used table size and content patterns to select the correct tables

4. **Challenge: Handling different time periods and comparisons**
   - *Solution:* Created standardized period identifiers
   - *Solution:* Developed algorithms to detect and normalize quarter and year formats

### Integration Points

- **Input:** Uses SEC filings from the sec_fetcher module
- **Output:** Produces structured financial_statements for use by:
  - sec_trends module for time-series analysis
  - company_service module for financial metrics
  - API endpoints for client consumption 

## 💰 Financial Modeling

### Data Aggregation

- **app/services/financial_data_aggregator.py**: Comprehensive financial data aggregator
  - Collects financial statements across multiple periods (quarterly and annual)
  - Extracts accounting policies and footnotes from filings
  - Creates standardized time series data for AI consumption
  - Caches results to optimize performance for repeated requests
  
### AI-Driven Modeling

- **app/services/ai_financial_modeler.py**: AI financial modeling engine
  - Leverages LLMs to analyze financial data and create projections
  - Processes company-specific accounting policies and nuances
  - Generates complete financial models with forecasted statements
  - Provides DCF valuations and other valuation approaches
  - Explains assumptions and reasoning for transparency

### Key Features

1. **Comprehensive Data Integration**
   - Combines financial statements, accounting policies, and qualitative information
   - Creates a unified dataset spanning multiple years and quarters
   - Identifies company-specific accounting treatments

2. **AI-Based Assumption Generation**
   - Analyzes historical performance to generate reasonable assumptions
   - Creates growth projections based on company trends and industry context
   - Adapts to company-specific accounting practices

3. **Complete Financial Modeling**
   - Generates projected financial statements (Income Statement, Balance Sheet, Cash Flow)
   - Calculates key financial ratios and performance metrics
   - Provides multiple valuation approaches (DCF, multiples)
   - Identifies key risk factors and sensitivities

4. **Testing and Usage**
   - Use `test_financial_data_aggregator.py` to test data collection
   - Use `test_ai_financial_modeler.py` to generate complete financial models
   - Models are saved as structured JSON for easy consumption

### Best Practices

- Accounting policies are carefully analyzed to handle company-specific treatments
- Historical data is normalized for comparability across periods
- AI explanations provide transparency for all assumptions and projections
- Models incorporate both quantitative metrics and qualitative factors from filings 