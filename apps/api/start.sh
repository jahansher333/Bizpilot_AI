#!/bin/sh
# Production entrypoint for the BizPilot API container.
#
# Rate limits key on the client IP that uvicorn derives from X-Forwarded-For. Trusting every
# proxy ("*") makes uvicorn take the left-most X-Forwarded-For entry, which the client writes,
# so any caller could pick its own IP. Only the platform ingress may be trusted: set
# FORWARDED_ALLOW_IPS to its address or CIDR (comma-separated for several).
set -eu

case "${FORWARDED_ALLOW_IPS:-}" in
  "")
    echo "FORWARDED_ALLOW_IPS is required: set it to the ingress proxy address or CIDR." >&2
    exit 64
    ;;
  *"*"*)
    echo "FORWARDED_ALLOW_IPS must not contain \"*\": list only the ingress proxy address or CIDR." >&2
    exit 64
    ;;
esac

exec uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000 \
  --proxy-headers --forwarded-allow-ips "$FORWARDED_ALLOW_IPS" --no-server-header
