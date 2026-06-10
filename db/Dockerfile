FROM mcr.microsoft.com/mssql/server:2022-latest

# 官方 mssql/server image 不含 mssql-tools(sqlcmd 客戶端),
# 自己裝一份才能在 healthcheck 裡跑 SELECT 1,也能在 entrypoint 跑 init scripts。
# 官方 image 是 Ubuntu 22.04(不是 Debian),用對應的 prod.list。
USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        apt-transport-https \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/ubuntu/22.04/prod.list \
        | tee /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends mssql-tools18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 自訂 entrypoint:
# - 啟動 SQL Server
# - 第一次啟動時跑 /docker-entrypoint-initdb.d/ 的 .sql/.sh(用 -f 65001 處理 UTF-8)
# - 把 SQL Server 帶回前景
# 預設 CMD 沿用 base image 的 /opt/mssql/bin/sqlservr
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER mssql

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/opt/mssql/bin/sqlservr"]
