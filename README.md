# WTPN

`WTPN` is a GitHub-friendly static web app for tracking Taiwanese news about police discipline, misconduct, and integrity issues.

It uses a small Python script to pull Google News RSS results for Taiwan-focused police-discipline keywords, filters them to trusted Taiwanese media outlets, and publishes a searchable front end with GitHub Pages.

## Why this stack

- Simple deployment: static files in `docs/` work well with GitHub Pages.
- Low maintenance: the scraper uses Python's standard library only.
- Easy automation: GitHub Actions can refresh `docs/data/news.json` on a schedule.

## Project structure

- `scrape_news.py`: fetches and normalizes news data.
- `docs/index.html`: the public search interface.
- `docs/app.js`: client-side filtering, rendering, and stats.
- `docs/styles.css`: site styling.
- `docs/data/news.json`: generated article index.
- `.github/workflows/update-news.yml`: scheduled data refresh.
- `.github/workflows/deploy-pages.yml`: deploys the site to GitHub Pages.

## Local usage

```bash
python scrape_news.py
python -m http.server 8000
```

Then open `http://localhost:8000/docs/`.

On Windows, you can also just double-click `run-local-test.bat`.

## GitHub setup

1. Push this repository to GitHub.
2. In repository settings, enable GitHub Pages with `GitHub Actions` as the source.
3. Run the `Update News Index` workflow once manually to generate the first live dataset.
4. The `Deploy GitHub Pages` workflow will publish the `docs/` folder automatically.

## Notes

- Results come from Google News RSS search pages, then get filtered to Taiwan media source names.
- This tool is best used as a monitoring and indexing layer. For citation or reporting, open the article and verify the original source.
- `WTPN` is the short project/repository name used for GitHub publishing.
- The public-facing site title can remain the Chinese system name shown in the web interface.
