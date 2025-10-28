# Repository Guidelines

## Project Structure & Module Organization
- `public/` holds the deployable static site (`index.html`, `styles.css`, JSON feeds). Upload this directory as-is to the host.
- `data/` stores the authoritative leaderboard sources (`config.json`, `events.json`, `plays.json`, `guest_tokens.json`). Edit these cautiously—scripts sync them into `public/`.
- `scripts/manage_scores.py` is the single Python entry point for awards, play logs, and rebuilds. Prefer it over manual JSON edits so timestamps and derived totals stay consistent.
- `.github/workflows/deploy.yml` rebuilds and publishes `public/` on pushes to `master`.

## Build, Test & Development Commands
- `python3 scripts/manage_scores.py rebuild` regenerates `public/leaderboard.json` and the unranked feed after any data or config edits.
- `python3 scripts/manage_scores.py award --player "Jess" --points 5` logs a ranked award; omit flags to answer prompts interactively.
- `python3 scripts/manage_scores.py plays list --limit 10` spot-checks recent plays to confirm ordering and point totals.
- `python3 scripts/manage_scores.py tokens add "Sasha"` issues greeting tokens and keeps `public/guest_tokens.json` in sync.

## Coding Style & Naming Conventions
- Python uses 4-space indentation, snake_case variables, and f-string formatting; follow PEP 8 and keep helper functions pure when possible.
- Preserve JSON structure and key casing; rely on the script to add timestamps (`2025-10-26T09:13:09.504685+00:00`) and maintain alphabetical guest tokens.
- Front-end files are plain HTML/CSS/JS—stick with vanilla patterns and keep new assets under `public/`.

## Testing & Verification
- After every award or manual JSON tweak, run `python3 scripts/manage_scores.py rebuild` and open `public/index.html` (and `plays.html` / `points.html`) in a browser to confirm charts and totals.
- Use `python3 scripts/manage_scores.py list` to double-check leaderboard ordering against expected scores.
- No automated tests exist; document manual checks in PR descriptions.

## Commit & Pull Request Guidelines
- Follow the existing short, imperative style (`add unranked page`, `fix wrong score`). Group related JSON updates and script changes in one commit when they must ship together.
- For PRs, provide: objective summary, data files touched, rebuild command output, and before/after screenshots when UI changes are visible.
- Link issues or describe the triggering event (e.g., “GN#12 scoring update”). Tag reviewers who manage deployment so they can monitor the Pages workflow.

## Deployment & Data Handling
- The GitHub Pages workflow expects `master`; ensure branches merge cleanly before triggering deploys.
- Never edit generated files in `public/leaderboard*.json` by hand—rerun `rebuild` instead so ranked/unranked views stay aligned.
- Keep raw data files committed; losing history complicates retroactive score corrections.
