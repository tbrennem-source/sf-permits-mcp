## Agent 3D: Permit Click Target Fix

### Changes
- Changed permit number links from DBI portal to `/tools/station-predictor?permit=` as primary click target
- Added secondary "View on DBI →" link next to permit numbers (small, --text-tertiary color)
- Updated `md_to_html` in `web/helpers.py` to:
  - Add `class="dbi-link"` to all DBI portal links (`dbiweb02.sfgov.org`)
  - Add `target="_blank" rel="noopener noreferrer"` to all external `https://` links
  - Internal links (starting with `/`) are not affected

### Modified Files
- `src/tools/permit_lookup.py` — 5 permit link locations updated:
  1. New permits (filed) list — address/block lookup results
  2. Recently issued permits list — address/block lookup results
  3. Recently completed permits list — address/block lookup results
  4. Permit table rows in address/block search results
  5. `_format_permit_detail()` — single permit detail card
- `web/helpers.py` — `md_to_html()` updated with external link post-processing
- `web/templates/index.html` — `.dbi-link` CSS added to `.result-card` section
- `web/templates/search_results.html` — `.dbi-link` CSS added to `.search-result-card` section
- `web/templates/search_results_public.html` — `.dbi-link` CSS added to `.results-content` section

### Created Files
- `tests/test_permit_click_target.py` — 12 tests covering:
  - CSS class presence in all 3 search result templates
  - `--text-tertiary` token usage for DBI link
  - `_format_permit_detail` primary link is station predictor
  - `_format_permit_detail` DBI link present as secondary with "View on DBI" label
  - DBI is NOT the primary link for permit number
  - `md_to_html` adds `class="dbi-link"` to DBI links
  - `md_to_html` adds `target="_blank"` to DBI links
  - Internal station predictor links do NOT get `target="_blank"`
  - Non-DBI external links get `target="_blank"` but NOT `class="dbi-link"`
  - End-to-end table row link ordering (station predictor before DBI)
