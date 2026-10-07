import urllib.request
import json

req = urllib.request.Request(
    'http://localhost:8001/api/v1/credentials/validate',
    data=json.dumps({'credential_secret': 'uecp_cred_tJlEbZNIUUHzhlE1p_1p8zW5Mvim3_aGPk9iZ2fNsCE', 'action': 'ai.chat'}).encode(),
    headers={
        'Content-Type': 'application/json',
        'X-Application-Key': 'uecp_niTwfr1VvGuqoRh-z9crAv9Wjm1Vbw1gbqGVAVLg06w',
        'X-Credential-ID': 'f9383fd2-4970-4a8e-90dc-3cc9663771b4'
    }
)
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        print('Validation status:', resp.status, '| allowed:', data.get('allowed'), '| effective_status:', data.get('status'))
except urllib.error.HTTPError as e:
    print('Failed with HTTP', e.code, e.read().decode())
