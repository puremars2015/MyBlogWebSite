You are adding a server-side rendered frontend to a Flask + SQLAlchemy + SQL Server multi-container project at this directory. Read the attached files first to understand the current state:
- blog/app.py — current blog API (JSON only, ~347 lines)
- shop/app.py — current shop API (JSON only, ~384 lines)
- docker-compose.yml — service definitions
- nginx/conf.d/nginx.conf — current routing (proxies /blog/ and /shop/ to backend JSON APIs)

Both Flask apps already have all the data, models, and CRUD endpoints. Your job is to ADD Jinja2 HTML pages in front of the existing API, and MOVE the existing JSON routes to an /api/ prefix so they do not collide with the HTML pages.

## CONSTRAINTS

- Use Flask built-in Jinja2 — do NOT add new dependencies. The image already has Flask.
- One shared CSS file (per app) for styling. No JS frameworks. Vanilla JS only if needed for interactivity.
- Keep existing API JSON behavior intact (just change the URL prefix). All existing tests/clients that hit /blog/posts etc. should hit /api/blog/posts instead.
- DO NOT change docker-compose.yml, Dockerfile, init.sql, or nginx.conf routing structure. Only ADD routes and templates to the Python files.
- DO NOT use a build step. No npm, no webpack, no Vite.
- DO NOT use Flask Blueprints or the application factory pattern. Keep the simple top-level app style.
- Do NOT add auth, comments, or admin features. Pure read-only public site.
- Cross-app queries: each app already queries the other app tables directly via raw SQL. Reuse that pattern.

## URL STRUCTURE

Public HTML pages (rendered by Jinja):
- GET / (in blog app) — homepage: latest 4 published posts + 4 featured products
- GET /articles/ — full article list (newest first, paginated ?page=N, 10/page)
- GET /articles/<slug> — single article page with full content + recommended products
- GET /articles/category/<category_slug> — articles in that category
- GET /articles/tag/<tag_name> — articles with that tag
- GET /shop (in shop app) — full product list (paginated ?page=N, 12/page)
- GET /shop/<slug> — single product page + posts that recommend it
- GET /shop/category/<category_slug> — products in that category

JSON API (existing endpoints, just moved to /api/ prefix):
- All existing /blog/... and /shop/... routes that return JSON move to /api/blog/... and /api/shop/...
- Keep all their request/response shapes identical
- Keep their POST/PUT/DELETE behavior (these are admin/CMS routes, no HTML wrapping)
- Health endpoints stay at /health (no /api/ prefix needed; same response)

Template files (Jinja2):
- blog/templates/base.html — layout shared by all blog HTML pages (header with nav, footer, link to style.css)
- blog/templates/index.html — homepage
- blog/templates/articles_list.html
- blog/templates/article_detail.html
- blog/templates/category.html — generic, used for both article-category and article-tag
- blog/static/style.css — single CSS file for blog templates
- shop/templates/shop_base.html — shop layout
- shop/templates/shop_list.html
- shop/templates/shop_detail.html
- shop/templates/shop_category.html
- shop/static/shop.css (or share with blog; you decide)

## DESIGN DIRECTION (lifestyle + curated goods aesthetic)

- Color palette: warm cream background #FAF7F2, deep brown text #2C2419, accent #A8553A (terracotta), subtle divider #E8E0D3
- Typography: serif for Chinese titles (use generic "serif" — user can swap to Noto Serif TC later), sans-serif for body
- Generous whitespace, max-width 720px for article body, 1200px for grids
- Article cards: cover placeholder (gray box with title overlay), title, excerpt, category badge
- Product cards: image placeholder (gray box), name, price (large), short description
- Mobile-responsive with simple flexbox/grid (no Tailwind, no Bootstrap)
- Include a small header with site name "拾光選物" and nav: 首頁 | 文章 | 商店
- Footer with copyright

## HOMEPAGE CONTENT (index.html)

1. Hero: site name "拾光選物" + tagline "慢慢生活,好好選物" (hardcode in template)
2. Section: 最新文章 — 4 most recent published posts as cards
3. Section: 本月精選 — 4 products marked by some criteria (e.g. is_active=1, order by stock ASC to surface "limited" items) as cards
4. Each card links to its detail page

## VERIFICATION (do not skip)

After implementing:
1. python -m py_compile blog/app.py shop/app.py — must pass
2. python -c "from blog.app import app; print(len(list(app.url_map.iter_rules())), 'routes')" — should be > 15 (existing 12 + new HTML routes)
3. Start a quick Flask test client and call / — must return HTML (Content-Type: text/html, body contains "拾光選物")
4. Call /api/blog/posts — must still return JSON list of 8 posts
5. Call /articles/kyoto-sanjou-afternoon — must return HTML with the article content
6. Call /shop — must return HTML with product grid
7. git diff --stat summary

## DO NOT
- Do not run docker compose up or docker compose build — I will do that
- Do not make a git commit — leave the working tree dirty
- Do not add new Python dependencies to requirements.txt
- Do not modify init-scripts/init.sql, db/, nginx/, or docker-compose.yml

## REFERENCE FILES (attached)
- blog/app.py — current blog API code
- shop/app.py — current shop API code
- docker-compose.yml — services and ports
- nginx/conf.d/nginx.conf — current proxy routing
