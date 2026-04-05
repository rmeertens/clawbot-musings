#!/usr/bin/env python3
"""
Fetch world leaders and analyze their tweet sentiment.
Outputs: world-leaders-data.json
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

# World leaders dataset - country -> (leader_name, twitter_handle)
WORLD_LEADERS = {
    "United States": ("Joe Biden", "potus"),
    "United Kingdom": ("Keir Starmer", "Keir_Starmer"),
    "France": ("Emmanuel Macron", "EmmanuelMacron"),
    "Germany": ("Olaf Scholz", "Bundeskanzler"),
    "India": ("Narendra Modi", "narendramodi"),
    "China": ("Xi Jinping", None),  # No public Twitter
    "Russia": ("Vladimir Putin", None),  # No public Twitter
    "Japan": ("Shigeru Ishiba", "ishiba_shigeru"),
    "Brazil": ("Luiz Inácio Lula da Silva", "lula"),
    "Mexico": ("Claudia Sheinbaum", "claudiashein"),
    "Canada": ("Justin Trudeau", "JustinTrudeau"),
    "Australia": ("Anthony Albanese", "AlboMP"),
    "South Korea": ("Yoon Suk Yeol", "president"),
    "Spain": ("Pedro Sánchez", "sanchezcastejon"),
    "Italy": ("Giorgia Meloni", "GiorgiaMeloni"),
    "Netherlands": ("Mark Rutte", "MinPres"),
    "Belgium": ("Alexander De Croo", "alexanderdecroo"),
    "Poland": ("Donald Tusk", "donaldtusk"),
    "Sweden": ("Ulf Kristersson", "UlfKristerson"),
    "Norway": ("Jonas Gahr Støre", "jonasgahrstore"),
    "Denmark": ("Mette Frederiksen", "mettelars"),
    "Finland": ("Petteri Orpo", "PetteriOrpo"),
    "Greece": ("Kyriakos Mitsotakis", "kmitsotakis"),
    "Portugal": ("Luís Montenegro", "luis_montenegro"),
    "Austria": ("Karl Nehammer", "karlnehammer"),
    "Czech Republic": ("Petr Fiala", "PetrFiala"),
    "Hungary": ("Viktor Orbán", "PM_ViktorOrban"),
    "Romania": ("Marcel Ciolacu", "MarcelCiolacu"),
    "Turkey": ("Recep Tayyip Erdoğan", "RTErdogan"),
    "South Africa": ("Cyril Ramaphosa", "CyrilRamaphosa"),
    "Nigeria": ("Bola Tinubu", "BolaTinubu"),
    "Kenya": ("William Ruto", "WilliamsRuto"),
    "Egypt": ("Abdel Fattah el-Sisi", None),
    "Saudi Arabia": ("Mohammed bin Salman", None),
    "Israel": ("Benjamin Netanyahu", "netanyahu"),
    "UAE": ("Mohammed bin Zayed Al Nahyan", None),
    "Thailand": ("Prayut Chan-o-cha", None),
    "Indonesia": ("Prabowo Subianto", "prabowo"),
    "Philippines": ("Ferdinand "Bongbong" Marcos Jr.", "bongbongmarcos"),
    "Malaysia": ("Anwar Ibrahim", "anwaribrahim"),
    "Singapore": ("Lawrence Wong", "lwongsk"),
    "Vietnam": ("Nguyễn Phú Trọng", None),
    "Pakistan": ("Shehbaz Sharif", "CMShehbaz"),
    "Bangladesh": ("Sheikh Hasina", "PM_SheikhHasina"),
    "Chile": ("Gabriel Boric", "gabrielboric"),
    "Argentina": ("Javier Milei", "JMilei"),
    "Colombia": ("Gustavo Petro", "petrogustavo"),
    "Peru": ("Dina Boluarte", None),
    "New Zealand": ("Christopher Luxon", "nzluxon"),
    "Ireland": ("Simon Harris", "SimonHarrisTD"),
    "Luxembourg": ("Luc Frieden", "Luc_Frieden"),
    "Slovenia": ("Robert Golob", "RobertGolob"),
    "Croatia": ("Andrej Plenković", "AndrejPlenkovic"),
    "Bulgaria": ("Boyko Borissov", "boykoborissov"),
    "Serbia": ("Aleksandar Vučić", "avucic"),
    "Ukraine": ("Volodymyr Zelenskyy", "zelenskyy_official"),
}

def fetch_tweets_twitter_api(handle: str, max_tweets: int = 10) -> List[str]:
    """
    Fetch tweets using Twitter API v2.
    Requires TWITTER_BEARER_TOKEN environment variable.
    
    For now, return empty list (you'll need to set up Twitter API credentials)
    """
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
    if not bearer_token:
        print(f"Warning: TWITTER_BEARER_TOKEN not set, skipping tweets for @{handle}")
        return []
    
    try:
        import requests
        
        headers = {"Authorization": f"Bearer {bearer_token}"}
        url = "https://api.twitter.com/2/tweets/search/recent"
        params = {
            "query": f"from:{handle} -is:retweet",
            "max_results": min(max_tweets, 100),
            "tweet.fields": "created_at,author_id,public_metrics",
            "expansions": "author_id",
            "user.fields": "verified"
        }
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Twitter API error for @{handle}: {response.status_code}")
            return []
        
        data = response.json()
        tweets = []
        if "data" in data:
            for tweet in data["data"][:max_tweets]:
                tweets.append(tweet["text"])
        return tweets
    
    except ImportError:
        print("requests library not installed, skipping Twitter API fetch")
        return []
    except Exception as e:
        print(f"Error fetching tweets for @{handle}: {e}")
        return []

def analyze_sentiment_local_llm(texts: List[str]) -> Optional[Dict]:
    """
    Analyze sentiment using local Ollama LLM.
    Returns: {"score": -1.0 to 1.0, "label": "...", "summary": "..."}
    """
    if not texts:
        return None
    
    try:
        import requests
        
        # Combine texts
        combined = "\n".join(texts[:5])  # First 5 tweets
        
        # Create prompt
        prompt = f"""Analyze the sentiment of the following tweets. 
Respond with ONLY a JSON object: {{"score": <-1.0 to 1.0>, "label": "<very negative|negative|neutral|positive|very positive>", "summary": "<1-2 sentence summary>"}}

Tweets:
{combined}

RESPONSE:"""
        
        # Call local Ollama
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen3.5:0.8b-small",
                "prompt": prompt,
                "stream": False,
                "think": False
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            text = result.get("response", "").strip()
            
            # Extract JSON
            try:
                # Find JSON in response
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = text[start:end]
                    sentiment = json.loads(json_str)
                    return sentiment
            except json.JSONDecodeError:
                print(f"Failed to parse sentiment JSON: {text}")
                return None
        else:
            print(f"Ollama error: {response.status_code}")
            return None
    
    except Exception as e:
        print(f"Error analyzing sentiment: {e}")
        return None

def get_twitter_url(handle: str) -> str:
    """Generate Twitter profile URL"""
    if handle:
        return f"https://twitter.com/{handle}"
    return ""

def main():
    print("Fetching world leaders sentiment...")
    
    sentiment_data = {}
    
    for country, (leader_name, twitter_handle) in WORLD_LEADERS.items():
        print(f"\nProcessing {country} ({leader_name})...", end=" ", flush=True)
        
        if not twitter_handle:
            print("(no Twitter)")
            sentiment_data[country] = {
                "leader_name": leader_name,
                "twitter_handle": None,
                "sentiment": None,
                "score": None,
                "tweet_count": 0
            }
            continue
        
        # Fetch tweets
        tweets = fetch_tweets_twitter_api(twitter_handle)
        
        if not tweets:
            print("(no tweets)")
            sentiment_data[country] = {
                "leader_name": leader_name,
                "twitter_handle": twitter_handle,
                "twitter_url": get_twitter_url(twitter_handle),
                "sentiment": None,
                "score": None,
                "tweet_count": 0
            }
            continue
        
        print(f"({len(tweets)} tweets) analyzing...", end=" ", flush=True)
        
        # Analyze sentiment
        sentiment = analyze_sentiment_local_llm(tweets)
        
        if sentiment:
            print(f"✓ {sentiment['label']}")
            sentiment_data[country] = {
                "leader_name": leader_name,
                "twitter_handle": twitter_handle,
                "twitter_url": get_twitter_url(twitter_handle),
                "sentiment": sentiment.get("label"),
                "summary": sentiment.get("summary"),
                "score": sentiment.get("score"),
                "tweet_count": len(tweets)
            }
        else:
            print("(sentiment analysis failed)")
            sentiment_data[country] = {
                "leader_name": leader_name,
                "twitter_handle": twitter_handle,
                "twitter_url": get_twitter_url(twitter_handle),
                "sentiment": None,
                "score": None,
                "tweet_count": len(tweets)
            }
    
    # Write output
    output_file = "world-leaders-data.json"
    with open(output_file, "w") as f:
        json.dump(sentiment_data, f, indent=2)
    
    print(f"\n✓ Saved to {output_file}")
    
    # Summary stats
    with_sentiment = sum(1 for d in sentiment_data.values() if d["score"] is not None)
    print(f"\nProcessed {len(WORLD_LEADERS)} countries, sentiment data for {with_sentiment}")

if __name__ == "__main__":
    main()
