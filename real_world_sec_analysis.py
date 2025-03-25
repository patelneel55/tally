"""
Real-World SEC Filing Analysis Example
-------------------------------------

This script demonstrates how to use the SEC filing analysis pipeline
for real-world financial analysis tasks:

1. Comparing multiple companies in the same sector
2. Analyzing historical filings to track changes over time
3. Extracting specific insights from filings

Usage:
    python real_world_sec_analysis.py
"""

import asyncio
import json
from datetime import date
from pathlib import Path
from typing import List, Dict, Any

from ai_analyst.app.services.sec_fetcher import sec_fetcher
from ai_analyst.app.services.sec_analyzer import sec_filing_analyzer
from ai_analyst.app.models.financial_statements import FilingType

# Create output directory
output_dir = Path("analysis_results")
output_dir.mkdir(exist_ok=True)

async def analyze_company(symbol: str, filing_type: FilingType = FilingType.FORM_10K, limit: int = 1) -> Dict[str, Any]:
    """
    Analyze the latest filing for a company.
    
    Args:
        symbol: Company stock symbol
        filing_type: Type of filing to analyze
        limit: Number of filings to retrieve (only the latest will be analyzed)
        
    Returns:
        Dictionary with analysis results
    """
    print(f"\n{'='*80}\nAnalyzing {filing_type} for {symbol}\n{'='*80}")
    
    # Step 1: Fetch the latest filing metadata
    print(f"Fetching {filing_type} filings for {symbol}...")
    filings_response = await sec_fetcher.get_sec_filings(
        symbol=symbol,
        filing_type=filing_type,
        limit=limit
    )
    
    if not filings_response or not filings_response.filings:
        print(f"No {filing_type} filings found for {symbol}")
        return {}
    
    filing = filings_response.filings[0]
    print(f"Found filing from {filing.filing_date}: {filing.document_url}")
    
    # Step 2: Download the filing as PDF
    print(f"Downloading filing as PDF...")
    pdf_path = await sec_fetcher.get_filing_pdf(filing)
    
    if not pdf_path:
        print(f"Failed to download PDF for {symbol}")
        return {}
    
    print(f"PDF downloaded to: {pdf_path}")
    
    # Step 3: Analyze the filing
    print(f"Analyzing filing with AI...")
    analysis_result = await sec_filing_analyzer.analyze_filing(filing)
    
    if not analysis_result:
        print(f"Failed to analyze filing for {symbol}")
        return {}
    
    # Step 4: Save the results
    result_dict = {
        "symbol": symbol,
        "filing_type": str(filing_type),
        "filing_date": filing.filing_date.isoformat(),
        "document_url": filing.document_url,
        "summary": analysis_result.summary,
        "analysis": analysis_result.analysis,
        "analysis_date": analysis_result.analysis_date.isoformat()
    }
    
    output_file = output_dir / f"{symbol}_{filing_type}_{filing.filing_date.isoformat()}.json"
    with open(output_file, 'w') as f:
        json.dump(result_dict, f, indent=2)
    
    print(f"Analysis saved to: {output_file}")
    return result_dict

async def compare_companies_in_sector(symbols: List[str], filing_type: FilingType = FilingType.FORM_10K) -> Dict[str, Any]:
    """
    Compare multiple companies in the same sector by analyzing their filings.
    
    Args:
        symbols: List of company stock symbols
        filing_type: Type of filing to analyze
        
    Returns:
        Dictionary with comparison results
    """
    print(f"\n{'='*80}\nComparing {filing_type} filings for {', '.join(symbols)}\n{'='*80}")
    
    # Analyze each company
    results = {}
    for symbol in symbols:
        results[symbol] = await analyze_company(symbol, filing_type)
    
    # Extract key metrics for comparison
    comparison = {
        "companies": symbols,
        "filing_type": str(filing_type),
        "comparison_date": date.today().isoformat(),
        "metrics": {}
    }
    
    # Compare revenue growth
    comparison["metrics"]["revenue_growth"] = {}
    comparison["metrics"]["profit_margins"] = {}
    comparison["metrics"]["risk_factors"] = {}
    
    for symbol, result in results.items():
        if not result:
            continue
            
        # Extract metrics from the analysis
        analysis = result.get("analysis", {})
        
        # Revenue growth
        financial_metrics = analysis.get("financial_metrics", "")
        comparison["metrics"]["revenue_growth"][symbol] = extract_metric(financial_metrics, "revenue growth")
        
        # Profit margins
        comparison["metrics"]["profit_margins"][symbol] = extract_metric(financial_metrics, "profit margin")
        
        # Risk factors
        risk_factors = analysis.get("risk_factors", "")
        comparison["metrics"]["risk_factors"][symbol] = summarize_risks(risk_factors)
    
    # Save comparison results
    output_file = output_dir / f"sector_comparison_{date.today().isoformat()}.json"
    with open(output_file, 'w') as f:
        json.dump(comparison, f, indent=2)
    
    print(f"Comparison saved to: {output_file}")
    return comparison

def extract_metric(text: str, metric_name: str) -> str:
    """
    Extract a specific metric from the analysis text.
    
    This is a simple extraction based on text search.
    In a production environment, you would use more sophisticated NLP.
    
    Args:
        text: The text to search in
        metric_name: The name of the metric to extract
        
    Returns:
        Extracted metric as text
    """
    # Find paragraphs containing the metric name
    paragraphs = text.split('\n\n')
    for paragraph in paragraphs:
        if metric_name.lower() in paragraph.lower():
            return paragraph
    
    return "Not found"

def summarize_risks(risk_text: str) -> List[str]:
    """
    Extract key risk factors from the risk analysis text.
    
    Args:
        risk_text: The risk analysis text
        
    Returns:
        List of key risk factors
    """
    # Split by bullet points or paragraphs
    risks = []
    for line in risk_text.split('\n'):
        line = line.strip()
        if line and len(line) > 20:  # Ignore short lines
            # Extract first sentence as the key risk
            sentence = line.split('.')[0]
            if len(sentence) > 20:  # Ensure it's substantial
                risks.append(sentence)
    
    # Return top risks (limit to 5)
    return risks[:5]

async def analyze_historical_filings(symbol: str, years: int = 3) -> Dict[str, Any]:
    """
    Analyze historical filings for a company to track changes over time.
    
    Args:
        symbol: Company stock symbol
        years: Number of years of filings to analyze
        
    Returns:
        Dictionary with historical analysis
    """
    print(f"\n{'='*80}\nAnalyzing historical {FilingType.FORM_10K} filings for {symbol} ({years} years)\n{'='*80}")
    
    # Step 1: Fetch multiple years of filings
    print(f"Fetching historical filings for {symbol}...")
    filings_response = await sec_fetcher.get_sec_filings(
        symbol=symbol,
        filing_type=FilingType.FORM_10K,
        limit=years
    )
    
    if not filings_response or not filings_response.filings:
        print(f"No historical filings found for {symbol}")
        return {}
    
    # Step 2: Analyze each filing
    historical_data = {
        "symbol": symbol,
        "filing_type": str(FilingType.FORM_10K),
        "years_analyzed": years,
        "filings": []
    }
    
    for filing in filings_response.filings:
        print(f"\nAnalyzing {filing.filing_date} filing...")
        
        # Download the filing
        pdf_path = await sec_fetcher.get_filing_pdf(filing)
        if not pdf_path:
            print(f"Failed to download PDF for {filing.filing_date}")
            continue
        
        # Analyze the filing
        analysis_result = await sec_filing_analyzer.analyze_filing(filing)
        if not analysis_result:
            print(f"Failed to analyze filing for {filing.filing_date}")
            continue
        
        # Extract key metrics and add to historical data
        filing_data = {
            "filing_date": filing.filing_date.isoformat(),
            "document_url": filing.document_url,
            "summary": analysis_result.summary,
            "key_metrics": extract_key_metrics(analysis_result.analysis)
        }
        
        historical_data["filings"].append(filing_data)
    
    # Step 3: Identify trends over time
    historical_data["trends"] = identify_trends(historical_data["filings"])
    
    # Save historical analysis
    output_file = output_dir / f"{symbol}_historical_{date.today().isoformat()}.json"
    with open(output_file, 'w') as f:
        json.dump(historical_data, f, indent=2)
    
    print(f"Historical analysis saved to: {output_file}")
    return historical_data

def extract_key_metrics(analysis: Dict[str, str]) -> Dict[str, Any]:
    """
    Extract key metrics from the analysis.
    
    Args:
        analysis: The analysis dictionary
        
    Returns:
        Dictionary with key metrics
    """
    metrics = {}
    
    # Extract revenue
    financial_metrics = analysis.get("financial_metrics", "")
    metrics["revenue"] = extract_metric(financial_metrics, "revenue")
    metrics["net_income"] = extract_metric(financial_metrics, "net income")
    metrics["eps"] = extract_metric(financial_metrics, "earnings per share")
    
    # Extract future outlook
    outlook = analysis.get("future_outlook", "")
    metrics["outlook"] = outlook[:200] + "..." if len(outlook) > 200 else outlook
    
    return metrics

def identify_trends(filings: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Identify trends in historical filings.
    
    Args:
        filings: List of filing data
        
    Returns:
        Dictionary with identified trends
    """
    # In a real implementation, this would use more sophisticated analysis
    # For this example, we'll just return a simple summary
    return {
        "revenue_trend": "Analyze revenue growth over time",
        "profitability_trend": "Analyze profitability changes",
        "outlook_changes": "Analyze changes in future outlook statements"
    }

async def extract_specific_insights(symbol: str, topics: List[str]) -> Dict[str, Any]:
    """
    Extract specific insights from a filing based on provided topics.
    
    Args:
        symbol: Company stock symbol
        topics: List of topics to extract insights for
        
    Returns:
        Dictionary with extracted insights
    """
    print(f"\n{'='*80}\nExtracting specific insights for {symbol} on topics: {', '.join(topics)}\n{'='*80}")
    
    # Step 1: Fetch the latest 10-K filing
    filings_response = await sec_fetcher.get_sec_filings(
        symbol=symbol,
        filing_type=FilingType.FORM_10K,
        limit=1
    )
    
    if not filings_response or not filings_response.filings:
        print(f"No 10-K filing found for {symbol}")
        return {}
    
    filing = filings_response.filings[0]
    
    # Step 2: Download the filing
    pdf_path = await sec_fetcher.get_filing_pdf(filing)
    if not pdf_path:
        print(f"Failed to download PDF for {symbol}")
        return {}
    
    # Step 3: Extract text from the PDF
    text = await sec_fetcher.get_filing_text(pdf_path)
    if not text:
        print(f"Failed to extract text from PDF for {symbol}")
        return {}
    
    # Step 4: Extract insights for each topic
    insights = {
        "symbol": symbol,
        "filing_date": filing.filing_date.isoformat(),
        "document_url": filing.document_url,
        "topics": {}
    }
    
    for topic in topics:
        print(f"Extracting insights on: {topic}")
        # In a real implementation, you would use more sophisticated NLP
        # For this example, we'll use a simple keyword search
        
        # Find paragraphs containing the topic
        paragraphs = text.split('\n\n')
        relevant_paragraphs = []
        
        for paragraph in paragraphs:
            if topic.lower() in paragraph.lower():
                # Clean up the paragraph
                clean_paragraph = ' '.join(paragraph.split())
                if len(clean_paragraph) > 50:  # Ensure it's substantial
                    relevant_paragraphs.append(clean_paragraph)
        
        # Limit to top 3 most relevant paragraphs
        insights["topics"][topic] = relevant_paragraphs[:3]
    
    # Save insights
    output_file = output_dir / f"{symbol}_insights_{date.today().isoformat()}.json"
    with open(output_file, 'w') as f:
        json.dump(insights, f, indent=2)
    
    print(f"Insights saved to: {output_file}")
    return insights

async def main():
    """
    Run the real-world SEC filing analysis examples.
    """
    # Example 1: Analyze a single company
    await analyze_company("AAPL", FilingType.FORM_10K)
    
    # Example 2: Compare companies in the same sector
    tech_companies = ["AAPL", "MSFT", "GOOGL"]
    await compare_companies_in_sector(tech_companies, FilingType.FORM_10K)
    
    # Example 3: Analyze historical filings
    await analyze_historical_filings("AAPL", years=2)
    
    # Example 4: Extract specific insights
    topics = ["AI", "machine learning", "innovation", "research and development"]
    await extract_specific_insights("AAPL", topics)
    
    print("\nAll analyses completed! Results saved to the 'analysis_results' directory.")

if __name__ == "__main__":
    asyncio.run(main()) 