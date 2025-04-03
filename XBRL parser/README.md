# XBRL Parsing Pipeline

A comprehensive pipeline for extracting structured data from iXBRL SEC filings and converting them to semantic Markdown for analysis.

## Overview

This pipeline processes Inline XBRL (iXBRL) documents, which are machine-readable financial reports filed with the SEC. The pipeline consists of four main modules:

1. **IXBRLPreprocessor** - Cleans the raw iXBRL HTML file by removing XBRL tags while preserving visual content
2. **XBRLFactExtractor** - Extracts machine-readable facts from XBRL tags
3. **VisualBlockExtractor** - Extracts visual elements like headings, paragraphs, and tables
4. **MarkdownRenderer** - Combines facts and visual structure into semantic Markdown

## Pipeline Results

Processing the JPMorgan Chase Q3 2024 10-Q filing:

### IXBRLPreprocessor
- Processed `samples/10q_jpm_q3_2024.html`
- Removed 86,229 XBRL tags
- Saved cleaned file as `samples/cleaned_10q_jpm_q3_2024.html`

### XBRLFactExtractor
- Extracted 7,684 XBRL facts across 877 unique concepts
- Found 2,148 unique contextRef values and 11 unique unitRef values
- Top GAAP concepts included:
  - `dei:EntityCommonStockSharesOutstanding`
  - `us-gaap:InvestmentBankingRevenue`
  - `us-gaap:PrincipalTransactionsRevenue`

### VisualBlockExtractor
- Extracted 4,227 visual blocks from the cleaned HTML
- Enhanced heading detection using font size analysis 
- Processed 284 tables with proper structure preservation

### MarkdownRenderer
- Generated 9,045 lines of structured Markdown 
- Created footnotes with references to XBRL facts
- Preserved table formatting with Markdown tables
- Maintained document structure with appropriate heading levels
- Output saved as `samples/output_jpm_q3_2024.md`

## Usage

To run the complete pipeline:

```bash
python run_xbrl_pipeline.py
```

This will process the sample JPMorgan 10-Q and generate a structured Markdown file with XBRL annotations.

## Future Improvements

- Better handling of nested tables 
- More sophisticated heading level detection
- Enhanced fact matching for better footnote creation
- Parallel processing for large documents
- Support for additional SEC filing types (8-K, DEF 14A, etc.) 