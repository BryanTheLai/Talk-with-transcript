import os
from llm.GeminiClient import GeminiClient
from utils.DocumentProcessor import DocumentProcessor
import time

if __name__ == "__main__":
    pdf_file = "src/vit.pdf"
    output_folder = "output_folder"
    
    start = time.time()

    # Initialize clients
    gemini_client = GeminiClient()
    doc_processor = DocumentProcessor(gemini_client)

    # Process PDF
    print(f"Processing PDF: {pdf_file}")
    doc_processor.pdf_to_markdown(pdf_file, output_folder)
    end = time.time()
    time_taken = end - start
    print(f"Time taken is {time_taken:.2f} seconds")