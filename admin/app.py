import os
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from flask import Flask, jsonify, request, render_template, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, text

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

app.secret_key = os.environ.get('SESSION_SECRET', 'dev-secret-key')
# SESSION_COOKIE_DOMAIN 預設不設(讓 Flask 用 origin 比對)
# 之前設 .localhost 被某些客戶端拒絕('bad tailmatch domain')。# 改用 origin-only cookie,代價是會員跨子網域 session 不再共用。
# 在正式網域(設 Domain=.yourdomain.com)就完全沒這問題。
# app.config['SESSION_COOKIE_DOMAIN'] = os.environ.get('SESSION_COOKIE_DOMAIN', '.localhost')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_NAME'] = 'session'

EXPECTED_USER_TYPE = os.getenv('EXPECTED_USER_TYPE', 'admin')

db = SQLAlchemy(app)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_type') != EXPECTED_USER_TYPE:
            return redirect(url_for('login', next=request.url))
        admin = db.session.get(Admin, session.get('user_id'))
        if not admin or not admin.is_active:
            session.clear()
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.Unicode(100), unique=True, nullable=False)
    email = db.Column(db.Unicode(200), unique=True, nullable=False)
    display_name = db.Column(db.Unicode(100))
    password_hash = db.Column(db.Unicode(255), nullable=False)
    role = db.Column(db.Unicode(20), nullable=False, default='admin')
    is_active = db.Column(db.Boolean, default=True)
    last_login_at = db.Column(db.DateTime)
    failed_login_count = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'display_name': self.display_name,
            'role': self.role,
            'is_active': self.is_active,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
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
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'display_name': self.display_name,
            'avatar_url': self.avatar_url,
            'bio': self.bio,
            'is_active': self.is_active,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


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

    def to_dict(self, include_tags=True):
        result = {
            'id': self.id,
            'slug': self.slug,
            'title': self.title,
            'excerpt': self.excerpt,
            'content': self.content,
            'cover_image_url': self.cover_image_url,
            'category': self.category.to_dict() if self.category else None,
            'is_published': self.is_published,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        if include_tags:
            result['tags'] = [t.name for t in self.tags]
        return result


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
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

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
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    member = db.relationship('Member', lazy='joined')
    product = db.relationship('Product', lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'order_number': self.order_number,
            'member_id': self.member_id,
            'member': self.member.to_dict() if self.member else None,
            'product_id': self.product_id,
            'product': self.product.to_dict() if self.product else None,
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


class EconomicSeries(db.Model):
    __tablename__ = 'economic_series'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.Unicode(80), unique=True, nullable=False)
    name = db.Column(db.Unicode(120), nullable=False)
    category = db.Column(db.Unicode(80), nullable=False)
    description = db.Column(db.Unicode(500))
    unit = db.Column(db.Unicode(40))
    source_name = db.Column(db.Unicode(120))
    source_url = db.Column(db.Unicode(500))
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


class EconomicObservation(db.Model):
    __tablename__ = 'economic_observations'
    id = db.Column(db.Integer, primary_key=True)
    series_id = db.Column(db.Integer, db.ForeignKey('economic_series.id'), nullable=False)
    observed_at = db.Column(db.DateTime, nullable=False)
    value = db.Column(db.Numeric(18, 4), nullable=False)
    previous_value = db.Column(db.Numeric(18, 4))
    change_label = db.Column(db.Unicode(40))
    status_label = db.Column(db.Unicode(20), default='flat')
    created_at = db.Column(db.DateTime, default=db.func.now())

    series = db.relationship('EconomicSeries', lazy='joined')


class EconomicEvent(db.Model):
    __tablename__ = 'economic_events'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.Unicode(120), unique=True, nullable=False)
    title = db.Column(db.Unicode(160), nullable=False)
    category = db.Column(db.Unicode(80), nullable=False)
    event_at = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.Unicode(500))
    source_name = db.Column(db.Unicode(120))
    source_url = db.Column(db.Unicode(500))
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


class EconomicFetchJob(db.Model):
    __tablename__ = 'economic_fetch_jobs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Unicode(120), nullable=False)
    provider = db.Column(db.Unicode(60), nullable=False, default='mock')
    series_code = db.Column(db.Unicode(80))
    schedule_type = db.Column(db.Unicode(20), nullable=False, default='daily')
    interval_minutes = db.Column(db.Integer, default=1440)
    daily_time = db.Column(db.Unicode(5), default='08:00')
    is_active = db.Column(db.Boolean, default=True)
    next_run_at = db.Column(db.DateTime)
    last_run_at = db.Column(db.DateTime)
    last_status = db.Column(db.Unicode(20))
    last_message = db.Column(db.Unicode(500))
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


class EconomicFetchRun(db.Model):
    __tablename__ = 'economic_fetch_runs'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('economic_fetch_jobs.id'), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False)
    finished_at = db.Column(db.DateTime)
    status = db.Column(db.Unicode(20), nullable=False)
    message = db.Column(db.Unicode(500))

    job = db.relationship('EconomicFetchJob', lazy='joined')


ECONOMIC_SERIES_SEED = [
    ('fed_funds_rate', 'FED 利率', '美國央行與利率', '聯邦基金目標利率區間上緣', '%', 'Federal Reserve', 1, Decimal('5.50'), Decimal('5.25'), '持平偏高', 'flat'),
    ('fomc_dot_median', '點陣圖利率中位數', '美國央行與利率', 'FOMC 最新點陣圖年末利率預估', '%', 'Federal Reserve SEP', 2, Decimal('4.75'), Decimal('5.00'), '下修 25bp', 'down'),
    ('us_nonfarm_payrolls', '非農就業新增', '美國就業與通膨', '美國非農就業人口月增', '千人', 'BLS', 10, Decimal('175'), Decimal('315'), '低於前值', 'down'),
    ('us_cpi_yoy', '美國 CPI 年增率', '美國就業與通膨', '美國消費者物價指數年增率', '%', 'BLS', 11, Decimal('3.30'), Decimal('3.50'), '降溫', 'down'),
    ('taiwan_policy_rate', '台灣央行政策利率', '台灣經濟數據', '中央銀行重貼現率', '%', '中央銀行', 20, Decimal('2.00'), Decimal('1.875'), '升息 12.5bp', 'up'),
    ('taiwan_cpi_yoy', '台灣 CPI 年增率', '台灣經濟數據', '台灣消費者物價指數年增率', '%', '主計總處', 21, Decimal('2.24'), Decimal('2.42'), '小幅降溫', 'down'),
    ('taiwan_gdp_yoy', '台灣 GDP 年增率', '台灣經濟數據', '台灣實質 GDP 年增率', '%', '主計總處', 22, Decimal('5.09'), Decimal('4.93'), '小幅上修', 'up'),
    ('taiwan_unemployment', '台灣失業率', '台灣經濟數據', '台灣失業率', '%', '主計總處', 23, Decimal('3.34'), Decimal('3.36'), '持平', 'flat'),
    ('txf_price', '台指期近月', '台灣市場價格', '台灣加權股價指數期貨近月合約即時價格', '點', 'External TXF Feed', 24, Decimal('0'), Decimal('0'), '等待資料', 'flat'),
    ('gold_spot_usd', '黃金現貨', '貴金屬', '黃金現貨美元價格', 'USD/oz', 'Mock Metals Feed', 30, Decimal('2332.40'), Decimal('2310.20'), '走高', 'up'),
    ('silver_spot_usd', '白銀現貨', '貴金屬', '白銀現貨美元價格', 'USD/oz', 'Mock Metals Feed', 31, Decimal('29.48'), Decimal('29.90'), '回落', 'down'),
]

ECONOMIC_EVENT_SEED = [
    ('next-fomc', 'FOMC 利率決策會議', '美國央行與利率', 18, '下次 FOMC 會議與利率聲明公布。', 'Federal Reserve'),
    ('next-us-cpi', '美國 CPI 公布', '美國就業與通膨', 9, '美國 CPI 與核心 CPI 數據公布。', 'BLS'),
    ('next-nfp', '美國非農就業公布', '美國就業與通膨', 14, '非農就業人口、失業率與薪資數據公布。', 'BLS'),
    ('next-tw-cpi', '台灣 CPI 公布', '台灣經濟數據', 11, '台灣 CPI 與物價相關統計公布。', '主計總處'),
]

ECONOMIC_JOB_SEED = [
    ('Mock: 美國央行與利率', 'mock', 'fed_funds_rate', 'daily', 1440, '08:00'),
    ('Mock: 美國就業與通膨', 'mock', 'us_cpi_yoy', 'daily', 1440, '08:10'),
    ('Mock: 台灣經濟數據', 'mock', 'taiwan_cpi_yoy', 'daily', 1440, '08:20'),
    ('Mock: 貴金屬價格', 'mock', 'gold_spot_usd', 'interval_minutes', 60, '08:30'),
]


def get_post_form_data(post=None):
    if not post:
        return {
            'title': '',
            'slug': '',
            'category_id': '',
            'excerpt': '',
            'content': '',
            'cover_image_url': '',
            'tags': '',
            'is_published': '',
            'published_at': ''
        }

    return {
        'title': post.title or '',
        'slug': post.slug or '',
        'category_id': str(post.category_id or ''),
        'excerpt': post.excerpt or '',
        'content': post.content or '',
        'cover_image_url': post.cover_image_url or '',
        'tags': ', '.join(tag.name for tag in post.tags),
        'is_published': '1' if post.is_published else '',
        'published_at': post.published_at.strftime('%Y-%m-%dT%H:%M') if post.published_at else ''
    }


def render_post_form(post=None, form_data=None, is_edit=False):
    admin = db.session.get(Admin, session.get('user_id'))
    categories = Category.query.order_by(Category.name).all()
    return render_template('posts/form.html', admin=admin, post=post,
        categories=categories, form_data=form_data or get_post_form_data(post),
        is_edit=is_edit)


def tags_from_input(tags_input):
    names = []
    for raw_name in tags_input.replace('，', ',').split(','):
        name = raw_name.strip()
        if name and name not in names:
            names.append(name)

    tags = []
    for name in names:
        tag = Tag.query.filter_by(name=name).first()
        if not tag:
            tag = Tag(name=name)
            db.session.add(tag)
        tags.append(tag)
    return tags


def update_post_from_form(post):
    title = request.form.get('title', '').strip()
    slug = request.form.get('slug', '').strip()
    content = request.form.get('content', '').strip()
    excerpt = request.form.get('excerpt', '').strip()
    cover_image_url = request.form.get('cover_image_url', '').strip()
    tags_input = request.form.get('tags', '').strip()
    category_id_raw = request.form.get('category_id', '').strip()
    published_at_raw = request.form.get('published_at', '').strip()
    is_published = request.form.get('is_published') == '1'

    errors = []
    if not title:
        errors.append('請輸入文章標題')
    if not slug:
        errors.append('請輸入 Slug')
    if not content:
        errors.append('請輸入文章內容')

    if slug:
        query = Post.query.filter(Post.slug == slug)
        if post.id:
            query = query.filter(Post.id != post.id)
        if query.first():
            errors.append('Slug 已被其他文章使用')

    category_id = None
    if category_id_raw:
        try:
            category_id = int(category_id_raw)
        except ValueError:
            errors.append('分類格式不正確')
        else:
            if not db.session.get(Category, category_id):
                errors.append('選擇的分類不存在')

    published_at = None
    if published_at_raw:
        try:
            published_at = datetime.fromisoformat(published_at_raw)
        except ValueError:
            errors.append('發布時間格式不正確')
    elif is_published:
        published_at = datetime.utcnow()

    if errors:
        return False, errors

    post.title = title
    post.slug = slug
    post.content = content
    post.excerpt = excerpt or None
    post.cover_image_url = cover_image_url or None
    post.category_id = category_id
    post.is_published = is_published
    post.published_at = published_at
    post.tags = tags_from_input(tags_input)
    post.updated_at = datetime.utcnow()
    return True, []


def get_product_form_data(product=None):
    if not product:
        return {
            'name': '',
            'slug': '',
            'category_id': '',
            'price': '',
            'stock': '0',
            'image_url': '',
            'description': '',
            'is_active': '1'
        }

    return {
        'name': product.name or '',
        'slug': product.slug or '',
        'category_id': str(product.category_id or ''),
        'price': str(product.price or ''),
        'stock': str(product.stock or 0),
        'image_url': product.image_url or '',
        'description': product.description or '',
        'is_active': '1' if product.is_active else ''
    }


def render_product_form(product=None, form_data=None, is_edit=False):
    admin = db.session.get(Admin, session.get('user_id'))
    categories = ProductCategory.query.order_by(ProductCategory.sort_order, ProductCategory.name).all()
    return render_template('products/form.html', admin=admin, product=product,
        categories=categories, form_data=form_data or get_product_form_data(product),
        is_edit=is_edit)


def update_product_from_form(product):
    name = request.form.get('name', '').strip()
    slug = request.form.get('slug', '').strip()
    description = request.form.get('description', '').strip()
    image_url = request.form.get('image_url', '').strip()
    category_id_raw = request.form.get('category_id', '').strip()
    price_raw = request.form.get('price', '').strip()
    stock_raw = request.form.get('stock', '').strip()
    is_active = request.form.get('is_active') == '1'

    errors = []
    if not name:
        errors.append('請輸入課程名稱')
    if not slug:
        errors.append('請輸入 Slug')

    if slug:
        query = Product.query.filter(Product.slug == slug)
        if product.id:
            query = query.filter(Product.id != product.id)
        if query.first():
            errors.append('Slug 已被其他課程使用')

    price = None
    if not price_raw:
        errors.append('請輸入價格')
    else:
        try:
            price = Decimal(price_raw)
        except InvalidOperation:
            errors.append('價格格式不正確')
        else:
            if price < 0:
                errors.append('價格不可小於 0')

    try:
        stock = int(stock_raw or 0)
    except ValueError:
        errors.append('名額格式不正確')
        stock = 0
    else:
        if stock < 0:
            errors.append('名額不可小於 0')

    category_id = None
    if category_id_raw:
        try:
            category_id = int(category_id_raw)
        except ValueError:
            errors.append('分類格式不正確')
        else:
            if not db.session.get(ProductCategory, category_id):
                errors.append('選擇的分類不存在')

    if errors:
        return False, errors

    product.name = name
    product.slug = slug
    product.description = description or None
    product.image_url = image_url or None
    product.category_id = category_id
    product.price = price
    product.stock = stock
    product.is_active = is_active
    product.updated_at = datetime.utcnow()
    return True, []


ORDER_STATUS_LABELS = {
    'pending': '待付款',
    'paid': '已付款',
    'shipped': '已出貨',
    'done': '已完成',
    'cancelled': '已取消'
}
ORDER_STATUS_OPTIONS = list(ORDER_STATUS_LABELS.items())


def get_order_form_data(order=None):
    if not order:
        return {
            'status': 'pending',
            'quantity': '1',
            'total_price': '0',
            'recipient_name': '',
            'recipient_phone': '',
            'shipping_address': '',
            'note': ''
        }

    return {
        'status': order.status or 'pending',
        'quantity': str(order.quantity or 1),
        'total_price': str(order.total_price or 0),
        'recipient_name': order.recipient_name or '',
        'recipient_phone': order.recipient_phone or '',
        'shipping_address': order.shipping_address or '',
        'note': order.note or ''
    }


def render_order_form(order, form_data=None):
    admin = db.session.get(Admin, session.get('user_id'))
    return render_template('orders/form.html', admin=admin, order=order,
        form_data=form_data or get_order_form_data(order),
        status_options=ORDER_STATUS_OPTIONS, status_labels=ORDER_STATUS_LABELS)


def update_order_from_form(order):
    status = request.form.get('status', '').strip()
    quantity_raw = request.form.get('quantity', '').strip()
    total_price_raw = request.form.get('total_price', '').strip()
    recipient_name = request.form.get('recipient_name', '').strip()
    recipient_phone = request.form.get('recipient_phone', '').strip()
    shipping_address = request.form.get('shipping_address', '').strip()
    note = request.form.get('note', '').strip()

    errors = []
    if status not in ORDER_STATUS_LABELS:
        errors.append('無效的訂單狀態')

    try:
        quantity = int(quantity_raw)
    except ValueError:
        errors.append('數量格式不正確')
        quantity = None
    else:
        if quantity < 1:
            errors.append('數量不可小於 1')

    try:
        total_price = Decimal(total_price_raw)
    except InvalidOperation:
        errors.append('金額格式不正確')
        total_price = None
    else:
        if total_price < 0:
            errors.append('金額不可小於 0')

    if errors:
        return False, errors

    order.status = status
    order.quantity = quantity
    order.total_price = total_price
    order.recipient_name = recipient_name or None
    order.recipient_phone = recipient_phone or None
    order.shipping_address = shipping_address or None
    order.note = note or None
    order.updated_at = datetime.utcnow()
    return True, []


def redirect_to_orders_list_from_form():
    page = request.form.get('page', 1)
    status = request.form.get('current_status', '')
    q = request.form.get('q', '')
    return redirect(url_for('orders_list', page=page, status=status, q=q))


def get_member_form_data(member=None):
    if not member:
        return {
            'username': '',
            'email': '',
            'display_name': '',
            'avatar_url': '',
            'bio': '',
            'is_active': '1'
        }

    return {
        'username': member.username or '',
        'email': member.email or '',
        'display_name': member.display_name or '',
        'avatar_url': member.avatar_url or '',
        'bio': member.bio or '',
        'is_active': '1' if member.is_active else ''
    }


def render_member_form(member, form_data=None):
    admin = db.session.get(Admin, session.get('user_id'))
    return render_template('members/form.html', admin=admin, member=member,
        form_data=form_data or get_member_form_data(member))


def update_member_from_form(member):
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    display_name = request.form.get('display_name', '').strip()
    avatar_url = request.form.get('avatar_url', '').strip()
    bio = request.form.get('bio', '').strip()
    is_active = request.form.get('is_active') == '1'

    errors = []
    if not username:
        errors.append('請輸入帳號')
    if not email:
        errors.append('請輸入 Email')

    if username:
        existing = Member.query.filter(Member.username == username, Member.id != member.id).first()
        if existing:
            errors.append('帳號已被其他會員使用')

    if email:
        existing = Member.query.filter(Member.email == email, Member.id != member.id).first()
        if existing:
            errors.append('Email 已被其他會員使用')

    if errors:
        return False, errors

    member.username = username
    member.email = email
    member.display_name = display_name or None
    member.avatar_url = avatar_url or None
    member.bio = bio or None
    member.is_active = is_active
    member.updated_at = datetime.utcnow()
    return True, []


def redirect_to_members_list_from_form():
    page = request.form.get('page', 1)
    return redirect(url_for('members_list', page=page))


def ensure_economic_schema_and_seed():
    db.create_all()

    if EconomicSeries.query.count() == 0:
        now = datetime.utcnow()
        for code, name, category, description, unit, source_name, sort_order, value, previous, change, status in ECONOMIC_SERIES_SEED:
            series = EconomicSeries(code=code, name=name, category=category,
                description=description, unit=unit, source_name=source_name,
                sort_order=sort_order)
            db.session.add(series)
            db.session.flush()
            db.session.add(EconomicObservation(series_id=series.id,
                observed_at=now - timedelta(hours=sort_order % 8), value=value,
                previous_value=previous, change_label=change, status_label=status))

    if EconomicEvent.query.count() == 0:
        now = datetime.utcnow()
        for slug, title, category, days, description, source_name in ECONOMIC_EVENT_SEED:
            db.session.add(EconomicEvent(slug=slug, title=title, category=category,
                event_at=now + timedelta(days=days), description=description,
                source_name=source_name))

    if EconomicFetchJob.query.count() == 0:
        now = datetime.utcnow()
        for name, provider, series_code, schedule_type, interval_minutes, daily_time in ECONOMIC_JOB_SEED:
            db.session.add(EconomicFetchJob(name=name, provider=provider,
                series_code=series_code, schedule_type=schedule_type,
                interval_minutes=interval_minutes, daily_time=daily_time,
                is_active=True, next_run_at=now + timedelta(minutes=5),
                last_status='seeded',
                last_message='Mock job seeded. API keys are expected from .env in future providers.'))

    db.session.commit()


def economic_next_run(job, now=None):
    now = now or datetime.utcnow()
    if job.schedule_type == 'interval_minutes':
        return now + timedelta(minutes=max(job.interval_minutes or 60, 1))
    if job.schedule_type == 'interval_hours':
        return now + timedelta(hours=max(job.interval_minutes or 60, 1) / 60)

    daily_time = job.daily_time or '08:00'
    try:
        hour, minute = [int(part) for part in daily_time.split(':', 1)]
    except ValueError:
        hour, minute = 8, 0
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def get_economic_job_form_data(job=None):
    if not job:
        return {
            'name': '',
            'provider': 'mock',
            'series_code': '',
            'schedule_type': 'daily',
            'interval_minutes': '1440',
            'daily_time': '08:00',
            'is_active': '1'
        }
    return {
        'name': job.name or '',
        'provider': job.provider or 'mock',
        'series_code': job.series_code or '',
        'schedule_type': job.schedule_type or 'daily',
        'interval_minutes': str(job.interval_minutes or 1440),
        'daily_time': job.daily_time or '08:00',
        'is_active': '1' if job.is_active else ''
    }


def render_economic_job_form(job, form_data=None):
    admin = db.session.get(Admin, session.get('user_id'))
    series_list = EconomicSeries.query.order_by(EconomicSeries.category, EconomicSeries.sort_order).all()
    return render_template('economic_data/job_form.html', admin=admin, job=job,
        form_data=form_data or get_economic_job_form_data(job), series_list=series_list)


def update_economic_job_from_form(job):
    name = request.form.get('name', '').strip()
    provider = request.form.get('provider', '').strip()
    series_code = request.form.get('series_code', '').strip()
    schedule_type = request.form.get('schedule_type', '').strip()
    interval_minutes_raw = request.form.get('interval_minutes', '').strip()
    daily_time = request.form.get('daily_time', '').strip()
    is_active = request.form.get('is_active') == '1'

    errors = []
    if not name:
        errors.append('請輸入排程名稱')
    if provider not in ['mock', 'fred', 'bls', 'taiwan', 'metals']:
        errors.append('Provider 不正確')
    if schedule_type not in ['interval_minutes', 'interval_hours', 'daily']:
        errors.append('排程類型不正確')
    if series_code and not EconomicSeries.query.filter_by(code=series_code).first():
        errors.append('選擇的指標不存在')

    try:
        interval_minutes = int(interval_minutes_raw or 1440)
    except ValueError:
        errors.append('間隔時間格式不正確')
        interval_minutes = 1440
    else:
        if interval_minutes < 1:
            errors.append('間隔時間不可小於 1 分鐘')

    if schedule_type == 'daily':
        try:
            hour, minute = [int(part) for part in daily_time.split(':', 1)]
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError
        except ValueError:
            errors.append('每日執行時間格式需為 HH:MM')

    if errors:
        return False, errors

    job.name = name
    job.provider = provider
    job.series_code = series_code or None
    job.schedule_type = schedule_type
    job.interval_minutes = interval_minutes
    job.daily_time = daily_time or '08:00'
    job.is_active = is_active
    job.next_run_at = economic_next_run(job) if is_active else None
    job.updated_at = datetime.utcnow()
    return True, []


def run_economic_job(job):
    started_at = datetime.utcnow()
    run = EconomicFetchRun(job_id=job.id, started_at=started_at, status='running')
    db.session.add(run)
    db.session.flush()

    try:
        if job.provider == 'mock':
            series = EconomicSeries.query.filter_by(code=job.series_code).first()
            if not series:
                message = f'Series {job.series_code} not found; mock job skipped.'
            else:
                latest = EconomicObservation.query.filter_by(series_id=series.id).order_by(EconomicObservation.observed_at.desc()).first()
                base = Decimal(latest.value if latest else 0)
                bump = Decimal('0.01') if series.unit == '%' else Decimal('1.00')
                value = base + bump
                db.session.add(EconomicObservation(series_id=series.id,
                    observed_at=datetime.utcnow(), value=value, previous_value=base,
                    change_label='手動 Mock 更新', status_label='up'))
                message = f'Mock updated {series.code} from {base} to {value}.'
        else:
            message = f'Provider {job.provider} 尚未實作。API key 將從 .env 讀取。'

        run.status = 'success'
        run.message = message
        job.last_status = 'success'
        job.last_message = message
    except Exception as exc:
        run.status = 'error'
        run.message = str(exc)
        job.last_status = 'error'
        job.last_message = str(exc)
    finally:
        now = datetime.utcnow()
        run.finished_at = now
        job.last_run_at = now
        job.next_run_at = economic_next_run(job, now) if job.is_active else None
        job.updated_at = now
        db.session.commit()

    return run


@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('請輸入帳號和密碼', 'error')
            return render_template('login.html')

        admin = Admin.query.filter_by(username=username).first()

        if not admin:
            flash('帳號或密碼錯誤', 'error')
            return render_template('login.html')

        if not admin.is_active:
            flash('帳號已被停用', 'error')
            return render_template('login.html')

        if admin.locked_until and admin.locked_until > datetime.utcnow():
            flash('帳號已鎖定，請稍後再試', 'error')
            return render_template('login.html')

        if not check_password_hash(admin.password_hash, password):
            admin.failed_login_count = (admin.failed_login_count or 0) + 1
            if admin.failed_login_count >= 5:
                admin.locked_until = datetime.utcnow()
            db.session.commit()
            flash('帳號或密碼錯誤', 'error')
            return render_template('login.html')

        admin.failed_login_count = 0
        admin.last_login_at = datetime.utcnow()
        db.session.commit()

        session['user_id'] = admin.id
        session['user_type'] = EXPECTED_USER_TYPE

        next_url = request.args.get('next')
        if next_url:
            return redirect(next_url)
        return redirect(url_for('dashboard'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def dashboard():
    post_count = Post.query.count()
    post_published = Post.query.filter_by(is_published=True).count()
    post_draft = post_count - post_published

    product_count = Product.query.count()
    product_active = Product.query.filter_by(is_active=True).count()
    product_inactive = product_count - product_active

    order_count = Order.query.count()
    order_pending = Order.query.filter_by(status='pending').count()
    order_paid = Order.query.filter_by(status='paid').count()
    order_shipped = Order.query.filter_by(status='shipped').count()
    order_done = Order.query.filter_by(status='done').count()

    member_count = Member.query.count()
    member_active = Member.query.filter_by(is_active=True).count()
    member_disabled = member_count - member_active

    admin_count = Admin.query.count()

    admin = db.session.get(Admin, session.get('user_id'))

    return render_template('dashboard.html',
        post_count=post_count, post_published=post_published, post_draft=post_draft,
        product_count=product_count, product_active=product_active, product_inactive=product_inactive,
        order_count=order_count, order_pending=order_pending, order_paid=order_paid,
        order_shipped=order_shipped, order_done=order_done,
        member_count=member_count, member_active=member_active, member_disabled=member_disabled,
        admin_count=admin_count, admin=admin)


@app.route('/economic-data')
@app.route('/economic-data/jobs')
@login_required
def economic_data_jobs():
    ensure_economic_schema_and_seed()
    admin = db.session.get(Admin, session.get('user_id'))
    jobs = EconomicFetchJob.query.order_by(EconomicFetchJob.id).all()
    runs = EconomicFetchRun.query.order_by(EconomicFetchRun.started_at.desc()).limit(12).all()
    series_count = EconomicSeries.query.count()
    observation_count = EconomicObservation.query.count()
    active_jobs = EconomicFetchJob.query.filter_by(is_active=True).count()
    return render_template('economic_data/jobs.html', admin=admin, jobs=jobs, runs=runs,
        series_count=series_count, observation_count=observation_count,
        active_jobs=active_jobs)


@app.route('/economic-data/jobs/<int:job_id>/edit', methods=['GET', 'POST'])
@login_required
def economic_data_job_edit(job_id):
    ensure_economic_schema_and_seed()
    job = db.session.get(EconomicFetchJob, job_id)
    if not job:
        flash('排程不存在', 'error')
        return redirect(url_for('economic_data_jobs'))

    if request.method == 'POST':
        success, errors = update_economic_job_from_form(job)
        if success:
            db.session.commit()
            flash(f'排程「{job.name}」已更新', 'success')
            return redirect(url_for('economic_data_jobs'))

        for error in errors:
            flash(error, 'error')
        return render_economic_job_form(job, form_data=request.form)

    return render_economic_job_form(job)


@app.route('/economic-data/jobs/<int:job_id>/run', methods=['POST'])
@login_required
def economic_data_job_run(job_id):
    ensure_economic_schema_and_seed()
    job = db.session.get(EconomicFetchJob, job_id)
    if not job:
        flash('排程不存在', 'error')
        return redirect(url_for('economic_data_jobs'))

    run = run_economic_job(job)
    if run.status == 'success':
        flash(f'排程「{job.name}」已手動執行', 'success')
    else:
        flash(f'排程「{job.name}」執行失敗: {run.message}', 'error')
    return redirect(url_for('economic_data_jobs'))


@app.route('/posts')
@login_required
def posts_list():
    page = max(1, int(request.args.get('page', 1)))
    per_page = 20
    offset = (page - 1) * per_page
    query = Post.query.order_by(Post.created_at.desc())
    total = query.count()
    posts = query.offset(offset).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    admin = db.session.get(Admin, session.get('user_id'))
    return render_template('posts/list.html', posts=posts, total=total,
        page=page, per_page=per_page, total_pages=total_pages, admin=admin)


@app.route('/posts/new', methods=['GET', 'POST'])
@login_required
def posts_new():
    post = Post()
    if request.method == 'POST':
        success, errors = update_post_from_form(post)
        if success:
            now = datetime.utcnow()
            post.created_at = now
            db.session.add(post)
            db.session.commit()
            flash(f'文章「{post.title}」已建立', 'success')
            return redirect(url_for('posts_detail', post_id=post.id))

        for error in errors:
            flash(error, 'error')
        return render_post_form(post=None, form_data=request.form, is_edit=False)

    return render_post_form(post=None, is_edit=False)


@app.route('/posts/<int:post_id>')
@login_required
def posts_detail(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        flash('文章不存在', 'error')
        return redirect(url_for('posts_list'))

    admin = db.session.get(Admin, session.get('user_id'))
    return render_template('posts/detail.html', post=post, admin=admin)


@app.route('/posts/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def posts_edit(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        flash('文章不存在', 'error')
        return redirect(url_for('posts_list'))

    if request.method == 'POST':
        success, errors = update_post_from_form(post)
        if success:
            db.session.commit()
            flash(f'文章「{post.title}」已更新', 'success')
            return redirect(url_for('posts_detail', post_id=post.id))

        for error in errors:
            flash(error, 'error')
        return render_post_form(post=post, form_data=request.form, is_edit=True)

    return render_post_form(post=post, is_edit=True)


@app.route('/posts/<int:post_id>/toggle-publish', methods=['POST'])
@login_required
def posts_toggle_publish(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        flash('文章不存在', 'error')
        return redirect(url_for('posts_list'))

    post.is_published = not post.is_published
    post.updated_at = datetime.utcnow()
    db.session.commit()

    status = '已發布' if post.is_published else '已設為草稿'
    flash(f'文章「{post.title}」{status}', 'success')
    return redirect(url_for('posts_detail', post_id=post_id))


@app.route('/posts/<int:post_id>/delete', methods=['POST'])
@login_required
def posts_delete(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        flash('文章不存在', 'error')
        return redirect(url_for('posts_list'))

    title = post.title
    post.tags = []
    db.session.execute(text('DELETE FROM post_products WHERE post_id = :post_id'), {'post_id': post_id})
    db.session.delete(post)
    db.session.commit()

    flash(f'文章「{title}」已刪除', 'success')
    return redirect(url_for('posts_list'))


@app.route('/products')
@login_required
def products_list():
    page = max(1, int(request.args.get('page', 1)))
    per_page = 20
    offset = (page - 1) * per_page
    query = Product.query.order_by(Product.created_at.desc())
    total = query.count()
    products = query.offset(offset).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    admin = db.session.get(Admin, session.get('user_id'))
    return render_template('products/list.html', products=products, total=total,
        page=page, per_page=per_page, total_pages=total_pages, admin=admin)


@app.route('/products/new', methods=['GET', 'POST'])
@login_required
def products_new():
    product = Product()
    if request.method == 'POST':
        success, errors = update_product_from_form(product)
        if success:
            now = datetime.utcnow()
            product.created_at = now
            db.session.add(product)
            db.session.commit()
            flash(f'課程「{product.name}」已建立', 'success')
            return redirect(url_for('products_detail', product_id=product.id))

        for error in errors:
            flash(error, 'error')
        return render_product_form(product=None, form_data=request.form, is_edit=False)

    return render_product_form(product=None, is_edit=False)


@app.route('/products/<int:product_id>')
@login_required
def products_detail(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        flash('課程不存在', 'error')
        return redirect(url_for('products_list'))

    admin = db.session.get(Admin, session.get('user_id'))
    return render_template('products/detail.html', product=product, admin=admin)


@app.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def products_edit(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        flash('課程不存在', 'error')
        return redirect(url_for('products_list'))

    if request.method == 'POST':
        success, errors = update_product_from_form(product)
        if success:
            db.session.commit()
            flash(f'課程「{product.name}」已更新', 'success')
            return redirect(url_for('products_detail', product_id=product.id))

        for error in errors:
            flash(error, 'error')
        return render_product_form(product=product, form_data=request.form, is_edit=True)

    return render_product_form(product=product, is_edit=True)


@app.route('/products/<int:product_id>/toggle-active', methods=['POST'])
@login_required
def products_toggle_active(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        flash('課程不存在', 'error')
        return redirect(url_for('products_list'))

    product.is_active = not product.is_active
    product.updated_at = datetime.utcnow()
    db.session.commit()

    status = '已上架' if product.is_active else '已下架'
    flash(f'課程「{product.name}」{status}', 'success')
    return redirect(url_for('products_detail', product_id=product_id))


@app.route('/products/<int:product_id>/delete', methods=['POST'])
@login_required
def products_delete(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        flash('課程不存在', 'error')
        return redirect(url_for('products_list'))

    if Order.query.filter_by(product_id=product_id).first():
        flash('此課程已有訂單紀錄，無法刪除；請改為下架。', 'error')
        return redirect(url_for('products_detail', product_id=product_id))

    name = product.name
    db.session.execute(text('DELETE FROM post_products WHERE product_id = :product_id'), {'product_id': product_id})
    db.session.delete(product)
    db.session.commit()

    flash(f'課程「{name}」已刪除', 'success')
    return redirect(url_for('products_list'))


@app.route('/orders')
@login_required
def orders_list():
    page = max(1, int(request.args.get('page', 1)))
    selected_status = request.args.get('status', '').strip()
    q = request.args.get('q', '').strip()
    per_page = 20
    offset = (page - 1) * per_page

    query = Order.query.outerjoin(Member, Order.member_id == Member.id).outerjoin(Product, Order.product_id == Product.id)
    if selected_status in ORDER_STATUS_LABELS:
        query = query.filter(Order.status == selected_status)
    else:
        selected_status = ''

    if q:
        keyword = f'%{q}%'
        query = query.filter(or_(
            Order.order_number.ilike(keyword),
            Member.display_name.ilike(keyword),
            Member.username.ilike(keyword),
            Product.name.ilike(keyword)
        ))

    total = query.count()
    orders = query.order_by(Order.created_at.desc()).offset(offset).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    admin = db.session.get(Admin, session.get('user_id'))
    return render_template('orders/list.html', orders=orders, total=total,
        page=page, per_page=per_page, total_pages=total_pages, admin=admin,
        status_options=ORDER_STATUS_OPTIONS, status_labels=ORDER_STATUS_LABELS,
        selected_status=selected_status, q=q)


@app.route('/orders/<int:order_id>')
@login_required
def orders_detail(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        flash('訂單不存在', 'error')
        return redirect(url_for('orders_list'))

    admin = db.session.get(Admin, session.get('user_id'))
    return render_template('orders/detail.html', order=order, admin=admin,
        status_options=ORDER_STATUS_OPTIONS, status_labels=ORDER_STATUS_LABELS)


@app.route('/orders/<int:order_id>/edit', methods=['GET', 'POST'])
@login_required
def orders_edit(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        flash('訂單不存在', 'error')
        return redirect(url_for('orders_list'))

    if request.method == 'POST':
        success, errors = update_order_from_form(order)
        if success:
            db.session.commit()
            flash(f'訂單「{order.order_number}」已更新', 'success')
            return redirect(url_for('orders_detail', order_id=order.id))

        for error in errors:
            flash(error, 'error')
        return render_order_form(order, form_data=request.form)

    return render_order_form(order)


@app.route('/orders/<int:order_id>/status', methods=['POST'])
@login_required
def orders_update_status(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        flash('訂單不存在', 'error')
        return redirect(url_for('orders_list'))

    new_status = request.form.get('status', '').strip()
    if new_status not in ORDER_STATUS_LABELS:
        flash('無效的訂單狀態', 'error')
        if request.form.get('return_to') == 'list':
            return redirect_to_orders_list_from_form()
        return redirect(url_for('orders_detail', order_id=order_id))

    order.status = new_status
    order.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f'訂單狀態已更新為「{ORDER_STATUS_LABELS[new_status]}」', 'success')
    if request.form.get('return_to') == 'list':
        return redirect_to_orders_list_from_form()
    return redirect(url_for('orders_detail', order_id=order_id))


@app.route('/orders/<int:order_id>/delete', methods=['POST'])
@login_required
def orders_delete(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        flash('訂單不存在', 'error')
        return redirect(url_for('orders_list'))

    order_number = order.order_number
    db.session.delete(order)
    db.session.commit()

    flash(f'訂單「{order_number}」已刪除', 'success')
    if request.form.get('return_to') == 'list':
        return redirect_to_orders_list_from_form()
    return redirect(url_for('orders_list'))


@app.route('/members')
@login_required
def members_list():
    page = max(1, int(request.args.get('page', 1)))
    per_page = 20
    offset = (page - 1) * per_page
    query = Member.query.order_by(Member.created_at.desc())
    total = query.count()
    members = query.offset(offset).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    admin = db.session.get(Admin, session.get('user_id'))
    return render_template('members/list.html', members=members, total=total,
        page=page, per_page=per_page, total_pages=total_pages, admin=admin)


@app.route('/members/<int:member_id>')
@login_required
def members_detail(member_id):
    member = db.session.get(Member, member_id)
    if not member:
        flash('會員不存在', 'error')
        return redirect(url_for('members_list'))

    orders = Order.query.filter_by(member_id=member_id).order_by(Order.created_at.desc()).all()

    admin = db.session.get(Admin, session.get('user_id'))
    return render_template('members/detail.html', member=member, orders=orders, admin=admin,
        status_labels=ORDER_STATUS_LABELS)


@app.route('/members/<int:member_id>/edit', methods=['GET', 'POST'])
@login_required
def members_edit(member_id):
    member = db.session.get(Member, member_id)
    if not member:
        flash('會員不存在', 'error')
        return redirect(url_for('members_list'))

    if request.method == 'POST':
        success, errors = update_member_from_form(member)
        if success:
            db.session.commit()
            flash(f'會員「{member.display_name or member.username}」已更新', 'success')
            return redirect(url_for('members_detail', member_id=member.id))

        for error in errors:
            flash(error, 'error')
        return render_member_form(member, form_data=request.form)

    return render_member_form(member)


@app.route('/members/<int:member_id>/toggle-active', methods=['POST'])
@login_required
def members_toggle_active(member_id):
    member = db.session.get(Member, member_id)
    if not member:
        flash('會員不存在', 'error')
        return redirect(url_for('members_list'))

    member.is_active = not member.is_active
    member.updated_at = datetime.utcnow()
    db.session.commit()

    status = '已啟用' if member.is_active else '已停用'
    flash(f'會員「{member.display_name or member.username}」{status}', 'success')
    if request.form.get('return_to') == 'list':
        return redirect_to_members_list_from_form()
    return redirect(url_for('members_detail', member_id=member_id))


@app.route('/members/<int:member_id>/disable', methods=['POST'])
@login_required
def members_disable(member_id):
    member = db.session.get(Member, member_id)
    if not member:
        flash('會員不存在', 'error')
        return redirect(url_for('members_list'))

    member.is_active = False
    member.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f'會員「{member.display_name or member.username}」已停用', 'success')
    if request.form.get('return_to') == 'list':
        return redirect_to_members_list_from_form()
    return redirect(url_for('members_detail', member_id=member_id))


@app.route('/members/<int:member_id>/delete', methods=['POST'])
@login_required
def members_delete(member_id):
    member = db.session.get(Member, member_id)
    if not member:
        flash('會員不存在', 'error')
        return redirect(url_for('members_list'))

    name = member.display_name or member.username
    Order.query.filter_by(member_id=member_id).update({'member_id': None, 'updated_at': datetime.utcnow()})
    db.session.delete(member)
    db.session.commit()

    flash(f'會員「{name}」已刪除，相關訂單已保留為訪客訂單', 'success')
    if request.form.get('return_to') == 'list':
        return redirect_to_members_list_from_form()
    return redirect(url_for('members_list'))


@app.route('/admins')
@login_required
def admins_list():
    page = max(1, int(request.args.get('page', 1)))
    per_page = 20
    offset = (page - 1) * per_page
    query = Admin.query.order_by(Admin.created_at.desc())
    total = query.count()
    admins = query.offset(offset).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    current_admin = db.session.get(Admin, session.get('user_id'))
    return render_template('admins/list.html', admins=admins, total=total,
        page=page, per_page=per_page, total_pages=total_pages, admin=current_admin)


@app.route('/admins/new', methods=['GET', 'POST'])
@login_required
def admins_new():
    current_admin = db.session.get(Admin, session.get('user_id'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        display_name = request.form.get('display_name', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'admin').strip()

        errors = []
        if not username:
            errors.append('帳號為必填')
        if not email:
            errors.append('Email 為必填')
        if not password:
            errors.append('密碼為必填')
        if len(password) < 6:
            errors.append('密碼至少需要 6 個字元')

        valid_roles = ['superadmin', 'admin', 'editor']
        if role not in valid_roles:
            errors.append('無效的角色')

        if Admin.query.filter_by(username=username).first():
            errors.append('帳號已存在')
        if Admin.query.filter_by(email=email).first():
            errors.append('Email 已被使用')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('admins/form.html', admin=current_admin,
                form_data=request.form, is_edit=False)

        admin = Admin(
            username=username,
            email=email,
            display_name=display_name or username,
            password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
            role=role,
            is_active=True
        )
        db.session.add(admin)
        db.session.commit()

        flash(f'管理員「{username}」已建立', 'success')
        return redirect(url_for('admins_list'))

    return render_template('admins/form.html', admin=current_admin, form_data=None, is_edit=False)


@app.route('/admins/<int:admin_id>')
@login_required
def admins_detail(admin_id):
    target_admin = db.session.get(Admin, admin_id)
    if not target_admin:
        flash('管理員不存在', 'error')
        return redirect(url_for('admins_list'))

    current_admin = db.session.get(Admin, session.get('user_id'))
    return render_template('admins/detail.html', target_admin=target_admin, admin=current_admin)


@app.route('/admins/<int:admin_id>/edit', methods=['GET', 'POST'])
@login_required
def admins_edit(admin_id):
    target_admin = db.session.get(Admin, admin_id)
    if not target_admin:
        flash('管理員不存在', 'error')
        return redirect(url_for('admins_list'))

    current_admin = db.session.get(Admin, session.get('user_id'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        display_name = request.form.get('display_name', '').strip()
        role = request.form.get('role', '').strip()
        is_active = request.form.get('is_active') == '1'

        errors = []
        if not email:
            errors.append('Email 為必填')

        valid_roles = ['superadmin', 'admin', 'editor']
        if role not in valid_roles:
            errors.append('無效的角色')

        existing_email = Admin.query.filter_by(email=email).first()
        if existing_email and existing_email.id != admin_id:
            errors.append('Email 已被使用')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('admins/form.html', admin=current_admin,
                target_admin=target_admin, form_data=request.form, is_edit=True)

        target_admin.email = email
        target_admin.display_name = display_name
        target_admin.role = role
        target_admin.is_active = is_active
        target_admin.updated_at = datetime.utcnow()
        db.session.commit()

        flash(f'管理員「{target_admin.username}」已更新', 'success')
        return redirect(url_for('admins_detail', admin_id=admin_id))

    return render_template('admins/form.html', admin=current_admin,
        target_admin=target_admin, form_data=None, is_edit=True)


@app.route('/admins/<int:admin_id>', methods=['POST'])
@login_required
def admins_update(admin_id):
    return redirect(url_for('admins_edit', admin_id=admin_id))


@app.route('/admins/<int:admin_id>/delete', methods=['POST'])
@login_required
def admins_delete(admin_id):
    target_admin = db.session.get(Admin, admin_id)
    if not target_admin:
        flash('管理員不存在', 'error')
        return redirect(url_for('admins_list'))

    if target_admin.id == session.get('user_id'):
        flash('無法刪除自己的帳號', 'error')
        return redirect(url_for('admins_list'))

    target_admin.is_active = False
    target_admin.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f'管理員「{target_admin.username}」已停用', 'success')
    return redirect(url_for('admins_list'))


@app.route('/admins/<int:admin_id>/reset-password', methods=['POST'])
@login_required
def admins_reset_password(admin_id):
    target_admin = db.session.get(Admin, admin_id)
    if not target_admin:
        flash('管理員不存在', 'error')
        return redirect(url_for('admins_list'))

    new_password = request.form.get('new_password', '')
    if len(new_password) < 6:
        flash('密碼至少需要 6 個字元', 'error')
        return redirect(url_for('admins_detail', admin_id=admin_id))

    target_admin.password_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
    target_admin.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f'管理員「{target_admin.username}」密碼已重設', 'success')
    return redirect(url_for('admins_detail', admin_id=admin_id))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
else:
    pass
