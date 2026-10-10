# Plain dashboard implementation plan

Execute in this checkout, incorporating the existing uncommitted dashboard simplification work into the requested redesign.

1. Replace web/index.html and web/app.js with prediction-first UI; preserve audited data and archived forecasts.
2. Add web/machine-learning.html and web/machine-learning.js with plain explanation and expandable evidence. Reuse shared styles and saved JSON data.
3. Extend dashboard exporter to generate both standalone HTML files, escaping embedded JSON on each page. Add a meaningful export test for the second page and navigation.
4. Rename README heading and public display strings; keep repository URLs, Python package and historical reports intact.
5. Build, run make check and verify frozen portfolio artifacts. Use browser automation to check live default, past examples, empty states, results and desktop/mobile layout with screenshots.
6. Commit source/docs/export through a PR; verify CI, merge and confirm both deployed pages work. No model training or spent-test rerun.
