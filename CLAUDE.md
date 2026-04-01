# Clawbot Musings

A collection of interactive articles and musings on programming, technology, and data.
Hosted on GitHub Pages at the domain in `CNAME`.

## Tech News Feed — Update Instructions

All configuration and tooling for the tech news page lives under **`tech-news/`**:

| Path | Purpose |
|------|---------|
| `tech-news/feeds.json` | RSS/Atom URLs, per-source priority, and `blocked_link_hosts` (always includes `infoq.com` so nothing on InfoQ is linked) |
| `tech-news/index.html` | The generated page (GitHub Pages serves it at `/tech-news/`) |
| `tech-news/update_feed.py` | Fetches feeds, merges, dedupes, writes `tech-news/index.html` |

### How to run locally

```bash
python3 tech-news/update_feed.py
```

Optional Jira cross-links: set the same environment variables as in `.env.example` before running.

### Automation (recommended)

GitHub Actions workflow **`.github/workflows/tech-news-feed.yml`** runs the script on a cron (09:00, 15:00, 21:00 UTC) and on manual dispatch. It commits `tech-news/index.html` when it changes.

Configure repository **secrets** (if using Jira): `JIRA_USER_EMAIL`, `JIRA_API_TOKEN`. Optional **variables**: `JIRA_DOMAIN`, `JIRA_PROJECT_KEY` (defaults can be omitted if you only use secrets for auth).

### Behaviour (matches the script)

1. Read `tech-news/feeds.json` for sources and priorities.
2. Fetch each feed (staggered requests, gzip-safe, HTTP 308 redirects, custom User-Agent).
3. Parse RSS 2.0 and Atom; extract title, link, date (`pubDate`, `published`/`updated`, or DC `date`).
4. Drop any item whose link matches `blocked_link_hosts` (InfoQ and similar).
5. Deduplicate by normalized URL; sort by date, newest first; keep **100** items.
6. If Jira env vars are set, look up tickets (same rules as before).
7. Rewrite **only** the `<strong>` timestamp inside `.last-updated` and the full `<section id="news-feed">` in `tech-news/index.html`.
8. If there are no items, show a diagnostic listing failed/empty feeds when applicable.

### Article HTML template

```html
<article class="news-item">
  <span class="news-source">{source}</span>
  <span class="priority-badge priority-{priority}">{Priority Label}</span>
  <h2 class="news-title">
    <a href="{link}" target="_blank" rel="noopener">{title}</a>
    <!-- If Jira ticket found: -->
    <a href="https://infoqnews.atlassian.net/browse/{ticket_key}" target="_blank"
       rel="noopener" style="font-size:0.75rem;font-weight:600;margin-left:0.5rem;
       color:#6b7280;text-decoration:none;" title="Jira ticket">{ticket_key}</a>
  </h2>
  <p class="news-date">{relative_date}</p>
</article>
```

Priority badge classes: `priority-very-high`, `priority-high`, `priority-medium`

### Jira key management

**Never commit Jira credentials to this repository.**

Known config (safe to store in repo):

- `JIRA_DOMAIN` = `infoqnews.atlassian.net`
- `JIRA_PROJECT_KEY` = `MLDE`

Secrets — store **only** in the scheduled trigger's environment variables or GitHub Actions secrets, never in this repo:

- `JIRA_USER_EMAIL` — the Atlassian account email for API access
- `JIRA_API_TOKEN` — API token from https://id.atlassian.com/manage-profile/security/api-tokens

See `.env.example` for the full list of variables.

### Commit message (manual or external automation)

`Auto-update: Tech news feed (YYYY-MM-DD HH:MM GMT)`
