#!/usr/bin/env python3
"""
Generate embeddings for news articles using title + summary.
Uses nomic-embed-text model for semantic similarity matching.
Stores embeddings in embeddings.json for later search/similarity operations.

Note on summaries:
- RSS/Atom feeds are parsed for title + link only (no description extracted)
- Summaries come from manually-added <p class="news-summary"> in index.html
- Only ~10% of articles currently have summaries
- Both title-only and title+summary articles are handled gracefully
"""

import json
import os
import re
import time
from pathlib import Path

import requests

OLLAMA_URL = "http://localhost:11434/api/embed"
MODEL = "nomic-embed-text"
EMBEDDINGS_FILE = "embeddings.json"
INDEX_HTML = "index.html"


def extract_articles(html_file):
    """Extract articles from index.html using regex.
    
    Extracts: title (always) + summary (optional from manually-added HTML)
    Returns list of dicts with title, summary, combined text, and has_summary flag.
    """
    with open(html_file, 'r', encoding='utf-8') as f:
        html = f.read()
    
    articles = []
    
    # Split by article blocks
    article_blocks = re.split(r'<article class="news-item">', html)[1:]
    
    for block in article_blocks:
        # Extract title (required)
        title_match = re.search(r'<h2 class="news-title">.*?<a[^>]*>([^<]+)</a>', block, re.DOTALL)
        if not title_match:
            continue
        title = title_match.group(1).strip()
        
        # Extract summary (optional, only if manually-added to HTML)
        summary_match = re.search(r'<p class="news-summary"><strong>Summary:</strong>\s*([^<]+)', block)
        summary = summary_match.group(1).strip() if summary_match else ""
        
        # Combine for embedding: title + summary (if available) or title alone
        if title:
            combined = f"{title} {summary}" if summary else title
            articles.append({
                "title": title,
                "summary": summary,
                "text": combined,
                "has_summary": bool(summary)
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
    
    print(f"Generating embeddings for {len(articles)} articles...")
    
    embeddings = {}
    successful = 0
    
    for i, article in enumerate(articles, 1):
        # Generate embedding from combined text (title + summary or title alone)
        embedding = embed_text(article['text'])
        if embedding:
            embeddings[article['title']] = embedding
            successful += 1
            marker = "✓" if article['has_summary'] else "○"  # ✓=has summary, ○=title only
            print(f"[{i:3d}/{len(articles)}] {marker} {article['title'][:70]}")
        else:
            print(f"[{i:3d}/{len(articles)}] ✗ {article['title'][:70]}")
        
        # Small delay to avoid overwhelming Ollama
        if i % 10 == 0:
            time.sleep(0.5)
    
    # Save embeddings
    with open(EMBEDDINGS_FILE, 'w') as f:
        json.dump(embeddings, f, indent=2)
    
    # Summary statistics
    with_summary = sum(1 for a in articles if a['has_summary'])
    without_summary = len(articles) - with_summary
    
    print(f"\n✅ Saved {successful}/{len(articles)} embeddings to {EMBEDDINGS_FILE}")
    print(f"Model: {MODEL}")
    print(f"Input breakdown:")
    print(f"  ✓ {with_summary} articles with title + summary")
    print(f"  ○ {without_summary} articles with title only")
    print(f"\nℹ️  Summaries are manually added to HTML, not extracted from RSS feeds.")
    print(f"To improve: Modify update_feed.py to extract <description>/<content>")


def cleanup():
    """Stop the embedding model to free GPU memory on Jetson."""
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
