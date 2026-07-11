"""
One-time setup script: builds the FAISS index from the fixed corpus.

Run this once, after fetch_corpus.py and before starting the API server:
    python fetch_corpus.py
    python build_index.py
    uvicorn main_api:app --port 8000

This can take a while (embedding every chunk via Ollama) — that cost is paid
once here, at the command line, not in the browser. The API server never
builds the index itself; it only loads what this script produced.
"""
import os
import time

import vectorize

BASE_DIR = os.path.dirname(__file__)
VECTOR_PATH = os.path.join(BASE_DIR, "vectorDB")
CORPUS_PATH = os.path.join(BASE_DIR, "data", "sherlock_holmes.txt")


def progress_cb(stage, current, total, message):
    percent = int((current / total) * 100) if total else 0
    print(f"[{stage:>10}] {percent:3d}%  {message}")


def main():
    if os.path.exists(VECTOR_PATH):
        print(f"Index already exists at {VECTOR_PATH}.")
        answer = input("Rebuild it from scratch? (y/N): ").strip().lower()
        if answer != "y":
            print("Leaving existing index in place. Nothing to do.")
            return
        import shutil
        shutil.rmtree(VECTOR_PATH)

    if not os.path.exists(CORPUS_PATH):
        raise SystemExit(
            f"Corpus file not found at {CORPUS_PATH}. Run `python fetch_corpus.py` first."
        )

    start = time.time()
    vectorize.build_index(VECTOR_PATH, CORPUS_PATH, progress_cb=progress_cb)
    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s. Index saved to {VECTOR_PATH}.")
    print("You can now start the API server: uvicorn main_api:app --port 8000")


if __name__ == "__main__":
    main()
