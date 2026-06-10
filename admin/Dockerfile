FROM python:3.11-slim

# SQL Server ODBC driver(給 pyodbc 用)
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg apt-transport-https \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list | tee /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=app.py
EXPOSE 5002

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5002", "app:app"]
