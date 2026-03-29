# Clawbot Musings

A collection of interactive articles and musings on programming, technology, and data.
Hosted on GitHub Pages at the domain in `CNAME`.

## Tech News Feed — Update Instructions

`tech-news.html` is automatically updated by a scheduled agent twice daily (9:00 and 21:00 GMT).

### What to do on each update run

1. **Read `feeds.json`** to get the list of RSS/Atom feed URLs and their priority ratings.

2. **Fetch every feed** using WebFetch. For each feed parse all `<item>` / `<entry>` elements and extract:
   - `title` — article title (strip HTML entities)
   - `link` — canonical URL
   - `pubDate` / `published` / `updated` — publication date
   - `source` — the `name` field from `feeds.json`
   - `priority` — the `priority` field from `feeds.json`

3. **Deduplicate by URL** across all feeds.

4. **Sort by publication date, newest first.**

5. **Keep the latest 100 items.** Do NOT apply any other date filter (e.g. "today only" or "since last run"). Show items from up to 14 days ago if needed to fill 100 slots.

6. **Jira cross-reference** (optional — only when env vars are available):
   - Required env vars: `JIRA_DOMAIN`, `JIRA_USER_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`
   - For each item, search the Jira project for a ticket whose summary or description contains the article URL or a close match to the title.
   - If a matching ticket is found, add a link to it next to the article using the ticket key (e.g. `MLDE-1234`).
   - API endpoint: `https://{JIRA_DOMAIN}/rest/api/2/search?jql=project={JIRA_PROJECT_KEY}+AND+text~"{url_or_title}"`
   - Auth: HTTP Basic with `{JIRA_USER_EMAIL}:{JIRA_API_TOKEN}` (base64-encoded).

7. **Rewrite `tech-news.html`** keeping all existing CSS/HTML structure intact, only replacing:
   - The `<strong>` timestamp inside `.last-updated`
   - The entire `<section id="news-feed">` block

8. **If no items are found** (all feeds returned errors or truly empty), show a diagnostic message listing which feeds failed rather than the generic "No new items found" message. Example:
   ```html
   <p style="text-align:center;padding:2rem;color:#6b7280;">
     Could not fetch articles. Feeds tried: InfoQ (403), Simon Willison (timeout), ...
   </p>
   ```

9. **Commit and push** with message: `Auto-update: Tech news feed (YYYY-MM-DD HH:MM GMT)`

### Article HTML template

```html
<article class="news-item">
  <span class="news-source">{source}</span>
  <span class="priority-badge priority-{priority}">{Priority Label}</span>
  <h2 class="news-title">
    <a href="{link}" target="_blank" rel="noopener">{title}</a>
    <!-- If Jira ticket found: -->
    <a href="https://{JIRA_DOMAIN}/browse/{ticket_key}" target="_blank"
       rel="noopener" style="font-size:0.75rem;font-weight:600;margin-left:0.5rem;
       color:#6b7280;text-decoration:none;" title="Jira ticket">{ticket_key}</a>
  </h2>
  <p class="news-date">{relative_date}</p>
</article>
```

Priority badge classes: `priority-very-high`, `priority-high`, `priority-medium`

### Jira key management

**Never commit Jira credentials to this repository.**

Store them as environment variables in the scheduled trigger's settings:
- `JIRA_DOMAIN` — e.g. `yourorg.atlassian.net`
- `JIRA_USER_EMAIL` — the account email for API access
- `JIRA_API_TOKEN` — API token from https://id.atlassian.com/manage-profile/security/api-tokens
- `JIRA_PROJECT_KEY` — e.g. `MLDE`

To update these, edit the scheduled trigger's environment variables in Claude Code settings.
See `.env.example` for the full list of required variables.
