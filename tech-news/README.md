# Tech News Update Script

This script updates the tech news feed and enriches summaries.

## Usage

Run the update process:

```bash
./update_and_push.sh
```

This will:
1. Fetch the latest feed with `update_feed.py`
2. Enrich summaries in batches of 10 (offsets 0, 10, 20)
3. Commit and push changes to GitHub

## Manual Steps

If needed, run individually:
```bash
/usr/bin/python3 update_feed.py
/usr/bin/python3 enrich_summaries.py --offset 0 --limit 10
/usr/bin/python3 enrich_summaries.py --offset 10 --limit 10
/usr/bin/python3 enrich_summaries.py --offset 20 --limit 10
git add index.html seen.json
git commit -m "tech news update: fetched feed and enriched summaries (offsets 0-20)"
git push
```