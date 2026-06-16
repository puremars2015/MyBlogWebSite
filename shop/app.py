import os
from datetime import datetime, timedelta, timezone
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

# 跨子網域 session
app.secret_key = os.environ.get('SESSION_SECRET', 'dev-secret-key')
# SESSION_COOKIE_DOMAIN 預設不設(讓 Flask 用 origin 比對)
# 之前設 .localhost 被某些客戶端拒絕('bad tailmatch domain')。# 改用 origin-only cookie,代價是會員跨子網域 session 不再共用。
# 在正式網域(設 Domain=.yourdomain.com)就完全沒這問題。
# app.config['SESSION_COOKIE_DOMAIN'] = os.environ.get('SESSION_COOKIE_DOMAIN', '.localhost')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
EXPECTED_USER_TYPE = os.getenv('EXPECTED_USER_TYPE', 'member')

# 跨子網域連結(shop 連到 blog 內容時用)
BLOG_HOST = os.getenv('BLOG_HOST', 'http://blog.localhost')

db = SQLAlchemy(app)

GMT_PLUS_8 = timezone(timedelta(hours=8))


def now_gmt8():
    return datetime.now(GMT_PLUS_8).replace(tzinfo=None)


# ============================================================
# Models
# ============================================================
class ProductCategory(db.Model):
    __tablename__ = 'product_categories'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.Unicode(80), unique=True, nullable=False)
    name = db.Column(db.Unicode(100), nullable=False)
    description = db.Column(db.Unicode(500))
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'slug': self.slug,
            'name': self.name,
            'description': self.description,
            'sort_order': self.sort_order
        }


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
    created_at = db.Column(db.DateTime, default=now_gmt8)
    updated_at = db.Column(db.DateTime, default=now_gmt8, onupdate=now_gmt8)

    category = db.relationship('ProductCategory', lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'slug': self.slug,
            'name': self.name,
            'description': self.description,
            'price': float(self.price) if self.price else 0,
            'stock': self.stock,
            'image_url': self.image_url,
            'category': self.category.to_dict() if self.category else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Member(db.Model):
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
    created_at = db.Column(db.DateTime, default=now_gmt8)
    updated_at = db.Column(db.DateTime, default=now_gmt8, onupdate=now_gmt8)


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.Unicode(40), unique=True, nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.Unicode(20), default='pending')
    recipient_name = db.Column(db.Unicode(100))
    recipient_phone = db.Column(db.Unicode(30))
    shipping_address = db.Column(db.Unicode(500))
    note = db.Column(db.Unicode(500))
    created_at = db.Column(db.DateTime, default=now_gmt8)
    updated_at = db.Column(db.DateTime, default=now_gmt8, onupdate=now_gmt8)

    member = db.relationship('Member', lazy='joined')
    product = db.relationship('Product', lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'order_number': self.order_number,
            'member_id': self.member_id,
            'member': self.member.to_dict() if self.member else None,
            'product_id': self.product_id,
            'product': self.product.to_dict(include_category=False) if self.product else None,
            'quantity': self.quantity,
            'total_price': float(self.total_price) if self.total_price else 0,
            'status': self.status,
            'recipient_name': self.recipient_name,
            'recipient_phone': self.recipient_phone,
            'shipping_address': self.shipping_address,
            'note': self.note,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Post(db.Model):
    """跨子網域用 — 課程頁要列出「哪些文章推薦這門課程」時,需要讀 posts 表"""
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.Unicode(200), unique=True, nullable=False)
    title = db.Column(db.Unicode(200), nullable=False)
    is_published = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'slug': self.slug,
            'title': self.title,
            'is_published': self.is_published
        }


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
def blog_url(path):
    """產生指向 blog 子網域的完整 URL"""
    if not path.startswith('/'):
        path = '/' + path
    return BLOG_HOST + path


# ============================================================
# 會員機制 — 註冊 / 登入 / 登出 / 我的帳號 / 我的訂單
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
        next_url = request.form.get('next') or request.args.get('next') or url_for('shop_index')

        member = Member.query.filter(
            (Member.username == username_or_email) | (Member.email == username_or_email.lower())
        ).first()
        if not member or not check_password_hash(member.password_hash, password):
            flash('帳號或密碼錯誤', 'error')
            return render_template('login.html', next=next_url)
        if not member.is_active:
            flash('此帳號已被停用,請聯絡管理員', 'error')
            return render_template('login.html', next=next_url)

        member.last_login_at = now_gmt8()
        member.failed_login_count = 0
        member.locked_until = None
        db.session.commit()

        session.clear()
        session['user_id'] = member.id
        session['user_type'] = EXPECTED_USER_TYPE
        flash(f'歡迎回來,{member.display_name}!', 'success')
        if not next_url.startswith('/'):
            next_url = url_for('shop_index')
        return redirect(next_url)

    return render_template('login.html', next=request.args.get('next', ''))


@app.route('/logout')
def member_logout():
    session.clear()
    flash('已登出', 'info')
    return redirect(url_for('shop_index'))


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
    member.updated_at = now_gmt8()
    db.session.commit()
    flash('個人資料已更新', 'success')
    return redirect(url_for('member_me'))


@app.route('/me/orders')
@login_required_member
def member_orders():
    member = current_member()
    orders = Order.query.filter(Order.member_id == member.id).order_by(Order.created_at.desc()).all()
    return render_template('my_orders.html', member=member, orders=orders)


# ============================================================
# Public HTML
# ============================================================
@app.route('/')
def shop_index():
    page = max(1, int(request.args.get('page', 1)))
    per_page = 12
    offset = (page - 1) * per_page
    query = Product.query.filter(Product.is_active == True).order_by(Product.created_at.desc())
    total = query.count()
    products = query.offset(offset).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page
    return render_template('shop_list.html',
                           products=products, total=total, page=page,
                           per_page=per_page, total_pages=total_pages)


@app.route('/<slug>')
def shop_product_detail(slug):
    product = Product.query.filter_by(slug=slug).first()
    if not product or not product.is_active:
        return render_template('shop_not_found.html', slug=slug), 404
    # 跨 app 查詢:哪些已發布文章推薦了這門課程
    query = text('''
        SELECT p.id, p.slug, p.title
        FROM posts p
        INNER JOIN post_products pp ON p.id = pp.post_id
        WHERE pp.product_id = :product_id AND p.is_published = 1
        ORDER BY pp.sort_order
    ''')
    rows = db.session.execute(query, {'product_id': product.id}).fetchall()
    posts = [{'id': r.id, 'slug': r.slug, 'title': r.title} for r in rows]
    return render_template('shop_detail.html', product=product, posts=posts)


@app.route('/category/<category_slug>')
def shop_category(category_slug):
    cat = ProductCategory.query.filter_by(slug=category_slug).first()
    if not cat:
        return render_template('shop_not_found.html', slug=category_slug), 404
    page = max(1, int(request.args.get('page', 1)))
    per_page = 12
    offset = (page - 1) * per_page
    query = Product.query.filter(
        Product.is_active == True,
        Product.category_id == cat.id
    ).order_by(Product.created_at.desc())
    total = query.count()
    products = query.offset(offset).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page
    return render_template('shop_category.html',
                           products=products, total=total, page=page,
                           per_page=per_page, total_pages=total_pages, category=cat)


@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})


# ============================================================
# JSON API(/api/...)
# ============================================================
@app.route('/api/categories', methods=['GET'])
def get_categories():
    categories = ProductCategory.query.order_by(ProductCategory.sort_order).all()
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
    existing = ProductCategory.query.filter_by(slug=slug).first()
    if existing:
        return jsonify({'error': 'Slug already exists'}), 409
    category = ProductCategory(
        slug=slug,
        name=name,
        description=data.get('description'),
        sort_order=data.get('sort_order', 0)
    )
    db.session.add(category)
    db.session.commit()
    return jsonify(category.to_dict()), 201


@app.route('/api/products', methods=['GET'])
def get_products():
    category_slug = request.args.get('category')
    is_active = request.args.get('is_active', 'true').lower() == 'true'
    limit = min(int(request.args.get('limit', 20)), 100)
    offset = int(request.args.get('offset', 0))

    query = Product.query.filter(Product.is_active == is_active)

    if category_slug:
        cat = ProductCategory.query.filter_by(slug=category_slug).first()
        if cat:
            query = query.filter(Product.category_id == cat.id)
        else:
            return jsonify({'items': [], 'total': 0, 'limit': limit, 'offset': offset})

    total = query.count()
    products = query.order_by(Product.created_at.desc()).offset(offset).limit(limit).all()

    return jsonify({
        'items': [p.to_dict() for p in products],
        'total': total,
        'limit': limit,
        'offset': offset
    })


@app.route('/api/products/<slug>', methods=['GET'])
def get_product(slug):
    product = Product.query.filter_by(slug=slug).first()
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    return jsonify(product.to_dict())


@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    name = data.get('name')
    slug = data.get('slug')
    price = data.get('price')
    if not all([name, slug, price]):
        return jsonify({'error': 'name, slug, price required'}), 400

    existing = Product.query.filter_by(slug=slug).first()
    if existing:
        return jsonify({'error': 'Slug already exists'}), 409

    category_id = data.get('category_id')
    category_slug = data.get('category_slug')
    if category_slug and not category_id:
        cat = ProductCategory.query.filter_by(slug=category_slug).first()
        if not cat:
            return jsonify({'error': 'Unknown category_slug'}), 400
        category_id = cat.id
    if not category_id:
        return jsonify({'error': 'category_id or category_slug required'}), 400
    cat = db.session.get(ProductCategory, category_id)
    if not cat:
        return jsonify({'error': 'Category not found'}), 400

    product = Product(
        slug=slug,
        name=name,
        description=data.get('description'),
        price=price,
        stock=data.get('stock', 0),
        image_url=data.get('image_url'),
        category_id=category_id,
        is_active=data.get('is_active', True)
    )
    db.session.add(product)
    db.session.commit()
    return jsonify(product.to_dict()), 201


@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    if 'slug' in data:
        existing = Product.query.filter(Product.slug == data['slug'], Product.id != product_id).first()
        if existing:
            return jsonify({'error': 'Slug already exists'}), 409
        product.slug = data['slug']
    if 'name' in data:
        product.name = data['name']
    if 'description' in data:
        product.description = data['description']
    if 'price' in data:
        product.price = data['price']
    if 'stock' in data:
        product.stock = data['stock']
    if 'image_url' in data:
        product.image_url = data['image_url']
    if 'is_active' in data:
        product.is_active = data['is_active']

    if 'category_id' in data:
        cat = db.session.get(ProductCategory, data['category_id'])
        if not cat:
            return jsonify({'error': 'Category not found'}), 400
        product.category_id = data['category_id']
    if 'category_slug' in data:
        cat = ProductCategory.query.filter_by(slug=data['category_slug']).first()
        if not cat:
            return jsonify({'error': 'Unknown category_slug'}), 400
        product.category_id = cat.id

    product.updated_at = now_gmt8()
    db.session.commit()
    return jsonify(product.to_dict())


@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    product.is_active = False
    db.session.commit()
    return '', 204


@app.route('/api/products/<int:product_id>/posts')
def get_product_posts(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    query = text('''
        SELECT p.id, p.slug, p.title
        FROM posts p
        INNER JOIN post_products pp ON p.id = pp.post_id
        WHERE pp.product_id = :product_id AND p.is_published = 1
        ORDER BY pp.sort_order
    ''')
    rows = db.session.execute(query, {'product_id': product_id}).fetchall()
    posts = [{'id': r.id, 'slug': r.slug, 'title': r.title, 'url': f'{BLOG_HOST}/articles/{r.slug}'} for r in rows]
    return jsonify({'product_id': product_id, 'posts': posts})


@app.route('/api/orders', methods=['GET'])
def get_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return jsonify([o.to_dict() for o in orders])


@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    product_id = data.get('product_id')
    quantity = data.get('quantity')
    if not product_id or not quantity:
        return jsonify({'error': 'product_id and quantity required'}), 400

    if quantity < 1:
        return jsonify({'error': 'quantity must be >= 1'}), 400

    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404

    total_price = float(product.price) * quantity

    now = now_gmt8()
    today = now.date()
    count_query = text('''
        SELECT COUNT(*) FROM orders
        WHERE CAST(created_at AS DATE) = :today
    ''')
    count_today = db.session.execute(count_query, {'today': today}).scalar() or 0
    order_num = f'ORD-{today.strftime("%Y%m%d")}-{str(count_today + 1).zfill(4)}'

    order = Order(
        order_number=order_num,
        member_id=data.get('member_id'),
        product_id=product_id,
        quantity=quantity,
        total_price=total_price,
        status='pending',
        recipient_name=data.get('recipient_name'),
        recipient_phone=data.get('recipient_phone'),
        shipping_address=data.get('shipping_address'),
        note=data.get('note'),
        created_at=now,
        updated_at=now
    )
    db.session.add(order)
    db.session.commit()
    return jsonify(order.to_dict()), 201


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
else:
    # gunicorn:寫 module-level 沒問題
    pass
