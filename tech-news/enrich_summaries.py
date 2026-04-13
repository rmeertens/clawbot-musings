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


def fetch_news_items(html_path: str, limit: int = None, offset: int = 0, skip_enriched: bool = True) -> list:
    """Extract news items from HTML.
    
    Args:
        html_path: Path to HTML file
        limit: Max items to process
        offset: Skip first N items
        skip_enriched: Skip items that already have summaries
    """
    with open(html_path) as f:
        html = f.read()

    pattern = r'<article class="news-item">.*?</article>'
    articles = re.findall(pattern, html, re.DOTALL)

    items = []
    for article in articles:
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

        # Check if already enriched
        item['is_enriched'] = '<p class="news-summary">' in article
        
        if item.get('title'):
            items.append(item)

    # Skip enriched items if requested
    if skip_enriched:
        items = [item for item in items if not item['is_enriched']]
    
    # Apply offset and limit
    if offset > 0:
        items = items[offset:]
    if limit:
        items = items[:limit]

    return items


def summarize_with_ollama(title: str, source: str, model: str = "qwen3.5:0.8b-small") -> str:
    """Generate summary using local Ollama.

    Writes a two-sentence relevance blurb in the voice of an InfoQ editor
    pitching the article in a ticket — what problem it speaks to and why
    it's worth reading — rather than a neutral abstract.
    """
    prompt = f"""You are an InfoQ editor writing a short note in a ticket to pitch this article to a colleague.

Title: {title}
Source: {source}

Write EXACTLY two sentences explaining why this article is relevant, in a natural, first-person voice.
- Sentence 1: frame the problem or context the article speaks to (what a practitioner is struggling with or curious about).
- Sentence 2: a brief take on why it's worth reading (what the reader will get out of it).

Example of the tone and length:
"I was lately struggling a lot trying to get good performance for my projects while keeping costs low. This article is quite an interesting read."

Do not include the title, the URL, bullet points, labels, or any preamble — output only the two sentences."""

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

        # Strip out any previously injected enrichment so this is idempotent.
        article = re.sub(r'\s*<div class="news-enrichment">.*?</div>', '', article, flags=re.DOTALL)
        article = re.sub(r'\s*<p class="news-summary">.*?</p>', '', article, flags=re.DOTALL)
        article = re.sub(r'\s*<p class="news-infoq">.*?</p>', '', article, flags=re.DOTALL)
        article = re.sub(r'\s*<span class="infoq-badge[^>]*>.*?</span>', '', article, flags=re.DOTALL)

        # Parse "[YES|NO|SKIP] - reason" so we render a clean badge + reason
        # instead of leaking the raw tag into the page.
        status, reason = None, ''
        m = re.match(r'\s*\[\s*(YES|NO|SKIP)\s*\]\s*[-:\u2013]?\s*(.*)', infoq, re.DOTALL)
        if m:
            status = m.group(1).upper()
            reason = m.group(2).strip()

        if status == 'YES':
            badge = ('<span class="infoq-badge infoq-yes" '
                     'title="Relevant for InfoQ.com">InfoQ Relevant ✓</span>')
        elif status == 'NO':
            badge = ('<span class="infoq-badge infoq-no" '
                     'title="Not typical InfoQ content">Not InfoQ</span>')
        else:
            badge = ''

        infoq_line = ''
        if badge:
            reason_html = (
                f'<span class="news-infoq-reason">{reason}</span>' if reason else ''
            )
            infoq_line = (
                '\n            <p class="news-infoq">'
                f'{badge} {reason_html}</p>'
            )

        summary_html = (
            '\n            <p class="news-summary">'
            '<span class="label">Why it\'s relevant</span>'
            f'{summary}</p>'
        ) if summary else ''

        injection = (
            '\n          <div class="news-enrichment">'
            f'{summary_html}{infoq_line}'
            '\n          </div>'
        )

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
    parser.add_argument('--offset', type=int, default=0, help="Skip first N un-enriched items (default: 0)")
    parser.add_argument('--model', default="qwen3.5:0.8b-small", help="Ollama model to use")
    parser.add_argument('--all', action='store_true', help="Process all items (including re-enriching enriched ones)")
    args = parser.parse_args()

    base_dir = Path(__file__).parent
    html_path = base_dir / "index.html"

    print(f"Fetching news items from {html_path}", file=sys.stderr)
    items = fetch_news_items(str(html_path), limit=args.limit, offset=args.offset, skip_enriched=not args.all)
    print(f"Found {len(items)} items to process", file=sys.stderr)

    if not items:
        print("No items to process.", file=sys.stderr)
        return

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
