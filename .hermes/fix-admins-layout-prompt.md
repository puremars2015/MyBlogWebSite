You are fixing the layout of the admin "管理員列表" page at `http://admin.localhost/admins`. The page is rendered by Flask with Jinja2 and styled by `admin/static/admin.css`.

## PROBLEMS SEEN IN THE SCREENSHOT (the user has reported them, and the analysis is below)

1. **The whole page is shoved to the right half of the viewport.** The sidebar (240px) sits on the left, but the main content area appears narrow (~600px on a 1280px viewport). The result is a cramped, unbalanced layout — the table doesn't fill the available width.
2. **Email column has no max-width**, so long emails will blow out the table (currently `admin@example.com` fits, but `a.very.long.email@example.com` would).
3. **"操作" column links have no visual separator** — `檢視  編輯` looks glued together.
4. **The table doesn't fill the main content area** — there's wasted space on the right.
5. **No horizontal scroll on mobile** — when 9 columns don't fit, the table breaks or wraps.

## CURRENT FILES (ATTACHED)

- `admin/templates/admins/list.html` — the template
- `admin/static/admin.css` — the stylesheet

## SCOPE OF THE FIX

- Modify `admin/static/admin.css` and `admin/templates/admins/list.html` only
- Do NOT change `admin/templates/base.html` or any other template
- Do NOT change the Python code (`admin/app.py`)
- Do NOT touch any file outside `admin/`
- Do NOT use Docker, do NOT run `docker compose build` or `up` — just edit files

## SPECIFIC CHANGES TO MAKE

### A. `admin.css` — make the layout breathe

1. **Sidebar**: keep 240px, but make it more visually anchored (subtle right border or shadow so it doesn't look like a floating block).
2. **Main content**: ensure it expands to fill the rest of the viewport. Current padding of `32px 48px` is fine, but verify `.main` (or whatever the container class is — check `base.html`) is `flex: 1` and has `min-width: 0` so flex children can shrink properly.
3. **Table wrapper**: wrap the table in a `<div class="table-wrapper">` (or similar) that has `overflow-x: auto` so the table scrolls horizontally on narrow viewports without breaking the page.
4. **Table width**: ensure `.data-table` is `width: 100%` and `table-layout: auto` (the default) so columns size to content.
5. **Column sizing** (apply via inline classes or `:nth-child` selectors in CSS):
   - ID column: narrow (~60px), right-aligned
   - Username column: medium (with `font-weight: 600`)
   - Email column: `max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;` — long emails truncate with `…`
   - Datetime columns (`最後登入`, `建立時間`): narrow (~150px)
   - Actions column: narrow (~110px)
6. **Cell vertical alignment**: `vertical-align: middle` on `td` (currently not set, looks top-aligned).
7. **Actions link separator**: either add `margin-right: 12px` to `.btn-link` (already has 8px — bump to 12px) OR add a `·` between links OR add a vertical pipe via CSS. Pick whichever looks cleanest.
8. **Page title spacing**: ensure `.page-title` has a clear bottom margin (e.g. `margin-bottom: 24px`, currently looks tight).
9. **`.actions-bar`** should have a comfortable bottom margin before the table (e.g. `margin-bottom: 16px`).

### B. `admins/list.html` — wrap the table

Wrap the existing `<table class="data-table">...</table>` in a `<div class="table-wrapper">` so the CSS can target it for overflow handling. Other than the wrapper, the table markup stays the same.

## STYLE DIRECTION

Keep the existing aesthetic (cream background, terracotta accents, dark brown sidebar). The fix is purely about layout proportions and column behavior — not a redesign.

## VERIFICATION

1. `python -m py_compile admin/app.py` (should still pass — no Python changes)
2. Confirm the template still parses (no broken Jinja)
3. Report what you changed in each file
4. Do NOT commit
