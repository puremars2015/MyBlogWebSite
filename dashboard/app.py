import os
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy


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

db = SQLAlchemy(app)


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


SERIES_SEED = [
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

EVENT_SEED = [
    ('next-fomc', 'FOMC 利率決策會議', '美國央行與利率', 18, '下次 FOMC 會議與利率聲明公布。', 'Federal Reserve'),
    ('next-us-cpi', '美國 CPI 公布', '美國就業與通膨', 9, '美國 CPI 與核心 CPI 數據公布。', 'BLS'),
    ('next-nfp', '美國非農就業公布', '美國就業與通膨', 14, '非農就業人口、失業率與薪資數據公布。', 'BLS'),
    ('next-tw-cpi', '台灣 CPI 公布', '台灣經濟數據', 11, '台灣 CPI 與物價相關統計公布。', '主計總處'),
]

JOB_SEED = [
    ('Mock: 美國央行與利率', 'mock', 'fed_funds_rate', 'daily', 1440, '08:00'),
    ('Mock: 美國就業與通膨', 'mock', 'us_cpi_yoy', 'daily', 1440, '08:10'),
    ('Mock: 台灣經濟數據', 'mock', 'taiwan_cpi_yoy', 'daily', 1440, '08:20'),
    ('Mock: 貴金屬價格', 'mock', 'gold_spot_usd', 'interval_minutes', 60, '08:30'),
]


def ensure_schema_and_seed():
    db.create_all()

    if EconomicSeries.query.count() == 0:
        now = datetime.utcnow()
        for code, name, category, description, unit, source_name, sort_order, value, previous, change, status in SERIES_SEED:
            series = EconomicSeries(
                code=code,
                name=name,
                category=category,
                description=description,
                unit=unit,
                source_name=source_name,
                sort_order=sort_order,
            )
            db.session.add(series)
            db.session.flush()
            db.session.add(EconomicObservation(
                series_id=series.id,
                observed_at=now - timedelta(hours=sort_order % 8),
                value=value,
                previous_value=previous,
                change_label=change,
                status_label=status,
            ))

    if EconomicEvent.query.count() == 0:
        now = datetime.utcnow()
        for slug, title, category, days, description, source_name in EVENT_SEED:
            db.session.add(EconomicEvent(
                slug=slug,
                title=title,
                category=category,
                event_at=now + timedelta(days=days),
                description=description,
                source_name=source_name,
            ))

    if EconomicFetchJob.query.count() == 0:
        now = datetime.utcnow()
        for name, provider, series_code, schedule_type, interval_minutes, daily_time in JOB_SEED:
            db.session.add(EconomicFetchJob(
                name=name,
                provider=provider,
                series_code=series_code,
                schedule_type=schedule_type,
                interval_minutes=interval_minutes,
                daily_time=daily_time,
                is_active=True,
                next_run_at=now + timedelta(minutes=5),
                last_status='seeded',
                last_message='Mock job seeded. API keys are expected from .env in future providers.',
            ))

    db.session.commit()


_schema_ready = False


@app.before_request
def bootstrap_once():
    global _schema_ready
    if not _schema_ready:
        ensure_schema_and_seed()
        _schema_ready = True


def latest_observation(series_id):
    return EconomicObservation.query.filter_by(series_id=series_id).order_by(EconomicObservation.observed_at.desc()).first()


def ensure_txf_series():
    series = EconomicSeries.query.filter_by(code='txf_price').first()
    if series:
        return series

    series = EconomicSeries(
        code='txf_price',
        name='台指期近月',
        category='台灣市場價格',
        description='台灣加權股價指數期貨近月合約即時價格',
        unit='點',
        source_name='External TXF Feed',
        sort_order=24,
    )
    db.session.add(series)
    db.session.commit()
    return series


def parse_observed_at(raw_value):
    if not raw_value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(str(raw_value).replace('Z', '+00:00')).replace(tzinfo=None)
    except ValueError:
        return None


def txf_payload():
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict()


def txf_authorized():
    token = os.getenv('DASHBOARD_INGEST_TOKEN', '').strip()
    if not token:
        return True
    return request.headers.get('X-Dashboard-Token') == token or request.args.get('token') == token


def serialize_txf(series, observation):
    return {
        'code': series.code,
        'name': series.name,
        'price': float(observation.value),
        'previous_price': float(observation.previous_value) if observation.previous_value is not None else None,
        'unit': series.unit,
        'change_label': observation.change_label,
        'status_label': observation.status_label,
        'observed_at': observation.observed_at.isoformat(),
        'source_name': series.source_name,
    }


def dashboard_cards():
    cards = []
    series_list = EconomicSeries.query.order_by(EconomicSeries.category, EconomicSeries.sort_order, EconomicSeries.id).all()
    for series in series_list:
        obs = latest_observation(series.id)
        if not obs:
            continue
        cards.append({
            'series': series,
            'observation': obs,
            'value': float(obs.value),
            'previous_value': float(obs.previous_value) if obs.previous_value is not None else None,
        })
    return cards


@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})


@app.route('/api/summary')
def api_summary():
    ensure_schema_and_seed()
    return jsonify({
        'items': [{
            'code': card['series'].code,
            'name': card['series'].name,
            'category': card['series'].category,
            'value': card['value'],
            'unit': card['series'].unit,
            'change_label': card['observation'].change_label,
            'status_label': card['observation'].status_label,
            'observed_at': card['observation'].observed_at.isoformat(),
            'source_name': card['series'].source_name,
        } for card in dashboard_cards()]
    })


@app.route('/api/txf_price', methods=['GET', 'POST'])
def api_txf_price():
    ensure_schema_and_seed()
    series = ensure_txf_series()

    if request.method == 'GET':
        observation = latest_observation(series.id)
        if not observation:
            return jsonify({'error': 'TXF price not found'}), 404
        return jsonify(serialize_txf(series, observation))

    if not txf_authorized():
        return jsonify({'error': 'Unauthorized'}), 401

    payload = txf_payload()
    raw_price = payload.get('price', payload.get('value'))
    if raw_price in (None, ''):
        return jsonify({'error': 'price is required'}), 400

    try:
        price = Decimal(str(raw_price))
    except InvalidOperation:
        return jsonify({'error': 'price must be numeric'}), 400

    if price <= 0:
        return jsonify({'error': 'price must be greater than 0'}), 400

    observed_at = parse_observed_at(payload.get('observed_at') or payload.get('timestamp'))
    if not observed_at:
        return jsonify({'error': 'observed_at must be ISO datetime'}), 400

    latest = latest_observation(series.id)
    previous_price = Decimal(latest.value) if latest else None
    if previous_price is None or price == previous_price:
        status_label = 'flat'
        change_label = '持平'
    elif price > previous_price:
        status_label = 'up'
        change_label = f'+{price - previous_price}'
    else:
        status_label = 'down'
        change_label = f'-{previous_price - price}'

    source_name = payload.get('source') or payload.get('source_name')
    if source_name:
        series.source_name = str(source_name).strip()[:120]
    series.updated_at = datetime.utcnow()

    observation = EconomicObservation(
        series_id=series.id,
        observed_at=observed_at,
        value=price,
        previous_value=previous_price,
        change_label=change_label,
        status_label=status_label,
    )
    db.session.add(observation)
    db.session.commit()

    return jsonify({'status': 'created', 'item': serialize_txf(series, observation)}), 201


@app.route('/')
def index():
    ensure_schema_and_seed()
    cards = dashboard_cards()
    categories = []
    for card in cards:
        if card['series'].category not in categories:
            categories.append(card['series'].category)
    events = EconomicEvent.query.order_by(EconomicEvent.event_at).limit(8).all()
    updated_at = max((card['observation'].observed_at for card in cards), default=None)
    return render_template('index.html', cards=cards, categories=categories,
        events=events, updated_at=updated_at)
