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
It supports multithreading for faster batch conversion, automatically extracts ZIP files, and allows you to specify a destination folder for output.  
Perfect for preparing image sets for the web, archiving, or automated processing pipelines.

**Usage:**  
```bash
python img2img.py <path_to_folder_or_zip> [-p | -jp | -g | -we] [-c <compression_level>] [-o <output_folder>]
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
- `-o <output_folder>` — Optional destination folder where converted images will be saved.

**Examples:**  
```bash
python img2img.py ./images -jp -c 6
```
Converts all images in the `images` folder to JPEG format with medium compression.

```bash
python img2img.py ./photos.zip -we -c 3 -o ./web_ready
```
Extracts `photos.zip`, converts all contained images to WEBP format, applies light compression, and saves them to `./web_ready`.

**How it works:**

1. Detects whether the input is a folder or ZIP archive.  
2. If ZIP, extracts its contents to a temporary directory.  
3. Recursively scans for supported image formats (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`, `.tiff`).  
4. Spawns multiple threads to convert images concurrently for speed.  
5. Converts images to the target format and applies the specified compression level.  
6. Saves all converted files to either the user-defined output folder or a new folder named `converted_<format>`.  
7. Cleans up any temporary files automatically if a ZIP was used.  

---

### 3. EPUB to PDF Converter with TOC (`epub_to_pdf_toc_chapters.py`)

**Description:**  
A fully self-contained Python utility that converts **EPUB** files into clean, well-structured **PDFs**. It preserves formatting, embeds images, generates a clickable **Table of Contents**, and ensures every chapter starts on a new page. This makes it ideal for turning ebooks, documentation, or long-form notes into polished, portable PDFs.

**Key Features:**  
- **Preserves formatting** (headings, lists, blockquotes, inline styles).  
- **Embeds all images** using base64 `data:` URIs — no external files required.  
- **Auto-generates a clickable TOC** based on chapter headings or fallbacks.  
- **Starts each chapter on a new page** for clean structure.  
- **Writes a debug HTML file** so you can inspect the intermediate output.  
- Works entirely offline and produces a single, portable PDF.

**Usage:**  
```bash
python epub_to_pdf_toc_chapters.py input.epub output.pdf
```

**Dependencies:**  
```
ebooklib
beautifulsoup4
xhtml2pdf
```
---

### X. Parallel Image Metadata Remover & Renamer (`rmmimg.py`)

**Description**  
Strips *all* metadata (EXIF, XMP, IPTC, PNG text, etc.) from a folder of images and renames them to
`image0.ext`, `image1.ext`, ... based on file creation time.  
Uses all CPU cores to process images in parallel and shows a live progress bar in the terminal.

Designed for cleaning datasets, anonymizing photos, and preparing image batches for ML training or uploads.

**Usage**

```bash
# Basic usage (oldest file becomes image0)
python rmmimg.py /path/to/images

# Newest file becomes image0
python rmmimg.py /path/to/images --newest-first

# Replace originals (creates backup first)
python rmmimg.py /path/to/images --in-place

# Limit CPU usage
python rmmimg.py /path/to/images --workers 8
```


## License

This project is licensed under the **MIT License**.  

The MIT License is a permissive open-source license that allows you to freely use, modify, and distribute the software, even in commercial applications, as long as the original copyright notice and license are included. It provides flexibility while protecting the author's rights.
