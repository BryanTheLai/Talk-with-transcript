import os
import fitz  # PyMuPDF
from google.genai import types
from llm.GeminiClient import GeminiClient

def clean_markdown_delimiters(text):
    """Remove markdown code block delimiters from text."""
    if text is None:
        return None
        
    if text.startswith("```markdown"):
        text = text[11:].lstrip()
    elif text.startswith("```"):
        text = text[3:].lstrip()
        
    if text.endswith("```"):
        text = text[:-3].rstrip()
        
    return text

def annotate_pdf_as_images(gemini_client: GeminiClient, pdf_path: str, output_folder: str) -> str:
    """Process a PDF by converting each page to an image and having Gemini annotate it."""
    annotation_prompt = """
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
    
    try:
        pdf_document = fitz.open(pdf_path)
        total_pages = len(pdf_document)
        all_pages_text = []
        pdf_filename_base = os.path.splitext(os.path.basename(pdf_path))[0]
        print(total_pages)
        for page_num in range(total_pages):
            print(f"Processing page {page_num+1}/{total_pages}")
            
            # Render page as image
            page = pdf_document[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))  # Increase from 2x to 3x
            img_bytes = pix.tobytes("png")

            # # Save image for verification
            # img_path = os.path.join(output_folder, f"{pdf_filename_base}_page_{page_num+1}.png")
            # with open(img_path, "wb") as img_file:
            #     img_file.write(img_bytes)
            # print(f"Saved image: {img_path}")
            
            # Get Gemini annotation
            response = gemini_client.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                    annotation_prompt
                ]
            )
            
            # Process response
            text = clean_markdown_delimiters(response.text) if response.text else f"[Error: Failed to process page {page_num+1}]"
            all_pages_text.append(text)
            
            # Add page separator if not the last page
            if page_num < total_pages - 1:
                all_pages_text.append(f"\n\n{{{page_num}}}------------------------------------------------\n\n")
        
        return "\n".join(all_pages_text)
        
    except Exception as e:
        return f"Error processing PDF: {str(e)}"

if __name__ == "__main__":
    pdf_file = "src/paper.pdf"
    output_folder = "output_folder"
    os.makedirs(output_folder, exist_ok=True)

    gemini_client = GeminiClient()
    print(f"Processing PDF: {pdf_file}")
    
    markdown_output = annotate_pdf_as_images(gemini_client, pdf_file, output_folder)

    if markdown_output.startswith("Error:"):
        print(markdown_output)
    else:
        pdf_filename_base = os.path.splitext(os.path.basename(pdf_file))[0]
        output_filepath = os.path.join(output_folder, f"{pdf_filename_base}_gemini.md")
        with open(output_filepath, "w", encoding="utf-8") as md_file:
            md_file.write(markdown_output)
        print(f"Annotated Markdown saved to: {output_filepath}")