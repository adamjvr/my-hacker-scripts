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

---

### 2. Image Format Converter (`img2img.py`)

**Description:**  
This Python script converts a folder or ZIP archive of images into a specified format (PNG, JPEG, GIF, or WEBP) with optional compression.  
It supports multithreading for faster batch conversion and automatically extracts ZIP files before processing.  
Useful for preparing images for web uploads, archiving, or batch reformatting while maintaining efficient compression control.

**Usage:**  
```bash
python img2img.py <path_to_folder_or_zip> [-p | -jp | -g | -we] [-c <compression_level>]
```

**Arguments:**
- `<path_to_folder_or_zip>` — Path to a folder containing images or a ZIP archive.
- `-p` — Convert images to **PNG** format.
- `-jp` — Convert images to **JPEG** format.
- `-g` — Convert images to **GIF** format.
- `-we` — Convert images to **WEBP** format.
- `-c <compression_level>` — Optional compression level (0–9).  
  - `0` = no compression (maximum quality)  
  - `9` = maximum compression (lower quality)

**Example:**  
```bash
python img2img.py ./images -jp -c 6
```
Converts all images in the `images` folder to JPEG format with moderate compression.

**How it works:**

1. Checks whether the given path is a folder or a ZIP archive.  
2. If ZIP, extracts all images into a temporary directory.  
3. Scans the directory for supported image files (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, etc.).  
4. Uses a multithreaded worker pool to process multiple images in parallel for speed.  
5. Converts each image to the desired format and applies the specified compression level.  
6. Saves the converted images in a new output folder named `converted_<format>` in the same directory.  
7. Cleans up any temporary files if a ZIP was extracted.  

---

## License

This project is licensed under the **MIT License**.  

The MIT License is a permissive open-source license that allows you to freely use, modify, and distribute the software, even in commercial applications, as long as the original copyright notice and license are included. It provides flexibility while protecting the author's rights.
