#!/usr/bin/env sh
set -eu

KUBECONFIG_PATH="${KUBECONFIG_PATH:-$HOME/.kube/configs/workload-1-k3s.yaml}"
NAMESPACE="${NAMESPACE:-shisha-guid}"
SERVICE="${SERVICE:-postgres}"
LOCAL_PORT="${LOCAL_PORT:-15432}"
REMOTE_PORT="${REMOTE_PORT:-5432}"

echo "Forwarding ${NAMESPACE}/${SERVICE}:${REMOTE_PORT} to 127.0.0.1:${LOCAL_PORT}"
echo "Keep this process running while the local backend is running."

exec kubectl --kubeconfig "$KUBECONFIG_PATH" \
  -n "$NAMESPACE" port-forward "svc/${SERVICE}" "${LOCAL_PORT}:${REMOTE_PORT}"
