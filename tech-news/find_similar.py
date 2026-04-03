#!/usr/bin/env python3
"""
Find similar news articles using cosine similarity on embeddings.
Generates an HTML page showing article clusters and relationships.
"""

import json
import math
from pathlib import Path
from collections import defaultdict

EMBEDDINGS_FILE = "embeddings.json"
INDEX_HTML = "index.html"
OUTPUT_HTML = "similar.html"
SIMILARITY_THRESHOLD = 0.75  # 0.75-1.0 = very similar, 0.6-0.75 = similar

def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity between two vectors."""
    if not vec1 or not vec2:
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    mag1 = math.sqrt(sum(a * a for a in vec1))
    mag2 = math.sqrt(sum(b * b for b in vec2))
    
    if mag1 == 0 or mag2 == 0:
        return 0.0
    
    return dot_product / (mag1 * mag2)

def load_embeddings():
    """Load embeddings from JSON file."""
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    if not Path(EMBEDDINGS_FILE).exists():
        print(f"Error: {EMBEDDINGS_FILE} not found")
        return None
    
    with open(EMBEDDINGS_FILE, 'r') as f:
        return json.load(f)

def find_similar_pairs(embeddings, threshold=SIMILARITY_THRESHOLD):
    """Find all similar article pairs above threshold."""
    titles = list(embeddings.keys())
    similar_pairs = []
    
    print(f"Comparing {len(titles)} articles for similarity (threshold: {threshold})...")
    
    for i, title1 in enumerate(titles):
        for j, title2 in enumerate(titles[i+1:], i+1):
            sim = cosine_similarity(
                embeddings[title1],
                embeddings[title2]
            )
            
            if sim >= threshold:
                similar_pairs.append({
                    'title1': title1,
                    'title2': title2,
                    'similarity': sim
                })
    
    return sorted(similar_pairs, key=lambda x: x['similarity'], reverse=True)

def build_similarity_graph(similar_pairs):
    """Build a graph of related articles."""
    graph = defaultdict(set)
    
    for pair in similar_pairs:
        graph[pair['title1']].add(pair['title2'])
        graph[pair['title2']].add(pair['title1'])
    
    return graph

def generate_html(similar_pairs, graph):
    """Generate HTML page showing similar articles."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Similar Tech News Articles</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: #333;
      padding: 2rem;
      min-height: 100vh;
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
    }
    h1 {
      color: white;
      margin-bottom: 0.5rem;
      text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }
    .stats {
      color: rgba(255,255,255,0.9);
      margin-bottom: 2rem;
      font-size: 0.95rem;
    }
    .filters {
      background: white;
      padding: 1.5rem;
      border-radius: 8px;
      margin-bottom: 2rem;
      box-shadow: 0 4px 6px rgba(0,0,0,0.1);
      display: flex;
      gap: 1rem;
      align-items: center;
      flex-wrap: wrap;
    }
    .filters label {
      font-weight: 600;
    }
    .filters input {
      padding: 0.5rem;
      border: 1px solid #ddd;
      border-radius: 4px;
    }
    .pair-group {
      background: white;
      border-radius: 8px;
      margin-bottom: 1.5rem;
      box-shadow: 0 4px 6px rgba(0,0,0,0.1);
      overflow: hidden;
      transition: transform 0.2s;
    }
    .pair-group:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
    .pair-header {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 1rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .similarity-score {
      background: rgba(255,255,255,0.2);
      padding: 0.25rem 0.75rem;
      border-radius: 20px;
      font-size: 0.9rem;
      font-weight: 600;
    }
    .pair-content {
      padding: 1.5rem;
    }
    .article {
      margin-bottom: 1rem;
    }
    .article:last-child {
      margin-bottom: 0;
    }
    .article-title {
      font-weight: 600;
      color: #333;
      margin-bottom: 0.5rem;
      line-height: 1.4;
    }
    .article-links {
      display: flex;
      gap: 1rem;
      font-size: 0.85rem;
      color: #666;
    }
    .similarity-bar {
      height: 4px;
      background: #e0e0e0;
      border-radius: 2px;
      margin: 0.5rem 0;
      overflow: hidden;
    }
    .similarity-fill {
      height: 100%;
      background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
      transition: width 0.3s;
    }
    .threshold-notice {
      background: #f0f4ff;
      border-left: 4px solid #667eea;
      padding: 1rem;
      margin-bottom: 2rem;
      border-radius: 4px;
      color: #667;
    }
    .related-count {
      background: #e0e7ff;
      color: #667eea;
      padding: 0.25rem 0.5rem;
      border-radius: 4px;
      font-size: 0.85rem;
      font-weight: 600;
    }
    @media (max-width: 768px) {
      body { padding: 1rem; }
      .pair-header { flex-direction: column; align-items: flex-start; gap: 0.5rem; }
      .article-links { flex-direction: column; }
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>🔗 Similar Tech News Articles</h1>
    <p class="stats">Found <strong>{{ pair_count }}</strong> similar article pairs • {{ total_articles }} unique articles linked • Similarity threshold: {{ threshold }}</p>
    
    <div class="threshold-notice">
      <strong>ℹ️ Similarity Score:</strong> Ranges from 0 to 1.0. Higher = more semantically similar. Threshold {{ threshold }} = very similar articles on same/related topics.
    </div>
    
    <div class="filters">
      <label for="minSim">Minimum Similarity:</label>
      <input type="range" id="minSim" min="0.7" max="1.0" step="0.01" value="{{ threshold }}">
      <span id="simValue">{{ threshold }}</span>
    </div>

    <div id="pairsList">
{{ pairs_html }}
    </div>
  </div>

  <script>
    const slider = document.getElementById('minSim');
    const simValue = document.getElementById('simValue');
    const pairs = document.querySelectorAll('.pair-group');
    
    slider.addEventListener('input', (e) => {
      const threshold = parseFloat(e.target.value);
      simValue.textContent = threshold.toFixed(2);
      
      pairs.forEach(pair => {
        const score = parseFloat(pair.dataset.similarity);
        pair.style.display = score >= threshold ? '' : 'none';
      });
    });
  </script>
</body>
</html>
"""

    # Generate pairs HTML
    pairs_html_list = []
    unique_articles = set()
    
    for pair in similar_pairs:
        unique_articles.add(pair['title1'])
        unique_articles.add(pair['title2'])
        
        related1 = len(graph[pair['title1']])
        related2 = len(graph[pair['title2']])
        sim_pct = int(pair['similarity'] * 100)
        
        pair_html = f"""    <div class="pair-group" data-similarity="{pair['similarity']:.3f}">
      <div class="pair-header">
        <div>
          <div class="article-title">{pair['title1'][:80]}</div>
          <div class="similarity-bar"><div class="similarity-fill" style="width: {sim_pct}%"></div></div>
          <div class="article-title">{pair['title2'][:80]}</div>
        </div>
        <div class="similarity-score">{pair['similarity']:.1%} match</div>
      </div>
      <div class="pair-content">
        <div class="article">
          <div class="article-title">📰 {pair['title1'][:100]}</div>
          <div class="article-links">
            <span><strong>{related1}</strong> related articles</span>
          </div>
        </div>
        <div style="border-top: 1px solid #eee; margin: 1rem 0;"></div>
        <div class="article">
          <div class="article-title">📰 {pair['title2'][:100]}</div>
          <div class="article-links">
            <span><strong>{related2}</strong> related articles</span>
          </div>
        </div>
      </div>
    </div>
"""
        pairs_html_list.append(pair_html)
    
    pairs_html = "".join(pairs_html_list)
    
    # Replace placeholders
    html_content = html_content.replace("{{ pair_count }}", str(len(similar_pairs)))
    html_content = html_content.replace("{{ total_articles }}", str(len(unique_articles)))
    html_content = html_content.replace("{{ threshold }}", f"{SIMILARITY_THRESHOLD:.2f}")
    html_content = html_content.replace("{{ pairs_html }}", pairs_html)
    
    return html_content

def main():
    """Main function."""
    embeddings = load_embeddings()
    if not embeddings:
        return
    
    print(f"Loaded {len(embeddings)} embeddings")
    
    # Find similar pairs
    similar_pairs = find_similar_pairs(embeddings)
    print(f"Found {len(similar_pairs)} similar pairs")
    
    if not similar_pairs:
        print(f"No pairs found above {SIMILARITY_THRESHOLD} threshold")
        return
    
    # Build graph
    graph = build_similarity_graph(similar_pairs)
    print(f"{len(graph)} unique articles have similarities")
    
    # Generate HTML
    html = generate_html(similar_pairs, graph)
    
    with open(OUTPUT_HTML, 'w') as f:
        f.write(html)
    
    print(f"✅ Generated {OUTPUT_HTML}")
    print(f"\nTop 5 most similar pairs:")
    for i, pair in enumerate(similar_pairs[:5], 1):
        print(f"{i}. {pair['similarity']:.1%} — {pair['title1'][:60]}")
        print(f"   ↔ {pair['title2'][:60]}")

if __name__ == "__main__":
    main()
