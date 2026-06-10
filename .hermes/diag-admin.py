import subprocess

env = {}
with open(r'C:\Users\user\Documents\MyBlogWebSite\.env', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k] = v
pwd = env.get('SA_PASSWORD', '')
print(f'pwd len: {len(pwd)}')

# 1. 看 admin 資料
print('=== 1. admin 資料 ===')
cmd = [
    'docker', 'exec', '-i', 'myblogwebsite-db-1',
    '/opt/mssql-tools18/bin/sqlcmd',
    '-S', 'localhost', '-U', 'sa', '-P', pwd,
    '-C', '-No', '-f', '65001',
    '-Q', "USE BlogShopDB; SELECT id, username, email, role, is_active, LEFT(password_hash, 40) AS hash_preview, LEN(password_hash) AS hash_len FROM admins;"
]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
print('STDOUT:', r.stdout)
print('STDERR:', r.stderr[:200])

# 2. 用 Python 算 admin123 的 hash,看跟 DB 一不一樣
print()
print('=== 2. 重新算 admin123 hash ===')
from werkzeug.security import generate_password_hash, check_password_hash
fresh = generate_password_hash('admin123', method='pbkdf2:sha256')
print(f'fresh hash: {fresh}')
print(f'fresh len: {len(fresh)}')

# 3. 從 DB 拿 hash 出來驗證
print()
print('=== 3. 從 DB 撈 hash 驗證 ===')
cmd2 = [
    'docker', 'exec', '-i', 'myblogwebsite-db-1',
    '/opt/mssql-tools18/bin/sqlcmd',
    '-S', 'localhost', '-U', 'sa', '-P', pwd,
    '-C', '-No', '-f', '65001',
    '-Q', "USE BlogShopDB; SELECT password_hash FROM admins WHERE username='admin';"
]
r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=10)
# 抓 hash(去掉 "Changed database context" 那行)
lines = r2.stdout.split('\n')
for line in lines:
    line = line.strip()
    if line and 'Changed database' not in line and 'rows affected' not in line and line != 'password_hash' and '----' not in line:
        if line.startswith('pbkdf2:'):
            print(f'DB hash: {line}')
            try:
                ok = check_password_hash(line, 'admin123')
                print(f'check_password_hash(admin123) = {ok}')
            except Exception as e:
                print(f'  check FAILED: {e}')
            break
