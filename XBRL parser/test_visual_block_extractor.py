#!/usr/bin/env python3
# test_visual_block_extractor.py

import logging
import json
from visual_block_extractor import VisualBlockExtractor

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_extractor_test():
    """
    Test the VisualBlockExtractor with a cleaned iXBRL HTML file.
    """
    # Path to the cleaned iXBRL file (already processed by IXBRLPreprocessor)
    input_file = "cleaned_sample_ixbrl.html"
    
    # Create and configure the extractor
    extractor = VisualBlockExtractor(log_level=logging.DEBUG)
    
    # Load the HTML file
    if not extractor.load_file(input_file):
        logger.error(f"Failed to load file: {input_file}")
        return
    
    # Extract visual blocks
    blocks = extractor.extract_blocks()
    
    if not blocks:
        logger.warning("No blocks were extracted from the file")
        return
    
    # Output statistics
    logger.info(f"Successfully extracted {len(blocks)} blocks from {input_file}")
    
    # Save blocks to JSON for later use (optional)
    output_file = "visual_blocks.json"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(blocks, f, indent=2)
        logger.info(f"Saved extracted blocks to {output_file}")
    except Exception as e:
        logger.error(f"Error saving blocks to file: {str(e)}")
    
    # Analyze block types
    analyze_blocks(blocks)

def analyze_blocks(blocks):
    """
    Perform additional analysis on the extracted blocks.
    
    Args:
        blocks: List of extracted block dictionaries
    """
    # Count blocks by type
    type_counts = {}
    for block in blocks:
        block_type = block["type"]
        type_counts[block_type] = type_counts.get(block_type, 0) + 1
    
    logger.info("Block type distribution:")
    for block_type, count in type_counts.items():
        logger.info(f"  - {block_type}: {count} blocks")
    
    # Count styled blocks
    bold_count = sum(1 for block in blocks if block["is_bold"])
    italic_count = sum(1 for block in blocks if block["is_italic"])
    underlined_count = sum(1 for block in blocks if block["is_underlined"])
    
    logger.info("Text styling:")
    logger.info(f"  - Bold text: {bold_count} blocks")
    logger.info(f"  - Italic text: {italic_count} blocks")
    logger.info(f"  - Underlined text: {underlined_count} blocks")

if __name__ == "__main__":
    run_extractor_test() 