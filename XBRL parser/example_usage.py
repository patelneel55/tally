import logging
from ixbrl_preprocessor import IXBRLPreprocessor

def main():
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Initialize the preprocessor with DEBUG log level
    preprocessor = IXBRLPreprocessor(log_level=logging.DEBUG)
    
    # Replace with your actual iXBRL file path
    input_file = "path/to/your/ixbrl_file.html"
    output_file = "cleaned_output.html"
    
    # Load and process the file
    if preprocessor.load_file(input_file):
        logger.info("File loaded successfully, processing...")
        
        # Process the file
        processed_html = preprocessor.process()
        
        if processed_html:
            # Save the processed HTML
            if preprocessor.save_to_file(output_file):
                logger.info(f"Processing complete. Output saved to {output_file}")
            else:
                logger.error("Failed to save processed file.")
        else:
            logger.error("Processing failed.")
    else:
        logger.error("Failed to load input file.")

if __name__ == "__main__":
    main() 