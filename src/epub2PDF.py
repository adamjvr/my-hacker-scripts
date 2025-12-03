#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
epub_to_pdf_toc_chapters.py
----------------------------------------------------------------------
A deeply commented, production-ready Python script that converts an EPUB
file into a PDF while preserving formatting, embedding images, creating
a clickable Table of Contents (TOC), and starting each chapter on a
new PDF page.

KEY CAPABILITIES
----------------
1) FORMATTING PRESERVATION
   - Uses xhtml2pdf to render HTML/CSS (subset of CSS2) directly into PDF.
   - Keeps headings <h1>...<h6>, bold/italic, lists, blockquotes, etc.

2) IMAGE EMBEDDING
   - Extracts EPUB resource files (e.g., JPEG/PNG/GIF/SVG*) and inlines them
     as base64 "data:" URIs.
   - This ensures robust, single-file PDF generation without external assets.

3) CHAPTER-LEVEL PAGE BREAKS
   - Each chapter begins on a new page via CSS "page-break-before".
   - The Table of Contents (TOC) is placed at the front and is followed by
     a page break before the first chapter.

4) TABLE OF CONTENTS (TOC)
   - A generated TOC lists chapter titles discovered from:
       a) The first heading tag found in each chapter (h1..h3 preferred),
          or
       b) The EPUB item's ID/href as a fallback.
   - TOC entries are internal links (<a href="#anchor">) that navigate to
     the corresponding chapter anchor in the PDF.

5) DEBUGGABILITY
   - Writes a temporary combined HTML file to disk for inspection.
   - Clearly logs progress and summarizes output paths.

LIMITATIONS / NOTES
-------------------
- XHTML2PDF supports a subset of CSS2 (not modern CSS3 layout features
  like flexbox/grid). Complex layouts may be simplified.
- SVG rendering support in xhtml2pdf is limited. Many SVGs will render
  as rasterized placeholders unless pre-rasterized. This script leaves
  <img src="data:image/svg+xml;base64,..."> in place; results vary.
- Fonts can be customized by injecting @font-face rules in <style> and
  referring to them in CSS. (Omitted here for portability.)

USAGE
-----
    python epub_to_pdf_toc_chapters.py input.epub output.pdf

DEPENDENCIES
------------
    pip install ebooklib beautifulsoup4 xhtml2pdf

AUTHOR
------
    GhostPCB / Roth Amplification Engineering Utilities
----------------------------------------------------------------------
"""

import sys
import os
import base64
import tempfile
from typing import List, Tuple, Dict

# EbookLib: parse EPUB structure (spine/manifest) and extract resources
from ebooklib import epub

# BeautifulSoup: sanitize/normalize XHTML, locate headings, and rewrite <img src=...>
from bs4 import BeautifulSoup

# xhtml2pdf (pisa): render HTML/CSS into PDF
from xhtml2pdf import pisa


# ---------------------------------------------------------------------------
# Utility: guess_mime_type_from_href
# ---------------------------------------------------------------------------
def guess_mime_type_from_href(href: str) -> str:
    """
    Attempt to infer a MIME type from a resource's file extension.

    Rationale:
        - EPUB manifests often embed MIME types, but when working directly
          with item hrefs we sometimes need a robust default guess to form
          data URIs.
        - xhtml2pdf understands common raster formats (JPEG/PNG/GIF). SVG
          support is limited but we encode/tag it anyway for completeness.

    Args:
        href: Relative path/filename from the EPUB manifest.

    Returns:
        A string MIME type suitable for "data:<mime>;base64,..." URIs.
    """
    lower = href.lower()
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".gif"):
        return "image/gif"
    if lower.endswith(".svg"):
        return "image/svg+xml"
    if lower.endswith(".webp"):
        # Not always supported by xhtml2pdf, but we tag it accurately.
        return "image/webp"
    # Fallback for unknown types; xhtml2pdf may ignore unsupported images.
    return "application/octet-stream"


# ---------------------------------------------------------------------------
# Utility: build_data_uri_map
# ---------------------------------------------------------------------------
def build_data_uri_map(book: epub.EpubBook) -> Dict[str, str]:
    """
    Construct a mapping from resource href → base64 data URI.

    Why:
        - When the HTML references <img src="images/foo.jpg">, the PDF renderer
          needs direct access to the image bytes. Because we want a self-contained,
          portable conversion step without writing out many temp files, we convert
          each image into a base64 "data:" URI and then rewrite <img> tags to
          embed that data directly in the HTML.

    Implementation details:
        - Iterate all items; for images (and possibly SVG), read bytes and encode.
        - Use the EPUB item href (e.g., "images/foo.jpg") as the dictionary key.
        - For non-image items (HTML/CSS), do nothing here.

    Args:
        book: Parsed EbookLib book object.

    Returns:
        A dict mapping { href (str) : data_uri (str) } for images/resources.
    """
    data_uri_by_href = {}

    for item in book.get_items():
        # We only care about binary resources we can embed via <img src=...>
        # EbookLib types: ITEM_IMAGE (images), ITEM_DOCUMENT (HTML), ITEM_STYLE (CSS), etc.
        if item.get_type() == epub.ITEM_IMAGE:
            href = item.get_name()  # item href within the EPUB (e.g., "images/foo.jpg")
            raw = item.get_content()  # bytes
            mime = item.media_type or guess_mime_type_from_href(href)
            b64 = base64.b64encode(raw).decode("ascii")
            data_uri_by_href[href] = f"data:{mime};base64,{b64}"

        # Optional: inline SVGs that might be stored as "other" resource types
        # Some EPUBs list SVGs as images, others as "misc". We can attempt to capture both.
        elif item.media_type and item.media_type.startswith("image/"):
            href = item.get_name()
            raw = item.get_content()
            mime = item.media_type
            b64 = base64.b64encode(raw).decode("ascii")
            data_uri_by_href[href] = f"data:{mime};base64,{b64}"

    return data_uri_by_href


# ---------------------------------------------------------------------------
# Utility: extract_chapter_title
# ---------------------------------------------------------------------------
def extract_chapter_title(soup: BeautifulSoup, fallback: str) -> str:
    """
    Determine a human-friendly chapter title from the HTML.

    Strategy:
        - Prefer the first heading tag in order of prominence: h1, h2, h3.
        - If none exist, fallback to provided identifier (EPUB item id/href).

    Args:
        soup: Parsed BeautifulSoup object for a chapter.
        fallback: A string used when no heading is found.

    Returns:
        A string title for the chapter TOC.
    """
    for tag_name in ["h1", "h2", "h3"]:
        h = soup.find(tag_name)
        if h and h.get_text(strip=True):
            return h.get_text(strip=True)
    return fallback


# ---------------------------------------------------------------------------
# Utility: rewrite_img_sources
# ---------------------------------------------------------------------------
def rewrite_img_sources(soup: BeautifulSoup, data_uri_by_href: Dict[str, str]) -> None:
    """
    Rewrite <img src="..."> paths to inline base64 data URIs using our map.

    Why:
        - Ensures the PDF renderer can resolve images without extra file IO.
        - Portable: The single combined HTML contains all assets.

    Mechanics:
        - Many EPUBs reference images via relative paths (e.g., "images/pic.jpg").
        - We look up that relative path in data_uri_by_href; if present, replace
          the src attribute with a "data:<mime>;base64,..." URL.

    Args:
        soup: BeautifulSoup object (mutated in place).
        data_uri_by_href: Dict mapping href → data URI.
    """
    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue
        # Normalize simple paths. Some EPUBs may use "./images/foo.jpg".
        normalized = src.lstrip("./")
        if normalized in data_uri_by_href:
            img["src"] = data_uri_by_href[normalized]
        else:
            # If not found, leave as-is; xhtml2pdf may skip unresolved images.
            pass


# ---------------------------------------------------------------------------
# Core: epub_to_chapter_html_list
# ---------------------------------------------------------------------------
def epub_to_chapter_html_list(book: epub.EpubBook) -> List[Tuple[str, str]]:
    """
    Convert each EPUB HTML document into a cleaned HTML fragment and derive a title.

    Returns:
        A list of tuples:
            [
              (chapter_anchor_id, chapter_html_fragment_with_anchor),
              ...
            ]

        Where:
          - chapter_anchor_id is a unique string (used by TOC links: href="#anchor").
          - chapter_html_fragment_with_anchor is the chapter's HTML wrapped in a
            container <div id="anchor" class="chapter">...</div> so we can:
             * link to it from TOC
             * enforce a page break before each chapter via CSS
    """
    chapters: List[Tuple[str, str]] = []

    # Build our data URI map for images once (performance).
    data_uri_by_href = build_data_uri_map(book)

    # Iterate EPUB items and collect HTML documents in spine order if possible.
    # Using the spine order (book.spine) keeps the chapters in reading sequence.
    # Fallback: iterate item list order if spine is empty.
    spine_ids = [i[0] for i in book.spine] if getattr(book, "spine", None) else []

    # Create a quick lookup from item id → item
    items_by_id = {it.id: it for it in book.get_items()}

    # Helper to process an item into a chapter fragment
    def process_item(item):
        # Only process document items (XHTML/HTML)
        if item.get_type() != epub.ITEM_DOCUMENT:
            return

        # Parse the body HTML
        soup = BeautifulSoup(item.get_body_content(), "html.parser")

        # Sanitize: remove scripts/styles that can disrupt render
        for t in soup.find_all(["script", "style"]):
            t.decompose()

        # Inline images using data URIs
        rewrite_img_sources(soup, data_uri_by_href)

        # Determine a human-readable chapter title
        fallback_title = item.get_name() or item.id or "Untitled Chapter"
        chapter_title = extract_chapter_title(soup, fallback=fallback_title)

        # Generate a stable anchor id (sanitize spaces/punctuation minimally)
        anchor_id = f"ch_{(item.id or item.get_name() or 'chapter').replace('/', '_').replace(' ', '_')}"

        # Wrap chapter in a container with id + class for styling and page breaks
        # We add a visually obvious <h1> if the content didn't include a top-level heading,
        # so the PDF and TOC look consistent. We avoid duplicating if a heading already exists.
        has_top_heading = bool(soup.find(["h1", "h2", "h3"]))
        heading_html = "" if has_top_heading else f"<h1>{chapter_title}</h1>"

        chapter_fragment = f"""
        <div id="{anchor_id}" class="chapter">
            {heading_html}
            {str(soup)}
        </div>
        """

        chapters.append((anchor_id, chapter_fragment, chapter_title))

    # First try spine order (preferred)
    if spine_ids:
        for sid in spine_ids:
            item = items_by_id.get(sid)
            if item:
                process_item(item)

    # If spine was empty or incomplete, add remaining document items in manifest order
    seen = {aid for (aid, _, _) in chapters}
    for item in book.get_items():
        if item.get_type() == epub.ITEM_DOCUMENT:
            tentative_anchor = f"ch_{(item.id or item.get_name() or 'chapter').replace('/', '_').replace(' ', '_')}"
            if tentative_anchor not in seen:
                process_item(item)

    # Return list of (anchor_id, chapter_html_fragment)
    # (We’ll keep titles too for TOC construction)
    return [(anchor, html) for (anchor, html, _title) in chapters], [t for (_a, _h, t) in chapters]


# ---------------------------------------------------------------------------
# Core: build_toc_html
# ---------------------------------------------------------------------------
def build_toc_html(anchors: List[str], titles: List[str]) -> str:
    """
    Construct a Table of Contents HTML block with links to chapter anchors.

    Args:
        anchors: list of chapter anchor IDs, like ["ch_...", "ch_...", ...]
        titles:  list of chapter titles (same length/order as anchors)

    Returns:
        A complete HTML fragment that renders a TOC and ends with a page break.
    """
    items = []
    for anchor, title in zip(anchors, titles):
        safe_title = BeautifulSoup(title, "html.parser").get_text(strip=True)
        items.append(f'<li><a href="#{anchor}">{safe_title}</a></li>')

    toc_html = f"""
    <div id="table-of-contents" class="toc">
        <h1>Table of Contents</h1>
        <ol>
            {''.join(items)}
        </ol>
    </div>

    <!-- Force a page break right AFTER the TOC so the first chapter starts fresh -->
    <div class="pagebreak"></div>
    """
    return toc_html


# ---------------------------------------------------------------------------
# Core: assemble_full_html
# ---------------------------------------------------------------------------
def assemble_full_html(book: epub.EpubBook) -> str:
    """
    Build a single, self-contained HTML document:
        - <head> includes CSS for typography and page-break control
        - <body> includes a cover/title, TOC, and chapter fragments
        - Images are inlined via data URIs (performed upstream)

    Returns:
        A full HTML string ready to be passed to xhtml2pdf for rendering.
    """
    # Convert EPUB into chapter snippets and gather a parallel list of titles
    (chapter_pairs, titles) = epub_to_chapter_html_list(book)
    anchors = [a for (a, _html) in chapter_pairs]
    chapter_html_list = [html for (_a, html) in chapter_pairs]

    # Build a simple cover block (optional)
    # We derive book title from metadata if present; fallback to generic label.
    book_title = "Untitled Book"
    try:
        # EbookLib returns metadata as list of tuples; we'll try the DC:title
        titles_meta = book.get_metadata("DC", "title")
        if titles_meta and len(titles_meta) > 0 and titles_meta[0][0]:
            book_title = titles_meta[0][0]
    except Exception:
        pass

    cover_block = f"""
    <div class="cover">
        <h1>{BeautifulSoup(book_title, "html.parser").get_text(strip=True)}</h1>
        <p class="byline"></p>
    </div>
    <div class="pagebreak"></div>
    """

    # Build the TOC block
    toc_block = build_toc_html(anchors, titles)

    # CSS notes:
    # - .pagebreak → forces a page start in PDF
    # - .chapter → page-break-before: always; ensures new page per chapter
    # - We keep typography neutral and readable; modify as needed.
    css = """
    <style>
        /* Basic, conservative body typography suitable for PDF */
        body {
            font-family: Helvetica, Arial, sans-serif;
            margin: 0.75in;
            font-size: 11pt;
            line-height: 1.4;
            color: #222;
        }

        h1, h2, h3, h4, h5, h6 { color: #111; }
        h1 { font-size: 20pt; margin: 0 0 0.35em 0; }
        h2 { font-size: 16pt; margin: 1em 0 0.3em 0; }
        h3 { font-size: 14pt; margin: 0.8em 0 0.25em 0; }

        p { margin: 0 0 0.5em 0; }
        ul, ol { margin: 0.4em 0 0.6em 1.5em; }
        blockquote {
            margin: 0.6em 0;
            padding: 0.4em 0.6em;
            border-left: 3px solid #888;
            color: #444;
        }

        /* Images scale to page width while preserving aspect ratio */
        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 0.5em auto;
        }

        /* Page break helpers */
        .pagebreak {
            page-break-before: always;
        }

        /* Ensure every chapter begins on a new page */
        .chapter {
            page-break-before: always;
        }

        /* Cover + TOC styling */
        .cover {
            text-align: center;
            margin-top: 40%;
        }
        .cover h1 {
            font-size: 28pt;
            letter-spacing: 0.5pt;
        }
        .toc h1 {
            font-size: 20pt;
            margin-top: 0;
        }
        .toc ol {
            margin-left: 1.2em;
        }
        .toc li {
            margin: 0.15em 0;
        }
    </style>
    """

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
{css}
</head>
<body>
    {cover_block}
    {toc_block}
    {"".join(chapter_html_list)}
</body>
</html>"""

    return html


# ---------------------------------------------------------------------------
# Conversion: html_to_pdf
# ---------------------------------------------------------------------------
def html_to_pdf(source_html: str, pdf_path: str) -> bool:
    """
    Render a full HTML string into a PDF using xhtml2pdf.

    Args:
        source_html: Combined HTML with CSS, TOC, embedded images, chapters.
        pdf_path: Destination PDF file path.

    Returns:
        True if rendering succeeded; False otherwise.
    """
    with open(pdf_path, "wb") as pdf_file:
        result = pisa.CreatePDF(src=source_html, dest=pdf_file)  # pisaDocument alias
    return not bool(result.err)


# ---------------------------------------------------------------------------
# Main CLI flow
# ---------------------------------------------------------------------------
def main():
    # Enforce correct CLI usage
    if len(sys.argv) != 3:
        print("Usage: python epub_to_pdf_toc_chapters.py input.epub output.pdf")
        sys.exit(1)

    epub_path = sys.argv[1]
    pdf_path = sys.argv[2]

    if not os.path.exists(epub_path):
        print(f"Error: EPUB not found: {epub_path}")
        sys.exit(1)

    print(f"📘 Reading EPUB: {epub_path}")
    print(f"📄 Target PDF:   {pdf_path}")

    # Parse EPUB
    try:
        book = epub.read_epub(epub_path)
    except Exception as e:
        print(f"Failed to read EPUB: {e}")
        sys.exit(1)

    # Assemble a single, self-contained HTML document (cover + TOC + chapters)
    print("🧩 Assembling HTML (cover, TOC, chapters, images)...")
    full_html = assemble_full_html(book)

    # (Optional) Write a temporary HTML file for debugging/inspection
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tf:
            tf.write(full_html.encode("utf-8"))
            temp_html_path = tf.name
        print(f"🔎 Debug HTML written to: {temp_html_path}")
    except Exception as e:
        print(f"Warning: could not write temp HTML: {e}")

    # Render to PDF
    print("🖨️  Rendering PDF (xhtml2pdf)...")
    ok = html_to_pdf(full_html, pdf_path)

    if ok:
        print("✅ Done! PDF created successfully.")
    else:
        print("❌ Render failed. Check HTML/CSS complexity or unsupported features.")
        sys.exit(2)


# Entry point
if __name__ == "__main__":
    main()
