# WTPN

`WTPN` tracks Taiwanese news about police discipline, misconduct, and integrity issues. A Python standard-library scraper reads Google News RSS results, filters them to selected Taiwanese sources, and writes the index used by the static front end.

## How the site works

- `docs/` is a static, read-only web site. GitHub Pages and any ordinary static host can display and search the saved dataset, but browser code cannot change repository files.
- `scrape_news.py` refreshes `docs/data/news.json`, retaining stored articles and merging newly fetched records.
- The browser rebuilds its derived search text after loading, then filters, sorts, and paginates locally. Article identity and URL normalization are handled during refresh so repeated RSS results do not create duplicate cards without storing a second copy of searchable text.
- `local_server.py` serves only `docs/` on `127.0.0.1` and exposes the local refresh endpoint. It does not expose the repository, `.git`, or workflow files.

The sign-in screen is a convenience gate for the interface. It is client-side code on a public static site and is **not** a confidentiality or access-control boundary for the published news data. Do not put a GitHub personal access token, API secret, or other private credential in `docs/`, JavaScript, browser storage, or committed configuration.

## Project structure

- `scrape_news.py`: fetches, filters, normalizes, deduplicates, and persists news data.
- `local_server.py`: loopback-only static server and guarded local refresh API.
- `docs/index.html`: public search interface.
- `docs/app.js`: client-side filtering, pagination, rendering, and statistics.
- `docs/styles.css`: interface styling.
- `docs/data/news.json`: generated article index.
- `.github/workflows/update-news.yml`: scheduled and manual dataset refresh.

## Local use

Run:

```bash
python local_server.py
```

Then open `http://127.0.0.1:8000/`. On Windows, double-click `run-local-test.bat`.

The local server accepts refresh requests only on the loopback interface, validates the request host and origin, limits JSON request bodies, and allows one refresh at a time. Set `WTPN_LOGIN_PASSWORD` before starting the server if you need to replace the development default. Changing this server-side value alone does not change the public interface's client-side sign-in hash.

You can also update without the browser:

```bash
python scrape_news.py
```

Both methods update the same saved JSON file. Stop other refresh processes first so only one writer operates on the dataset.

## Automated updates and Pages

`Update News Index` runs every three hours and can also be started with `workflow_dispatch`. It runs the offline unit tests before fetching, commits only changed generated data, and uses an ordinary non-force push to `main`.

This repository is published by GitHub Pages' branch-based, dynamic `pages-build-deployment` workflow. A successful commit to the configured Pages branch causes that GitHub-managed deployment to publish the new static files. Keep the repository's Pages source setting and this documentation aligned if the deployment mode changes.

For a new repository using the current arrangement:

1. Push the repository to GitHub.
2. In **Settings → Pages**, select deployment from the intended branch and folder for this repository.
3. Enable Actions so the scheduled update workflow can run with `contents: write` permission.
4. Run `Update News Index` manually once and verify both its commit and the subsequent GitHub-managed Pages deployment.

## Data limits

- Search results come from Google News RSS and are filtered automatically. RSS failures, source naming changes, and classification rules can omit or misclassify articles.
- The index is a monitoring aid. Open the original article and verify it before citation or reporting.
- Previously stored records remain available across refreshes, so the index can grow over time.
