#!/usr/bin/env python3
"""
generate_tree_md.py

Generates an ASCII folder structure diagram
and outputs it as a formatted Markdown file.
"""

import argparse
from pathlib import Path
from datetime import datetime


# ------------------------------------------------------------
# Default ignore list
# ------------------------------------------------------------

DEFAULT_IGNORE = {
    ".git",
    "__pycache__",
    ".DS_Store",
    "node_modules",
    ".idea",
    ".vscode"
}


# ------------------------------------------------------------
# Tree Builder
# ------------------------------------------------------------

def build_tree(root_path: Path, ignore_set=None):
    """
    Recursively builds an ASCII tree structure string.

    :param root_path: Root directory Path object
    :param ignore_set: Set of names to ignore
    :return: String containing ASCII tree
    """

    if ignore_set is None:
        ignore_set = set()

    lines = []

    def _walk(directory: Path, prefix=""):
        # Sort: directories first, then files (alphabetical)
        entries = sorted(
            [e for e in directory.iterdir() if e.name not in ignore_set],
            key=lambda e: (e.is_file(), e.name.lower())
        )

        total = len(entries)

        for index, entry in enumerate(entries):
            connector = "└── " if index == total - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")

            if entry.is_dir():
                extension = "    " if index == total - 1 else "│   "
                _walk(entry, prefix + extension)

    # Add root name at top
    lines.append(root_path.name)
    _walk(root_path)

    return "\n".join(lines)


# ------------------------------------------------------------
# Markdown Writer
# ------------------------------------------------------------

def write_markdown(output_path: Path, root_path: Path, tree_string: str):
    """
    Writes Markdown output file.

    :param output_path: Path to save .md file
    :param root_path: Root directory analyzed
    :param tree_string: ASCII tree string
    """

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    markdown_content = (
        f"# 📁 Project Structure\n\n"
        f"**Generated:** {timestamp}  \n"
        f"**Root Folder:** `{root_path.resolve()}`\n\n"
        f"---\n\n"
        f"## Directory Tree\n\n"
        f"```text\n"
        f"{tree_string}\n"
        f"```\n"
    )

    output_path.write_text(markdown_content, encoding="utf-8")


# ------------------------------------------------------------
# CLI Entry
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate ASCII folder structure diagram as Markdown."
    )

    parser.add_argument(
        "folder",
        type=str,
        help="Path to root folder"
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="folder_structure.md",
        help="Output markdown file name"
    )

    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include hidden files/folders"
    )

    args = parser.parse_args()

    root_path = Path(args.folder)

    if not root_path.exists() or not root_path.is_dir():
        print("❌ Error: Provided path is not a valid directory.")
        return

    ignore_set = set() if args.include_hidden else DEFAULT_IGNORE

    print(f"📂 Generating tree for: {root_path.resolve()}")

    tree_string = build_tree(root_path, ignore_set=ignore_set)

    output_path = Path(args.output)

    write_markdown(output_path, root_path, tree_string)

    print(f"✅ Markdown file created: {output_path.resolve()}")


# ------------------------------------------------------------
# Run
# ------------------------------------------------------------

if __name__ == "__main__":
    main()
