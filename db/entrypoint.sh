#!/bin/bash
# 自訂 entrypoint:啟動 SQL Server,第一次啟動時執行 init scripts
# 為什麼要自己寫:MSSQL 官方 image 預設**不會**自動跑 /docker-entrypoint-initdb.d/ 的 .sql
# (跟 postgres / mysql image 不一樣,文件沒寫但踩過才會知道)
#
# 行為:
# 1. 在背景啟動 sqlservr
# 2. 等 SQL Server 接受連線(最多 90 秒)
# 3. 檢查 BlogShopDB 是否已存在 → 判斷是不是第一次啟動
# 4. 第一次啟動就跑 /docker-entrypoint-initdb.d/ 裡所有 .sql / .sh
# 5. 把 sqlservr 帶回前景,等它結束
#
# 注意:sqlcmd 預設用 CP437 讀檔,中文會變問號 — 必須加 -f 65001(UTF-8)

set -e

SQLCMD="/opt/mssql-tools18/bin/sqlcmd"
SQLSERVR="/opt/mssql/bin/sqlservr"

# 啟動 SQL Server 在背景
$SQLSERVR &
SQL_PID=$!

# 設 trap,容器被終止時把訊號轉給 SQL Server
trap "kill -TERM $SQL_PID 2>/dev/null || true" SIGTERM SIGINT

# 等 SQL Server 接受連線
echo "[entrypoint] 等待 SQL Server 啟動..."
READY=false
for i in {1..90}; do
    if $SQLCMD -S localhost -U sa -P "${SA_PASSWORD}" -Q "SELECT 1" -C -No > /dev/null 2>&1; then
        echo "[entrypoint] SQL Server 已就緒 (等了 ${i} 秒)"
        READY=true
        break
    fi
    sleep 1
done

if [ "$READY" != "true" ]; then
    echo "[entrypoint] ERROR: SQL Server 90 秒內沒起來,放棄"
    kill -TERM $SQL_PID 2>/dev/null || true
    exit 1
fi

# 判斷是否第一次啟動:BlogShopDB 不存在 → 跑 init scripts
DB_EXISTS=$($SQLCMD -S localhost -U sa -P "${SA_PASSWORD}" -h -1 -W -C -No \
    -Q "SET NOCOUNT ON; IF DB_ID('BlogShopDB') IS NOT NULL PRINT 'yes' ELSE PRINT 'no'" \
    2>/dev/null | tr -d ' \r\n')

if [ "$DB_EXISTS" = "yes" ]; then
    echo "[entrypoint] BlogShopDB 已存在,跳過 init scripts"
else
    echo "[entrypoint] 第一次啟動,執行 /docker-entrypoint-initdb.d/ 下的 init scripts"
    shopt -s nullglob
    for f in /docker-entrypoint-initdb.d/*; do
        [ -f "$f" ] || continue
        case "$f" in
            *.sql)
                echo "[entrypoint] 執行 SQL: $f"
                # -f 65001 = 告訴 sqlcmd 檔案是 UTF-8 編碼
                $SQLCMD -S localhost -U sa -P "${SA_PASSWORD}" -i "$f" -C -No -f 65001
                ;;
            *.sh)
                echo "[entrypoint] 執行 SH: $f"
                bash "$f"
                ;;
            *)
                echo "[entrypoint] 跳過(不支援的副檔名): $f"
                ;;
        esac
    done
    echo "[entrypoint] init scripts 完成"
fi

# 讓 SQL Server 繼續跑(這會 block 直到 SQL Server 結束)
wait $SQL_PID
