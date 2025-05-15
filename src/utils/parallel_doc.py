import os
import fitz  # PyMuPDF
from google.genai import types
from typing import Optional, List, Tuple, Union
from llm.GeminiClient import GeminiClient
import concurrent.futures
import threading
import time
from collections import deque
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("DocumentProcessor")

class RateLimiter:
    """Simple rate limiter to prevent exceeding API rate limits"""
    
    def __init__(self, max_requests: int, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.request_timestamps = deque()
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        with self.lock:
            now = datetime.now()
            # Remove timestamps outside time window
            while self.request_timestamps and self.request_timestamps[0] < now - timedelta(seconds=self.time_window):
                self.request_timestamps.popleft()
            
            if len(self.request_timestamps) >= self.max_requests:
                oldest = self.request_timestamps[0]
                wait_time = (oldest + timedelta(seconds=self.time_window) - now).total_seconds()
                if wait_time > 0:
                    time.sleep(wait_time + 0.1)  # Small buffer
                    return self.wait_if_needed()
            
            self.request_timestamps.append(now)

class DocumentProcessor:
    """Processor for extracting and analyzing document content"""
    
    # PDF annotation prompt template
    PDF_ANNOTATION_PROMPT = """
    You are a professional image-to-markdown converter. You have decades of experience optimizing this.
    You are extremely intelligent; for example, you preserve bold and italic text in your conversions.
    Your conversions are tidy and exact copies of the content, maintaining 100 percent accuracy.
    Do not change or omit anything. If a table has 5 columns and 5 rows, your output must also be 5x5 with all of the content.
    Your outputs are MARKDOWN ONLY, with intelligent sectioning.
    Intelligently determine if the text represents titles, headings, etc.
    For example, use #, ##, etc., to make the markdown tidy and clearly structured without changing the core content.
    Images are replaced with detailed descriptions that capture exactly what they are and what they show,
    clearly and in detail, as replacements for the images or diagrams. For example, for charts, describe the position of lines, trends, skewness, etc.
    Turn math equations into correct Markdown LaTeX format.
    Separate sections intelligently and clearly. Your conversions must be accurate, then tidy.
    **Correct Output Example:** No extra text or delimiters.

    ```markdown
    # Document Title

    ## Subheading

    | Column 1 | Column 2 |
    |----------|----------|
    | Data 1   | Data 2   |
    ```
    Tables and text are 100% accurate with aligned columns and `|` seperators with no ommissions.

    Format Rich Content:** Tables, forms, equations, inline math, links, code, references.
    """
    
    def __init__(self, gemini_client: Optional[GeminiClient] = None):
        self.gemini_client = gemini_client or GeminiClient()
        self.rate_limiter = RateLimiter(max_requests=10)  # Gemini 2.0 Flash: 15 RPM
    
    def clean_markdown_delimiters(self, text):
        if not text:
            return None
            
        if text.startswith("```markdown"):
            text = text[11:].lstrip()
        elif text.startswith("```"):
            text = text[3:].lstrip()
            
        if text.endswith("```"):
            text = text[:-3].rstrip()
            
        return text
    
    def process_single_page(self, page_num: int, page: fitz.Page, total_pages: int) -> Tuple[int, str]:
        """Process a single PDF page and return its markdown content"""
        try:
            logger.info(f"Processing page {page_num+1}/{total_pages}")
            
            # Render page as image
            pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
            img_bytes = pix.tobytes("png")
            
            # Respect rate limits and get annotation
            self.rate_limiter.wait_if_needed()
            response = self.gemini_client.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                    self.PDF_ANNOTATION_PROMPT
                ]
            )
            
            # Process response
            text = self.clean_markdown_delimiters(response.text) if response.text else f"[Error: Failed to process page {page_num+1}]"
            return page_num, text
            
        except Exception as e:
            logger.error(f"Error processing page {page_num+1}: {str(e)}")
            return page_num, f"[Error processing page {page_num+1}: {str(e)}]"
        
    def pdf_to_markdown(
        self, 
        pdf_path: str, 
        output_folder: Optional[str] = None, 
        max_workers: int = 4,
        page_range: Optional[Union[List[int], Tuple[int, int]]] = None
    ) -> str:
        """Process a PDF by converting each page to markdown in parallel"""
        if not os.path.exists(pdf_path):
            return f"PDF file not found: {pdf_path}"
            
        max_workers = max(1, max_workers)
        pdf_document = None
        
        try:
            # Setup environment
            if output_folder:
                os.makedirs(output_folder, exist_ok=True)
                
            pdf_document = fitz.open(pdf_path)
            total_pages = len(pdf_document)
            
            if total_pages == 0:
                return "PDF contains no pages"
                
            # Determine pages to process
            if page_range:
                if isinstance(page_range, (list, set)):
                    pages_to_process = [p for p in page_range if 0 <= p < total_pages]
                elif isinstance(page_range, tuple) and len(page_range) == 2:
                    start, end = page_range
                    pages_to_process = list(range(
                        max(0, min(start, total_pages-1)),
                        max(start, min(end, total_pages))
                    ))
                else:
                    pages_to_process = list(range(total_pages))
            else:
                pages_to_process = list(range(total_pages))
                
            if not pages_to_process:
                return "No valid pages to process"
                
            # Process pages in parallel
            page_results = {}
            pdf_filename_base = os.path.splitext(os.path.basename(pdf_path))[0]
            logger.info(f"Processing {len(pages_to_process)} of {total_pages} pages")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_page = {
                    executor.submit(self.process_single_page, page_num, pdf_document[page_num], total_pages): page_num 
                    for page_num in pages_to_process
                }
                
                for future in concurrent.futures.as_completed(future_to_page):
                    try:
                        page_num, text = future.result()
                        page_results[page_num] = text
                        logger.info(f"Completed page {page_num+1}/{total_pages}")
                    except Exception as e:
                        page_num = future_to_page[future]
                        page_results[page_num] = f"[Error processing page {page_num+1}: {str(e)}]"
                        logger.error(f"Error in future for page {page_num+1}: {str(e)}")
            
            # Combine results in order
            all_pages_text = []
            for page_num in sorted(pages_to_process):
                all_pages_text.append(page_results.get(page_num, f"[Missing content for page {page_num+1}]"))
                if page_num != pages_to_process[-1]:
                    all_pages_text.append(f"\n\n{{Page {page_num+1}}}------------------------------------------------\n\n")
            
            markdown_output = "\n".join(all_pages_text)
            
            # Save to file if requested
            if output_folder:
                output_filepath = os.path.join(output_folder, f"{pdf_filename_base}_gemini.md")
                try:
                    with open(output_filepath, "w", encoding="utf-8") as md_file:
                        md_file.write(markdown_output)
                    logger.info(f"Markdown saved to: {output_filepath}")
                except IOError as e:
                    logger.error(f"Failed to write output file: {str(e)}")
                
            return markdown_output
            
        except Exception as e:
            return f"Error processing PDF: {str(e)}"
        finally:
            if pdf_document:
                pdf_document.close()