#!/usr/bin/env python3
"""
Simple tech news article evaluator - no external model calls.
Marks articles as needing manual review instead of using Ollama.
"""

import json
import sys
from datetime import datetime, timezone

def main():
    print("Starting simple tech news article evaluation (no external model calls)...")
    print(f"Current time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    try:
        with open('/home/roland/.openclaw/workspace/news_summaries.json', 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading news_summaries.json: {e}")
        sys.exit(1)
    
    items = list(data.items())
    to_evaluate = items[:10]  # Evaluate first 10 articles
    print(f"Marking {len(to_evaluate)} articles for manual review.")
    
    for url, article in to_evaluate:
        title = article.get('title', 'No title')
        print(f"Marking for review: {title}")
        
        # Clear previous evaluation and mark for manual review
        article['is_relevant'] = None  # None means needs manual review
        article['reason'] = "Marked for manual review - no automatic evaluation performed"
        article['evaluated_at'] = datetime.now(timezone.utc).isoformat()
        article['evaluation_method'] = "manual_review_needed"
        print(f"  Marked for manual review")
    
    # Write back
    try:
        with open('/home/roland/.openclaw/workspace/news_summaries.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("Marking complete. Updated news_summaries.json")
    except Exception as e:
        print(f"Error writing news_summaries.json: {e}")
        sys.exit(1)
    
    # Print summary
    evaluated_count = sum(1 for v in data.values() if v.get('is_relevant') is not None)
    manual_review_count = sum(1 for v in data.values() if v.get('is_relevant') is None)
    total_count = len(data)
    print(f"Summary: {evaluated_count}/{total_count} articles evaluated, {manual_review_count}/{total_count} need manual review")

if __name__ == '__main__':
    main()