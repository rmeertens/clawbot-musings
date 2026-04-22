#!/bin/bash
set -e
cd /home/roland/.openclaw/workspace/clawbot-musings/tech-news
echo "Running update_feed.py"
/usr/bin/python3 update_feed.py
echo "Running enrich_summaries.py offset 0"
/usr/bin/python3 enrich_summaries.py --offset 0 --limit 10
echo "Running enrich_summaries.py offset 10"
/usr/bin/python3 enrich_summaries.py --offset 10 --limit 10
echo "Running enrich_summaries.py offset 20"
/usr/bin/python3 enrich_summaries.py --offset 20 --limit 10
git add index.html seen.json
git commit -m "tech news update: fetched feed and enriched summaries (offsets 0-20)"
echo "Attempting push..."
GIT_ASKPASS=/home/roland/.openclaw/workspace/clawbot-musings/tech-news/git-askpass.sh GIT_TERMINAL_PROMPT=0 git push https://ghp_your_actual_personal_access_token_here@github.com/rmeertens/clawbot-musings.git