import urllib.request
import json
import base64

def login():
    req = urllib.request.Request(
        'http://localhost:8001/api/v1/auth/login',
        data=json.dumps({'email': 'admin@uecp.local', 'password': 'ChangeThisAdminPassword!2026'}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        return data['access_token']

token = login()
print('Logged in as platform admin')

# Try to create an app with the exact same name as Nanvi (case-insensitive)
req = urllib.request.Request(
    'http://localhost:8001/api/v1/admin/applications',
    data=json.dumps({'name': 'nanvi ai enterprise assistant'}).encode(),
    headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
)
try:
    with urllib.request.urlopen(req) as resp:
        print('Unexpected success:', resp.status)
except urllib.error.HTTPError as e:
    err_body = json.loads(e.read().decode())
    print(f'HTTP {e.code} as expected!')
    print('Error message:', err_body.get('message'))
