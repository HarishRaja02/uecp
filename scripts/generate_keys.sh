#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$(dirname "$0")/../secrets"
command -v openssl >/dev/null || { echo "OpenSSL is required"; exit 1; }
openssl genrsa -out "$(dirname "$0")/../secrets/jwt_private_key.pem" 3072
openssl rsa -in "$(dirname "$0")/../secrets/jwt_private_key.pem" -pubout -out "$(dirname "$0")/../secrets/jwt_public_key.pem"
echo "JWT keys generated. Never commit secrets/."
