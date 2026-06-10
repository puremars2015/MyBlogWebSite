import sys
sys.path.insert(0, 'admin')
from app import app
import logging
logging.disable(logging.CRITICAL)

c = app.test_client()

# 1. GET / 應該 302 到 /login
r = c.get('/')
print(f'1) GET /                       -> {r.status_code}  Location: {r.headers.get("Location", "")}')

# 2. GET /login 應該 200
r = c.get('/login')
print(f'2) GET /login                  -> {r.status_code}  has "後台管理" in body: {"後台管理" in r.get_data(as_text=True)}')

# 3. POST /login 錯誤密碼
r = c.post('/login', data={'username': 'admin', 'password': 'wrong'})
print(f'3) POST /login wrong            -> {r.status_code}')

# 4. POST /login 正確
r = c.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=False)
print(f'4) POST /login admin/admin123   -> {r.status_code}  Location: {r.headers.get("Location", "")}')

# 5. GET / 登入後應該 200
r = c.get('/')
print(f'5) GET / after login            -> {r.status_code}  has "儀表板" in body: {"儀表板" in r.get_data(as_text=True)}')

# 6. GET /admins
r = c.get('/admins')
print(f'6) GET /admins                  -> {r.status_code}  has "admin" in body: {"admin" in r.get_data(as_text=True)}')

# 7. GET /posts
r = c.get('/posts')
print(f'7) GET /posts                   -> {r.status_code}')

# 8. GET /products
r = c.get('/products')
print(f'8) GET /products                -> {r.status_code}')

# 9. GET /orders
r = c.get('/orders')
print(f'9) GET /orders                  -> {r.status_code}')

# 10. GET /members
r = c.get('/members')
print(f'10) GET /members                -> {r.status_code}')

# 11. GET /health (no auth)
r = c.get('/health')
print(f'11) GET /health                 -> {r.status_code}  body: {r.get_json()}')

# 12. logout
r = c.get('/logout', follow_redirects=False)
print(f'12) GET /logout                 -> {r.status_code}  Location: {r.headers.get("Location", "")}')

# 13. After logout, / should redirect again
r = c.get('/')
print(f'13) GET / after logout          -> {r.status_code}  Location: {r.headers.get("Location", "")}')
