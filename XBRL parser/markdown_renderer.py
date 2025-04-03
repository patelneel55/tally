import logging
import os
from typing import Dict, List, Optional, Any


class MarkdownRenderer:
    """
    Converts visual blocks and XBRL facts into a structured Markdown document.
    
    This class takes extracted visual blocks and optional XBRL facts and 
    creates a formatted Markdown document that preserves the original hierarchy
    while enriching it with XBRL semantic metadata when available.
    """
    
    # Font size mapping to Markdown heading levels
    FONT_SIZE_TO_HEADING = {
        24: "#",       # font ≥ 24 → #
        22: "##",      # font ≥ 22 → ##
        20: "###",     # font ≥ 20 → ###
        18: "####",    # font ≥ 18 → ####
        16: "#####",   # font ≥ 16 → #####
        14: "######",  # font ≥ 14 → ######
    }
    
    def __init__(self, blocks: List[Dict[str, Any]], facts: Optional[Dict[str, List[Dict[str, Any]]]] = None, 
                 log_level: int = logging.INFO):
        """
        Initialize the MarkdownRenderer.
        
        Args:
            blocks: List of visual block dictionaries extracted from VisualBlockExtractor
            facts: Optional dictionary of XBRL facts from XBRLFactExtractor
            log_level: Logging level (default: logging.INFO)
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        
        self.blocks = blocks
        self.facts = facts or {}
        
        # Track statistics for logging
        self.rendered_blocks = {
            "heading": 0,
            "paragraph": 0,
            "table": 0,
            "other": 0
        }
        
        self.footnotes = {}  # Will store XBRL fact footnotes
        self.footnote_counter = 1  # Counter for footnote numbering
        
        self.markdown_content = ""  # Will hold the generated Markdown
        
    def _get_heading_level(self, font_size: int) -> str:
        """
        Determine the Markdown heading level based on font size.
        
        Args:
            font_size: The numeric font size
            
        Returns:
            str: Markdown heading prefix (e.g., "#", "##", etc.)
        """
        # Find the largest heading level that's less than or equal to the font size
        for size in sorted(self.FONT_SIZE_TO_HEADING.keys(), reverse=True):
            if font_size >= size:
                return self.FONT_SIZE_TO_HEADING[size]
        
        # If no match, it's not a heading
        return ""
    
    def _render_heading(self, block: Dict[str, Any]) -> str:
        """
        Render a heading block as Markdown.
        
        Args:
            block: The heading block dictionary
            
        Returns:
            str: Markdown formatted heading
        """
        heading_level = self._get_heading_level(block.get("font_size", 0))
        
        # If no valid heading level found, treat as paragraph
        if not heading_level:
            self.logger.debug(f"Block with font size {block.get('font_size')} treated as paragraph, not heading")
            return self._render_paragraph(block)
        
        text = block.get("text", "").strip()
        
        # Apply styling if needed
        if block.get("is_bold"):
            text = f"**{text}**"
        if block.get("is_italic"):
            text = f"*{text}*"
        if block.get("is_underlined"):
            text = f"<u>{text}</u>"
        
        # Check for XBRL facts and create footnotes
        text = self._add_fact_footnotes(text)
        
        # Log the heading creation
        self.rendered_blocks["heading"] += 1
        return f"{heading_level} {text}\n\n"
    
    def _render_paragraph(self, block: Dict[str, Any]) -> str:
        """
        Render a paragraph block as Markdown.
        
        Args:
            block: The paragraph block dictionary
            
        Returns:
            str: Markdown formatted paragraph
        """
        text = block.get("text", "").strip()
        
        # Apply styling
        if block.get("is_bold"):
            text = f"**{text}**"
        if block.get("is_italic"):
            text = f"*{text}*"
        if block.get("is_underlined"):
            text = f"<u>{text}</u>"
        
        # Check for XBRL facts and create footnotes
        text = self._add_fact_footnotes(text)
        
        # Log the paragraph creation
        self.rendered_blocks["paragraph"] += 1
        return f"{text}\n\n"
    
    def _render_table(self, block: Dict[str, Any]) -> str:
        """
        Render a table block as Markdown.
        
        Args:
            block: The table block dictionary
            
        Returns:
            str: Markdown formatted table (or HTML if conversion not possible)
        """
        text = block.get("text", "").strip()
        
        # For now, we'll just preserve the HTML content as is
        # A more advanced implementation could parse HTML tables and convert to Markdown
        
        # Check for XBRL facts and create footnotes
        text = self._add_fact_footnotes(text)
        
        # Log the table creation
        self.rendered_blocks["table"] += 1
        return f"<div class='table-container'>\n{text}\n</div>\n\n"
    
    def _render_other(self, block: Dict[str, Any]) -> str:
        """
        Render other types of blocks as Markdown.
        
        Args:
            block: The block dictionary
            
        Returns:
            str: Markdown formatted content
        """
        text = block.get("text", "").strip()
        
        # Apply styling
        if block.get("is_bold"):
            text = f"**{text}**"
        if block.get("is_italic"):
            text = f"*{text}*"
        if block.get("is_underlined"):
            text = f"<u>{text}</u>"
        
        # Check for XBRL facts and create footnotes
        text = self._add_fact_footnotes(text)
        
        # Log the other block creation
        self.rendered_blocks["other"] += 1
        return f"{text}\n\n"
    
    def _add_fact_footnotes(self, text: str) -> str:
        """
        Add footnotes for any XBRL facts found in the text.
        
        Args:
            text: The block text content
            
        Returns:
            str: Text with footnote references added
        """
        if not self.facts or not text:
            return text
        
        # Check each fact name to see if it appears in the text
        for fact_name in self.facts:
            # Try different matching approaches - both full name and concept part
            full_match = fact_name in text
            concept_part = fact_name.split(':')[-1] if ':' in fact_name else fact_name
            concept_match = concept_part in text
            
            # Check for matches in common financial terms that might appear in text
            financial_terms = {
                "Revenue": "us-gaap:Revenue",
                "Net Income": "us-gaap:NetIncomeLoss",
                "Income": "us-gaap:NetIncomeLoss",
                "Assets": "us-gaap:Assets",
                "Liabilities": "us-gaap:Liabilities",
                "Sales": "us-gaap:Revenue"
            }
            
            term_match = False
            matching_term = None
            for term, term_fact in financial_terms.items():
                if term in text and term_fact == fact_name:
                    term_match = True
                    matching_term = term
                    break
            
            # If any type of match occurs, create a footnote
            if full_match or concept_match or term_match:
                # Add footnote reference if not already present
                if fact_name not in self.footnotes:
                    # Create the footnote
                    fact_instances = self.facts[fact_name]
                    if fact_instances:
                        fact = fact_instances[0]  # Take first instance for simplicity
                        context_ref = fact.get("contextRef", "")
                        unit_ref = fact.get("unitRef", "")
                        
                        footnote_text = f"{fact_name}"
                        if context_ref:
                            footnote_text += f" | Context: {context_ref}"
                        if unit_ref:
                            footnote_text += f" | Unit: {unit_ref}"
                        
                        self.footnotes[fact_name] = {
                            "number": self.footnote_counter,
                            "text": footnote_text
                        }
                        self.footnote_counter += 1
                
                # Get footnote number
                footnote_num = self.footnotes[fact_name]["number"]
                footnote_ref = f"[^{footnote_num}]"
                
                # Only add the reference if not already present
                if footnote_ref not in text:
                    # Apply the reference based on what matched
                    if full_match and fact_name in text:
                        text = text.replace(fact_name, f"{fact_name}{footnote_ref}")
                    elif concept_match and concept_part in text and concept_part != fact_name:
                        text = text.replace(concept_part, f"{concept_part}{footnote_ref}")
                    elif term_match and matching_term:
                        text = text.replace(matching_term, f"{matching_term}{footnote_ref}")
        
        return text
    
    def render(self) -> str:
        """
        Render blocks into a complete Markdown document.
        
        Returns:
            str: The complete Markdown content
        """
        self.logger.info("Starting Markdown rendering")
        
        # Reset output and statistics
        self.markdown_content = ""
        self.rendered_blocks = {
            "heading": 0,
            "paragraph": 0,
            "table": 0,
            "other": 0
        }
        self.footnotes = {}
        self.footnote_counter = 1
        
        # Process each block in original order
        sorted_blocks = sorted(self.blocks, key=lambda b: b.get("line_number", 0))
        
        for block in sorted_blocks:
            block_type = block.get("type")
            
            if block_type == "heading":
                self.markdown_content += self._render_heading(block)
            elif block_type == "paragraph":
                self.markdown_content += self._render_paragraph(block)
            elif block_type == "table":
                self.markdown_content += self._render_table(block)
            else:
                self.markdown_content += self._render_other(block)
        
        # Add footnotes at the end
        if self.footnotes:
            self.markdown_content += "\n## Footnotes\n\n"
            for fact_name, footnote in sorted(self.footnotes.items(), key=lambda x: x[1]["number"]):
                number = footnote["number"]
                text = footnote["text"]
                self.markdown_content += f"[^{number}]: {text}\n"
        
        # Log rendering statistics
        self.logger.info(f"Rendered {sum(self.rendered_blocks.values())} blocks to Markdown")
        for block_type, count in self.rendered_blocks.items():
            self.logger.info(f"- {block_type}: {count} blocks")
        
        # Log sample of first 3 lines
        md_lines = self.markdown_content.split('\n')[:6]  # First 3 'logical' lines (assuming 2 lines per block)
        self.logger.info(f"Sample Markdown output (first few lines):")
        for line in md_lines:
            if line.strip():
                self.logger.info(f"- {line[:50]}...")
        
        return self.markdown_content
    
    def save_to_file(self, file_path: str) -> bool:
        """
        Save the rendered Markdown to a file.
        
        Args:
            file_path: Path to save the Markdown file
            
        Returns:
            bool: True if file was saved successfully, False otherwise
        """
        # Ensure we have markdown content
        if not self.markdown_content:
            self.render()
            
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.markdown_content)
                
            self.logger.info(f"Markdown saved to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving Markdown to {file_path}: {str(e)}")
            return False
    
    def preview(self, n: int = 10) -> str:
        """
        Preview the first n lines of the rendered Markdown.
        
        Args:
            n: Number of lines to preview (default: 10)
            
        Returns:
            str: Preview of rendered Markdown
        """
        # Ensure we have markdown content
        if not self.markdown_content:
            self.render()
            
        # Get the first n lines
        lines = self.markdown_content.split('\n')[:n]
        preview = '\n'.join(lines)
        
        self.logger.info(f"Markdown preview (first {n} lines):")
        self.logger.info(preview)
        
        return preview 