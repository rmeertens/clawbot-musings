# Tech News Feed

Curated technical articles from 35+ engineering blogs and thought leaders, updated twice daily.

## Overview

- **Main page:** `../tech-news.html`
- **Sources:** Netflix, Meta, Uber, Lyft, Airbnb, Pinterest, Stripe, Slack, GitHub, Cloudflare, Databricks, NVIDIA, AWS, Azure, Google Cloud, OpenAI, Anthropic, Hugging Face, Simon Willison, and more
- **Topics:** AI, ML, cloud infrastructure, distributed systems, architecture, software engineering
- **Update frequency:** Twice daily (automated)

## How to Trigger Updates

### Automated (Recommended)

The tech news feed should be updated via an automated cron job or scheduled workflow:

1. **OpenClaw Cron Job** (preferred):
   - Create a cron task that runs a feed scraper/aggregator twice daily
   - Regenerates `../tech-news.html` with latest articles
   - Respects priority rankings and source filtering
   - Example schedule: `0 6,18 * * *` (6 AM and 6 PM GMT)

2. **GitHub Actions** (alternative):
   - Set up a workflow to scrape feeds every 12 hours
   - Commit updated `tech-news.html` to the repo
   - Trigger on schedule or manual dispatch

3. **External feed aggregator**:
   - Point to RSS/Atom feeds from each engineering blog
   - Filter and rank by relevance/priority
   - Generate static HTML output

### Manual Trigger

For immediate updates:

```bash
# IMPORTANT: Always pull the latest version first
cd /home/roland/.openclaw/workspace/clawbot-musings
git pull

# Then run the feed updater
python tech-news/update_feed.py
```

**Remember:** Always run `git pull` before executing `update_feed.py` to ensure you have the latest feed configuration and script updates.

## Feed Format

The HTML file includes:

- **news-source**: Blog/publication name (Simon Willison, AWS ML, GitHub, etc.)
- **priority-badge**: Very High, High, or Medium
- **news-title**: Article headline (linked)
- **news-date**: Publication date (Today, Yesterday, N days ago)
- **last-updated**: Timestamp of when the feed was last refreshed

## Next Steps

1. Build/adapt a feed aggregator (Python/Node.js) that:
   - Fetches RSS/Atom feeds from source blogs
   - Filters articles by relevance (keywords: AI, ML, cloud, architecture, etc.)
   - Ranks by priority/engagement
   - Generates static HTML from a template

2. Schedule it with OpenClaw cron (`openclaw cron add ...`) or GitHub Actions

3. Link to InfoQ Jira workflow if this feeds into news curation tasks

---

**Last updated:** 2026-04-02 12:38 GMT+1
