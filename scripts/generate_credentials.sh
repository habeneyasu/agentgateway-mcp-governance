#!/usr/bin/env bash
# Generate demo credentials for the gateway's JWT authentication.
#
# Writes to gateway/credentials/ (git-ignored):
#   signing-key.pem            RSA private key (stays on this machine; never mounted)
#   jwks.json                  public key set, mounted read-only into agentgateway
#   gateway.env                SESSION_KEY (AES-256-GCM) that encrypts MCP session IDs
#   tokens/analyst.jwt         valid token, role=analyst
#   tokens/auditor.jwt         valid token, role=auditor
#   tokens/guest.jwt           valid token, role=guest (no tool access)
#   tokens/ratelimit.jwt       valid token, own rate-limit bucket (rate-limit tests)
#   tokens/expired.jwt         correct signature, expired        (negative test)
#   tokens/wrong-issuer.jwt    correct signature, wrong iss       (negative test)
#   tokens/wrong-audience.jwt  correct signature, wrong aud       (negative test)
#   tokens/bad-signature.jwt   signed by an untrusted key         (negative test)
#
# Re-running replaces the key; restart the gateway afterwards
# (docker compose restart agentgateway).
#
# Requires: openssl, basenc, xxd.
set -euo pipefail

ISSUER="agentgateway-mcp-governance"
AUDIENCE="mcp-gateway"
KID="mcp-governance-demo-1"
TTL_SECONDS="${TOKEN_TTL_SECONDS:-86400}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/gateway/credentials"
TOKENS="$OUT/tokens"

for cmd in openssl basenc xxd; do
  command -v "$cmd" >/dev/null || { echo "error: '$cmd' is required" >&2; exit 1; }
done

umask 077
rm -rf "$OUT"
mkdir -p "$TOKENS"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

b64url() { basenc --base64url -w0 | tr -d '='; }

# Signing key and an untrusted key for the bad-signature token.
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$OUT/signing-key.pem" 2>/dev/null
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$TMP/untrusted.pem" 2>/dev/null

# JWKS: modulus from the key; exponent is 65537 (AQAB).
N="$(openssl rsa -in "$OUT/signing-key.pem" -noout -modulus | cut -d= -f2 | xxd -r -p | b64url)"
cat > "$OUT/jwks.json" <<EOF
{"keys":[{"kty":"RSA","use":"sig","alg":"RS256","kid":"$KID","n":"$N","e":"AQAB"}]}
EOF
chmod 0644 "$OUT/jwks.json"   # read by the gateway's non-root user

# Key for encrypting MCP session IDs. Without it, agentgateway falls back to
# unencrypted session IDs because its config file is mounted read-only.
printf 'SESSION_KEY=%s\n' "$(openssl rand -hex 32)" > "$OUT/gateway.env"

# sign_jwt <key.pem> <payload-json>
sign_jwt() {
  local header payload sig
  header="$(printf '{"alg":"RS256","typ":"JWT","kid":"%s"}' "$KID" | b64url)"
  payload="$(printf '%s' "$2" | b64url)"
  sig="$(printf '%s.%s' "$header" "$payload" | openssl dgst -sha256 -sign "$1" -binary | b64url)"
  printf '%s.%s.%s\n' "$header" "$payload" "$sig"
}

# claims <sub> <role> <iss> <aud> <iat> <exp>
claims() {
  printf '{"iss":"%s","aud":"%s","sub":"%s","role":"%s","iat":%d,"exp":%d}' "$3" "$4" "$1" "$2" "$5" "$6"
}

NOW="$(date +%s)"
EXP=$((NOW + TTL_SECONDS))
KEY="$OUT/signing-key.pem"

sign_jwt "$KEY" "$(claims analyst-1 analyst "$ISSUER" "$AUDIENCE" "$NOW" "$EXP")" > "$TOKENS/analyst.jwt"
sign_jwt "$KEY" "$(claims auditor-1 auditor "$ISSUER" "$AUDIENCE" "$NOW" "$EXP")" > "$TOKENS/auditor.jwt"
sign_jwt "$KEY" "$(claims guest-1 guest "$ISSUER" "$AUDIENCE" "$NOW" "$EXP")" > "$TOKENS/guest.jwt"
sign_jwt "$KEY" "$(claims rate-limit-test analyst "$ISSUER" "$AUDIENCE" "$NOW" "$EXP")" > "$TOKENS/ratelimit.jwt"
sign_jwt "$KEY" "$(claims analyst-1 analyst "$ISSUER" "$AUDIENCE" $((NOW - 7200)) $((NOW - 3600)))" > "$TOKENS/expired.jwt"
sign_jwt "$KEY" "$(claims analyst-1 analyst "someone-else" "$AUDIENCE" "$NOW" "$EXP")" > "$TOKENS/wrong-issuer.jwt"
sign_jwt "$KEY" "$(claims analyst-1 analyst "$ISSUER" "another-service" "$NOW" "$EXP")" > "$TOKENS/wrong-audience.jwt"
sign_jwt "$TMP/untrusted.pem" "$(claims analyst-1 analyst "$ISSUER" "$AUDIENCE" "$NOW" "$EXP")" > "$TOKENS/bad-signature.jwt"

echo "Credentials written to ${OUT#"$ROOT"/}/ (tokens valid for ${TTL_SECONDS}s)."
echo "Example: python mcp-client/client.py --token \"\$(cat gateway/credentials/tokens/analyst.jwt)\" demo"
