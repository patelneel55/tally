# Analyst AI

An AI-powered financial research assistant that automates stock valuation, investment research, and financial analysis.

## 🚀 Features

Analyst AI helps you analyze stocks and financial data through a RESTful API:

- **Company Data Retrieval**
  - Basic company information (name, industry, market cap)
  - Key financial metrics and ratios
  - SEC filings (10-K, 10-Q, 8-K)
  - Historical stock price data
  
- **Financial Statement Analysis**
  - Structured extraction of Income Statements, Balance Sheets, and Cash Flow Statements
  - Standardized metrics across different companies and time periods
  - Trend analysis across multiple reporting periods
  - Financial ratio calculations and comparisons

- **Coming Soon**
  - Automated Valuation Models (DCF, multiples)
  - AI-Generated Research Reports
  - Earnings Call Summarization

## 🔧 Technical Architecture

Analyst AI is built with the following technologies:

- **Backend Framework**: FastAPI (Python)
- **Data Sources**: yFinance, Alpha Vantage API, SEC API
- **AI Integration**: OpenAI GPT-4, Anthropic Claude, LangChain
- **Data Processing**: Pandas, NumPy, BeautifulSoup
- **Text Analysis**: RegEx, NLP techniques for financial text parsing

The application uses a modular architecture with these components:

- **API Layer**: HTTP endpoints for accessing data
- **Service Layer**: Business logic for retrieving and processing financial data
- **Models**: Pydantic models for data validation and documentation
- **Core Utilities**: Configuration, caching, and shared utilities

### SEC Analysis Pipeline

Our SEC analysis pipeline consists of several components:

1. **SEC Fetcher**: Downloads filings from the SEC API with intelligent caching
2. **SEC Analyzer**: Uses AI to extract insights from individual filings
3. **Financial Statement Extractor**: Extracts structured financial data from SEC filings
4. **SEC Trends**: Compares filings and financial data across time periods

## 📋 API Endpoints

### Company Data

- `GET /api/v1/company/{symbol}` - Retrieve basic company information
- `GET /api/v1/company/{symbol}/financials` - Get key financial metrics
- `GET /api/v1/company/{symbol}/sec_filings` - Fetch SEC filings
- `GET /api/v1/company/{symbol}/historical` - Get historical stock data

### Financial Statements

- `GET /api/v1/company/{symbol}/financial_statements` - Get all financial statements
- `GET /api/v1/company/{symbol}/income_statement` - Get income statement
- `GET /api/v1/company/{symbol}/balance_sheet` - Get balance sheet
- `GET /api/v1/company/{symbol}/cash_flow` - Get cash flow statement
- `GET /api/v1/company/{symbol}/financial_trends` - Get financial trends across multiple periods

## 🛠️ Setup and Installation

### Prerequisites

- Python 3.10+
- API keys for:
  - Alpha Vantage (optional, enhances financial data)
  - SEC API (required for SEC filings)
  - OpenAI or Anthropic (for AI-powered analysis)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd ai_analyst
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file with your API keys:
   ```
   ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
   SEC_API_KEY=your_sec_api_key
   OPENAI_API_KEY=your_openai_key
   ANTHROPIC_API_KEY=your_anthropic_key
   ```

5. Run the application:
   ```bash
   uvicorn app.main:app --reload
   ```

6. Access the API documentation:
   - Open a browser and go to `http://localhost:8000/docs`

## 📚 How to Use

### Example: Getting Company Information

```python
import requests

# Get basic company information
response = requests.get("http://localhost:8000/api/v1/company/AAPL")
company_data = response.json()
print(f"Company: {company_data['name']}")
print(f"Industry: {company_data['industry']}")
print(f"Market Cap: ${company_data['market_cap']:,}")

# Get financial metrics
metrics = requests.get("http://localhost:8000/api/v1/company/AAPL/financials").json()
print(f"P/E Ratio: {metrics['pe_ratio']}")
print(f"Profit Margin: {metrics['profit_margin']*100:.2f}%")
```

### Example: Getting Financial Statements

```python
# Get income statement for the last 3 years
income_statement = requests.get(
    "http://localhost:8000/api/v1/company/AAPL/income_statement",
    params={"years": 3}
).json()

# Print revenue and net income for each year
for year, data in income_statement['metrics']['revenue']['values'].items():
    print(f"Year {year}:")
    print(f"  Revenue: ${data:,.0f}")
    print(f"  Net Income: ${income_statement['metrics']['net_income']['values'].get(year, 'N/A'):,.0f}")
    
# Calculate and print year-over-year growth
years = sorted(income_statement['metrics']['revenue']['values'].keys())
for i in range(1, len(years)):
    prev_year = years[i-1]
    curr_year = years[i]
    revenue_growth = (income_statement['metrics']['revenue']['values'][curr_year] / 
                     income_statement['metrics']['revenue']['values'][prev_year] - 1) * 100
    print(f"Revenue growth {prev_year} to {curr_year}: {revenue_growth:.2f}%")
```

## 🔒 Rate Limiting and Caching

Analyst AI implements:
- **Caching**: Responses are cached to minimize redundant API calls
- **Rate Limiting**: API calls are limited to prevent hitting external service limits

These features ensure:
- Better performance
- Lower operating costs
- Compliance with external API terms of service

## 🔍 Financial Statement Extractor

The Financial Statement Extractor is a powerful component that:

1. **Extracts structured financial data** from SEC filings (10-K, 10-Q)
2. **Normalizes financial metrics** across different reporting formats
3. **Standardizes line items** to enable cross-company comparisons
4. **Handles different reporting periods** (quarterly, annual)
5. **Identifies and processes financial tables** in both HTML and text formats

### Key Capabilities:

- **Intelligent section identification** to locate financial statements within filings
- **HTML and text table parsing** to handle various filing formats
- **Metric standardization** to normalize different naming conventions
- **Time period detection** to correctly associate values with reporting periods
- **Unit detection** to properly scale values (thousands, millions, billions)
- **Caching** to improve performance for repeated analyses

### Example Usage:

```python
from ai_analyst.app.services.financial_statement_extractor import extract_financial_statements
from ai_analyst.app.services.sec_fetcher import sec_filing_fetcher
from ai_analyst.app.models.company import FilingType

# Get a filing
filing = sec_filing_fetcher.get_filing(
    ticker="AAPL",
    filing_type=FilingType.FORM_10K,
    fiscal_year=2022
)

# Extract financial statements
statements = extract_financial_statements(filing)

# Access income statement metrics
income_statement = statements.get(FinancialStatementType.INCOME_STATEMENT)
if income_statement:
    revenue = income_statement.metrics.get("revenue", {})
    net_income = income_statement.metrics.get("net_income", {})
    
    print(f"Revenue: {revenue}")
    print(f"Net Income: {net_income}")
```

## 🤝 Contributing

Contributions are welcome! Areas for improvement include:
- Additional financial data sources
- Enhanced financial models and analysis
- AI-powered insights and research
- Frontend development
- Testing and documentation

## 📄 License

[MIT License](LICENSE)

---

Built with ❤️ for financial analysts and investors 