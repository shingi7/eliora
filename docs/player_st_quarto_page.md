# Player ST Prototype (Standalone HTML)

- Prototype source: site/player-st.html
- Copied output: docs/site/player-st.html
- JS path: docs/site/player-st.js
- JSON path: docs/site/data/player_st_comparison_features.json
- GitHub Pages URL path: /site/player-st.html

Note: this remains a standalone static HTML page to avoid Quarto markdown rendering issues. The assets are copied into `docs/` during `quarto render`.

## Troubleshooting
- This page must be viewed via GitHub Pages or a local HTTP server. Opening the HTML directly from disk (file://) can cause fetch() to fail.
- Local test command: `python -m http.server 8000 -d docs`
- Local test URL: `http://localhost:8000/site/player-st.html`
