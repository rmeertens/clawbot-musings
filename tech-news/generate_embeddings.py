#!/usr/bin/env python3
"""
Generate embeddings for news articles using title + summary.
Uses nomic-embed-text model for semantic similarity matching.
Stores embeddings in embeddings.json for later search/similarity operations.
"""

import json
import requests
import time
import os
import re
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/embed"
MODEL = "nomic-embed-text"
EMBEDDINGS_FILE = "embeddings.json"
INDEX_HTML = "index.html"

def extract_articles(html_file):
    """Extract articles using regex from index.html."""
    with open(html_file, 'r') as f:
        html = f.read()
    
    articles = []
    
    # Split by article items
    article_blocks = re.split(r'<article class="news-item">', html)[1:]
    
    for block in article_blocks:
        # Extract title from <h2 class="news-title">
        title_match = re.search(r'<h2 class="news-title">.*?<a[^>]*>([^<]+)</a>', block, re.DOTALL)
        if not title_match:
            continue
        
        title = title_match.group(1).strip()
        
        # Extract summary if present
        summary_match = re.search(r'<p class="news-summary"><strong>Summary:</strong>\s*([^<]+)', block)
        summary = summary_match.group(1).strip() if summary_match else ""
        
        # Use title + summary if available, otherwise just title
        if title:
            articles.append({
                "title": title,
                "summary": summary,
                "text": f"{title} {summary}" if summary else title
            })
    
    return articles

def embed_text(text):
    """Generate embedding for text using Ollama."""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "input": text},
            timeout=30
        )
        response.raise_for_status()
        return response.json()["embeddings"][0]
    except requests.exceptions.RequestException as e:
        print(f"Error embedding text: {e}")
        return None

def generate_all_embeddings():
    """Extract articles and generate embeddings."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    if not Path(INDEX_HTML).exists():
        print(f"Error: {INDEX_HTML} not found")
        return
    
    # Extract articles
    print(f"Extracting articles from {INDEX_HTML}...")
    articles = extract_articles(INDEX_HTML)
    print(f"Extracted {len(articles)} articles")
    
    if not articles:
        print("No articles found")
        return
    
    print(f"Generating embeddings for {len(articles)} articles (title + summary)...")
    
    embeddings = {}
    successful = 0
    
    for i, article in enumerate(articles, 1):
        embedding = embed_text(article['text'])
        if embedding:
            # Use title as key
            embeddings[article['title']] = embedding
            successful += 1
            has_summary = "✓" if article['summary'] else "○"
            print(f"[{i:3d}/{len(articles)}] {has_summary} {article['title'][:70]}")
        else:
            print(f"[{i:3d}/{len(articles)}] ✗ {article['title'][:70]}")
        
        # Small delay to avoid overwhelming Ollama
        if i % 10 == 0:
            time.sleep(0.5)
    
    # Save embeddings
    with open(EMBEDDINGS_FILE, 'w') as f:
        json.dump(embeddings, f, indent=2)
    
    print(f"\n✅ Saved {successful}/{len(articles)} embeddings to {EMBEDDINGS_FILE}")
    print(f"Model: {MODEL}")
    print(f"Input: Title + Summary (when available) for semantic matching")

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
