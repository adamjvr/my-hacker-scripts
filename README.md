# my-hacker-scripts

A collection of scripts I use to automate tasks, streamline workflows, and make life easier on Linux. These scripts help boost productivity for work and hobbies, covering everything from file management to simple automation.

---

## Scripts

### 1. Markdown to PDF Converter (`md2pdf.py`)

**Description:**  
This Python script converts Markdown files into PDF documents with the same filename. It reads a Markdown file, converts it to HTML, and then renders a nicely formatted PDF using `WeasyPrint`. Perfect for quickly creating readable PDFs from your notes, documentation, or reports.

**Usage:**  
```bash
python md2pdf.py <your_markdown_file>.md
```

**How it works:**

1. Reads the Markdown content from the specified file.  
2. Converts Markdown to HTML using the `markdown` library.  
3. Wraps the HTML in basic styling for readability.  
4. Generates a PDF using `WeasyPrint` with the same name as the input file.


## License

This project is licensed under the **MIT License**.  

The MIT License is a permissive open-source license that allows you to freely use, modify, and distribute the software, even in commercial applications, as long as the original copyright notice and license are included. It provides flexibility while protecting the author's rights.
