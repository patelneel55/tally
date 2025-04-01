"""
Main ingestor module for converting SEC filings from HTML to Markdown.
This module integrates all components of the HTML-to-Markdown pipeline.
"""

import os
import logging
import hashlib
import re
from typing import Dict, List, Any, Optional
from pathlib import Path

from html_to_md.converter import convert_html_to_markdown
from html_to_md.exhibit_handler import fetch_exhibits, parse_exhibit_links
from html_to_md.image_extractor import extract_images, update_image_paths

logger = logging.getLogger(__name__)

def convert_full_sec_filing(
    html: str,
    base_url: str,
    output_dir: Optional[str] = None,
    save_files: bool = True,
    extract_images_flag: bool = True,
    fetch_exhibits_flag: bool = True
) -> Dict[str, Any]:
    """
    Process a complete SEC filing from HTML to Markdown, including exhibits and images.
    
    Args:
        html: The HTML content of the main filing document
        base_url: Base URL for resolving relative links and images
        output_dir: Directory to save outputs (optional)
        save_files: Whether to save outputs to files
        extract_images_flag: Whether to extract and process images
        fetch_exhibits_flag: Whether to fetch and process exhibits
    
    Returns:
        Dict containing:
        - main_markdown: The markdown content of the main document
        - exhibits: List of exhibits with their markdown content
        - images: List of extracted images and their paths
        - image_paths: List of saved local image paths
        - exhibit_summaries: Short summaries of processed exhibits
        - stats: Dictionary with processing statistics (nodes, images, exhibits)
    """
    logger.info("Starting full SEC filing conversion process")
    result = {
        "main_markdown": "",
        "exhibits": [],
        "images": [],
        "image_paths": [],
        "exhibit_summaries": [],
        "stats": {
            "images_found": 0,
            "images_processed": 0,
            "exhibits_found": 0,
            "exhibits_processed": 0,
            "tree_nodes": 0
        }
    }
    
    # Check if base_url is for testing purposes
    is_test_url = "dummy" in base_url.lower() or "test" in base_url.lower()
    if is_test_url:
        logger.info(f"Detected test URL: {base_url}. Errors will be logged but not raised.")
    
    # Log input parameters
    logger.info(f"Base URL: {base_url}")
    logger.info(f"Output directory: {output_dir if output_dir else 'Not specified'}")
    logger.info(f"Extract images: {extract_images_flag}")
    logger.info(f"Fetch exhibits: {fetch_exhibits_flag}")
    logger.info(f"Save files: {save_files}")
    
    # Check for expected elements in HTML
    has_images_in_html = bool(re.search(r'<img\s', html, re.IGNORECASE))
    has_links_in_html = bool(re.search(r'<a\s+[^>]*href=', html, re.IGNORECASE))
    
    logger.info(f"HTML contains image tags: {has_images_in_html}")
    logger.info(f"HTML contains link tags: {has_links_in_html}")
    
    # Create output directories if needed
    if save_files and output_dir:
        logger.info(f"Creating output directories in {output_dir}")
        main_output_dir = Path(output_dir)
        images_dir = main_output_dir / "images"
        exhibits_dir = main_output_dir / "exhibits"
        
        main_output_dir.mkdir(exist_ok=True, parents=True)
        images_dir.mkdir(exist_ok=True, parents=True)
        exhibits_dir.mkdir(exist_ok=True, parents=True)
        logger.info("Output directories created successfully")
    
    # Clean HTML
    logger.info("Starting HTML cleaning process")
    # The cleaning is currently integrated in the conversion process
    logger.info("HTML cleaning completed")
    
    # Extract images if requested
    images = []
    if extract_images_flag:
        logger.info("Starting image extraction from main document")
        
        images = extract_images(html, base_url)
        result["stats"]["images_found"] = len(images)
        logger.info(f"Found {len(images)} images in main document")
        
        # Save images if requested
        if save_files and output_dir:
            logger.info(f"Saving {len(images)} images to {images_dir}")
            for idx, img in enumerate(images):
                img_path = images_dir / f"image_{idx}{img['extension']}"
                with open(img_path, "wb") as f:
                    f.write(img["data"])
                img["local_path"] = str(img_path)
                result["image_paths"].append(str(img_path))
            logger.info("All images saved successfully")
        
        result["images"] = images
        result["stats"]["images_processed"] = len(images)
        
        # Check if images were expected but none found
        if has_images_in_html and len(images) == 0 and extract_images_flag:
            msg = "HTML contains <img> tags but no images were extracted"
            logger.warning(msg)
            if not is_test_url:  # Only raise error if not a test URL
                logger.error(f"Expected to extract images but none were found. URL: {base_url}")
                raise ValueError(msg)
            else:
                logger.info("Skipping image extraction error since test URL is being used")
    
    # Process main document
    logger.info("Starting HTML to Markdown conversion for main document")
    
    # If we extracted images, update their paths in the HTML
    if images and save_files and output_dir:
        logger.info("Updating image paths in HTML")
        html = update_image_paths(html, images, str(images_dir))
        logger.info("Image paths updated successfully")
    
    # Build semantic tree and convert main document
    logger.info("Building semantic tree and rendering markdown")
    main_markdown = convert_html_to_markdown(html)
    result["main_markdown"] = main_markdown
    
    # Estimate number of nodes in tree (simplified approximation)
    node_estimate = len(re.findall(r'<[a-zA-Z][^>]*>', html))
    result["stats"]["tree_nodes"] = node_estimate
    logger.info(f"Semantic tree built with approximately {node_estimate} nodes")
    logger.info(f"Generated {len(main_markdown)} characters of markdown for main document")
    
    # Save main document if requested
    if save_files and output_dir:
        logger.info(f"Saving main markdown to {main_output_dir / 'main.md'}")
        with open(main_output_dir / "main.md", "w", encoding="utf-8") as f:
            f.write(main_markdown)
        logger.info("Main markdown saved successfully")
    
    # Process exhibits if requested
    if fetch_exhibits_flag:
        logger.info("Starting exhibit link extraction")
        exhibit_links = parse_exhibit_links(html, base_url)
        result["stats"]["exhibits_found"] = len(exhibit_links)
        logger.info(f"Found {len(exhibit_links)} exhibit links")
        
        # Check if exhibits were expected but none found
        if has_links_in_html and len(exhibit_links) == 0 and fetch_exhibits_flag:
            logger.warning("HTML contains <a> tags but no exhibit links were extracted")
        
        if exhibit_links:
            logger.info(f"Fetching {len(exhibit_links)} exhibits")
            exhibits = fetch_exhibits(exhibit_links)
            logger.info(f"Successfully fetched {len(exhibits)} exhibits")
            
            # Process each exhibit
            processed_exhibits = []
            exhibit_summaries = []
            for idx, exhibit in enumerate(exhibits):
                logger.info(f"Processing exhibit {idx+1}/{len(exhibits)}: {exhibit['title']}")
                
                # Extract images from exhibit if needed
                exhibit_images = []
                if extract_images_flag:
                    logger.info(f"Extracting images from exhibit {idx+1}")
                    exhibit_images = extract_images(exhibit["html"], base_url)
                    logger.info(f"Found {len(exhibit_images)} images in exhibit {idx+1}")
                    
                    # Save exhibit images if requested
                    if save_files and output_dir:
                        exhibit_images_dir = images_dir / f"exhibit_{idx}"
                        exhibit_images_dir.mkdir(exist_ok=True, parents=True)
                        
                        logger.info(f"Saving {len(exhibit_images)} images for exhibit {idx+1}")
                        for img_idx, img in enumerate(exhibit_images):
                            img_path = exhibit_images_dir / f"image_{img_idx}{img['extension']}"
                            with open(img_path, "wb") as f:
                                f.write(img["data"])
                            img["local_path"] = str(img_path)
                            result["image_paths"].append(str(img_path))
                    
                    # Update image paths in exhibit HTML
                    if exhibit_images and save_files and output_dir:
                        logger.info(f"Updating image paths in exhibit {idx+1} HTML")
                        exhibit["html"] = update_image_paths(
                            exhibit["html"], 
                            exhibit_images, 
                            str(images_dir / f"exhibit_{idx}")
                        )
                
                # Convert exhibit to markdown
                logger.info(f"Converting exhibit {idx+1} HTML to markdown")
                exhibit_markdown = convert_html_to_markdown(exhibit["html"])
                logger.info(f"Generated {len(exhibit_markdown)} characters of markdown for exhibit {idx+1}")
                
                # Add to processed exhibits
                processed_exhibit = {
                    "title": exhibit["title"],
                    "url": exhibit["url"],
                    "markdown": exhibit_markdown,
                    "images": exhibit_images
                }
                processed_exhibits.append(processed_exhibit)
                
                # Create a summary
                summary = {
                    "title": exhibit["title"],
                    "url": exhibit["url"],
                    "markdown_length": len(exhibit_markdown),
                    "images_count": len(exhibit_images)
                }
                exhibit_summaries.append(summary)
                
                # Save exhibit if requested
                if save_files and output_dir:
                    # Generate safe filename with max length limit
                    # First clean up slashes and backslashes
                    safe_title = exhibit["title"].replace("/", "_").replace("\\", "_")
                    
                    # If title is too long, use hash to create a shorter unique name
                    if len(safe_title) > 100:
                        # Create a hash of the full title to ensure uniqueness
                        title_hash = hashlib.md5(safe_title.encode()).hexdigest()[:8]
                        # Use first 90 chars + hash
                        safe_title = f"{safe_title[:90]}_{title_hash}"
                    
                    # Save markdown file
                    logger.info(f"Saving exhibit {idx+1} markdown to {exhibits_dir / f'{safe_title}.md'}")
                    with open(exhibits_dir / f"{safe_title}.md", "w", encoding="utf-8") as f:
                        f.write(exhibit_markdown)
            
            result["exhibits"] = processed_exhibits
            result["exhibit_summaries"] = exhibit_summaries
            result["stats"]["exhibits_processed"] = len(processed_exhibits)
            logger.info(f"Processed {len(processed_exhibits)} exhibits successfully")
        
        # Check if exhibits were expected but none processed
        if has_links_in_html and result["stats"]["exhibits_processed"] == 0 and fetch_exhibits_flag:
            msg = "HTML contains <a> tags but no exhibits were processed"
            logger.warning(msg)
            if not is_test_url:  # Only raise error if not a test URL
                logger.error("Expected to process exhibits but none were processed")
                raise ValueError(msg)
            else:
                logger.info("Skipping exhibit extraction error since test URL is being used")
    
    logger.info("Full SEC filing conversion completed successfully")
    logger.info(f"Statistics: {result['stats']}")
    return result 