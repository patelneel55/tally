import logging
from bs4 import BeautifulSoup
import re
from typing import Dict, List, Optional, Union, Any

class VisualBlockExtractor:
    """
    Extracts visual content blocks from cleaned iXBRL HTML files.
    
    This class parses HTML documents and identifies block-level elements such as
    headings, paragraphs, tables, and other content blocks, along with their
    styling information.
    """
    
    # Default font size mappings for heading elements
    DEFAULT_FONT_SIZES = {
        "h1": 24,
        "h2": 22,
        "h3": 20,
        "h4": 18,
        "h5": 16,
        "h6": 14,
        "p": 12,
        "div": 12,
        "table": 12
    }
    
    # Mapping of HTML tags to block types
    BLOCK_TYPE_MAPPING = {
        "h1": "heading",
        "h2": "heading",
        "h3": "heading",
        "h4": "heading",
        "h5": "heading",
        "h6": "heading",
        "p": "paragraph",
        "div": "other",
        "table": "table",
        "ul": "other",
        "ol": "other",
        "li": "other",
        "pre": "other",
        "blockquote": "other"
    }
    
    def __init__(self, log_level: int = logging.INFO):
        """
        Initialize the VisualBlockExtractor.
        
        Args:
            log_level: Logging level (default: logging.INFO)
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        self.soup = None
        self.blocks = []
        self.block_count = 0
        self.block_types = {}
    
    def load_html(self, html_content: str) -> bool:
        """
        Load HTML content for processing.
        
        Args:
            html_content: HTML content as a string
            
        Returns:
            bool: True if HTML was loaded successfully, False otherwise
        """
        self.logger.info("Loading HTML content for processing")
        try:
            self.soup = BeautifulSoup(html_content, 'html.parser')
            self.logger.debug("HTML content loaded successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error loading HTML content: {str(e)}")
            return False
    
    def load_file(self, file_path: str) -> bool:
        """
        Load HTML from a file.
        
        Args:
            file_path: Path to the HTML file
            
        Returns:
            bool: True if file was loaded successfully, False otherwise
        """
        self.logger.info(f"Loading HTML file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                html_content = file.read()
            return self.load_html(html_content)
        except Exception as e:
            self.logger.error(f"Error loading file {file_path}: {str(e)}")
            return False
    
    def _extract_text(self, element) -> str:
        """
        Extract clean text from an element, preserving only the visible content.
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            str: Cleaned text content
        """
        # Get text with spacing preserved
        text = element.get_text(separator=' ', strip=True)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _extract_font_size(self, element) -> Optional[int]:
        """
        Extract font size from element's style or tag name.
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            int or None: Font size if found, default value based on tag, or None
        """
        # Try to extract from inline style
        style = element.get('style', '')
        if style:
            # Look for font-size in the style attribute
            font_size_match = re.search(r'font-size\s*:\s*(\d+)px', style)
            if font_size_match:
                return int(font_size_match.group(1))
        
        # If no inline style, use tag-based default
        tag_name = element.name.lower()
        return self.DEFAULT_FONT_SIZES.get(tag_name)
    
    def _is_bold(self, element) -> bool:
        """
        Check if an element or its parents have bold styling.
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            bool: True if element has bold styling, False otherwise
        """
        # Check for bold tags within or as parent
        bold_tags = element.find_all(['b', 'strong'])
        if bold_tags or element.name in ['b', 'strong']:
            return True
        
        # Check for font-weight in style
        style = element.get('style', '')
        if 'font-weight' in style and ('bold' in style or '700' in style or '800' in style or '900' in style):
            return True
        
        return False
    
    def _is_italic(self, element) -> bool:
        """
        Check if an element or its parents have italic styling.
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            bool: True if element has italic styling, False otherwise
        """
        # Check for italic tags within or as parent
        italic_tags = element.find_all(['i', 'em'])
        if italic_tags or element.name in ['i', 'em']:
            return True
        
        # Check for font-style in style
        style = element.get('style', '')
        if 'font-style' in style and 'italic' in style:
            return True
        
        return False
    
    def _is_underlined(self, element) -> bool:
        """
        Check if an element or its parents have underline styling.
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            bool: True if element has underline styling, False otherwise
        """
        # Check for underline tags within or as parent
        underline_tags = element.find_all('u')
        if underline_tags or element.name == 'u':
            return True
        
        # Check for text-decoration in style
        style = element.get('style', '')
        if 'text-decoration' in style and 'underline' in style:
            return True
        
        return False
    
    def _get_block_type(self, tag_name: str) -> str:
        """
        Determine the block type based on tag name.
        
        Args:
            tag_name: HTML tag name
            
        Returns:
            str: Block type (heading, paragraph, table, or other)
        """
        return self.BLOCK_TYPE_MAPPING.get(tag_name.lower(), "other")
    
    def _is_block_element(self, element) -> bool:
        """
        Check if an element is a block-level element of interest.
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            bool: True if element is a block element, False otherwise
        """
        if not element.name:
            return False
            
        # Check if tag is in our mapping
        tag_name = element.name.lower()
        return tag_name in self.BLOCK_TYPE_MAPPING
    
    def _is_text_only_div(self, element) -> bool:
        """
        Check if a div element contains only text or inline elements.
        
        Args:
            element: BeautifulSoup div element
            
        Returns:
            bool: True if div has only text/inline content, False otherwise
        """
        if element.name != 'div':
            return False
            
        # Check for block elements inside
        for child in element.children:
            if child.name and self._is_block_element(child):
                return False
                
        # If reached here, div only has text or inline elements
        return bool(self._extract_text(element).strip())
    
    def extract_blocks(self) -> List[Dict[str, Any]]:
        """
        Extract visual content blocks from the loaded HTML.
        
        Returns:
            List[Dict]: List of dictionaries containing block information
        """
        if not self.soup:
            self.logger.error("No HTML content loaded, cannot extract blocks")
            return []
            
        self.logger.info("Extracting visual content blocks")
        
        self.blocks = []
        self.block_count = 0
        self.block_types = {}
        
        # Find all heading elements
        headings = self.soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        
        # Find all paragraph elements
        paragraphs = self.soup.find_all('p')
        
        # Find all tables
        tables = self.soup.find_all('table')
        
        # Find text-only div elements
        divs = [div for div in self.soup.find_all('div') if self._is_text_only_div(div)]
        
        # Process all blocks in their DOM order
        all_elements = headings + paragraphs + tables + divs
        
        # Sort elements by their position in the document
        # This is a simplification - in a real DOM traversal we would want to maintain the exact order
        all_elements.sort(key=lambda x: str(x))
        
        # Process each element
        for idx, element in enumerate(all_elements, 1):
            tag_name = element.name
            block_type = self._get_block_type(tag_name)
            
            # Skip empty elements
            text = self._extract_text(element)
            if not text and block_type != "table":  # Allow empty tables as they might have structure
                self.logger.debug(f"Skipping empty {tag_name} element")
                continue
                
            # Create block dictionary
            block = {
                "type": block_type,
                "tag": tag_name,
                "text": text,
                "font_size": self._extract_font_size(element),
                "is_bold": self._is_bold(element),
                "is_italic": self._is_italic(element),
                "is_underlined": self._is_underlined(element),
                "line_number": idx
            }
            
            # Update block type counter
            self.block_types[block_type] = self.block_types.get(block_type, 0) + 1
            
            # Add block to list
            self.blocks.append(block)
            
        self.block_count = len(self.blocks)
        
        # Log summary of extracted blocks
        self.logger.info(f"Extracted {self.block_count} visual content blocks")
        for block_type, count in self.block_types.items():
            self.logger.info(f"- {block_type}: {count} blocks")
            
        # Log the first 3 blocks for manual review
        for i, block in enumerate(self.blocks[:3]):
            self.logger.info(f"Block {i+1} sample: {block['type']} (tag: {block['tag']}) - '{block['text'][:50]}...'")
            
        return self.blocks
    
    def get_blocks(self) -> List[Dict[str, Any]]:
        """
        Get the extracted blocks.
        
        Returns:
            List[Dict]: List of block dictionaries
        """
        return self.blocks 