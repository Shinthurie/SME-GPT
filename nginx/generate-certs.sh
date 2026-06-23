#!/bin/sh
mkdir -p "$(dirname "$0")/certs"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$(dirname "$0")/certs/selfsigned.key" \
  -out    "$(dirname "$0")/certs/selfsigned.crt" \
  -subj   "/C=LK/ST=Western/L=Colombo/O=SME-GPT/CN=localhost"
echo "Self-signed cert generated in nginx/certs/ — for local dev only."
