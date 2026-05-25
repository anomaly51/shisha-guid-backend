#!/usr/bin/env sh
set -eu

KUBECONFIG_PATH="${KUBECONFIG_PATH:-$HOME/.kube/configs/workload-1-k3s.yaml}"
NAMESPACE="${NAMESPACE:-shisha-guid}"
SECRET_NAME="${SECRET_NAME:-postgres-secret}"
LOCAL_PORT="${LOCAL_PORT:-15432}"
ENV_FILE="${ENV_FILE:-.env}"
DB_NAME="${DB_NAME:-shishadb}"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-host.docker.internal}"

env_value() {
  key="$1"
  fallback="$2"
  if [ -f "$ENV_FILE" ]; then
    value="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true)"
    if [ -n "$value" ]; then
      printf '%s' "$value"
      return
    fi
  fi
  printf '%s' "$fallback"
}

password="$(kubectl --kubeconfig "$KUBECONFIG_PATH" \
  -n "$NAMESPACE" get secret "$SECRET_NAME" \
  -o jsonpath='{.data.password}' | base64 -d)"

secret_key="$(env_value SECRET_KEY change-me)"
google_client_id="$(env_value GOOGLE_CLIENT_ID your_google_client_id_here)"
google_client_secret="$(env_value GOOGLE_CLIENT_SECRET your_google_client_secret_here)"
minio_public_url="$(env_value MINIO_PUBLIC_URL http://localhost:9000/shisha-guid)"
openrouter_model="$(env_value OPENROUTER_MODEL sao10k/l3-lunaris-8b)"

cat > "$ENV_FILE" <<EOF
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${password}@${DB_HOST}:${LOCAL_PORT}/${DB_NAME}
SECRET_KEY=${secret_key}
GOOGLE_CLIENT_ID=${google_client_id}
GOOGLE_CLIENT_SECRET=${google_client_secret}
MINIO_PUBLIC_URL=${minio_public_url}
OPENROUTER_MODEL=${openrouter_model}
EOF

chmod 600 "$ENV_FILE"
echo "Wrote ${ENV_FILE} for Docker Compose remote database access."
echo "Run ./scripts/remote-db-port-forward.sh before docker compose up."
