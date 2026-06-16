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
    region = db.Column(db.Unicode(8), default='US')
    frequency = db.Column(db.Unicode(16), default='daily')
    is_derived = db.Column(db.Boolean, default=False)
    transformation = db.Column(db.Unicode(20), default='level')
    fred_code = db.Column(db.Unicode(80))
    yfinance_symbol = db.Column(db.Unicode(40))
    legacy_cleaned = db.Column(db.Boolean, default=False)
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
    derived_sources = db.Column(db.Unicode(200))
    derived_op = db.Column(db.Unicode(20))
    yfinance_symbol = db.Column(db.Unicode(40))
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
    {
        'code': 'fed_funds_rate', 'name': 'FED 利率',
        'category': '利率', 'description': '聯邦基金目標利率區間上緣',
        'unit': '%', 'source_name': 'Federal Reserve', 'sort_order': 1,
        'region': 'US', 'frequency': 'daily', 'transformation': 'level',
        'fred_code': 'DFF', 'yfinance_symbol': '',
    },
    {
        'code': 'us_cpi_yoy', 'name': '美國 CPI 年增率',
        'category': '通膨', 'description': '美國消費者物價指數年增率',
        'unit': '%', 'source_name': 'BLS', 'sort_order': 11,
        'region': 'US', 'frequency': 'monthly', 'transformation': 'yoy',
        'fred_code': 'CPIAUCSL', 'yfinance_symbol': '',
    },
    {
        'code': 'taiwan_policy_rate', 'name': '台灣央行政策利率',
        'category': '利率', 'description': '中央銀行重貼現率',
        'unit': '%', 'source_name': '中央銀行', 'sort_order': 20,
        'region': 'TW', 'frequency': 'quarterly', 'transformation': 'level',
        'fred_code': '', 'yfinance_symbol': '',
    },
    {
        'code': 'taiwan_cpi_yoy', 'name': '台灣 CPI 年增率',
        'category': '通膨', 'description': '台灣消費者物價指數年增率',
        'unit': '%', 'source_name': '主計總處', 'sort_order': 21,
        'region': 'TW', 'frequency': 'monthly', 'transformation': 'level',
        'fred_code': '', 'yfinance_symbol': '',
    },
    {
        'code': 'taiwan_gdp_yoy', 'name': '台灣 GDP 年增率',
        'category': '景氣', 'description': '台灣實質 GDP 年增率',
        'unit': '%', 'source_name': '主計總處', 'sort_order': 22,
        'region': 'TW', 'frequency': 'quarterly', 'transformation': 'level',
        'fred_code': '', 'yfinance_symbol': '',
    },
    {
        'code': 'taiwan_unemployment', 'name': '台灣失業率',
        'category': '景氣', 'description': '台灣失業率',
        'unit': '%', 'source_name': '主計總處', 'sort_order': 23,
        'region': 'TW', 'frequency': 'monthly', 'transformation': 'level',
        'fred_code': '', 'yfinance_symbol': '',
    },
    {
        'code': 'txf_price', 'name': '台指期近月',
        'category': '台灣市場價格', 'description': '台灣加權股價指數期貨近月合約前一交易日收盤價',
        'unit': '點', 'source_name': 'TAIFEX', 'sort_order': 24,
        'region': 'TW', 'frequency': 'daily', 'transformation': 'level',
        'fred_code': '', 'yfinance_symbol': '',
    },
    {
        'code': 'gold_spot_usd', 'name': '黃金現貨',
        'category': '商品', 'description': '黃金現貨美元價格',
        'unit': 'USD/oz', 'source_name': 'yfinance', 'sort_order': 30,
        'region': 'Global', 'frequency': 'daily', 'transformation': 'level',
        'fred_code': '', 'yfinance_symbol': 'GC=F',
    },
    {
        'code': 'silver_spot_usd', 'name': '白銀現貨',
        'category': '商品', 'description': '白銀現貨美元價格',
        'unit': 'USD/oz', 'source_name': 'yfinance', 'sort_order': 31,
        'region': 'Global', 'frequency': 'daily', 'transformation': 'level',
        'fred_code': '', 'yfinance_symbol': 'SI=F',
    },
    {
        'code': 'sp500', 'name': 'S&P 500',
        'category': '大盤指數', 'description': '美國標普 500 指數收盤',
        'unit': '點', 'source_name': 'FRED', 'sort_order': 1,
        'region': 'US', 'frequency': 'daily', 'transformation': 'level',
        'fred_code': 'SP500', 'yfinance_symbol': '^GSPC',
    },
    {
        'code': 'nasdaq', 'name': 'NASDAQ Composite',
        'category': '大盤指數', 'description': '那斯達克綜合指數收盤',
        'unit': '點', 'source_name': 'FRED', 'sort_order': 2,
        'region': 'US', 'frequency': 'daily', 'transformation': 'level',
        'fred_code': 'NASDAQCOM', 'yfinance_symbol': '^IXIC',
    },
    {
        'code': 'twse_index', 'name': '台股加權指數',
        'category': '大盤指數', 'description': '台灣加權股價指數',
        'unit': '點', 'source_name': 'TWSE 開放 API', 'sort_order': 3,
        'region': 'TW', 'frequency': 'daily', 'transformation': 'level',
        'fred_code': '', 'yfinance_symbol': '^TWII',
    },
    {
        'code': 'fear_greed', 'name': 'Fear & Greed Index',
        'category': '市場情緒', 'description': 'CNN 恐懼與貪婪指數 (0-100)',
        'unit': '', 'source_name': 'CNN', 'sort_order': 1,
        'region': 'US', 'frequency': 'daily', 'transformation': 'level',
        'fred_code': '', 'yfinance_symbol': '',
    },
    {
        'code': 'vix', 'name': 'VIX',
        'category': '市場情緒', 'description': 'CBOE 波動率指數 (VIXCLS)',
        'unit': '', 'source_name': 'FRED', 'sort_order': 2,
        'region': 'US', 'frequency': 'daily', 'transformation': 'level',
        'fred_code': 'VIXCLS', 'yfinance_symbol': '^VIX',
    },
    {
        'code': 'put_call_ratio', 'name': 'Put/Call Ratio',
        'category': '市場情緒', 'description': 'CBOE daily options put/call 成交量比例',
        'unit': 'ratio', 'source_name': 'CBOE', 'sort_order': 3,
        'region': 'US', 'frequency': 'daily', 'transformation': 'level',
        'fred_code': '', 'yfinance_symbol': 'SPY',
    },
    {
        'code': 'ust_2y', 'name': '美國 2Y 公債殖利率',
        'category': '利率', 'description': '美國 2 年期公債殖利率 (DGS2)',
        'unit': '%', 'source_name': 'FRED', 'sort_order': 1,
        'region': 'US', 'frequency': 'daily', 'transformation': 'level',
        'fred_code': 'DGS2', 'yfinance_symbol': '',
    },
    {
        'code': 'ust_10y', 'name': '美國 10Y 公債殖利率',
        'category': '利率', 'description': '美國 10 年期公債殖利率 (DGS10)',
        'unit': '%', 'source_name': 'FRED', 'sort_order': 2,
        'region': 'US', 'frequency': 'daily', 'transformation': 'level',
        'fred_code': 'DGS10', 'yfinance_symbol': '',
    },
    {
        'code': 'ust_2y10y_spread', 'name': '2Y-10Y 利差',
        'category': '利率', 'description': '10 年期減 2 年期公債殖利率利差 (衰退指標)',
        'unit': '%', 'source_name': 'Derived', 'sort_order': 3,
        'region': 'US', 'frequency': 'daily', 'transformation': 'level',
        'fred_code': '', 'yfinance_symbol': '',
        'is_derived': True,
    },
    {
        'code': 'core_cpi_yoy', 'name': '美國 Core CPI 年增率',
        'category': '通膨', 'description': '美國核心 CPI 年增率 (CPILFESL)',
        'unit': '%', 'source_name': 'FRED', 'sort_order': 1,
        'region': 'US', 'frequency': 'monthly', 'transformation': 'yoy',
        'fred_code': 'CPILFESL', 'yfinance_symbol': '',
    },
    {
        'code': 'pce_yoy', 'name': '美國 PCE 年增率',
        'category': '通膨', 'description': '美國個人消費支出物價指數年增率 (PCEPI)',
        'unit': '%', 'source_name': 'FRED', 'sort_order': 2,
        'region': 'US', 'frequency': 'monthly', 'transformation': 'yoy',
        'fred_code': 'PCEPI', 'yfinance_symbol': '',
    },
    {
        'code': 'us_unemployment', 'name': '美國失業率',
        'category': '景氣', 'description': '美國 U-3 失業率 (UNRATE)',
        'unit': '%', 'source_name': 'FRED', 'sort_order': 1,
        'region': 'US', 'frequency': 'monthly', 'transformation': 'level',
        'fred_code': 'UNRATE', 'yfinance_symbol': '',
    },
    {
        'code': 'us_nfp', 'name': '美國非農就業新增',
        'category': '景氣', 'description': '美國非農就業人口月增 (PAYEMS MoM)',
        'unit': '千人', 'source_name': 'FRED', 'sort_order': 2,
        'region': 'US', 'frequency': 'monthly', 'transformation': 'mom',
        'fred_code': 'PAYEMS', 'yfinance_symbol': '',
    },
    {
        'code': 'us_gdp_yoy', 'name': '美國 GDP 年增率',
        'category': '景氣', 'description': '美國實質 GDP 年增率 (GDPC1)',
        'unit': '%', 'source_name': 'FRED', 'sort_order': 3,
        'region': 'US', 'frequency': 'quarterly', 'transformation': 'yoy',
        'fred_code': 'GDPC1', 'yfinance_symbol': '',
    },
    {
        'code': 'tw_foreign_net', 'name': '台股外資買賣超',
        'category': '資金流', 'description': '台股外資及陸資買賣超 (TWSE 開放 API)',
        'unit': '億元', 'source_name': 'TWSE 開放 API', 'sort_order': 2,
        'region': 'TW', 'frequency': 'daily', 'transformation': 'level',
        'fred_code': '', 'yfinance_symbol': '',
    },
    {
        'code': 'tw_margin_balance', 'name': '台股融資餘額',
        'category': '資金流', 'description': '台股整體融資餘額 (TWSE 開放 API)',
        'unit': '千元', 'source_name': 'TWSE 開放 API', 'sort_order': 3,
        'region': 'TW', 'frequency': 'daily', 'transformation': 'level',
        'fred_code': '', 'yfinance_symbol': '',
    },
]

EVENT_SEED = [
    ('next-fomc', 'FOMC 利率決策會議', '美國央行與利率', 18, '下次 FOMC 會議與利率聲明公布。', 'Federal Reserve'),
    ('next-us-cpi', '美國 CPI 公布', '通膨', 9, '美國 CPI 與核心 CPI 數據公布。', 'BLS'),
    ('next-nfp', '美國非農就業公布', '景氣', 14, '非農就業人口、失業率與薪資數據公布。', 'BLS'),
    ('next-tw-cpi', '台灣 CPI 公布', '台灣經濟數據', 11, '台灣 CPI 與物價相關統計公布。', '主計總處'),
    ('next-pce', '美國 PCE 公布', '通膨', 22, 'Fed 偏好的通膨指標 PCE 公布。', 'BEA'),
    ('next-jackson-hole', 'Jackson Hole 央行年會', '美國央行與利率', 60, '全球央行年會, 重要政策訊號釋出。', 'Federal Reserve'),
]

JOB_SEED = [
    {'name': 'FRED: 美國利率', 'provider': 'fred', 'series_code': 'fed_funds_rate',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '08:00'},
    {'name': 'FRED: 美國 2Y', 'provider': 'fred', 'series_code': 'ust_2y',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '08:05'},
    {'name': 'FRED: 美國 10Y', 'provider': 'fred', 'series_code': 'ust_10y',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '08:05'},
    {'name': 'Derived: 2Y-10Y 利差', 'provider': 'derived', 'series_code': 'ust_2y10y_spread',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '08:10',
     'derived_sources': 'ust_10y,ust_2y', 'derived_op': 'sub'},
    {'name': 'FRED: 美國 CPI', 'provider': 'fred', 'series_code': 'us_cpi_yoy',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '08:15'},
    {'name': 'FRED: 美國 Core CPI', 'provider': 'fred', 'series_code': 'core_cpi_yoy',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '08:15'},
    {'name': 'FRED: 美國 PCE', 'provider': 'fred', 'series_code': 'pce_yoy',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '08:20'},
    {'name': 'FRED: 失業率', 'provider': 'fred', 'series_code': 'us_unemployment',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '08:25'},
    {'name': 'FRED: NFP', 'provider': 'fred', 'series_code': 'us_nfp',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '08:30'},
    {'name': 'FRED: GDP', 'provider': 'fred', 'series_code': 'us_gdp_yoy',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '08:35'},
    {'name': 'FRED: S&P 500', 'provider': 'fred', 'series_code': 'sp500',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '08:40'},
    {'name': 'FRED: NASDAQ', 'provider': 'fred', 'series_code': 'nasdaq',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '08:40'},
    {'name': 'FRED: VIX', 'provider': 'fred', 'series_code': 'vix',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '08:45'},
    {'name': 'TWSE: 台股加權', 'provider': 'twse_openapi', 'series_code': 'twse_index',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '17:00'},
    {'name': 'TAIFEX: 台指期近月收盤', 'provider': 'taifex', 'series_code': 'txf_price',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '08:00'},
    {'name': 'yfinance: 黃金現貨', 'provider': 'yfinance', 'series_code': 'gold_spot_usd',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '20:00',
     'yfinance_symbol': 'GC=F'},
    {'name': 'yfinance: 白銀現貨', 'provider': 'yfinance', 'series_code': 'silver_spot_usd',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '20:00',
     'yfinance_symbol': 'SI=F'},
    {'name': 'CBOE: Put/Call Ratio', 'provider': 'cboe', 'series_code': 'put_call_ratio',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '20:30',
     'yfinance_symbol': 'SPY'},
    {'name': 'CNN Official: Fear & Greed', 'provider': 'cnn_official_fear_greed', 'series_code': 'fear_greed',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '09:00'},
    {'name': 'TWSE: 外資買賣超', 'provider': 'twse_openapi', 'series_code': 'tw_foreign_net',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '17:00'},
    {'name': 'TWSE: 融資餘額', 'provider': 'twse_openapi', 'series_code': 'tw_margin_balance',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '17:05'},
    {'name': 'Taiwan Economic: 央行政策利率', 'provider': 'taiwan_economic', 'series_code': 'taiwan_policy_rate',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '09:10'},
    {'name': 'Taiwan Economic: CPI', 'provider': 'taiwan_economic', 'series_code': 'taiwan_cpi_yoy',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '09:15'},
    {'name': 'Taiwan Economic: GDP', 'provider': 'taiwan_economic', 'series_code': 'taiwan_gdp_yoy',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '09:20'},
    {'name': 'Taiwan Economic: 失業率', 'provider': 'taiwan_economic', 'series_code': 'taiwan_unemployment',
     'schedule_type': 'daily', 'interval_minutes': 1440, 'daily_time': '09:25'},
]


TEMPERATURE_RULES = {
    'fear_greed': {
        'benchmark': '0-25 恐懼, 25-75 中性, 75-100 貪婪',
        'bands': [(25, '過冷', 'cold'), (45, '偏冷', 'cool'), (55, '中性', 'neutral'), (75, '偏熱', 'warm'), (float('inf'), '過熱', 'hot')],
    },
    'vix': {
        'benchmark': '12-20 常態區, 20 以上壓力升高',
        'bands': [(12, '過熱', 'hot'), (20, '中性', 'neutral'), (30, '偏冷', 'cool'), (float('inf'), '過冷', 'cold')],
    },
    'put_call_ratio': {
        'benchmark': '0.7-1.2 常態區, 越高越偏防禦',
        'bands': [(0.7, '過熱', 'hot'), (0.9, '偏熱', 'warm'), (1.2, '中性', 'neutral'), (1.5, '偏冷', 'cool'), (float('inf'), '過冷', 'cold')],
    },
    'fed_funds_rate': {
        'benchmark': '2-4% 中性附近, 高於 5% 政策偏緊',
        'bands': [(1, '過冷', 'cold'), (2, '偏冷', 'cool'), (4, '中性', 'neutral'), (5, '偏熱', 'warm'), (float('inf'), '過熱', 'hot')],
    },
    'ust_2y10y_spread': {
        'benchmark': '0-1% 常態區, 倒掛代表衰退壓力',
        'bands': [(-0.5, '過冷', 'cold'), (0, '偏冷', 'cool'), (1, '中性', 'neutral'), (1.5, '偏熱', 'warm'), (float('inf'), '過熱', 'hot')],
    },
    'us_cpi_yoy': {
        'benchmark': 'Fed 目標約 2%, 3% 以上偏熱',
        'bands': [(1.5, '偏冷', 'cool'), (2.7, '中性', 'neutral'), (4, '偏熱', 'warm'), (float('inf'), '過熱', 'hot')],
    },
    'core_cpi_yoy': {
        'benchmark': '2% 附近較均衡, 3% 以上偏熱',
        'bands': [(1.5, '偏冷', 'cool'), (2.7, '中性', 'neutral'), (4, '偏熱', 'warm'), (float('inf'), '過熱', 'hot')],
    },
    'pce_yoy': {
        'benchmark': 'Fed PCE 目標 2%, 3% 以上偏熱',
        'bands': [(1.5, '偏冷', 'cool'), (2.5, '中性', 'neutral'), (3.5, '偏熱', 'warm'), (float('inf'), '過熱', 'hot')],
    },
    'us_unemployment': {
        'benchmark': '4-4.5% 附近較均衡, 越低越熱',
        'bands': [(3.8, '過熱', 'hot'), (4.5, '中性', 'neutral'), (5.5, '偏冷', 'cool'), (float('inf'), '過冷', 'cold')],
    },
    'us_nfp': {
        'benchmark': '月增 100-250 千人通常較均衡',
        'bands': [(0, '過冷', 'cold'), (100, '偏冷', 'cool'), (250, '中性', 'neutral'), (400, '偏熱', 'warm'), (float('inf'), '過熱', 'hot')],
    },
    'us_gdp_yoy': {
        'benchmark': '1.5-3% 常態成長區',
        'bands': [(0, '過冷', 'cold'), (1.5, '偏冷', 'cool'), (3, '中性', 'neutral'), (4, '偏熱', 'warm'), (float('inf'), '過熱', 'hot')],
    },
    'taiwan_cpi_yoy': {
        'benchmark': '2% 附近較均衡, 3% 以上偏熱',
        'bands': [(1, '偏冷', 'cool'), (2.5, '中性', 'neutral'), (3.5, '偏熱', 'warm'), (float('inf'), '過熱', 'hot')],
    },
    'taiwan_gdp_yoy': {
        'benchmark': '2-4% 常態成長區',
        'bands': [(0, '過冷', 'cold'), (2, '偏冷', 'cool'), (4, '中性', 'neutral'), (6, '偏熱', 'warm'), (float('inf'), '過熱', 'hot')],
    },
    'taiwan_unemployment': {
        'benchmark': '3.5-4% 附近較均衡, 越低越熱',
        'bands': [(3.3, '過熱', 'hot'), (4, '中性', 'neutral'), (4.5, '偏冷', 'cool'), (float('inf'), '過冷', 'cold')],
    },
    'taiwan_policy_rate': {
        'benchmark': '1.5-2.5% 常態區, 越高政策越偏緊',
        'bands': [(1, '過冷', 'cold'), (1.5, '偏冷', 'cool'), (2.5, '中性', 'neutral'), (3, '偏熱', 'warm'), (float('inf'), '過熱', 'hot')],
    },
    'tw_foreign_net': {
        'benchmark': '-100 至 +100 億元視為中性資金流',
        'bands': [(-300, '過冷', 'cold'), (-100, '偏冷', 'cool'), (100, '中性', 'neutral'), (300, '偏熱', 'warm'), (float('inf'), '過熱', 'hot')],
    },
}


TEMPERATURE_WEIGHTS = {
    'cold': -2,
    'cool': -1,
    'neutral': 0,
    'warm': 1,
    'hot': 2,
}


def _column_exists(conn, table, column):
    row = conn.execute(db.text(
        "SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(:t) AND name = :c"
    ), {'t': table, 'c': column}).scalar()
    return row is not None


def _add_column_if_missing(table, column, ddl_type, default_sql=None):
    with db.engine.connect() as conn:
        if _column_exists(conn, table, column):
            return
        stmt = f'ALTER TABLE {table} ADD {column} {ddl_type}'
        if default_sql is not None:
            stmt += f' DEFAULT {default_sql}'
        conn.execute(db.text(stmt))
        conn.commit()


def _migrate_schema():
    series_cols = [
        ('region', 'NVARCHAR(8)', "'US'"),
        ('frequency', 'NVARCHAR(16)', "'daily'"),
        ('is_derived', 'BIT', '0'),
        ('transformation', 'NVARCHAR(20)', "'level'"),
        ('fred_code', 'NVARCHAR(80)', None),
        ('yfinance_symbol', 'NVARCHAR(40)', None),
    ]
    for col, ddl, default in series_cols:
        _add_column_if_missing('economic_series', col, ddl, default)

    job_cols = [
        ('derived_sources', 'NVARCHAR(200)', None),
        ('derived_op', 'NVARCHAR(20)', None),
        ('yfinance_symbol', 'NVARCHAR(40)', None),
    ]
    for col, ddl, default in job_cols:
        _add_column_if_missing('economic_fetch_jobs', col, ddl, default)

    _add_column_if_missing('economic_series', 'legacy_cleaned', 'BIT', '0')
    with db.engine.connect() as conn:
        conn.execute(db.text(
            "UPDATE economic_series SET legacy_cleaned = 0 WHERE legacy_cleaned IS NULL"
        ))
        conn.commit()


def _cleanup_legacy():
    mock_jobs = EconomicFetchJob.query.filter_by(provider='mock').all()
    if mock_jobs:
        mock_ids = [j.id for j in mock_jobs]
        EconomicFetchRun.query.filter(
            EconomicFetchRun.job_id.in_(mock_ids)
        ).delete(synchronize_session=False)
        EconomicFetchJob.query.filter(
            EconomicFetchJob.id.in_(mock_ids)
        ).delete(synchronize_session=False)

    seeded_codes = {e['code'] for e in SERIES_SEED}
    stale_series = EconomicSeries.query.filter(
        ~EconomicSeries.code.in_(seeded_codes)
    ).all()
    if stale_series:
        stale_ids = [s.id for s in stale_series]
        EconomicObservation.query.filter(
            EconomicObservation.series_id.in_(stale_ids)
        ).delete(synchronize_session=False)
        EconomicSeries.query.filter(
            EconomicSeries.id.in_(stale_ids)
        ).delete(synchronize_session=False)

    target_ids = [
        s.id for s in EconomicSeries.query
        .filter(EconomicSeries.code.in_(seeded_codes))
        .filter(EconomicSeries.code != 'txf_price').all()
    ]
    if target_ids:
        EconomicObservation.query.filter(
            EconomicObservation.series_id.in_(target_ids)
        ).delete(synchronize_session=False)

    EconomicSeries.query.update({EconomicSeries.legacy_cleaned: True})


def _cleanup_obsolete_jobs():
    obsolete = EconomicFetchJob.query.filter(db.or_(
        db.and_(
            EconomicFetchJob.series_code == 'put_call_ratio',
            EconomicFetchJob.provider == 'yfinance_options',
        ),
        db.and_(
            EconomicFetchJob.series_code.in_(['sp500', 'nasdaq', 'twse_index']),
            EconomicFetchJob.provider == 'yfinance',
        ),
        db.and_(
            EconomicFetchJob.series_code == 'fear_greed',
            EconomicFetchJob.provider == 'cnn_fear_greed',
        ),
    )).all()
    if not obsolete:
        return
    ids = [j.id for j in obsolete]
    EconomicFetchRun.query.filter(
        EconomicFetchRun.job_id.in_(ids)
    ).delete(synchronize_session=False)
    EconomicFetchJob.query.filter(
        EconomicFetchJob.id.in_(ids)
    ).delete(synchronize_session=False)


def _cleanup_obsolete_series():
    obsolete_codes = ['fomc_dot_median', 'us_nonfarm_payrolls']
    obsolete = EconomicSeries.query.filter(EconomicSeries.code.in_(obsolete_codes)).all()
    if not obsolete:
        return
    ids = [s.id for s in obsolete]
    EconomicObservation.query.filter(
        EconomicObservation.series_id.in_(ids)
    ).delete(synchronize_session=False)
    EconomicSeries.query.filter(
        EconomicSeries.id.in_(ids)
    ).delete(synchronize_session=False)


def ensure_schema_and_seed():
    db.create_all()
    _migrate_schema()

    needs_cleanup = EconomicSeries.query.filter_by(legacy_cleaned=False).first() is not None
    if needs_cleanup:
        _cleanup_legacy()
    else:
        mock_jobs_still = EconomicFetchJob.query.filter_by(provider='mock').count()
        if mock_jobs_still > 0:
            _cleanup_legacy()
    _cleanup_obsolete_jobs()
    _cleanup_obsolete_series()

    existing_series = {s.code: s for s in EconomicSeries.query.all()}
    now = datetime.utcnow()
    for entry in SERIES_SEED:
        code = entry['code']
        if code in existing_series:
            series = existing_series[code]
            series.name = entry['name']
            series.category = entry['category']
            series.description = entry.get('description', '')
            series.unit = entry.get('unit', '')
            series.source_name = entry.get('source_name', '')
            series.sort_order = entry.get('sort_order', 0)
            series.region = entry.get('region', 'US')
            series.frequency = entry.get('frequency', 'daily')
            series.is_derived = entry.get('is_derived', False)
            series.transformation = entry.get('transformation', 'level')
            series.fred_code = entry.get('fred_code', '') or None
            series.yfinance_symbol = entry.get('yfinance_symbol', '') or None
            continue
        series = EconomicSeries(
            code=code,
            name=entry['name'],
            category=entry['category'],
            description=entry.get('description', ''),
            unit=entry.get('unit', ''),
            source_name=entry.get('source_name', ''),
            sort_order=entry.get('sort_order', 0),
            region=entry.get('region', 'US'),
            frequency=entry.get('frequency', 'daily'),
            is_derived=entry.get('is_derived', False),
            transformation=entry.get('transformation', 'level'),
            fred_code=entry.get('fred_code', '') or None,
            yfinance_symbol=entry.get('yfinance_symbol', '') or None,
        )
        db.session.add(series)

    if EconomicEvent.query.count() == 0:
        for slug, title, category, days, description, source_name in EVENT_SEED:
            db.session.add(EconomicEvent(
                slug=slug,
                title=title,
                category=category,
                event_at=now + timedelta(days=days),
                description=description,
                source_name=source_name,
            ))

    existing_job_keys = {
        (j.provider, j.series_code) for j in EconomicFetchJob.query.all()
    }
    for entry in JOB_SEED:
        key = (entry['provider'], entry.get('series_code', ''))
        if key in existing_job_keys:
            continue
        db.session.add(EconomicFetchJob(
            name=entry['name'],
            provider=entry['provider'],
            series_code=entry.get('series_code'),
            schedule_type=entry.get('schedule_type', 'daily'),
            interval_minutes=entry.get('interval_minutes', 1440),
            daily_time=entry.get('daily_time', '08:00'),
            is_active=entry.get('is_active', True),
            next_run_at=now + timedelta(minutes=5),
            last_status='seeded',
            last_message='Seeded. Will be picked up by scheduler.',
            derived_sources=entry.get('derived_sources'),
            derived_op=entry.get('derived_op'),
            yfinance_symbol=entry.get('yfinance_symbol'),
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
        description='台灣加權股價指數期貨近月合約前一交易日收盤價',
        unit='點',
        source_name='TAIFEX',
        sort_order=24,
        region='TW',
        frequency='daily',
        transformation='level',
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


def classify_temperature(code, value):
    rule = TEMPERATURE_RULES.get(code)
    if not rule or value is None:
        return None
    for limit, label, tone in rule['bands']:
        if value <= limit:
            return {
                'label': label,
                'tone': tone,
                'benchmark': rule['benchmark'],
            }
    return None


def summarize_temperature(cards):
    scored = [card['temperature'] for card in cards if card.get('temperature')]
    if not scored:
        return None
    score = sum(TEMPERATURE_WEIGHTS[item['tone']] for item in scored) / len(scored)
    if score <= -1.2:
        label, tone = '整體過冷', 'cold'
    elif score < -0.35:
        label, tone = '整體偏冷', 'cool'
    elif score <= 0.35:
        label, tone = '整體中性', 'neutral'
    elif score < 1.2:
        label, tone = '整體偏熱', 'warm'
    else:
        label, tone = '整體過熱', 'hot'
    counts = {tone_key: 0 for tone_key in TEMPERATURE_WEIGHTS}
    for item in scored:
        counts[item['tone']] += 1
    return {
        'label': label,
        'tone': tone,
        'score': round(score, 2),
        'count': len(scored),
        'counts': counts,
    }


def dashboard_cards():
    cards = []
    series_list = EconomicSeries.query.order_by(EconomicSeries.category, EconomicSeries.sort_order, EconomicSeries.id).all()
    for series in series_list:
        obs = latest_observation(series.id)
        has_data = obs is not None and obs.value not in (None, 0)
        value = float(obs.value) if (obs and obs.value is not None) else None
        cards.append({
            'series': series,
            'observation': obs,
            'value': value,
            'previous_value': float(obs.previous_value) if (obs and obs.previous_value is not None) else None,
            'has_data': has_data,
            'temperature': classify_temperature(series.code, value) if has_data else None,
        })
    return cards


@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})


@app.route('/api/summary')
def api_summary():
    ensure_schema_and_seed()
    cards = dashboard_cards()
    return jsonify({
        'temperature_summary': summarize_temperature(cards),
        'items': [{
            'code': card['series'].code,
            'name': card['series'].name,
            'category': card['series'].category,
            'value': card['value'],
            'unit': card['series'].unit,
            'change_label': card['observation'].change_label if card['observation'] else None,
            'status_label': card['observation'].status_label if card['observation'] else None,
            'observed_at': card['observation'].observed_at.isoformat() if card['observation'] else None,
            'source_name': card['series'].source_name,
            'has_data': card['has_data'],
            'temperature': card['temperature'],
        } for card in cards]
    })


@app.route('/api/agent/dashboard')
def api_agent_dashboard():
    ensure_schema_and_seed()
    cards = dashboard_cards()
    now = datetime.utcnow()

    categories_payload = {}
    for card in cards:
        category = card['series'].category or '未分類'
        categories_payload.setdefault(category, []).append({
            'code': card['series'].code,
            'name': card['series'].name,
            'description': card['series'].description or '',
            'unit': card['series'].unit or '',
            'source_name': card['series'].source_name or '',
            'value': card['value'],
            'previous_value': card['previous_value'],
            'change_label': card['observation'].change_label if card['observation'] else None,
            'status_label': card['observation'].status_label if card['observation'] else None,
            'observed_at': card['observation'].observed_at.isoformat() if card['observation'] else None,
            'has_data': card['has_data'],
            'temperature': card['temperature'],
        })

    return jsonify({
        'generated_at': now.isoformat() + 'Z',
        'note': '此 API 提供給 AI Agent 一次讀取所有 dashboard 指標；has_data=false 表示尚未抓到資料。',
        'temperature_summary': summarize_temperature(cards),
        'categories': categories_payload,
        'items': [{
            'code': card['series'].code,
            'name': card['series'].name,
            'category': card['series'].category,
            'value': card['value'],
            'previous_value': card['previous_value'],
            'unit': card['series'].unit,
            'change_label': card['observation'].change_label if card['observation'] else None,
            'status_label': card['observation'].status_label if card['observation'] else None,
            'observed_at': card['observation'].observed_at.isoformat() if card['observation'] else None,
            'source_name': card['series'].source_name,
            'has_data': card['has_data'],
            'temperature': card['temperature'],
        } for card in cards],
    })


@app.route('/api/txf_price', methods=['GET'])
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


@app.route('/api/ingest/<code>', methods=['POST'])
def api_ingest_series(code):
    ensure_schema_and_seed()
    if not txf_authorized():
        return jsonify({'error': 'Unauthorized'}), 401

    series = EconomicSeries.query.filter_by(code=code).first()
    if not series:
        return jsonify({'error': f'series {code} not found'}), 404

    payload = txf_payload()
    raw_value = payload.get('value', payload.get('price'))
    if raw_value in (None, ''):
        return jsonify({'error': 'value is required'}), 400

    try:
        value = Decimal(str(raw_value))
    except InvalidOperation:
        return jsonify({'error': 'value must be numeric'}), 400

    observed_at = parse_observed_at(payload.get('observed_at') or payload.get('timestamp'))
    if not observed_at:
        return jsonify({'error': 'observed_at must be ISO datetime'}), 400

    latest = latest_observation(series.id)
    previous_value = Decimal(latest.value) if latest else None
    status_label = (payload.get('status_label') or '').strip()
    change_label = (payload.get('change_label') or '').strip()
    if not status_label:
        if previous_value is None or value == previous_value:
            status_label = 'flat'
        elif value > previous_value:
            status_label = 'up'
        else:
            status_label = 'down'
    if not change_label:
        if previous_value is None:
            change_label = '手動上報'
        elif value == previous_value:
            change_label = '持平'
        elif value > previous_value:
            change_label = f'+{value - previous_value}'
        else:
            change_label = f'-{previous_value - value}'

    source_name = payload.get('source') or payload.get('source_name')
    if source_name:
        series.source_name = str(source_name).strip()[:120]
    series.updated_at = datetime.utcnow()

    observation = EconomicObservation(
        series_id=series.id,
        observed_at=observed_at,
        value=value,
        previous_value=previous_value,
        change_label=change_label[:40],
        status_label=status_label[:20],
    )
    db.session.add(observation)
    db.session.commit()

    return jsonify({
        'status': 'created',
        'item': {
            'code': series.code,
            'name': series.name,
            'value': float(observation.value),
            'previous_value': float(observation.previous_value) if observation.previous_value is not None else None,
            'unit': series.unit,
            'change_label': observation.change_label,
            'status_label': observation.status_label,
            'observed_at': observation.observed_at.isoformat(),
            'source_name': series.source_name,
        },
    }), 201


def scheduler_status_rows():
    jobs = EconomicFetchJob.query.order_by(
        EconomicFetchJob.is_active.desc(),
        EconomicFetchJob.provider,
        EconomicFetchJob.name,
    ).all()
    runs = EconomicFetchRun.query.order_by(
        EconomicFetchRun.started_at.desc()
    ).limit(200).all()
    latest_by_job = {}
    for run in runs:
        latest_by_job.setdefault(run.job_id, run)

    rows = []
    for job in jobs:
        latest_run = latest_by_job.get(job.id)
        rows.append({
            'job': job,
            'latest_run': latest_run,
            'status': job.last_status or (latest_run.status if latest_run else 'seeded'),
            'message': job.last_message or (latest_run.message if latest_run else ''),
        })
    return rows, runs[:50]


@app.route('/scheduler')
def scheduler_status():
    ensure_schema_and_seed()
    rows, recent_runs = scheduler_status_rows()
    counts = {
        'total': len(rows),
        'active': sum(1 for row in rows if row['job'].is_active),
        'success': sum(1 for row in rows if row['status'] == 'success'),
        'error': sum(1 for row in rows if row['status'] == 'error'),
        'pending': sum(1 for row in rows if row['status'] not in ('success', 'error')),
    }
    return render_template(
        'scheduler.html',
        rows=rows,
        recent_runs=recent_runs,
        counts=counts,
        now=datetime.utcnow(),
    )


@app.route('/')
def index():
    ensure_schema_and_seed()
    cards = dashboard_cards()
    temperature_summary = summarize_temperature(cards)
    categories = []
    for card in cards:
        if card['series'].category not in categories:
            categories.append(card['series'].category)
    events = EconomicEvent.query.order_by(EconomicEvent.event_at).limit(8).all()
    observations_with_time = [c['observation'].observed_at for c in cards if c['observation']]
    updated_at = max(observations_with_time, default=None)
    return render_template('index.html', cards=cards, categories=categories,
        events=events, updated_at=updated_at, temperature_summary=temperature_summary)
