#!/usr/bin/env python3
import json
import requests
import sys
from datetime import datetime, timezone

def evaluate_with_ollama(title):
    prompt = f"""Title: {title}

Is this article relevant for InfoQ? InfoQ covers topics such as software development, architecture, AI/ML, DevOps, cloud, etc. Answer with 'relevant' or 'not relevant' and a brief reason."""
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "phi3:3.8b",
                "prompt": prompt,
                "stream": False
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        output = result.get('response', '').strip()
        if not output:
            return False, "No response from model"
        lower_output = output.lower()
        if 'relevant' in lower_output and 'not relevant' not in lower_output:
            is_relevant = True
        else:
            is_relevant = False
        return is_relevant, output
    except Exception as e:
        return False, f"Error during evaluation: {str(e)}"

def main():
    print("Starting tech news article evaluation for up to 10 articles...")
    print(f"Current time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    try:
        with open('/home/roland/.openclaw/workspace/news_summaries.json', 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading news_summaries.json: {e}")
        sys.exit(1)
    
    items = list(data.items())
    to_evaluate = items[:10]
    print(f"Evaluating {len(to_evaluate)} articles.")
    
    for url, article in to_evaluate:
        title = article.get('title', 'No title')
        print(f"Evaluating: {title}")
        
        # Clear previous evaluation
        article.pop('is_relevant', None)
        article.pop('reason', None)
        article.pop('evaluated_at', None)
        
        is_relevant, reason = evaluate_with_ollama(title)
        article['is_relevant'] = is_relevant
        article['reason'] = reason
        article['evaluated_at'] = datetime.now(timezone.utc).isoformat()
        print(f"  Result: {'Relevant' if is_relevant else 'Not relevant'} - {reason[:100]}...")
    
    # Write back
    try:
        with open('/home/roland/.openclaw/workspace/news_summaries.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("Evaluation complete. Updated news_summaries.json")
    except Exception as e:
        print(f"Error writing news_summaries.json: {e}")
        sys.exit(1)
    
    # Print summary
    relevant_count = sum(1 for v in data.values() if v.get('is_relevant') == True)
    total_count = len(data)
    print(f"Summary: {relevant_count}/{total_count} articles marked as relevant")

if __name__ == '__main__':
    main()