#!/bin/bash
# SeSAC Admin Page 기동/정지 스크립트 (부트캠프 VM)
# 사용법:
#   ~/admin_page/run_admin.sh          → 빌드+기동 (기존 컨테이너 있으면 교체)
#   ~/admin_page/run_admin.sh recreate → 재생성만 (빌드 skip, 빠름)
#   ~/admin_page/run_admin.sh stop     → 중지
#   ~/admin_page/run_admin.sh status   → 상태 + OCI 마운트 자동 점검
#   ~/admin_page/run_admin.sh log      → 로그 tail
#
# ✓ docker-compose.override.yml (OCI 마운트) 가 자동 병합되므로
#   pull 받은 직후에도 이 스크립트 한 번이면 됨.

set -a
source "$(dirname "$0")/.env"
set +a

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

healthcheck() {
    # OCI 마운트가 살아있는지 컨테이너 내부에서 직접 확인
    if docker exec sesac-admin-page ls /root/.oci/config >/dev/null 2>&1; then
        echo "✅ OCI config 마운트 정상"
    else
        echo "❌ OCI config 마운트 없음! docker-compose.override.yml 확인 후 재생성:"
        echo "   docker compose up -d --force-recreate"
        return 1
    fi
}

case "$1" in
    stop)
        docker compose down && echo "중지 완료" ;;
    status)
        docker ps --filter name=sesac-admin-page --format '상태: {{.Status}}' || true
        curl -s -o /dev/null -w "HTTP: %{http_code}\n" http://localhost:8501/static/style.css || echo "HTTP: 응답 없음"
        healthcheck
        ;;
    recreate)
        docker compose up -d --force-recreate && sleep 2 && healthcheck && \
        curl -s -o /dev/null -w "HTTP: %{http_code}\n" http://localhost:8501/static/style.css ;;
    log)
        docker logs sesac-admin-page --tail 30 -f ;;
    *)
        docker compose up -d --build && sleep 2 && healthcheck && \
        curl -s -o /dev/null -w "HTTP: %{http_code}\n" http://localhost:8501/static/style.css ;;
esac