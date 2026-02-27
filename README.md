# motor_oil

This repository contains a static e-commerce site for motor oil based on data scraped from https://www.racinglubes.fr.

## Structure

- `parser/` – Python script that crawls the supplier site and exports product data.
- `site/` – static site source (Hugo) using `data/products.json` produced by parser.
- `.github/workflows/` – GitHub Actions workflow to run parser, build site, and deploy to GitHub Pages.

## Getting started

1. Install Python packages:
   ```sh
   cd parser
   pip install -r requirements.txt
   ```
2. Run parser to fetch current catalog:
   ```sh
   python scrape.py
   ```
3. Build the site with Hugo (see `site/` README).

Push changes to `main` to trigger automatic build and deploy.
