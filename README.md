# WTPN

`WTPN` is a GitHub-friendly web app for tracking Taiwanese news about police discipline, misconduct, and integrity issues.

It uses a small Python script to pull Google News RSS results for Taiwan-focused police-discipline keywords, filters them to trusted Taiwanese media outlets, and publishes a searchable front end with GitHub Pages. For local use, it also supports refreshing and persisting the news index when the user signs in.

## Why this stack

- Simple deployment: static files in `docs/` work well with GitHub Pages.
- Low maintenance: the scraper uses Python's standard library only.
- Easy automation: GitHub Actions can refresh `docs/data/news.json` on a schedule.
- Local persistence: the local server can append newly fetched items into the existing data file.

## Project structure

- `scrape_news.py`: fetches and normalizes news data.
- `local_server.py`: local server with a refresh API for sign-in triggered updates.
- `docs/index.html`: the public search interface.
- `docs/app.js`: client-side filtering, rendering, and stats.
- `docs/styles.css`: site styling.
- `docs/data/news.json`: generated article index.
- `.github/workflows/update-news.yml`: scheduled data refresh.
- `.github/workflows/deploy-pages.yml`: deploys the site to GitHub Pages.

## Local usage

```bash
python local_server.py
```

Then open `http://localhost:8000/`.

On Windows, you can also just double-click `run-local-test.bat`.

## GitHub setup

1. Push this repository to GitHub.
2. In repository settings, enable GitHub Pages with `GitHub Actions` as the source.
3. The repository already includes `docs/data/news.json`, so the site can work on first deploy.
4. The `Update News Index` workflow can be run manually or by schedule to refresh the dataset.
5. The `Deploy GitHub Pages` workflow will publish the `docs/` folder automatically.

## Notes

- Results come from Google News RSS search pages, then get filtered to Taiwan media source names.
- Local sign-in triggers a live refresh only when running through `local_server.py`. A static GitHub Pages site cannot save new files directly from the browser.
- `docs/data/news.json` now keeps previously stored articles and merges new ones on each refresh, so the local dataset can grow over time.
- This tool is best used as a monitoring and indexing layer. For citation or reporting, open the article and verify the original source.
- `WTPN` is the short project/repository name used for GitHub publishing.
- The public-facing site title can remain the Chinese system name shown in the web interface.
