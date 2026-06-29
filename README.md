# my-hacker-scripts

A collection of small command-line scripts I use to automate boring tasks, clean up messy files, batch-process media, and keep Linux workflows moving without turning every little job into a whole software project.

The whole point of this repo is simple: practical scripts, clear behavior, dry-run modes where destructive behavior is possible, and tools that are easy to copy into another machine when a folder has become a disaster zone.

## Running Scripts

Most scripts live in `src/` and can be run from the repo root like this:

```bash
python src/script_name.py --help
```

Some scripts use only the Python standard library. Others depend on Python packages or Linux command-line tools. Newer scripts check their dependencies at runtime and try to install missing dependencies automatically when that is safe and practical.

If you do not want a script to install anything for you, use the script's `--no-auto-install` option when available.

## Scripts

### 1. Markdown to PDF Converter (`md2pdf.py`)

**Description:** Converts Markdown files into PDF documents with the same filename.

It reads a Markdown file, converts it to HTML, and renders a formatted PDF using WeasyPrint. This is useful for turning notes, documentation, reports, and README-style drafts into portable PDFs.

**Usage:**

```bash
python src/md2pdf.py input.md
```

**How it works:**

1. Reads the Markdown content from the specified file.
2. Converts Markdown to HTML using the `markdown` library.
3. Wraps the HTML in basic styling for readability.
4. Generates a PDF using `WeasyPrint`.

---

### 2. Image Format Converter (`img2img.py`)

**Description:** Converts a folder or ZIP archive of images into a target format such as PNG, JPEG, GIF, or WEBP.

It supports multithreading, automatic ZIP extraction, optional compression, and custom output folders. This is useful for preparing image sets for the web, archiving, dataset cleanup, or bulk format conversion.

**Usage:**

```bash
python src/img2img.py ./images -jp -c 6
python src/img2img.py ./photos.zip -we -c 3 -o ./web_ready
```

**Common options:**

```text
-p        Convert to PNG
-jp       Convert to JPEG
-g        Convert to GIF
-we       Convert to WEBP
-c        Compression level, usually 0 through 9
-o        Output folder
```

**How it works:**

1. Detects whether the input is a folder or ZIP archive.
2. Extracts ZIP input to a temporary directory when needed.
3. Recursively scans for supported image formats.
4. Converts images in parallel.
5. Saves converted files to the selected output folder.
6. Cleans up temporary extraction folders.

---

### 3. EPUB to PDF Converter with TOC (`epub_to_pdf_toc_chapters.py`)

**Description:** Converts EPUB files into clean PDF files with formatting, embedded images, a clickable table of contents, and chapter page breaks.

This is useful for turning ebooks, documentation, and long-form notes into a single portable PDF.

**Usage:**

```bash
python src/epub_to_pdf_toc_chapters.py input.epub output.pdf
```

**Dependencies:**

```text
ebooklib
beautifulsoup4
xhtml2pdf
```

---

### 4. Parallel Image Metadata Remover and Renamer (`rmmimg.py`)

**Description:** Strips metadata from a folder of images and renames them into a clean sequence such as `image0.ext`, `image1.ext`, and so on.

It removes EXIF, XMP, IPTC, PNG text chunks, and other image metadata. This is useful for cleaning datasets, anonymizing photos, and preparing batches for upload or machine learning workflows.

**Usage:**

```bash
python src/rmmimg.py /path/to/images
python src/rmmimg.py /path/to/images --newest-first
python src/rmmimg.py /path/to/images --in-place
python src/rmmimg.py /path/to/images --workers 8
```

**Notes:**

- Uses parallel processing.
- Shows progress in the terminal.
- Can replace originals when requested.
- Makes image folders more predictable before archiving or publishing.

---

### 5. Advanced Image Deduplication Tool (`dedupe_images.py`)

**Description:** Scans a folder of images and detects visually duplicate images, even when they have different filenames, sizes, resolutions, or compression settings.

Instead of only checking exact file hashes, it uses perceptual hashing to compare how images look. For each duplicate group, it keeps the best version and removes or relocates the rest.

**Usage:**

```bash
python src/dedupe_images.py /path/to/image/folder
python src/dedupe_images.py /path/to/image/folder --move-duplicates ./duplicates
python src/dedupe_images.py /path/to/image/folder --csv-report dedupe_report.csv
```

**What it does:**

1. Recursively scans for supported image files.
2. Computes perceptual hashes.
3. Groups near-identical images.
4. Keeps the highest-resolution or largest file.
5. Deletes or moves the lower-quality duplicates.
6. Optionally writes a CSV report.

**Notes:**

- Best used on a copy first when the data matters.
- Comparison can take time on very large collections.
- Designed to avoid unnecessary heavy dependencies.

---

### 6. H.265 / HEVC Encoder Wrapper (`x265_encode.py`)

**Description:** A Python CLI wrapper around `ffmpeg` for encoding videos using H.265 / x265 with predictable defaults.

It is designed for batch-safe video encoding, archive workflows, optional MP4 output, subtitle handling, 10-bit output, hardware encoder options, and progress display.

**Usage:**

```bash
python src/x265_encode.py input.mp4
python src/x265_encode.py input.mkv --container mp4
python src/x265_encode.py input.mp4 -c 20
python src/x265_encode.py input.mkv -p slow
python src/x265_encode.py input.mkv --audio-copy
python src/x265_encode.py dummy --batch-dir ./videos
```

**Default behavior:**

```text
Video:      H.265 / x265 / libx265
CRF:        23
Preset:     medium
Pixel fmt:  yuv420p
Container:  MKV
Audio:      AAC at 192 kbps
```

**Requirements:**

```text
ffmpeg
ffprobe
Python 3.9+
```

---

### 7. ASCII Folder Tree Generator (`generate_tree_md.py`)

**Description:** Generates a clean ASCII directory tree from any folder and exports it as a Markdown file.

This is useful for hardware repo documentation, firmware snapshots, reverse-engineering notes, README structure sections, project inventory, and archive documentation.

**Usage:**

```bash
python src/generate_tree_md.py /path/to/project
python src/generate_tree_md.py /path/to/project -o project_structure.md
python src/generate_tree_md.py /path/to/project --include-hidden
```

**What it does:**

1. Recursively scans a target folder.
2. Ignores common junk like `.git` and `__pycache__` by default.
3. Builds a readable ASCII folder tree.
4. Writes the tree into a Markdown file.
5. Includes timestamp and root path metadata.

---

### 8. Folder ZIP Batch Archiver (`zip_each_folder.py`)

**Description:** Zips every immediate folder in a target directory into its own ZIP archive.

Loose files in the target directory are ignored. This is useful when a directory contains a bunch of project folders and each one needs to become its own archive.

**Usage:**

```bash
python src/zip_each_folder.py
python src/zip_each_folder.py /path/to/folders
python src/zip_each_folder.py /path/to/folders -o /path/to/zips
python src/zip_each_folder.py /path/to/folders --overwrite
```

**What it does:**

1. Scans the target directory.
2. Finds immediate child folders only.
3. Ignores loose files.
4. Creates one ZIP per folder.
5. Preserves the folder itself as the top-level item inside the archive.
6. Preserves empty directories.
7. Skips existing ZIP files unless overwrite mode is enabled.

---

### 9. Filename Sanitizer (`sanitize_filenames.py`)

**Description:** Cleans messy filenames and folder names into boring automation-safe names.

This is for downloads, Google Drive exports, camera folders, vendor ZIPs, copied Windows folders, KiCad junk, image datasets, and any other pile of files that needs to stop fighting shell scripts.

**Usage:**

```bash
python src/sanitize_filenames.py ./messy_folder --dry-run
python src/sanitize_filenames.py ./messy_folder --recursive --dry-run
python src/sanitize_filenames.py ./messy_folder --recursive
python src/sanitize_filenames.py ./messy_folder --recursive --ascii-only
python src/sanitize_filenames.py ./messy_folder --recursive --preserve-case
python src/sanitize_filenames.py ./messy_folder --recursive --separator -
```

**What it does:**

1. Replaces whitespace and sketchy punctuation with a separator.
2. Lowercases names by default.
3. Preserves file extensions by default.
4. Can fold Unicode down to ASCII with `--ascii-only`.
5. Avoids overwriting existing files by appending counters.
6. Can operate on files only, directories only, or both.
7. Supports dry-run mode before touching anything.

**Dependency behavior:**

Uses only the Python standard library. No pip or apt packages are required.

---

### 10. Folder Flattener (`flatten_folder.py`)

**Description:** Copies or moves files out of nested folders into one flat output folder.

By default, it prefixes filenames with their parent folder path so duplicate names do not immediately collide. This is useful after extracting archives, cleaning image sets, gathering assets, or preparing files for another batch tool.

**Usage:**

```bash
python src/flatten_folder.py ./nested_folder --dry-run
python src/flatten_folder.py ./nested_folder
python src/flatten_folder.py ./nested_folder -o ./flat_output
python src/flatten_folder.py ./nested_folder --move
python src/flatten_folder.py ./nested_folder --no-parent-prefix
```

**What it does:**

1. Recursively scans a folder for files.
2. Copies files into one output folder by default.
3. Can move files instead with `--move`.
4. Adds parent-folder prefixes to preserve context.
5. Handles filename collisions safely.
6. Supports dry-run mode.

**Dependency behavior:**

Uses only the Python standard library. No pip or apt packages are required.

---

### 11. Empty Directory Cleaner (`empty_dir_cleaner.py`)

**Description:** Finds empty folders and optionally deletes them.

This is the cleanup pass after moving files, extracting archives, flattening folders, deleting generated junk, or cleaning old project directories.

**Usage:**

```bash
python src/empty_dir_cleaner.py ./some_folder
python src/empty_dir_cleaner.py ./some_folder --delete
python src/empty_dir_cleaner.py ./some_folder --include-hidden --delete
```

**What it does:**

1. Scans a folder tree from the bottom up.
2. Finds directories with no files or subdirectories left inside.
3. Reports empty folders by default.
4. Deletes empty folders only when `--delete` is passed.
5. Can include hidden dot-folders when requested.

**Dependency behavior:**

Uses only the Python standard library. No pip or apt packages are required.

---

### 12. Directory Hash Comparator (`hash_compare_dirs.py`)

**Description:** Compares two directories by hashing their files and reporting what is same, changed, missing, added, or moved.

This is for checking backups, comparing copied project folders, verifying Google Drive downloads, and making sure a folder migration did not quietly screw something up.

**Usage:**

```bash
python src/hash_compare_dirs.py ./folder_a ./folder_b
python src/hash_compare_dirs.py ./folder_a ./folder_b --show-same
python src/hash_compare_dirs.py ./folder_a ./folder_b --csv compare_report.csv
python src/hash_compare_dirs.py ./folder_a ./folder_b --algorithm sha1
python src/hash_compare_dirs.py ./folder_a ./folder_b --ignore-hidden
```

**What it reports:**

```text
same       Same relative path and same hash
changed    Same relative path but different hash
missing    File exists in folder A but not folder B
added      File exists in folder B but not folder A
moved      Same file content exists but at a different relative path
```

**Dependency behavior:**

Uses only the Python standard library. No pip or apt packages are required.

---

### 13. Numbered Batch Renamer (`batch_rename_numbered.py`)

**Description:** Renames files into a clean numbered sequence with a chosen prefix.

This is for image sets, frame exports, audio clips, scanned pages, reference files, and other folders where the names are garbage but the ordering matters.

**Usage:**

```bash
python src/batch_rename_numbered.py ./images --prefix photo --dry-run
python src/batch_rename_numbered.py ./images --prefix photo
python src/batch_rename_numbered.py ./frames --prefix frame --digits 6 --start 0
python src/batch_rename_numbered.py ./samples --prefix sample --sort mtime
python src/batch_rename_numbered.py ./images --prefix image --ext jpg --ext png
```

**What it does:**

1. Sorts files by name, modified time, or size.
2. Renames files into a numbered sequence.
3. Preserves extensions by default.
4. Can filter by extension.
5. Uses a two-pass temporary rename strategy to avoid collisions.
6. Supports recursive mode.
7. Supports dry-run mode.

**Dependency behavior:**

Uses only the Python standard library. No pip or apt packages are required.

---

### 14. Recursive Archive Extractor (`extract_all_archives.py`)

**Description:** Extracts archive files into clean folders.

This is the inverse of the folder ZIP batch archiver. It can process a single archive or scan a folder for archives, optionally recursively.

**Usage:**

```bash
python src/extract_all_archives.py ./downloads --dry-run
python src/extract_all_archives.py ./downloads
python src/extract_all_archives.py ./downloads --recursive
python src/extract_all_archives.py ./archive.zip -o ./extracted
python src/extract_all_archives.py ./downloads --recursive --delete-original
python src/extract_all_archives.py ./downloads --recursive --no-auto-install
```

**Supported archive types:**

```text
.zip
.tar
.tar.gz
.tgz
.tar.bz2
.tbz2
.tar.xz
.txz
.7z
.rar
```

**Dependency behavior:**

- ZIP and TAR formats use the Python standard library.
- 7z and RAR extraction require external tools.
- The script tries to install `p7zip-full` with apt when needed.
- RAR extraction uses `unrar` or `7z` when available.
- Use `--no-auto-install` to disable automatic installation attempts.

---

### 15. Video Audio Extractor (`video_audio_extract.py`)

**Description:** Extracts audio from video files using `ffmpeg`.

This is useful for pulling WAV files from video references, grabbing audio from camera clips, converting recorded phone videos into usable audio files, and batch-prepping media for DAW or sample work.

**Usage:**

```bash
python src/video_audio_extract.py ./clip.mp4
python src/video_audio_extract.py ./videos --recursive
python src/video_audio_extract.py ./videos --recursive --format flac
python src/video_audio_extract.py ./videos --recursive --format mp3 --bitrate 320k
python src/video_audio_extract.py ./videos -o ./audio --dry-run
python src/video_audio_extract.py ./videos --no-auto-install
```

**Supported output formats:**

```text
wav
flac
mp3
aac
m4a
ogg
```

**Dependency behavior:**

Requires `ffmpeg`. If it is missing, the script tries to install it with apt unless `--no-auto-install` is passed.

---

### 16. Recursive WebP to PNG Converter (`webp_to_png_recursive.py`)

**Description:** Converts WebP images to PNG recursively.

This is for dealing with downloaded web images, scraped references, browser-saved image folders, and any batch where WebP is annoying but PNG is easier to use downstream.

**Usage:**

```bash
python src/webp_to_png_recursive.py ./images --dry-run
python src/webp_to_png_recursive.py ./images
python src/webp_to_png_recursive.py ./images -o ./png_output
python src/webp_to_png_recursive.py ./images --overwrite
python src/webp_to_png_recursive.py ./images --delete-original
python src/webp_to_png_recursive.py ./images --no-auto-install
```

**What it does:**

1. Finds `.webp` files from a file or folder input.
2. Converts each image to PNG.
3. Preserves folder structure when an output root is provided.
4. Skips existing PNGs unless `--overwrite` is used.
5. Can delete source WebP files after successful conversion.
6. Supports dry-run mode.

**Dependency behavior:**

Requires Pillow. If Pillow is missing, the script tries to install it with pip unless `--no-auto-install` is passed.

---

### 17. PDF Image Extractor (`pdf_images_extract.py`)

**Description:** Extracts embedded images from PDFs, or renders full PDF pages to PNG images when requested.

This is useful for pulling images out of documentation, schematics, manuals, reports, scanned references, and weird PDFs where the useful part is trapped inside the file.

**Usage:**

```bash
python src/pdf_images_extract.py ./document.pdf
python src/pdf_images_extract.py ./pdf_folder --recursive
python src/pdf_images_extract.py ./pdf_folder --recursive -o ./extracted_images
python src/pdf_images_extract.py ./document.pdf --render-pages
python src/pdf_images_extract.py ./document.pdf --render-pages --dpi 300
python src/pdf_images_extract.py ./document.pdf --dry-run
python src/pdf_images_extract.py ./document.pdf --no-auto-install
```

**Modes:**

```text
Default mode:      Extract embedded image objects from the PDF.
--render-pages:   Render each full page as a PNG image.
```

**Dependency behavior:**

Requires PyMuPDF. If PyMuPDF is missing, the script tries to install it with pip unless `--no-auto-install` is passed.

---

### 18. PDF Merge, Split, and Page Extractor (`pdf_merge_split.py`)

**Description:** Merges multiple PDFs, splits one PDF into smaller PDFs, or extracts selected page ranges into a new PDF.

This is the general PDF utility that covers the annoying day-to-day document jobs without opening a giant PDF editor.

**Usage:**

Merge PDFs:

```bash
python src/pdf_merge_split.py merge a.pdf b.pdf c.pdf -o merged.pdf
python src/pdf_merge_split.py merge a.pdf b.pdf -o merged.pdf --overwrite
```

Split a PDF into single-page PDFs:

```bash
python src/pdf_merge_split.py split input.pdf -o split_pages
```

Split a PDF into chunks:

```bash
python src/pdf_merge_split.py split input.pdf -o split_chunks --chunk-size 10
```

Extract selected pages:

```bash
python src/pdf_merge_split.py extract input.pdf --pages 1-3,7,10 -o extracted.pdf
python src/pdf_merge_split.py extract input.pdf --pages 5-12 -o chapter.pdf --overwrite
```

Disable automatic dependency installation:

```bash
python src/pdf_merge_split.py --no-auto-install merge a.pdf b.pdf -o merged.pdf
```

**Dependency behavior:**

Requires pypdf. If pypdf is missing, the script tries to install it with pip unless `--no-auto-install` is passed.

---

## Dependency Notes

The newer scripts are designed to check for dependencies at runtime. They either use the Python standard library or attempt to bootstrap what they need.

```text
sanitize_filenames.py       stdlib only
flatten_folder.py           stdlib only
empty_dir_cleaner.py        stdlib only
hash_compare_dirs.py        stdlib only
batch_rename_numbered.py    stdlib only
extract_all_archives.py     stdlib plus optional p7zip/unrar tools
video_audio_extract.py      ffmpeg
webp_to_png_recursive.py    Pillow
pdf_images_extract.py       PyMuPDF
pdf_merge_split.py          pypdf
```

Manual install commands when you want to set things up yourself:

```bash
python -m pip install --user pillow pymupdf pypdf
sudo apt update
sudo apt install ffmpeg p7zip-full unrar poppler-utils
```

## General Safety Notes

- Use dry-run modes before destructive operations.
- Test on a copy first when the data matters.
- Read `--help` before running a script on a large folder.
- These are small practical utilities, not magic. They do what they say and try not to be clever behind your back.

## License

This project is licensed under the MIT License.

The MIT License is a permissive open-source license that allows you to use, modify, and distribute the software, including in commercial applications, as long as the original copyright notice and license are included.
