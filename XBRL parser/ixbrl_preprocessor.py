import logging
import os
from bs4 import BeautifulSoup
from typing import List, Set, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class IXBRLPreprocessor:
    """
    Preprocessor for iXBRL (Inline XBRL) HTML files that removes XBRL tags
    while preserving their inner content.
    """
    
    def __init__(self, log_level: int = logging.INFO):
        """
        Initialize the preprocessor.
        
        Args:
            log_level: Logging level (default: logging.INFO)
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        self.soup = None
        self.xbrl_tag_count = 0
        self.xbrl_namespaces = set()
        
    def load_file(self, file_path: str) -> bool:
        """
        Load an iXBRL file from the specified path.
        
        Args:
            file_path: Path to the iXBRL file
            
        Returns:
            bool: True if file was loaded successfully, False otherwise
        """
        self.logger.info(f"Loading iXBRL file: {file_path}")
        
        if not os.path.exists(file_path):
            self.logger.error(f"File not found: {file_path}")
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                html_content = file.read()
                
            self.soup = BeautifulSoup(html_content, 'html.parser')
            self.logger.info(f"Successfully loaded file: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading file {file_path}: {str(e)}")
            return False
            
    def _identify_xbrl_namespaces(self) -> Set[str]:
        """
        Identify all XBRL namespaces used in the document.
        
        Returns:
            Set of namespace prefixes used for XBRL tags
        """
        if not self.soup:
            self.logger.warning("No file loaded, cannot identify namespaces")
            return set()
            
        self.logger.debug("Identifying XBRL namespaces")
        namespaces = set()
        
        # Look for common XBRL namespace prefixes in the HTML tag attributes
        html_tag = self.soup.find('html')
        if html_tag:
            for attr_name, attr_value in html_tag.attrs.items():
                if attr_name.startswith('xmlns:'):
                    ns_prefix = attr_name.split(':', 1)[1]
                    if 'xbrl' in attr_value.lower():
                        namespaces.add(ns_prefix)
                        self.logger.debug(f"Found XBRL namespace: {ns_prefix} = {attr_value}")
        
        # Always include common XBRL namespaces
        default_ns = {"ix", "xbrli", "xbrl"}
        namespaces.update(default_ns)
        
        self.xbrl_namespaces = namespaces
        self.logger.info(f"Identified {len(namespaces)} XBRL namespaces: {', '.join(namespaces)}")
        return namespaces
            
    def _find_xbrl_tags(self, namespaces: Set[str]) -> List:
        """
        Find all XBRL tags in the document based on the given namespaces.
        
        Args:
            namespaces: Set of XBRL namespace prefixes to look for
            
        Returns:
            List of BeautifulSoup Tag objects
        """
        all_tags = []
        
        for ns in namespaces:
            # Find all tags with this namespace (using direct tag name matching)
            tags = self.soup.find_all(lambda tag: tag.name and ":" in tag.name and tag.name.split(":", 1)[0] == ns)
            
            self.logger.debug(f"Found {len(tags)} tags with namespace '{ns}'")
            all_tags.extend(tags)
            
        return all_tags
            
    def process(self) -> Optional[str]:
        """
        Process the loaded iXBRL file by removing XBRL tags but preserving their content.
        Handles nested XBRL tags by processing repeatedly until no more tags are found.
        
        Returns:
            str: Processed HTML content with XBRL tags removed, or None if processing failed
        """
        if not self.soup:
            self.logger.error("No file loaded, cannot process")
            return None
            
        self.logger.info("Starting iXBRL processing")
        
        # Identify XBRL namespaces
        namespaces = self._identify_xbrl_namespaces()
        
        # Reset tag counter
        self.xbrl_tag_count = 0
        
        # Process repeatedly until no more XBRL tags are found
        max_iterations = 5  # Prevent infinite loops
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Find all XBRL tags
            tags = self._find_xbrl_tags(namespaces)
            
            if not tags:
                self.logger.debug(f"No more XBRL tags found after {iteration} iterations")
                break
                
            self.logger.debug(f"Iteration {iteration}: Processing {len(tags)} XBRL tags")
            self.xbrl_tag_count += len(tags)
            
            # Replace each tag with its contents
            for tag in tags:
                # Extract the tag's content
                content = tag.decode_contents()
                
                # Create a new fragment from the content
                new_content = BeautifulSoup("<span>" + content + "</span>", 'html.parser').span
                
                # Replace the tag with its content
                if new_content and new_content.contents:
                    tag.replace_with(*new_content.contents)
                else:
                    # If no content, just remove the tag
                    tag.decompose()
        
        if iteration >= max_iterations:
            self.logger.warning(f"Reached maximum iteration limit ({max_iterations}). There may still be XBRL tags in the document.")
            
        self.logger.info(f"Completed processing: removed {self.xbrl_tag_count} XBRL tags in {iteration} iterations")
        return str(self.soup)
    
    def save_to_file(self, output_path: str) -> bool:
        """
        Save the processed HTML content to a file.
        
        Args:
            output_path: Path where the processed HTML will be saved
            
        Returns:
            bool: True if file was saved successfully, False otherwise
        """
        if not self.soup:
            self.logger.error("No file processed, cannot save")
            return False
            
        try:
            with open(output_path, 'w', encoding='utf-8') as file:
                file.write(str(self.soup))
                
            self.logger.info(f"Successfully saved processed file to: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving file to {output_path}: {str(e)}")
            return False

    def get_processed_html(self) -> Optional[str]:
        """
        Get the processed HTML content as a string.
        
        Returns:
            str: Processed HTML content, or None if no file was processed
        """
        if not self.soup:
            self.logger.warning("No file processed, cannot return HTML")
            return None
            
        return str(self.soup) 