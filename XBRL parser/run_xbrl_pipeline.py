#!/usr/bin/env python3
"""
XBRL Parsing Pipeline.

This script runs a complete pipeline to parse a SEC iXBRL file:
1. IXBRLPreprocessor - Removes XBRL tags, preserving visual content
2. XBRLFactExtractor - Extracts machine-readable facts from XBRL tags
3. VisualBlockExtractor - Extracts visual blocks from cleaned HTML
4. MarkdownRenderer - Generates structured Markdown from blocks and facts
"""

import logging
import os
from ixbrl_preprocessor import IXBRLPreprocessor
from xbrl_fact_extractor import XBRLFactExtractor
from visual_block_extractor import VisualBlockExtractor
from markdown_renderer import MarkdownRenderer

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# File paths
INPUT_FILE = "samples/10q_jpm_q3_2024.html"
CLEANED_FILE = "samples/cleaned_10q_jpm_q3_2024.html"
OUTPUT_FILE = "samples/output_jpm_q3_2024.md"

def run_preprocessor():
    """
    Step 1: Run IXBRLPreprocessor to clean the iXBRL HTML file.
    """
    logger.info("=== STEP 1: IXBRLPreprocessor ===")
    
    preprocessor = IXBRLPreprocessor(log_level=logging.DEBUG)
    
    # Load the iXBRL file
    if not preprocessor.load_file(INPUT_FILE):
        logger.error(f"Failed to load file: {INPUT_FILE}")
        return False
    
    # Process the file (remove XBRL tags)
    processed_html = preprocessor.process()
    if not processed_html:
        logger.error("Failed to process the iXBRL file")
        return False
    
    # Save the cleaned HTML
    if not preprocessor.save_to_file(CLEANED_FILE):
        logger.error(f"Failed to save cleaned HTML to: {CLEANED_FILE}")
        return False
    
    logger.info(f"Successfully removed {preprocessor.xbrl_tag_count} XBRL tags")
    logger.info(f"Cleaned HTML saved to: {CLEANED_FILE}")
    return True

def run_fact_extractor():
    """
    Step 2: Run XBRLFactExtractor to extract XBRL facts.
    """
    logger.info("=== STEP 2: XBRLFactExtractor ===")
    
    extractor = XBRLFactExtractor(log_level=logging.DEBUG)
    
    # Load the original iXBRL file (with XBRL tags)
    if not extractor.load_file(INPUT_FILE):
        logger.error(f"Failed to load file: {INPUT_FILE}")
        return None
    
    # Extract facts
    facts = extractor.extract_facts()
    if not facts:
        logger.warning("No XBRL facts were extracted from the file")
        return None
    
    # Log statistics
    total_facts = sum(len(facts[name]) for name in facts)
    unique_contexts = set()
    unique_units = set()
    
    # Collect unique contextRef and unitRef values
    for fact_name, fact_instances in facts.items():
        for fact in fact_instances:
            if "contextRef" in fact:
                unique_contexts.add(fact["contextRef"])
            if "unitRef" in fact:
                unique_units.add(fact["unitRef"])
    
    logger.info(f"Extracted {total_facts} facts across {len(facts)} unique concepts")
    logger.info(f"Found {len(unique_contexts)} unique contextRef values")
    logger.info(f"Found {len(unique_units)} unique unitRef values")
    
    # Log top 5 GAAP concepts (with values)
    logger.info("Top 5 GAAP concepts:")
    us_gaap_facts = {name: instances for name, instances in facts.items() 
                     if name.startswith("us-gaap:")}
    
    sorted_facts = sorted(us_gaap_facts.items(), key=lambda x: len(x[1]), reverse=True)
    
    for i, (fact_name, fact_instances) in enumerate(sorted_facts[:5], 1):
        sample_value = fact_instances[0]["value"] if fact_instances else "N/A"
        logger.info(f"{i}. {fact_name} ({len(fact_instances)} instances) - Sample value: {sample_value}")
    
    return facts

def enhance_visual_blocks(blocks):
    """
    Enhance visual blocks by detecting headings based on font size patterns.
    
    Args:
        blocks: List of visual blocks from the extractor
        
    Returns:
        List of enhanced visual blocks
    """
    logger.info("Enhancing visual blocks to better detect headings")
    
    # Identify potential headings by font size
    font_sizes = {}
    for block in blocks:
        size = block.get("font_size")
        if size:
            font_sizes[size] = font_sizes.get(size, 0) + 1
    
    # Find common font sizes (frequency > 5)
    common_sizes = {size: count for size, count in font_sizes.items() if count > 5}
    
    # Sort them by size (largest first)
    sorted_sizes = sorted(common_sizes.keys(), reverse=True)
    
    if len(sorted_sizes) >= 3:
        # Map the top 3 largest common font sizes to heading levels
        heading_size_mapping = {
            sorted_sizes[0]: "heading",  # H1
            sorted_sizes[1]: "heading",  # H2
            sorted_sizes[2]: "heading",  # H3
        }
        
        # Update block types based on font size
        for block in blocks:
            font_size = block.get("font_size")
            if font_size in heading_size_mapping:
                # Check if it's likely a heading (short text, bold, etc.)
                text = block.get("text", "")
                is_bold = block.get("is_bold", False)
                
                # Heuristic: short text + large font = heading
                if len(text) < 200 and (is_bold or len(text) < 100):
                    block["type"] = heading_size_mapping[font_size]
                    if font_size == sorted_sizes[0]:
                        block["heading_level"] = 1
                    elif font_size == sorted_sizes[1]:
                        block["heading_level"] = 2
                    else:
                        block["heading_level"] = 3
    
    # Count the enhanced headings
    heading_count = sum(1 for block in blocks if block["type"] == "heading")
    logger.info(f"Enhanced blocks: {heading_count} headings detected after enhancement")
    
    return blocks

def run_visual_block_extractor():
    """
    Step 3: Run VisualBlockExtractor to extract visual blocks.
    """
    logger.info("=== STEP 3: VisualBlockExtractor ===")
    
    extractor = VisualBlockExtractor(log_level=logging.DEBUG)
    
    # Load the cleaned HTML (without XBRL tags)
    if not extractor.load_file(CLEANED_FILE):
        logger.error(f"Failed to load file: {CLEANED_FILE}")
        return None
    
    # Extract blocks
    blocks = extractor.extract_blocks()
    if not blocks:
        logger.warning("No visual blocks were extracted from the file")
        return None
    
    # Enhance blocks to better detect headings
    blocks = enhance_visual_blocks(blocks)
    
    # Log statistics
    heading_count = sum(1 for block in blocks if block["type"] == "heading")
    paragraph_count = sum(1 for block in blocks if block["type"] == "paragraph")
    table_count = sum(1 for block in blocks if block["type"] == "table")
    other_count = sum(1 for block in blocks if block["type"] == "other")
    
    logger.info(f"Extracted {len(blocks)} visual blocks from the cleaned HTML")
    logger.info(f"- {heading_count} headings")
    logger.info(f"- {paragraph_count} paragraphs")
    logger.info(f"- {table_count} tables")
    logger.info(f"- {other_count} other blocks")
    
    # Show first 3 blocks as preview
    logger.info("First 3 blocks preview:")
    for i, block in enumerate(blocks[:3], 1):
        logger.info(f"Block {i} - Type: {block['type']}, Tag: {block['tag']}")
        logger.info(f"  Font size: {block['font_size']}, Bold: {block['is_bold']}, Italic: {block['is_italic']}")
        logger.info(f"  Text: {block['text'][:100]}...")
    
    return blocks

def run_markdown_renderer(blocks, facts):
    """
    Step 4: Run MarkdownRenderer to generate Markdown.
    """
    logger.info("=== STEP 4: MarkdownRenderer ===")
    
    renderer = MarkdownRenderer(blocks, facts, log_level=logging.DEBUG)
    
    # Render Markdown
    markdown = renderer.render()
    if not markdown:
        logger.error("Failed to render Markdown")
        return False
    
    # Save Markdown to file
    if not renderer.save_to_file(OUTPUT_FILE):
        logger.error(f"Failed to save Markdown to: {OUTPUT_FILE}")
        return False
    
    # Show preview
    preview = renderer.preview(15)
    logger.info(f"Markdown saved to: {OUTPUT_FILE}")
    logger.info("Markdown preview (first 15 lines):")
    logger.info("\n" + preview)
    
    return True

def run_pipeline():
    """
    Run the complete XBRL parsing pipeline.
    """
    logger.info("Starting XBRL parsing pipeline")
    
    # Step 1: Preprocess the iXBRL file
    if not run_preprocessor():
        logger.error("Pipeline failed at preprocessing step")
        return False
    
    # Step 2: Extract XBRL facts
    facts = run_fact_extractor()
    if facts is None:
        logger.warning("No facts extracted. Continuing pipeline without fact enrichment")
        facts = {}
    
    # Step 3: Extract visual blocks
    blocks = run_visual_block_extractor()
    if not blocks:
        logger.error("Pipeline failed at visual block extraction step")
        return False
    
    # Step 4: Render Markdown
    if not run_markdown_renderer(blocks, facts):
        logger.error("Pipeline failed at Markdown rendering step")
        return False
    
    logger.info("XBRL parsing pipeline completed successfully")
    return True

if __name__ == "__main__":
    run_pipeline() 