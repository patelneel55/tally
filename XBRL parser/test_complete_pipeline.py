#!/usr/bin/env python3
# test_complete_pipeline.py

import logging
import json
from ixbrl_preprocessor import IXBRLPreprocessor
from visual_block_extractor import VisualBlockExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_pipeline():
    """
    Demonstrate the complete pipeline:
    1. Load and preprocess iXBRL file
    2. Extract visual blocks from cleaned HTML
    3. Output structured content
    """
    # Source iXBRL file
    ixbrl_file = "sample_ixbrl.html"
    
    # Step 1: Preprocess the iXBRL file
    logger.info("STEP 1: Preprocessing iXBRL file")
    preprocessor = IXBRLPreprocessor(log_level=logging.INFO)
    
    if not preprocessor.load_file(ixbrl_file):
        logger.error(f"Failed to load iXBRL file: {ixbrl_file}")
        return
        
    # Process the file to remove XBRL tags
    processed_html = preprocessor.process()
    if not processed_html:
        logger.error("Failed to process iXBRL file")
        return
        
    logger.info(f"Successfully removed {preprocessor.xbrl_tag_count} XBRL tags")
    
    # Temporary file for cleaned HTML
    cleaned_file = "pipeline_cleaned.html"
    preprocessor.save_to_file(cleaned_file)
    logger.info(f"Saved cleaned HTML to {cleaned_file}")
    
    # Step 2: Extract visual blocks
    logger.info("STEP 2: Extracting visual blocks")
    extractor = VisualBlockExtractor(log_level=logging.INFO)
    
    # Load the cleaned HTML
    if not extractor.load_file(cleaned_file):
        logger.error(f"Failed to load cleaned HTML file: {cleaned_file}")
        return
        
    # Extract visual blocks
    blocks = extractor.extract_blocks()
    if not blocks:
        logger.error("No blocks were extracted")
        return
        
    # Step 3: Output structured content
    logger.info("STEP 3: Generating structured output")
    
    # Save blocks to JSON
    output_file = "pipeline_blocks.json"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(blocks, f, indent=2)
        logger.info(f"Saved extracted blocks to {output_file}")
    except Exception as e:
        logger.error(f"Error saving blocks to file: {str(e)}")
    
    # Display pipeline summary
    heading_count = sum(1 for block in blocks if block["type"] == "heading")
    paragraph_count = sum(1 for block in blocks if block["type"] == "paragraph")
    table_count = sum(1 for block in blocks if block["type"] == "table")
    
    logger.info("Pipeline summary:")
    logger.info(f"  - Processed iXBRL file: {ixbrl_file}")
    logger.info(f"  - Removed XBRL tags: {preprocessor.xbrl_tag_count}")
    logger.info(f"  - Extracted blocks: {len(blocks)}")
    logger.info(f"    - Headings: {heading_count}")
    logger.info(f"    - Paragraphs: {paragraph_count}")
    logger.info(f"    - Tables: {table_count}")
    logger.info(f"    - Other blocks: {len(blocks) - heading_count - paragraph_count - table_count}")
    
    # Show sample of the first heading and paragraph
    first_heading = next((block for block in blocks if block["type"] == "heading"), None)
    if first_heading:
        logger.info(f"Sample heading: {first_heading['text'][:50]}...")
        
    first_paragraph = next((block for block in blocks if block["type"] == "paragraph"), None)
    if first_paragraph:
        logger.info(f"Sample paragraph: {first_paragraph['text'][:50]}...")

if __name__ == "__main__":
    run_pipeline() 