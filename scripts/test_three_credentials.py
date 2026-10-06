import urllib.request
import json

def post(url, headers, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

app_key = 'uecp_KJ2cFJ4N6shuAY1xq2-BrLHw56q49Rv9I75guGVOsf8'

creds = [
    ('Primary', 'b53f18de-4546-4364-9b3c-5ff410dab2d8', 'uecp_cred_s-p3EIGFCUpbv8usqcFqQuqWgl2wrJKkKcv2ZUrDyZo'),
    ('Secondary', '525fd565-8d7c-4648-a4db-2db94cc6d5fa', 'uecp_cred_exys1oxszozn-odvZb_waUfV5S7d5ALYP5imumV9hTs'),
    ('Worker', 'd3d0dece-5080-4c0d-a081-204139059739', 'uecp_cred_THCN54mOjCpXuFBUxHpvoYNs6XX348d6-i1-PTcR6rw'),
]

print("=== TESTING 3 CREDENTIALS VALIDATION ===")
for label, cid, secret in creds:
    headers = {
        'Content-Type': 'application/json',
        'X-Application-Key': app_key,
        'X-Credential-ID': cid
    }
    status, body = post('http://localhost:8001/api/v1/credentials/validate', headers, {'credential_secret': secret, 'action': 'ai.chat'})
    print(f'{label} -> HTTP {status} | allowed: {body.get("allowed")} | status: {body.get("status")}')
