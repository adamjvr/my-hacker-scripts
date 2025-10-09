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

## License

This project is licensed under the **MIT License**.  

The MIT License is a permissive open-source license that allows you to freely use, modify, and distribute the software, even in commercial applications, as long as the original copyright notice and license are included. It provides flexibility while protecting the author's rights.
