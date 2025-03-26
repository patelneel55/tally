"""
Tools for analyzing and summarizing keyword matches from SEC filings.
"""
from typing import List, Dict, Optional
from collections import defaultdict
from openai import OpenAI
import logging
from app.core.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# Safety limit to ensure we don't exceed GPT-4's token context window
# GPT-4 has a limit of ~8K-128K tokens depending on the model version
# We use a conservative limit of 14000 characters (~3500 tokens) to stay well within bounds
MAX_CONTEXT_LENGTH = 14000
# Maximum matches to include per keyword
MAX_MATCHES_PER_KEYWORD = 10
# Token limit per chunk when processing in batches
CHUNK_TOKEN_LIMIT = 6000
# Approximate characters per token
CHARS_PER_TOKEN = 4


def chunk_context_by_token_count(context_sections: List[str], max_tokens: int = CHUNK_TOKEN_LIMIT) -> List[str]:
    """
    Split a list of context sections into chunks that fit within token limits.
    
    Args:
        context_sections: List of formatted text sections (one per keyword)
        max_tokens: Maximum tokens per chunk
        
    Returns:
        List of context chunks, where each chunk is a string
    """
    chunks = []
    current_chunk = []
    current_token_count = 0
    max_chars = max_tokens * CHARS_PER_TOKEN
    
    for section in context_sections:
        # Estimate token count for this section
        section_token_count = len(section) / CHARS_PER_TOKEN
        
        # If adding this section would exceed the limit, start a new chunk
        if current_token_count + section_token_count > max_tokens and current_chunk:
            # Join the current chunk sections and add to chunks
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [section]
            current_token_count = section_token_count
        else:
            # Add to the current chunk
            current_chunk.append(section)
            current_token_count += section_token_count
    
    # Add the last chunk if there's anything left
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
    
    logger.info(f"Split context into {len(chunks)} chunks")
    return chunks


def summarize_keyword_matches(matches: list[dict], original_query: str = "") -> str:
    """
    Summarize keyword matches from SEC filings using GPT-4.
    
    Args:
        matches: List of dictionaries containing keyword matches from SEC filings
        original_query: Optional original user query to provide context
        
    Returns:
        str: Generated summary of the keyword matches
    
    The function:
    1. Groups matches by keyword
    2. Formats them as readable text blocks
    3. Sends them to OpenAI's GPT-4 via API
    4. Returns the response text as a summary
    """
    # Check if we have any matches to analyze
    if not matches:
        return "No keyword matches were found in the filing. Try refining your search terms."
    
    # 1. Group matches by keyword
    keyword_groups = defaultdict(list)
    for match in matches:
        keyword_groups[match["keyword"]].append(match)
    
    # 2. Format them as readable text blocks with markdown headers, limiting matches per keyword
    formatted_sections = []
    
    # Sort keywords by number of matches (most frequent first)
    sorted_keywords = sorted(keyword_groups.keys(), 
                            key=lambda k: len(keyword_groups[k]), 
                            reverse=True)
    
    # Process each keyword into sections
    for keyword in sorted_keywords:
        keyword_matches = keyword_groups[keyword]
        
        # Limit matches per keyword to prevent excessive context length
        limited_matches = keyword_matches[:MAX_MATCHES_PER_KEYWORD]
        
        section_lines = [f"### Keyword: {keyword} ({len(keyword_matches)} total matches, showing {len(limited_matches)})"]
        for match in limited_matches:
            # Limit each context snippet to 200 chars for consistency
            context_snippet = f"- Page {match['page']}: {match['context'][:200]}..."
            section_lines.append(context_snippet)
        
        section_text = "\n".join(section_lines)
        formatted_sections.append(section_text)
    
    # 3. Process the sections in chunks if necessary
    chunks = chunk_context_by_token_count(formatted_sections)
    
    # If we have multiple chunks, we'll need to analyze each separately and combine
    if len(chunks) > 1:
        logger.info(f"Processing {len(chunks)} chunks separately and combining results")
        chunk_summaries = []
        
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)}")
            chunk_summary = _analyze_context_with_gpt(
                chunk, 
                original_query=f"{original_query} (Part {i+1} of {len(chunks)})"
            )
            chunk_summaries.append(chunk_summary)
        
        # Combine the chunk summaries
        combined_summary = "\n\n".join([
            f"--- Analysis Part {i+1}/{len(chunks)} ---\n{summary}" 
            for i, summary in enumerate(chunk_summaries)
        ])
        
        # Perform a final summarization of the combined results
        final_prompt = f"""You are analyzing a set of SEC filing analysis results that were split into {len(chunks)} parts due to length.
Below are the individual analyses. Please synthesize these into a single coherent summary that addresses the key points across all parts.
When information appears in multiple parts, consolidate it. Focus on providing an integrated view.

{combined_summary}"""
        
        system_msg = {
            "role": "system",
            "content": (
                "You are a senior equity research analyst at a top-tier investment firm. "
                "Your summary will be read by hundreds of institutional investors, including CIOs, PMs, and potentially someone like Warren Buffett. "
                "There is no room for fluff or vagueness. Be specific. Use real numbers from the input. Highlight material risks, segment trends, capital strength, and valuation-relevant insight. "
                "Write as if this is going in a published stock pitch or research note."
            )
        }
        
        user_msg = {
            "role": "user",
            "content": final_prompt
        }
        
        # Send the final synthesis request
        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[system_msg, user_msg],
                temperature=0.3,
                max_tokens=1500
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error in final synthesis: {e}")
            # Return the individual summaries if the synthesis fails
            return "Error in final synthesis. Individual part summaries:\n\n" + combined_summary
    else:
        # If only one chunk, process it directly
        return _analyze_context_with_gpt(chunks[0], original_query)


def _analyze_context_with_gpt(context: str, original_query: str = "") -> str:
    """
    Send context to OpenAI's GPT-4 and get analysis.
    
    Args:
        context: Formatted context string to analyze
        original_query: Optional original user query
        
    Returns:
        str: GPT-4 analysis result
    """
    # Create dynamic system message
    system_msg = {
        "role": "system",
        "content": (
            "You are a professional equity research analyst at a top-tier investment bank. "
            "Your task is to analyze excerpts from SEC filings and produce sharp, finance-specific insights. "
            "Be concise, quantify where possible, and focus on material risks, capital strength, and valuation-relevant disclosures."
        )
    }
    
    # Create dynamic user message based on original_query
    user_msg = {
        "role": "user",
        "content": (
            f"Based on the following excerpts from the 10-K, write a summary as if you were contributing to a stock pitch. "
            f"Include specific figures (e.g., ratios, Losses, YoY trends, QoQ trends, ) and flag any risk signals. "
            f"If the user provided a specific query, address it directly.\n\n"
            f"{context}"
        )
    }
    
    # Send to OpenAI's GPT-4 using new SDK
    try:
        # Initialize OpenAI client with API key from config
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[system_msg, user_msg],
            temperature=0.4
        )
        
        # Return the response text
        return response.choices[0].message.content
    
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        return f"Error generating summary: {str(e)}" 