import os
from datetime import datetime
from functools import wraps
from flask import Flask, jsonify, request, render_template, url_for, session, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_url_path='/static', static_folder='static')

db_host = os.getenv('DB_HOST', 'db')
db_port = os.getenv('DB_PORT', '1433')
db_name = os.getenv('DB_NAME', 'BlogShopDB')
db_user = os.getenv('DB_USER', 'sa')
db_password = os.getenv('DB_PASSWORD', '')

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f'mssql+pyodbc://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    '?driver=ODBC Driver 18 for SQL Server'
    '&TrustServerCertificate=yes'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 跨子網域 session(3 個 app 共享 SESSION_SECRET + cookie domain .localhost)
app.secret_key = os.environ.get('SESSION_SECRET', 'dev-secret-key')
# SESSION_COOKIE_DOMAIN 預設不設(讓 Flask 用 origin 比對)
# 之前設 .localhost 被某些客戶端拒絕('bad tailmatch domain')。# 改用 origin-only cookie,代價是會員跨子網域 session 不再共用。
# 在正式網域(設 Domain=.yourdomain.com)就完全沒這問題。
# app.config['SESSION_COOKIE_DOMAIN'] = os.environ.get('SESSION_COOKIE_DOMAIN', '.localhost')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
EXPECTED_USER_TYPE = os.getenv('EXPECTED_USER_TYPE', 'member')


# 跨子網域 URL
SHOP_HOST = os.getenv('SHOP_HOST', 'http://shop.localhost')
db = SQLAlchemy(app)


# ============================================================
# Auth helpers
# ============================================================
def login_required_member(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_type') != EXPECTED_USER_TYPE:
            return redirect(url_for('member_login', next=request.url))
        member = db.session.get(Member, session.get('user_id'))
        if not member or not member.is_active:
            session.clear()
            return redirect(url_for('member_login'))
        return f(*args, **kwargs)
    return decorated


def current_member():
    if session.get('user_type') == EXPECTED_USER_TYPE:
        return db.session.get(Member, session.get('user_id'))
    return None


@app.context_processor
def inject_globals():
    return {'current_user': current_member()}

# ============================================================
# Jinja helpers — 跨子網域 URL
# ============================================================
@app.template_global()
def shop_url(path):
    """產生指向 shop 子網域的完整 URL"""
    if not path.startswith('/'):
        path = '/' + path
    return SHOP_HOST + path



class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.Unicode(80), unique=True, nullable=False)
    name = db.Column(db.Unicode(100), nullable=False)
    description = db.Column(db.Unicode(500))

    def to_dict(self):
        return {
            'id': self.id,
            'slug': self.slug,
            'name': self.name,
            'description': self.description
        }


class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Unicode(50), unique=True, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name
        }


post_tags = db.Table('post_tags',
    db.Column('post_id', db.Integer, db.ForeignKey('posts.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)


class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.Unicode(200), unique=True, nullable=False)
    title = db.Column(db.Unicode(200), nullable=False)
    excerpt = db.Column(db.Unicode(500))
    content = db.Column(db.UnicodeText, nullable=False)
    cover_image_url = db.Column(db.Unicode(500))
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    is_published = db.Column(db.Boolean, default=True)
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    category = db.relationship('Category', lazy='joined')
    tags = db.relationship('Tag', secondary=post_tags, lazy='selectin')

    def to_dict(self, include_tags=True, include_products=False):
        result = {
            'id': self.id,
            'slug': self.slug,
            'title': self.title,
            'excerpt': self.excerpt,
            'content': self.content,
            'cover_image_url': self.cover_image_url,
            'category': {'id': self.category.id, 'slug': self.category.slug, 'name': self.category.name} if self.category else None,
            'is_published': self.is_published,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        if include_tags:
            result['tags'] = [t.name for t in self.tags]
        if include_products:
            result['products'] = self._get_products()
        return result

    def _get_products(self):
        query = text('''
            SELECT p.id, p.slug, p.name, p.price, p.image_url
            FROM products p
            INNER JOIN post_products pp ON p.id = pp.product_id
            WHERE pp.post_id = :post_id
            ORDER BY pp.sort_order
        ''')
        rows = db.session.execute(query, {'post_id': self.id}).fetchall()
        return [{
            'id': r.id,
            'slug': r.slug,
            'name': r.name,
            'price': float(r.price),
            'image_url': r.image_url,
            'url': f'{SHOP_HOST}/{r.slug}'
        } for r in rows]


class Member(db.Model):
    """網站會員(blog 跟 shop 共用)"""
    __tablename__ = 'members'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.Unicode(100), nullable=False, unique=True)
    email = db.Column(db.Unicode(200), nullable=False, unique=True)
    display_name = db.Column(db.Unicode(100))
    password_hash = db.Column(db.Unicode(255), nullable=False)
    avatar_url = db.Column(db.Unicode(500))
    bio = db.Column(db.UnicodeText)
    is_active = db.Column(db.Boolean, default=True)
    last_login_at = db.Column(db.DateTime)
    failed_login_count = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.Unicode(200), unique=True, nullable=False)
    name = db.Column(db.Unicode(200), nullable=False)
    description = db.Column(db.UnicodeText)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, default=0)
    image_url = db.Column(db.Unicode(500))
    category_id = db.Column(db.Integer, db.ForeignKey('product_categories.id'))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'slug': self.slug,
            'name': self.name,
            'description': self.description,
            'price': float(self.price) if self.price else 0,
            'stock': self.stock,
            'image_url': self.image_url,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


@app.route('/')
def index():
    recent_posts = Post.query.filter(Post.is_published == True).order_by(Post.published_at.desc()).limit(4).all()
    featured_products = Product.query.filter(Product.is_active == True).order_by(Product.stock.asc()).limit(4).all()
    return render_template('index.html', posts=recent_posts, products=featured_products)

@app.route('/articles/')
def articles_list():
    page = max(1, int(request.args.get('page', 1)))
    per_page = 10
    offset = (page - 1) * per_page
    query = Post.query.filter(Post.is_published == True).order_by(Post.published_at.desc())
    total = query.count()
    posts = query.offset(offset).limit(per_page).all()
    return render_template('articles_list.html', posts=posts, total=total, page=page, per_page=per_page)

@app.route('/articles/<slug>')
def article_detail(slug):
    post = Post.query.filter_by(slug=slug).first()
    if not post or not post.is_published:
        return render_template('article_not_found.html', slug=slug), 404
    products = post._get_products()
    recommended_posts = Post.query.filter(
        Post.is_published == True,
        Post.category_id == post.category_id,
        Post.id != post.id
    ).order_by(Post.published_at.desc()).limit(3).all()
    return render_template('article_detail.html', post=post, products=products, recommended_posts=recommended_posts)

@app.route('/articles/category/<category_slug>')
def article_category(category_slug):
    cat = Category.query.filter_by(slug=category_slug).first()
    if not cat:
        return render_template('article_not_found.html', slug=category_slug), 404
    page = max(1, int(request.args.get('page', 1)))
    per_page = 10
    offset = (page - 1) * per_page
    query = Post.query.filter(Post.is_published == True, Post.category_id == cat.id).order_by(Post.published_at.desc())
    total = query.count()
    posts = query.offset(offset).limit(per_page).all()
    return render_template('category.html', posts=posts, total=total, page=page, per_page=per_page, category=cat, tag_name=None)

@app.route('/articles/tag/<tag_name>')
def article_tag(tag_name):
    tag = Tag.query.filter_by(name=tag_name).first()
    if not tag:
        return render_template('article_not_found.html', slug=tag_name), 404
    page = max(1, int(request.args.get('page', 1)))
    per_page = 10
    offset = (page - 1) * per_page
    query = Post.query.join(post_tags).filter(
        post_tags.c.tag_id == tag.id,
        Post.is_published == True
    ).order_by(Post.published_at.desc())
    total = query.count()
    posts = query.offset(offset).limit(per_page).all()
    return render_template('category.html', posts=posts, total=total, page=page, per_page=per_page, category=None, tag_name=tag.name)


# ============================================================
# 會員機制 — 註冊 / 登入 / 登出 / 我的帳號
# ============================================================
@app.route('/register', methods=['GET', 'POST'])
def member_register():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        display_name = (request.form.get('display_name') or '').strip() or username

        if not username or not email or not password:
            flash('帳號、Email、密碼都是必填', 'error')
            return render_template('register.html')
        if len(password) < 6:
            flash('密碼至少 6 字元', 'error')
            return render_template('register.html')
        if Member.query.filter((Member.username == username) | (Member.email == email)).first():
            flash('帳號或 Email 已被使用', 'error')
            return render_template('register.html')

        member = Member(
            username=username,
            email=email,
            display_name=display_name,
            password_hash=generate_password_hash(password, method='pbkdf2:sha256')
        )
        db.session.add(member)
        db.session.commit()
        session.clear()
        session['user_id'] = member.id
        session['user_type'] = EXPECTED_USER_TYPE
        flash(f'歡迎 {member.display_name}!註冊成功,已自動登入', 'success')
        return redirect(url_for('member_me'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def member_login():
    if request.method == 'POST':
        username_or_email = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        next_url = request.form.get('next') or request.args.get('next') or url_for('index')

        member = Member.query.filter(
            (Member.username == username_or_email) | (Member.email == username_or_email.lower())
        ).first()
        if not member or not check_password_hash(member.password_hash, password):
            flash('帳號或密碼錯誤', 'error')
            return render_template('login.html', next=next_url)
        if not member.is_active:
            flash('此帳號已被停用,請聯絡管理員', 'error')
            return render_template('login.html', next=next_url)

        member.last_login_at = datetime.utcnow()
        member.failed_login_count = 0
        member.locked_until = None
        db.session.commit()

        session.clear()
        session['user_id'] = member.id
        session['user_type'] = EXPECTED_USER_TYPE
        flash(f'歡迎回來,{member.display_name}!', 'success')
        if not next_url.startswith('/'):
            next_url = url_for('index')
        return redirect(next_url)

    return render_template('login.html', next=request.args.get('next', ''))


@app.route('/logout')
def member_logout():
    session.clear()
    flash('已登出', 'info')
    return redirect(url_for('index'))


@app.route('/me')
@login_required_member
def member_me():
    return render_template('me.html', member=current_member())


@app.route('/me/edit', methods=['POST'])
@login_required_member
def member_me_edit():
    member = current_member()
    member.display_name = (request.form.get('display_name') or member.username).strip()
    member.bio = request.form.get('bio') or None
    avatar = (request.form.get('avatar_url') or '').strip() or None
    member.avatar_url = avatar
    member.updated_at = datetime.utcnow()
    db.session.commit()
    flash('個人資料已更新', 'success')
    return redirect(url_for('member_me'))


@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})


@app.route('/api/categories', methods=['GET'])
def get_categories():
    categories = Category.query.all()
    return jsonify([c.to_dict() for c in categories])

@app.route('/api/categories', methods=['POST'])
def create_category():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    slug = data.get('slug')
    name = data.get('name')
    if not slug or not name:
        return jsonify({'error': 'slug and name required'}), 400
    existing = Category.query.filter_by(slug=slug).first()
    if existing:
        return jsonify({'error': 'Slug already exists'}), 409
    category = Category(slug=slug, name=name, description=data.get('description'))
    db.session.add(category)
    db.session.commit()
    return jsonify(category.to_dict()), 201


@app.route('/api/tags', methods=['GET'])
def get_tags():
    tags = Tag.query.all()
    result = []
    for tag in tags:
        count_query = text('''
            SELECT COUNT(*) as cnt FROM post_tags pt
            INNER JOIN posts p ON pt.post_id = p.id
            WHERE pt.tag_id = :tag_id AND p.is_published = 1
        ''')
        count = db.session.execute(count_query, {'tag_id': tag.id}).scalar()
        result.append({'id': tag.id, 'name': tag.name, 'post_count': count})
    return jsonify(result)


@app.route('/api/posts', methods=['GET'])
def get_posts():
    category_slug = request.args.get('category')
    tag_name = request.args.get('tag')
    is_published = request.args.get('is_published', 'true').lower() == 'true'
    limit = min(int(request.args.get('limit', 20)), 100)
    offset = int(request.args.get('offset', 0))

    query = Post.query

    if category_slug:
        cat = Category.query.filter_by(slug=category_slug).first()
        if cat:
            query = query.filter(Post.category_id == cat.id)
        else:
            return jsonify({'items': [], 'total': 0, 'limit': limit, 'offset': offset})

    if tag_name:
        tag = Tag.query.filter_by(name=tag_name).first()
        if tag:
            query = query.join(post_tags).filter(post_tags.c.tag_id == tag.id)
        else:
            return jsonify({'items': [], 'total': 0, 'limit': limit, 'offset': offset})

    query = query.filter(Post.is_published == is_published)
    total = query.count()
    posts = query.order_by(Post.published_at.desc()).offset(offset).limit(limit).all()

    return jsonify({
        'items': [p.to_dict(include_tags=True, include_products=False) for p in posts],
        'total': total,
        'limit': limit,
        'offset': offset
    })

@app.route('/api/posts/<slug>', methods=['GET'])
def get_post(slug):
    post = Post.query.filter_by(slug=slug).first()
    if not post:
        return jsonify({'error': 'Post not found'}), 404
    return jsonify(post.to_dict(include_tags=True, include_products=True))

@app.route('/api/posts', methods=['POST'])
def create_post():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    title = data.get('title')
    slug = data.get('slug')
    content = data.get('content')
    if not all([title, slug, content]):
        return jsonify({'error': 'title, slug, content required'}), 400

    existing = Post.query.filter_by(slug=slug).first()
    if existing:
        return jsonify({'error': 'Slug already exists'}), 409

    category_id = data.get('category_id')
    category_slug = data.get('category_slug')
    if category_slug and not category_id:
        cat = Category.query.filter_by(slug=category_slug).first()
        if not cat:
            return jsonify({'error': 'Unknown category_slug'}), 400
        category_id = cat.id
    if not category_id:
        return jsonify({'error': 'category_id or category_slug required'}), 400

    cat = db.session.get(Category, category_id)
    if not cat:
        return jsonify({'error': 'Category not found'}), 400

    now = datetime.utcnow()
    post = Post(
        slug=slug,
        title=title,
        excerpt=data.get('excerpt'),
        content=content,
        cover_image_url=data.get('cover_image_url'),
        category_id=category_id,
        is_published=data.get('is_published', True),
        published_at=data.get('published_at') or now,
        created_at=now,
        updated_at=now
    )

    tag_ids = data.get('tag_ids', [])
    if tag_ids:
        tags = Tag.query.filter(Tag.id.in_(tag_ids)).all()
        post.tags = tags

    db.session.add(post)
    db.session.commit()
    return jsonify(post.to_dict(include_tags=True, include_products=True)), 201

@app.route('/api/posts/<int:post_id>', methods=['PUT'])
def update_post(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'error': 'Post not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    if 'slug' in data:
        existing = Post.query.filter(Post.slug == data['slug'], Post.id != post_id).first()
        if existing:
            return jsonify({'error': 'Slug already exists'}), 409
        post.slug = data['slug']

    if 'title' in data:
        post.title = data['title']
    if 'excerpt' in data:
        post.excerpt = data['excerpt']
    if 'content' in data:
        post.content = data['content']
    if 'cover_image_url' in data:
        post.cover_image_url = data['cover_image_url']
    if 'category_id' in data:
        cat = db.session.get(Category, data['category_id'])
        if not cat:
            return jsonify({'error': 'Category not found'}), 400
        post.category_id = data['category_id']
    if 'category_slug' in data:
        cat = Category.query.filter_by(slug=data['category_slug']).first()
        if not cat:
            return jsonify({'error': 'Unknown category_slug'}), 400
        post.category_id = cat.id
    if 'is_published' in data:
        post.is_published = data['is_published']
    if 'published_at' in data:
        post.published_at = data['published_at']

    if 'tag_ids' in data:
        tags = Tag.query.filter(Tag.id.in_(data['tag_ids'])).all()
        post.tags = tags

    post.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(post.to_dict(include_tags=True, include_products=True))

@app.route('/api/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'error': 'Post not found'}), 404
    post.is_published = False
    db.session.commit()
    return '', 204

@app.route('/api/posts/<int:post_id>/products', methods=['GET'])
def get_post_products(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'error': 'Post not found'}), 404
    query = text('''
        SELECT p.id, p.slug, p.name, p.price, p.image_url
        FROM products p
        INNER JOIN post_products pp ON p.id = pp.product_id
        WHERE pp.post_id = :post_id
        ORDER BY pp.sort_order
    ''')
    rows = db.session.execute(query, {'post_id': post_id}).fetchall()
    products = [{'id': r.id, 'slug': r.slug, 'name': r.name, 'price': float(r.price), 'image_url': r.image_url} for r in rows]
    return jsonify({'post_id': post_id, 'products': products})