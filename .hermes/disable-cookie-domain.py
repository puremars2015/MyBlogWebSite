"""把 3 個 app 的 SESSION_COOKIE_DOMAIN 拿掉,讓 Flask 預設(origin-only)"""
import re
for path in [
    r'C:\Users\user\Documents\MyBlogWebSite\admin\app.py',
    r'C:\Users\user\Documents\MyBlogWebSite\blog\app.py',
    r'C:\Users\user\Documents\MyBlogWebSite\shop\app.py',
]:
    with open(path, encoding='utf-8') as f:
        content = f.read()
    new = content.replace(
        "app.config['SESSION_COOKIE_DOMAIN'] = os.environ.get('SESSION_COOKIE_DOMAIN', '.localhost')",
        "# SESSION_COOKIE_DOMAIN 預設不設(讓 Flask 用 origin 比對)\n"
        "# 之前設 .localhost 被某些客戶端拒絕('bad tailmatch domain')。"
        "# 改用 origin-only cookie,代價是會員跨子網域 session 不再共用。\n"
        "# 在正式網域(設 Domain=.yourdomain.com)就完全沒這問題。\n"
        "# app.config['SESSION_COOKIE_DOMAIN'] = os.environ.get('SESSION_COOKIE_DOMAIN', '.localhost')"
    )
    if new != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new)
        print(f'  {path}: updated')
    else:
        print(f'  {path}: no change (line not found exactly)')
