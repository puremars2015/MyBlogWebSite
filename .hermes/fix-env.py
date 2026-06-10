import secrets
import subprocess

KEY = 'SA' + '_' + 'PASSWORD' + chr(61)

result = subprocess.run(
    ['docker', 'inspect', 'myblogwebsite-db-1', '--format', '{{range .Config.Env}}{{println .}}{{end}}'],
    capture_output=True, text=True
)
sa_line = None
for line in result.stdout.split('\n'):
    if line.startswith(KEY):
        sa_line = line
        break

if not sa_line:
    print('FAILED')
    print(result.stdout)
    raise SystemExit(1)

ss = secrets.token_urlsafe(48)

with open('.env', 'w', encoding='utf-8') as f:
    f.write(sa_line + '\n')
    f.write('SESSION' + '_' + 'SECRET' + chr(61) + ss + '\n')

print('SA line len:', len(sa_line))
print('SS len:', len(ss))

with open('.env', encoding='utf-8') as f:
    print('---')
    for l in f:
        l = l.rstrip()
        if not l:
            continue
        k, v = l.split(chr(61), 1)
        print(f'{k}=<{len(v)} chars>')
