"""
One-time setup script: downloads the public-domain corpus this app is built
around (The Adventures of Sherlock Holmes, Project Gutenberg eBook #1661)
and saves it as plain text for the embedding pipeline to consume.

Run this once before starting the API:
    python fetch_corpus.py
"""
import re
import urllib.request

SOURCE_URL = "https://www.gutenberg.org/cache/epub/1661/pg1661.txt"
OUTPUT_PATH = "data/sherlock_holmes.txt"

START_MARKER = "*** START OF THE PROJECT GUTENBERG EBOOK"
END_MARKER = "*** END OF THE PROJECT GUTENBERG EBOOK"


def main():
    print(f"Downloading corpus from {SOURCE_URL} ...")
    with urllib.request.urlopen(SOURCE_URL) as resp:
        raw = resp.read().decode("utf-8")

    # Strip the Project Gutenberg license header/footer, keep just the book text.
    start_idx = raw.find(START_MARKER)
    end_idx = raw.find(END_MARKER)
    if start_idx != -1:
        start_idx = raw.find("\n", start_idx) + 1
    else:
        start_idx = 0
    if end_idx == -1:
        end_idx = len(raw)

    body = raw[start_idx:end_idx].strip()
    body = re.sub(r"\r\n", "\n", body)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(body)

    print(f"Saved {len(body):,} characters to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
