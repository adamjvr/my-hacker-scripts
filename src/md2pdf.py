#!/usr/bin/env python3
import sys
import os
from markdown import markdown
from weasyprint import HTML

def md_to_pdf(md_file):
    if not os.path.exists(md_file):
        print(f"Error: File '{md_file}' not found.")
        return

    # Read markdown content
    with open(md_file, "r", encoding="utf-8") as f:
        text = f.read()

    # Convert markdown to HTML
    html_content = markdown(text, output_format="html5")

    # Wrap in basic HTML for styling
    html_page = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: "DejaVu Sans", sans-serif;
                margin: 2em;
                line-height: 1.5;
            }}
            h1, h2, h3, h4, h5, h6 {{
                color: #333;
            }}
            code {{
                background: #f4f4f4;
                padding: 2px 4px;
                border-radius: 4px;
            }}
            pre {{
                background: #f4f4f4;
                padding: 10px;
                border-radius: 6px;
                overflow-x: auto;
            }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """

    # Output file name
    pdf_file = os.path.splitext(md_file)[0] + ".pdf"

    # Convert HTML to PDF
    HTML(string=html_page).write_pdf(pdf_file)
    print(f"✅ Converted '{md_file}' → '{pdf_file}'")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python md2pdf.py <markdown_file>")
        sys.exit(1)

    md_to_pdf(sys.argv[1])
