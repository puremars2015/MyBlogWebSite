# MyBlogWebSite

> 生活風格部落格 + 嚴選選物商店 + 巨集經濟儀表板
> 容器化、單一 docker-compose 一鍵啟動

這是一個多服務容器化專案,目前由四個 Flask 應用、Nginx 反向代理、SQL Server 2022 Express,以及一支排程 worker 組成。詳細的內容規劃、品牌定位與 Schema 請見 [`內容規劃.md`](內容規劃.md);架構、Container 規劃與路由請見 [`網站架構.md`](網站架構.md)。

## 服務總覽

| 服務 | 路徑 | Port(對外) | 用途 |
|------|------|-----------|------|
| Cloudflare Tunnel | - | - | 對外 HTTPS 入口,免開主機 port |
| Nginx | - | - | 路徑基底反向代理(內部,只接 cloudflared) |
| Blog  | `/blog/*` | `5000` | 部落格文章 |
| Shop  | `/shop/*` | `5001` | 選物商城 |
| Admin | `/admin/*` | `5002` | 後台管理 |
| Dashboard | `/` & `/dashboard` | `5003` | 巨集經濟儀表板 |
| Dashboard Scheduler | - | - | 自動抓取經濟資料 |
| MSSQL | - | `1433` | 資料庫 |

Dashboard 也額外提供:
- `/scheduler` — 排程狀態監控頁
- `/api/agent/dashboard` — 給 AI Agent 一次讀所有指標

對外入口由 `cloudflared` 建立的 Cloudflare Tunnel 提供,免開主機 80/443 port。

## 快速開始

### 1. 準備環境變數

```bash
cp .env-sample .env
# 編輯 .env,至少設定 SA_PASSWORD 與 SESSION_SECRET
# 若要讓 dashboard 抓到 FRED 資料,請填 FRED_API_KEY
```

`.env` 範例:

```
SA_PASSWORD=YourStrong!Passw0rd
SESSION_SECRET=replace-with-random
FRED_API_KEY=
```

### 2. 啟動整組服務

```bash
docker compose up -d --build
```

第一次啟動時 SQL Server 會自動執行 `init-scripts/init.sql` 建表 + 塞示範資料。

### 3. 確認服務

```bash
curl http://localhost/blog/posts          # 透過 Nginx 進入 Blog
curl http://localhost/shop/products       # 透過 Nginx 進入 Shop
curl http://localhost:5000/health         # 直接打 Blog
curl http://localhost:5003/health         # 直接打 Dashboard
curl http://localhost:5003/scheduler      # 排程狀態頁
curl http://localhost:5003/api/agent/dashboard | jq .   # 給 AI Agent
```

## 開發常用指令

```bash
# 重新建立並重啟 dashboard(包含 scheduler)
docker compose up -d --build --force-recreate dashboard dashboard-scheduler

# 觸發所有 dashboard 排程立即跑一次
docker compose exec -T dashboard python -c "from datetime import datetime; \
  from app import app, db, EconomicFetchJob; \
  ctx=app.app_context(); ctx.push(); \
  EconomicFetchJob.query.update({'next_run_at': datetime.utcnow()}, synchronize_session=False); \
  db.session.commit()"

# 看排程 log
docker compose logs --tail=200 dashboard-scheduler

# 停掉所有服務
docker compose down
```

## 結構

```
MyBlogWebSite/
├── docker-compose.yml
├── .env / .env-sample
├── README.md
├── 內容規劃.md
├── 網站架構.md
├── nginx/                # 反向代理
├── cloudflared/          # Cloudflare Tunnel 對外入口
├── blog/                 # 5000
├── shop/                 # 5001
├── admin/                # 5002
├── dashboard/            # 5003 + scheduler
│   ├── providers/        # 各資料來源
│   ├── templates/        # 首頁 + scheduler 狀態頁
│   ├── static/
│   ├── app.py            # Flask API + 頁面
│   └── scheduler.py      # 排程 worker
├── db/                   # SQL Server image 客製化
└── init-scripts/         # 第一次啟動自動執行的 SQL
```

## Cloudflare Tunnel(對外 HTTPS 入口)

`cloudflared` 容器是唯一對外入口,連進內部 `nginx:80`。

### 模式 A:Named Tunnel(正式用)

1. 在 [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) 建立一個 Tunnel
2. 把要對外的子網域(`trading.thetainformation.com` / `blog.thetainformation.com` / `shop.thetainformation.com` / `admin.thetainformation.com`)指到這個 tunnel
3. 複製 tunnel token,貼到 `.env`:
   ```
   TUNNEL_TOKEN=eyJhIjoi...
   ```
4. 把 `docker-compose.yml` 中 `cloudflared` 的 `command` 改成 `["tunnel", "run", "--token", "${TUNNEL_TOKEN}"]`
5. `docker compose up -d --build cloudflared`

> 主站網域是 `trading.thetainformation.com`(dashboard,因為它顯示交易指標)。其他服務用子網域。nginx 預設 server 已設為 fallback 到 dashboard,quick tunnel 模式(*.trycloudflare.com) 也能直接用。

### 模式 B:Quick Tunnel(本機測試用)

留白 `TUNNEL_TOKEN`,`docker compose up -d --build cloudflared`,啟動後從 `docker compose logs cloudflared` 抓 `*.trycloudflare.com` 臨時網址。**僅供本機測試,每次重啟網址會變**。

## Dashboard 重點

- **完全自動化**:不再使用 mock 資料,每個指標都由排程從公開 API 抓取(FRED、TWSE、TAIFEX、CBOE、CNN、yfinance)。
- **冷熱判讀**:每個指標獨立門檻 + 整體加權 score,首頁 hero 顯示「目前整體偏冷 / 中性 / 偏熱」,每張卡片顯示該指標的 tone 與比較基準。
- **AI Agent 友善**:`GET /api/agent/dashboard` 一次吐 `categories` + `items` + `temperature_summary`,`has_data=false` 表示尚未抓到資料(不該被當作實際指標)。
- **狀態透明**:`GET /scheduler` 列出所有 jobs 的成功/錯誤/下次執行時間,並列出最近 50 筆 `economic_fetch_runs` 與錯誤訊息。
- **手動 fallback**:`POST /api/ingest/<code>` 可手動餵入任何序列的觀測值(例如目前還沒接公開來源的台灣官方總經)。

詳細指標清單與門檻見 [`內容規劃.md` 第五節](內容規劃.md#五dashboard-巨集儀表板)。

## 部署注意事項

- **正式對外走 Cloudflare Tunnel**,nginx 不再對外 expose 80/443。`blog` / `shop` / `admin` / `dashboard` 的 `ports:` 段落是開發期本機直連用,正式上線可以拿掉。
- `SA_PASSWORD` 與 `SESSION_SECRET` 請改用 secrets 管理。
- `FRED_API_KEY` 有 rate limit,正式部署前請評估流量。
- `yfinance` provider 偶發會被 Yahoo rate limit 影響,排程 log 看到 `YFRateLimitError` 是已知狀況,監控重點為失敗頻率。

## 維護文件

- [`內容規劃.md`](內容規劃.md) — 品牌、內容策略、Schema、CRUD API、儀表板規則
- [`網站架構.md`](網站架構.md) — Container、路由、環境變數、部署、指令
