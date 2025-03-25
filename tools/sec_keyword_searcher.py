"""
SEC Filing Keyword Searcher

This module provides functionality to search SEC filings for specific keywords
and extract context-rich snippets around those keywords.

What this file does:
1. Searches pages of text for specified keywords
2. Extracts context windows around keyword matches
3. Returns structured results with page numbers and context
"""

import re
from typing import List, Dict


def search_filing_for_keywords(pages: List[Dict], keywords: List[str], window: int = 500) -> List[Dict]:
    """
    Searches each page's text for each keyword and returns matched context snippets.

    Args:
        pages (List[Dict]): Output from extract_text_from_pdf(), i.e., [{page, text}]
        keywords (List[str]): List of keywords to search for
        window (int): Number of characters before and after keyword to capture for context

    Returns:
        List[Dict]: Matches with 'keyword', 'page', and 'context'
    """
    matches = []
    for page in pages:
        text = page["text"]
        for keyword in keywords:
            pattern = re.compile(rf".{{0,{window}}}{re.escape(keyword)}.{{0,{window}}}", re.IGNORECASE)
            found = pattern.findall(text)
            for snippet in found:
                matches.append({
                    "keyword": keyword,
                    "page": page["page"],
                    "context": snippet.strip()
                })
    return matches 