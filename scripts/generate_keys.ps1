$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path "$PSScriptRoot\..\secrets" | Out-Null
if (Get-Command openssl -ErrorAction SilentlyContinue) {
    openssl genrsa -out "$PSScriptRoot\..\secrets\jwt_private_key.pem" 3072
    openssl rsa -in "$PSScriptRoot\..\secrets\jwt_private_key.pem" -pubout -out "$PSScriptRoot\..\secrets\jwt_public_key.pem"
} else {
    $python = $null
    $candidates = @(
        (Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"),
        (Join-Path $PSScriptRoot "..\venv\Scripts\python.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { $python = Get-Item $candidate; break }
    }
    if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
    if (-not $python) { throw "OpenSSL or Python is required. Install one and rerun this script." }
    $env:UECP_SECRETS_DIR = (Resolve-Path "$PSScriptRoot\..\secrets").Path
    @'
import os
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

output = Path(os.environ["UECP_SECRETS_DIR"])
key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
(output / "jwt_private_key.pem").write_bytes(key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
))
(output / "jwt_public_key.pem").write_bytes(key.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
))
'@ | & $python.FullName -
    if ($LASTEXITCODE -ne 0) { throw "Python key generation failed." }
    Remove-Item Env:\UECP_SECRETS_DIR
}
Write-Host "JWT keys generated. Never commit secrets/."
