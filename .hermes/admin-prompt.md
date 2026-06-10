You are building a new admin backend Flask web app for a multi-container Docker project. The app will live at `admin/` and run as the `myblogwebsite-admin` service (port 5002 inside the Docker network). It serves the subdomain `admin.localhost` via nginx reverse proxy.

## EXISTING PROJECT CONTEXT

The project has 3 other Flask apps already running:
- `blog/app.py` (port 5000, serves blog.localhost) — has Post, Category, Tag models
- `shop/app.py` (port 5001, serves shop.localhost) — has Product, ProductCategory, Order, Member models
- All 3 apps (blog, shop, admin) share the same SQL Server database `BlogShopDB`
- SQL Server is at host `db`, port 1433, user `sa`, password from `SA_PASSWORD` env

## DATABASE SCHEMA (read this carefully — must match exactly)

Read `init-scripts/init.sql` for the full schema. Key tables admin needs to manage:

**posts** (managed by blog app, but admin has full CRUD access via direct DB):
```
id, slug (UNIQUE NVARCHAR 200), title NVARCHAR 200, excerpt NVARCHAR 500,
content NVARCHAR MAX, cover_image_url NVARCHAR 500, category_id INT,
is_published BIT, published_at DATETIME, created_at DATETIME, updated_at DATETIME
```

**products** (managed by shop app):
```
id, slug (UNIQUE NVARCHAR 200), name NVARCHAR 200, description NVARCHAR MAX,
price DECIMAL(10,2), stock INT, image_url NVARCHAR 500, category_id INT,
is_active BIT, created_at DATETIME, updated_at DATETIME
```

**orders**:
```
id, order_number (UNIQUE NVARCHAR 40), member_id INT, product_id INT,
quantity INT, total_price DECIMAL(10,2), status NVARCHAR 20,
recipient_name, recipient_phone, shipping_address, note,
created_at DATETIME, updated_at DATETIME
```

**members** (end users, NOT admins):
```
id, username (UNIQUE NVARCHAR 100), email (UNIQUE NVARCHAR 200), display_name NVARCHAR 100,
password_hash NVARCHAR 255, avatar_url NVARCHAR 500, bio NVARCHAR MAX,
is_active BIT, last_login_at, failed_login_count INT, locked_until,
created_at DATETIME, updated_at DATETIME
```

**admins** (this app's user table, already seeded with 1 superadmin):
```
id, username (UNIQUE), email (UNIQUE), display_name, password_hash,
role NVARCHAR 20  -- 'superadmin' / 'admin' / 'editor',
is_active BIT, last_login_at, failed_login_count INT, locked_until,
created_at, updated_at
```

Default seed: admin / admin123 (already in DB with werkzeug pbkdf2 hash).

**categories** (article categories, managed by blog): id, slug, name, description
**product_categories** (product categories, managed by shop): id, slug, name, description, sort_order
**tags**: id, name

## CROSS-SUBDOMAIN SESSION (important)

All 3 apps will share session cookies. Configure:
- `app.secret_key = os.environ['SESSION_SECRET']`
- `app.config['SESSION_COOKIE_DOMAIN'] = '.localhost'` (or whatever env says)
- `app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'`
- `app.config['SESSION_COOKIE_SECURE'] = False` (HTTP dev)
- `app.config['SESSION_COOKIE_NAME']` — let it default to 'session' so all 3 apps can read each other's cookies

Session payload expected for admin: `{'user_id': int, 'user_type': 'admin'}`. The `EXPECTED_USER_TYPE` env var will be 'admin' for this app. The login_required decorator must verify `session.get('user_type') == 'admin'` and that the user is_active=1 in the admins table.

## CONSTRAINTS

- Same code style as blog/app.py and shop/app.py: top-level `app = Flask(__name__)`, no blueprints, no factory pattern.
- Use `db.Unicode(...)` for all text columns, `db.UnicodeText` for content/description. NEVER use `db.String` (Latin1 issue).
- Models: duplicate what you need locally in this app (no shared models package).
- No auth library like Flask-Login — just use `session` directly + custom decorator.
- Password hashing: `werkzeug.security.generate_password_hash` / `check_password_hash`. Use `method='pbkdf2:sha256'` for consistency with seed.
- All routes return HTML (render_template) for the admin UI. No JSON API needed (admin is single-page-app-ish, all server-rendered).
- DO NOT touch any other files in the project. Only create files in `admin/`.
- DO NOT use Docker, only edit source files.
- DO NOT commit to git.

## URL STRUCTURE

```
GET  /                     → dashboard (stats) — login required
GET  /login               → login form
POST /login               → authenticate, set session
GET  /logout              → clear session, redirect to login
GET  /posts               → list all posts (paginated ?page=N)
GET  /posts/<id>          → view post detail (no edit form for now)
POST /posts/<id>/toggle-publish → toggle is_published
GET  /products            → list all products
GET  /products/<id>       → view product detail
POST /products/<id>/toggle-active → toggle is_active
GET  /orders              → list all orders, newest first
GET  /orders/<id>         → view order detail
POST /orders/<id>/status  → update order status (form field)
GET  /members             → list all members
GET  /members/<id>        → view member detail + order history
POST /members/<id>/toggle-active → enable/disable
GET  /admins              → list all admins
GET  /admins/new          → form to create new admin
POST /admins              → create admin (validate, hash pw)
GET  /admins/<id>         → view admin detail
GET  /admins/<id>/edit    → form to edit (display_name, email, role, is_active)
POST /admins/<id>         → update
POST /admins/<id>/delete  → soft delete (set is_active=0)
POST /admins/<id>/reset-password -> set new password (form: new_password)
GET  /health              → 200 OK JSON
```

## TEMPLATES (Jinja2)

All extend `base.html`. Use the same warm-cream / terracotta aesthetic as the blog:

```
admin/templates/
├── base.html                          ← shell with sidebar nav
├── login.html                         ← centered login card
├── dashboard.html                     ← grid of stat cards
├── posts/
│   ├── list.html
│   └── detail.html
├── products/
│   ├── list.html
│   └── detail.html
├── orders/
│   ├── list.html
│   └── detail.html
├── members/
│   ├── list.html
│   └── detail.html
└── admins/
    ├── list.html
    ├── form.html                      ← used for new + edit
    └── detail.html
```

`base.html` should have:
- Header: "後台管理" + 当前 admin name + logout link
- Sidebar nav: 儀表板 / 文章 / 商品 / 訂單 / 會員 / 管理員
- Main content area with `{% block content %}`
- Show flash messages at top (success / error)

`dashboard.html` should show 5 stat cards in a grid:
- 文章總數 (with published / draft breakdown)
- 商品總數 (with active / inactive breakdown)
- 訂單總數 (with status breakdown — pending / paid / shipped / done)
- 會員總數 (with active / disabled breakdown)
- 管理員總數

Each stat card links to the relevant list page.

## CSS

`admin/static/admin.css` — simple, clean. Use the same color palette:
- Background: #FAF7F2
- Text: #2C2419
- Accent: #A8553A
- Border: #E8E0D3
- Sidebar background: #2C2419 (dark) with cream text

Layout: 240px sidebar on the left, main content on the right. Tables: clean rows, hover state, action buttons.

## VERIFICATION (do not skip)

After implementation:
1. `python -m py_compile admin/app.py` — must pass
2. `python -c "from admin.app import app; print(len(list(app.url_map.iter_rules())), 'routes')"` — should be ~20
3. `python -c "from admin.app import app; print([r.rule for r in app.url_map.iter_rules()][:5])"` — quick sanity
4. `git diff --stat` summary
5. Try to `python -c "from admin.app import app; c = app.test_client(); r = c.get('/health'); print(r.status_code, r.get_json())"` to verify the test client works
6. Try `r = c.get('/')` — should redirect to /login (302)
7. Try `r = c.post('/login', data={'username': 'admin', 'password': 'admin123'})` — should set session and redirect to /
8. Try `r = c.get('/', follow_redirects=False)` after login — should return 200 HTML with "後台管理" or similar

## REFERENCE FILES (attached)

- `init-scripts/init.sql` — full DB schema
- `blog/app.py` — pattern reference for Flask app structure
- `shop/app.py` — pattern reference
- `docker-compose.yml` — service definitions
- `nginx/conf.d/nginx.conf` — nginx routing
