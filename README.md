## Game Night Leaderboard

This repo bundles a small static site and helper script for publishing the Gravina Game Night leaderboard at `lorenzogravina.com/gamenights`.

### Project layout

- `public/` — upload the files in this folder to your web host (or let GitHub Pages deploy it). `index.html` reads from `leaderboard.json` to render the page.
- `data/config.json` — page copy and scoring rules. Update this when you tweak how points are awarded or want to change the headline/tagline.
- `data/events.json` — the running event log. Each event lists the individual point awards that were logged for that night.
- `data/guest_tokens.json` — mapping of short greeting tokens to player names.
- `scripts/manage_scores.py` — command-line helper for adding awards and rebuilding `public/leaderboard.json`.

### Updating scores

1. **Award points**

   ```bash
   python3 scripts/manage_scores.py award \
     --player "Jess" \
     --points 5 \
     --reason "Won the Heat final" \
     --event "Game Night #9" \
     --date 2024-07-12
   ```

   Any option you omit is requested interactively. The script updates `data/events.json` and regenerates `public/leaderboard.json`.

2. **Preview locally (optional)**

   Open `public/index.html` in a browser. The page fetches `leaderboard.json`, so you can double-check the updates before uploading.

3. **Deploy (automatic via GitHub Pages)**

   - Commit the updated JSON (and any other edits) and push to `main`.
   - GitHub Actions runs the workflow in `.github/workflows/deploy.yml`, rebuilds the leaderboard JSON, and publishes the `public/` folder to GitHub Pages automatically.
   - Within ~60 seconds the live site updates at `https://ytrms.github.io/game-nights/` (or your custom domain once configured).

### First-time GitHub Pages setup

1. In your GitHub repository, go to **Settings → Pages → Build and deployment**.
2. Choose **Source: GitHub Actions** (the workflow in this repo already targets Pages).
3. Push to `main` once; the `Deploy Leaderboard` workflow will create the Pages site.
4. The workflow output shows the public URL—copy it for the redirect step below.

### Hooking up your domain

**Option A: Subdomain (recommended)**

1. In Namecheap, create a new CNAME record:  
   - Host: `gamenights`  
   - Value: `ytrms.github.io.`  
   - TTL: automatic  
2. In GitHub, add `gamenights.lorenzogravina.com` as the custom domain under **Settings → Pages**. GitHub will provision HTTPS automatically.
3. Update any links on your WordPress site to point to `https://gamenights.lorenzogravina.com`.

**Option B: Redirect from `/gamenights`**

- Keep your WordPress page at `lorenzogravina.com/gamenights`, but configure it to redirect (meta refresh or WordPress redirect plugin) to the Pages URL (`https://ytrms.github.io/game-nights/` or the subdomain above). This keeps WordPress in control while leveraging the automatic deploys.

### Other helper commands

- `python3 scripts/manage_scores.py list` — print the current leaderboard in the terminal.
- `python3 scripts/manage_scores.py events` — review the event log and the points awarded at each night.
- `python3 scripts/manage_scores.py rebuild` — regenerate `public/leaderboard.json` without changing any data (useful after editing `config.json` manually).

### Personalized greeting links

Generate a short, non-obvious token for each guest so they can tap a NFC tag or QR code that greets them by name:

1. Create tokens

   ```bash
   python3 scripts/manage_scores.py tokens add "Sasha"
   ```

   The command prints something like `Sasha: Q7xG8O`. Repeat for each guest. Tokens are stored in `data/guest_tokens.json` and published to `public/guest_tokens.json` during `rebuild`.

2. Program links onto tags/cards using the token as a query parameter:

   ```
   https://ytrms.github.io/game-nights/?guest=Q7xG8O
   ```

   (You can also use `?token=...`, `?code=...`, or `?ticket=...` if you prefer.) Only valid tokens trigger the greeting; anything else hides the banner altogether.

3. Review existing tokens or remove them later:

   ```bash
   python3 scripts/manage_scores.py tokens list
   python3 scripts/manage_scores.py tokens remove Q7xG8O
   ```

### Customisation tips

- Adjust the look and feel by editing `public/styles.css`.
- Add or change scoring rules and wording in `data/config.json`.
- If you prefer to edit `events.json` manually, run `python3 scripts/manage_scores.py rebuild` afterwards to refresh the generated JSON for the live page.

Everything uses plain HTML/CSS/JS and vanilla Python (no extra packages), so it will work on any hosting plan where you can upload static files.
