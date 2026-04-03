#!/usr/bin/env python3
"""
Enrich tech news items with AI-generated summaries and InfoQ relevance assessment.

Uses local Ollama (qwen3.5:0.8b-small) running on Jetson Orin Nano.
Generates summaries and InfoQ relevance tags for each news item.

Usage:
    python3 tech-news/enrich_summaries.py [--limit N]

Output: Updates tech-news/index.html with <summary> and <infoq-relevance> sections.
"""

import re
import json
import subprocess
import sys
import time
from pathlib import Path


def fetch_news_items(html_path: str, limit: int = None) -> list:
    """Extract news items from HTML."""
    with open(html_path) as f:
        html = f.read()

    pattern = r'<article class="news-item">.*?</article>'
    articles = re.findall(pattern, html, re.DOTALL)

    items = []
    for article in articles[:limit]:
        item = {}

        # Source
        src_match = re.search(r'<span class="news-source">([^<]+)</span>', article)
        if src_match:
            item['source'] = src_match.group(1).strip()

        # Title and URL
        title_match = re.search(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', article)
        if title_match:
            item['url'] = title_match.group(1)
            item['title'] = title_match.group(2).strip()

        # Date
        date_match = re.search(r'<p class="news-date">([^<]+)</p>', article)
        if date_match:
            item['date'] = date_match.group(1).strip()

        if item.get('title'):
            items.append(item)

    return items


def summarize_with_ollama(title: str, source: str, model: str = "qwen3.5:0.8b-small") -> str:
    """Generate summary using local Ollama."""
    prompt = f"""Based on this tech news title and source, provide a 2-sentence technical summary of what this article likely covers:

Title: {title}
Source: {source}

Write a concise, informative summary that a tech professional would find useful."""

    try:
        result = subprocess.run(
            ['ollama', 'run', model, '--think=false', prompt],
            capture_output=True,
            text=True,
            timeout=45
        )
        return result.stdout.strip() if result.returncode == 0 else "(Summary generation failed)"
    except subprocess.TimeoutExpired:
        return "(Timeout during summary)"
    except Exception as e:
        return f"(Error: {e})"


def assess_infoq_relevance(title: str, source: str, summary: str, model: str = "qwen3.5:0.8b-small") -> str:
    """Assess InfoQ relevance using local Ollama."""
    prompt = f"""Assess if this tech news item would be relevant for InfoQ.com (a platform focused on software architecture, development practices, cloud, AI/ML, and technical thought leadership).

Title: {title}
Source: {source}
Summary: {summary}

Respond with EXACTLY this format:
[YES/NO] - One sentence reason."""

    try:
        result = subprocess.run(
            ['ollama', 'run', model, '--think=false', prompt],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout.strip() if result.returncode == 0 else "[SKIP] - Assessment failed"
    except Exception:
        return "[SKIP] - Assessment failed"


def enrich_items(items: list, model: str = "qwen3.5:0.8b-small") -> list:
    """Enrich items with summaries and InfoQ assessment."""
    enriched = []

    for i, item in enumerate(items, 1):
        print(f"[{i}/{len(items)}] {item['title'][:60]}...", file=sys.stderr, flush=True)

        summary = summarize_with_ollama(item['title'], item['source'], model)
        infoq = assess_infoq_relevance(item['title'], item['source'], summary, model)

        item['summary'] = summary
        item['infoq_relevance'] = infoq
        enriched.append(item)

        time.sleep(0.5)  # Rate limiting

    return enriched


def update_html(html_path: str, enriched_items: list) -> None:
    """Inject summaries and InfoQ badges into HTML."""
    with open(html_path) as f:
        html = f.read()

    # Create lookup table
    url_to_item = {item['url']: item for item in enriched_items}

    def enhance_article(match):
        article = match.group(0)

        # Extract URL
        url_match = re.search(r'<a href="([^"]+)"', article)
        if not url_match or url_match.group(1) not in url_to_item:
            return article

        url = url_match.group(1)
        item = url_to_item[url]
        summary = item.get('summary', '').strip()
        infoq = item.get('infoq_relevance', '').strip()

        # Determine InfoQ badge
        infoq_badge = ''
        if infoq.startswith('[YES]'):
            infoq_badge = '<span class="infoq-badge infoq-yes" title="Relevant for InfoQ.com">InfoQ Relevant ✓</span>'
        elif infoq.startswith('[NO]'):
            infoq_badge = '<span class="infoq-badge infoq-no" title="Not typical InfoQ content">Not InfoQ</span>'

        # Inject HTML
        injection = f'''
        <p class="news-summary"><strong>Summary:</strong> {summary}</p>
        <p class="news-infoq"><strong>InfoQ Relevance:</strong> {infoq}</p>
        {infoq_badge}'''

        article = article.replace('</article>', injection + '\n        </article>')
        return article

    # Update all articles
    html = re.sub(r'<article class="news-item">.*?</article>', enhance_article, html, flags=re.DOTALL)

    with open(html_path, 'w') as f:
        f.write(html)

    print(f"Updated {len(enriched_items)} articles in {html_path}", file=sys.stderr)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Enrich tech news with AI summaries and InfoQ relevance.")
    parser.add_argument('--limit', type=int, default=10, help="Max items to process (default: 10)")
    parser.add_argument('--model', default="qwen3.5:0.8b-small", help="Ollama model to use")
    args = parser.parse_args()

    base_dir = Path(__file__).parent
    html_path = base_dir / "index.html"

    print(f"Fetching news items from {html_path}", file=sys.stderr)
    items = fetch_news_items(str(html_path), limit=args.limit)
    print(f"Found {len(items)} items", file=sys.stderr)

    print(f"\nEnriching with {args.model}...", file=sys.stderr)
    enriched = enrich_items(items, model=args.model)

    print(f"\nUpdating HTML...", file=sys.stderr)
    update_html(str(html_path), enriched)

    # Stop Ollama to free memory
    print(f"\nStopping {args.model} to free GPU memory...", file=sys.stderr)
    subprocess.run(['ollama', 'stop', args.model], capture_output=True, timeout=10)

    print("Done!", file=sys.stderr)


if __name__ == "__main__":
    main()
