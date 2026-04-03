#!/usr/bin/env python3
"""
Generate embeddings for news article titles using Ollama.
Stores embeddings in embeddings.json for later search/similarity operations.
"""

import json
import requests
import time
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/embed"
MODEL = "nomic-embed-text"
EMBEDDINGS_FILE = "embeddings.json"
TITLES_FILE = "titles.json"

def embed_title(title):
    """Generate embedding for a single title using Ollama."""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "input": title},
            timeout=30
        )
        response.raise_for_status()
        return response.json()["embeddings"][0]
    except requests.exceptions.RequestException as e:
        print(f"Error embedding '{title}': {e}")
        return None

def generate_all_embeddings():
    """Load titles and generate embeddings for all."""
    # Ensure we're in the right directory
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    if not Path(TITLES_FILE).exists():
        print(f"Error: {TITLES_FILE} not found. Run extract_titles.py first.")
        return
    
    with open(TITLES_FILE, 'r') as f:
        titles = json.load(f)
    
    print(f"Generating embeddings for {len(titles)} titles...")
    
    embeddings = {}
    for i, title in enumerate(titles, 1):
        embedding = embed_title(title)
        if embedding:
            embeddings[title] = embedding
            print(f"[{i}/{len(titles)}] ✓ {title[:60]}")
        else:
            print(f"[{i}/{len(titles)}] ✗ {title[:60]}")
        
        # Small delay to avoid overwhelming Ollama
        if i % 10 == 0:
            time.sleep(0.5)
    
    # Save embeddings
    with open(EMBEDDINGS_FILE, 'w') as f:
        json.dump(embeddings, f, indent=2)
    
    print(f"\nSaved {len(embeddings)} embeddings to {EMBEDDINGS_FILE}")

def cleanup():
    """Stop the embedding model to free GPU memory."""
    try:
        requests.post("http://localhost:11434/api/stop", json={"model": MODEL})
        print(f"Stopped {MODEL}")
    except:
        pass

if __name__ == "__main__":
    try:
        generate_all_embeddings()
    finally:
        cleanup()
