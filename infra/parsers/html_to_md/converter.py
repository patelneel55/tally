"""
Converter module for HTML to Markdown conversion.
Provides the main entry point function for the package.
"""
import os
import re
from typing import Dict, List, Tuple, Optional
from bs4 import BeautifulSoup
from pathlib import Path

from html_to_md.parser import (
    clean_html,
    build_semantic_tree,
    render_tree_to_markdown
)
from html_to_md.image_extractor import extract_and_replace_images
from html_to_md.exhibit_handler import extract_exhibit_links, fetch_and_parse_exhibits
from html_to_md.markdown_cleaner import clean_markdown


def convert_html_to_markdown(html: str) -> str:
    """
    Convert HTML content to Markdown format.
    
    This function serves as the main entry point for the HTML to Markdown
    conversion process, combining cleaning, parsing, tree building and 
    rendering steps.
    
    Args:
        html: Raw HTML input as a string
        
    Returns:
        Markdown formatted string
    """
    # Step 1: Clean the HTML by removing unwanted elements
    cleaned_html = clean_html(html)
    
    # Step 2: Parse the cleaned HTML with BeautifulSoup
    soup = BeautifulSoup(cleaned_html, 'html.parser')
    
    # Step 3: Build a semantic tree from the parsed HTML
    tree = build_semantic_tree(soup)
    
    # Step 4: Render the semantic tree to Markdown
    markdown = render_tree_to_markdown(tree)
    
    # Step 5: Clean and standardize the Markdown output
    cleaned_markdown = clean_markdown(markdown)
    
    return cleaned_markdown 


def convert_full_sec_filing(html: str, base_url: str, output_dir: str, save_files: bool = True) -> Dict:
    """
    Convert a full SEC filing including the main document, images, and exhibits.
    
    Args:
        html: Raw HTML of the SEC filing
        base_url: Base URL of the filing, used for resolving relative links
        output_dir: Directory to save output files
        save_files: Whether to save files to disk (default: True)
        
    Returns:
        Dictionary containing:
        - main_markdown: Converted main document
        - images: List of extracted image paths
        - exhibits: List of exhibit information dictionaries
    """
    # Create output directory structure
    main_output_dir = Path(output_dir)
    images_dir = main_output_dir / "images"
    exhibits_dir = main_output_dir / "exhibits"
    
    if save_files:
        main_output_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(exist_ok=True)
        exhibits_dir.mkdir(exist_ok=True)

    # Step 1: Clean the HTML
    cleaned_html = clean_html(html)
    
    # Step 2: Extract and replace images
    html_with_img_refs, image_paths = extract_and_replace_images(
        cleaned_html, 
        str(images_dir),
        "sec_img"
    )
    
    # Get relative image paths for return value
    relative_image_paths = [os.path.relpath(path, output_dir) for path in image_paths]
    
    # Step 3: Parse the main document to markdown
    soup = BeautifulSoup(html_with_img_refs, 'html.parser')
    semantic_tree = build_semantic_tree(soup)
    main_markdown = render_tree_to_markdown(semantic_tree)
    
    # Step 4: Clean and standardize the markdown
    main_markdown = clean_markdown(main_markdown)
    
    # Step 5: Extract exhibit links
    exhibit_links = extract_exhibit_links(cleaned_html, base_url)
    
    # Step 6: Fetch and parse exhibits
    # Define the parser function to pass to fetch_and_parse_exhibits
    def html_to_md_parser(html_content: str) -> str:
        cleaned = clean_html(html_content)
        # Also extract images from exhibits
        exhibit_soup = BeautifulSoup(cleaned, 'html.parser')
        exhibit_tree = build_semantic_tree(exhibit_soup)
        exhibit_md = render_tree_to_markdown(exhibit_tree)
        # Clean the exhibit markdown too
        return clean_markdown(exhibit_md)
    
    exhibits = fetch_and_parse_exhibits(
        exhibit_links, 
        str(exhibits_dir) if save_files else "", 
        html_to_md_parser
    )
    
    # Step 7: Inject exhibit references into the main markdown if there are any
    if exhibits:
        # Add a section header for exhibits
        exhibit_section = "\n\n## Exhibits\n\n"
        
        # Add entries for each exhibit
        for exhibit in exhibits:
            title = exhibit.get("title", "Untitled Exhibit")
            # Create a reference to the exhibit
            exhibit_section += f"- [{title}](./exhibits/{re.sub(r'[^\w\-\.]', '_', title)}.md)\n"
        
        # Append to main markdown
        main_markdown += exhibit_section
    
    # Step 8: Save the main markdown file if requested
    if save_files:
        main_file_path = main_output_dir / "main.md"
        with open(main_file_path, "w", encoding="utf-8") as f:
            f.write(main_markdown)
    
    # Step 9: Prepare the return structure
    result = {
        "main_markdown": main_markdown,
        "images": relative_image_paths,
        "exhibits": exhibits
    }
    
    return result 