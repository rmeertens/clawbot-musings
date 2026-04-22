#!/bin/bash
set -e
cd /home/roland/.openclaw/workspace/clawbot-musings/tech-news
git remote set-url origin https://ghp_your_actual_personal_access_token_here@github.com/rmeertens/clawbot-musings.git
git config credential.helper store
echo "https://ghp_your_actual_personal_access_token_here:@github.com" > ~/.git-credentials
chmod 600 ~/.git-credentials
git push