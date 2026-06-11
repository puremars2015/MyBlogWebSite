import os
from datetime import datetime
from functools import wraps
from flask import Flask, jsonify, request, render_template, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text

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


@app.route('/products/<int:product_id>')
@login_required
def products_detail(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        flash('課程不存在', 'error')
        return redirect(url_for('products_list'))

    admin = db.session.get(Admin, session.get('user_id'))
    return render_template('products/detail.html', product=product, admin=admin)


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


@app.route('/orders')
@login_required
def orders_list():
    page = max(1, int(request.args.get('page', 1)))
    per_page = 20
    offset = (page - 1) * per_page
    query = Order.query.order_by(Order.created_at.desc())
    total = query.count()
    orders = query.offset(offset).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    admin = db.session.get(Admin, session.get('user_id'))
    return render_template('orders/list.html', orders=orders, total=total,
        page=page, per_page=per_page, total_pages=total_pages, admin=admin)


@app.route('/orders/<int:order_id>')
@login_required
def orders_detail(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        flash('訂單不存在', 'error')
        return redirect(url_for('orders_list'))

    admin = db.session.get(Admin, session.get('user_id'))
    return render_template('orders/detail.html', order=order, admin=admin)


@app.route('/orders/<int:order_id>/status', methods=['POST'])
@login_required
def orders_update_status(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        flash('訂單不存在', 'error')
        return redirect(url_for('orders_list'))

    new_status = request.form.get('status', '').strip()
    valid_statuses = ['pending', 'paid', 'shipped', 'done', 'cancelled']
    if new_status not in valid_statuses:
        flash('無效的訂單狀態', 'error')
        return redirect(url_for('orders_detail', order_id=order_id))

    order.status = new_status
    order.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f'訂單狀態已更新為「{new_status}」', 'success')
    return redirect(url_for('orders_detail', order_id=order_id))


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
    return render_template('members/detail.html', member=member, orders=orders, admin=admin)


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
    return redirect(url_for('members_detail', member_id=member_id))


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
