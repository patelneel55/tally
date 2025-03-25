# Analyst AI: AI-Powered Financial Research Platform

Analyst AI is an advanced financial research platform that leverages artificial intelligence to automate financial analysis, modeling, and investment research. It processes financial data from multiple sources, builds financial models, and generates investment insights with minimal human intervention.

## 🚀 Features

- **Automated Financial Data Collection**: Fetches data from SEC filings and financial APIs
- **AI-Driven Financial Modeling**: Creates detailed financial models including DCF valuation
- **Investment Analysis**: Generates comprehensive investment analysis reports
- **Competitive Analysis**: Compares companies against industry peers
- **Executive Summaries**: Produces concise summaries for decision makers

## 🔧 Installation

### Prerequisites

- Python 3.9+
- OpenAI API key
- Polygon.io API key
- SEC API key (optional, for enhanced functionality)

### Setup

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/analyst-ai.git
   cd analyst-ai
   ```

2. Create and activate a virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables
   ```bash
   # Create a .env file with your API keys
   echo "OPENAI_API_KEY=your-openai-key" > .env
   echo "POLYGON_API_KEY=your-polygon-key" >> .env
   echo "SEC_API_KEY=your-sec-key" >> .env
   ```

## 📊 Usage

### Fetch Financial Data

```bash
# Fetch financial data for Apple Inc.
python test_polygon_financials.py AAPL --years 3
```

### Generate Comprehensive Financial Data

```bash
# Aggregate financial data from multiple sources
python test_financial_data_aggregator.py AAPL --years 3 --force
```

### Create Investment Analysis

```bash
# Generate comprehensive investment analysis
python test_ai_analyst.py AAPL --years 3 [--no-peers] [--force]
```

### Options

- `--years`: Number of years of historical data to include (default: 3)
- `--force`: Force refresh data (ignore cache)
- `--no-peers`: Skip peer comparison analysis
- `--output`: Specify custom output file path

## 📁 Project Structure

```
analyst-ai/
├── ai_analyst/               # Main package
│   ├── app/                 # Application code
│   │   ├── core/           # Core configuration
│   │   ├── services/       # Service modules
│   │   └── utils/          # Utility functions
├── tests/                   # Test directory
├── analysis_results/        # Output directory
│   ├── aggregated_data/     # Aggregated financial data
│   ├── polygon_data/        # Raw Polygon.io data
│   └── investment_analysis/ # AI-generated analysis
├── cache/                   # Cache directory
│   ├── sec_filings/         # SEC filing cache
│   └── sec_analysis/        # SEC analysis cache
├── requirements.txt         # Dependencies
└── README.md                # This file
```

## 🧠 AI Implementation

Analyst AI uses several AI models to process financial data:

1. **Financial Document Processing**: Extracts structured data from unstructured SEC filings
2. **Financial Modeling**: Creates projections based on historical trends and business fundamentals
3. **Investment Analysis**: Evaluates investment potential and generates recommendations
4. **Natural Language Generation**: Creates readable, concise summaries and reports

## 📝 Example Output

The system generates comprehensive financial analysis in JSON format, which includes:

- Executive Summary
- Investment Recommendation (Buy/Sell/Hold)
- Financial Performance Analysis
- Valuation Analysis
- Growth Opportunities
- Risk Assessment
- Competitive Analysis
- Detailed Financial Projections

## 🔐 API Keys and Credentials

The system requires several API keys to function properly:

- **OpenAI API Key**: For AI-powered analysis and modeling
- **Polygon.io API Key**: For financial statements and market data
- **SEC API Key**: For enhanced SEC filing retrieval

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📚 Documentation

For more detailed documentation, see the `explanations.md` file in this repository, which includes:

- Detailed architecture explanation
- Component descriptions
- Data flow diagrams
- Implementation details
- Best practices and alternative approaches

## 📊 Future Development

Planned enhancements include:

- Market data integration
- Advanced visualization capabilities
- Scenario analysis functionality
- Custom model training for financial analysis 