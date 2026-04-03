# clawbot-musings

A tiny static homepage with project ideas inspired by the playful engineering style of [Meertens.dev](https://meertens.dev).

## Files

- `index.html` — homepage markup
- `styles.css` — styling

## Run locally

Open `index.html` in a browser.

## Tech News

The `tech-news/` directory contains a curated feed of technical articles from 124+ engineering blogs and thought leaders.

### Updating the feed

```bash
cd /home/roland/clawbot-musings
python3 tech-news/update_feed.py
```

This fetches the latest articles and regenerates `tech-news/index.html` (100 items). Run it several times daily, then commit & push.

### Summarising articles with local Ollama (Jetson Orin Nano)

We can summarise tech news articles using a local Qwen 3.5 model (0.8B) running on the Jetson Orin Nano via Ollama — no cloud API needed.

**Prerequisites:** Ollama installed and running (`ollama serve` runs as a service).

**1. Run a summary (non-thinking mode for fast, direct answers):**

```bash
# CLI — pass the article text directly
ollama run qwen3.5:0.8b-small --think=false "Summarise this article: <paste article text>"

# API — useful for scripting
curl -s http://localhost:11434/api/generate -d '{
  "model": "qwen3.5:0.8b-small",
  "prompt": "Summarise this article: <article text>",
  "think": false,
  "stream": false
}'
```

**2. Stop the model after use (free GPU memory):**

```bash
ollama stop qwen3.5:0.8b-small
```

**Key flags:**

| Flag | Purpose |
|---|---|
| `--think=false` | Disables chain-of-thought reasoning (faster, direct output) |
| `--hidethinking` | Keeps thinking internally but hides it from output |
| `/set nothink` | Disable thinking in an interactive `ollama run` session |
| `/set think` | Re-enable thinking in an interactive session |

**Why non-thinking mode?** The 0.8B model is small enough to fit on the Jetson's limited memory. Disabling thinking reduces latency and token usage, giving snappy summaries without the chain-of-thought overhead.

**Why stop after use?** The Jetson Orin Nano has constrained GPU memory. Running `ollama stop` unloads the model weights, freeing VRAM for other tasks.

### Key files

- `tech-news/index.html` — Generated news page
- `tech-news/update_feed.py` — Feed fetcher script
- `tech-news/feeds.json` — Source configuration (124+ feeds)

## Next ideas

- Link each card to a real post or repo
- Add screenshots or sketches
- Turn the project cards into a small blog index
