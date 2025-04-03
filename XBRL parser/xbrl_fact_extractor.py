import logging
import os
from bs4 import BeautifulSoup
import re
from typing import Dict, List, Optional, Any


class XBRLFactExtractor:
    """
    Extracts XBRL facts from iXBRL (inline XBRL) HTML files.
    
    This class parses an original iXBRL HTML file and extracts all facts embedded within
    `<ix:nonFraction>` and `<ix:nonNumeric>` tags, which contain machine-readable values
    associated with GAAP/IFRS concepts.
    """
    
    def __init__(self, log_level: int = logging.INFO):
        """
        Initialize the XBRLFactExtractor.
        
        Args:
            log_level: Logging level (default: logging.INFO)
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        self.soup = None
        self.facts = {}  # Dictionary to store extracted facts
        
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
    
    def extract_facts(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract all XBRL facts from the loaded iXBRL file.
        
        Returns:
            Dict: Dictionary of extracted facts organized by concept name
        """
        if not self.soup:
            self.logger.error("No file loaded, cannot extract facts")
            return {}
        
        self.logger.info("Starting XBRL fact extraction")
        self.facts = {}
        
        # Find tags more robustly - find all tags with names ending in nonFraction/nonNumeric
        # regardless of namespace prefix
        non_fraction_pattern = re.compile(r'.*nonfraction$', re.IGNORECASE)
        non_numeric_pattern = re.compile(r'.*nonnumeric$', re.IGNORECASE)
        
        # Find all tags matching the patterns
        non_fraction_tags = self.soup.find_all(lambda tag: tag.name and 
                                              non_fraction_pattern.match(tag.name.lower()))
        self.logger.info(f"Found {len(non_fraction_tags)} nonFraction tags")
        
        non_numeric_tags = self.soup.find_all(lambda tag: tag.name and 
                                             non_numeric_pattern.match(tag.name.lower()))
        self.logger.info(f"Found {len(non_numeric_tags)} nonNumeric tags")
        
        # Fall back to direct tag search if the pattern approach didn't find any tags
        if len(non_fraction_tags) == 0:
            non_fraction_tags = self.soup.find_all(['ix:nonfraction', 'ix:nonFraction', 'ix:NonFraction'])
            self.logger.info(f"Fall back: Found {len(non_fraction_tags)} explicit ix:nonFraction tags")
            
        if len(non_numeric_tags) == 0:
            non_numeric_tags = self.soup.find_all(['ix:nonnumeric', 'ix:nonNumeric', 'ix:NonNumeric'])
            self.logger.info(f"Fall back: Found {len(non_numeric_tags)} explicit ix:nonNumeric tags")
        
        # Process all tags
        total_facts = 0
        
        # Process nonFraction tags
        for tag in non_fraction_tags:
            self._process_tag(tag, "ix:nonFraction")
            total_facts += 1
            
        # Process nonNumeric tags
        for tag in non_numeric_tags:
            self._process_tag(tag, "ix:nonNumeric")
            total_facts += 1
        
        # Log statistics
        self.logger.info(f"Extracted {total_facts} facts total")
        self.logger.info(f"Found {len(self.facts)} unique concept names")
        
        # Log unique contextRef and unitRef values
        context_refs = set()
        unit_refs = set()
        
        for facts_list in self.facts.values():
            for fact in facts_list:
                if "contextRef" in fact:
                    context_refs.add(fact["contextRef"])
                if "unitRef" in fact:
                    unit_refs.add(fact["unitRef"])
        
        self.logger.info(f"Found {len(context_refs)} unique contextRef values")
        self.logger.info(f"Found {len(unit_refs)} unique unitRef values")
        
        # Log top 5 name keys with their values
        if self.facts:
            self.logger.info("Top 5 concept names with their values:")
            for i, (name, facts_list) in enumerate(list(self.facts.items())[:5]):
                fact_values = [f["value"] for f in facts_list]
                self.logger.info(f"  {name}: {fact_values}")
        
        return self.facts
    
    def _process_tag(self, tag, tag_type: str) -> None:
        """
        Process a single XBRL tag and extract its fact information.
        
        Args:
            tag: BeautifulSoup Tag object representing an XBRL tag
            tag_type: The type of tag ("ix:nonFraction" or "ix:nonNumeric")
        """
        try:
            # Extract required attributes (checking multiple case variations)
            name = None
            for attr in ['name', 'Name']:
                if tag.has_attr(attr):
                    name = tag[attr]
                    break
            
            if not name:
                self.logger.warning(f"Found {tag_type} tag without 'name' attribute, skipping")
                return
            
            # Extract contextRef (checking multiple case variations)
            context_ref = None
            for attr in ['contextRef', 'contextref', 'contextREF']:
                if tag.has_attr(attr):
                    context_ref = tag[attr]
                    break
                    
            if not context_ref:
                self.logger.warning(f"Missing 'contextRef' attribute for {name}")
            
            # Extract unitRef (checking multiple case variations)
            unit_ref = None
            for attr in ['unitRef', 'unitref', 'unitREF']:
                if tag.has_attr(attr):
                    unit_ref = tag[attr]
                    break
                    
            if not unit_ref and tag_type == "ix:nonFraction":
                self.logger.warning(f"Missing 'unitRef' attribute for {name} (nonFraction tag)")
                
            # Extract the value (text content of the tag)
            value = tag.get_text(strip=True)
            
            # Create fact dictionary
            fact = {
                "value": value,
                "tag": tag_type,
            }
            
            # Add optional attributes if they exist
            if context_ref:
                fact["contextRef"] = context_ref
            if unit_ref:
                fact["unitRef"] = unit_ref
                
            # Add to the facts dictionary
            if name not in self.facts:
                self.facts[name] = []
            
            self.facts[name].append(fact)
            
        except Exception as e:
            self.logger.error(f"Error processing tag: {str(e)}")
    
    def get_facts_by_name(self, name: str) -> List[Dict[str, Any]]:
        """
        Get all facts for a specific concept name.
        
        Args:
            name: The XBRL concept name
            
        Returns:
            List of fact dictionaries for the specified concept
        """
        return self.facts.get(name, []) 