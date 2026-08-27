#!/bin/bash
# 최종 상태 점검: 컨테이너, 포트 바인딩, 로그인 페이지, 외부 노출 여부
echo "=== 컨테이너 상태 ==="
docker ps --filter name=sesac --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo
echo "=== admin-page 포트 바인딩 (127.0.0.1 만이어야 함) ==="
ss -tln | grep 8501
echo
echo "=== DB 행 수 (테스트 데이터 정리 확인) ==="
docker exec sesac-admin-page python -c "
from app import db
for s, t in [('SPEECHAPP_USER','APP_USER'),('SPEECHAPP_USER','USER_PROFILE'),('SPEECHAPP_CONTENT','IMAGE_RESOURCE'),('SPEECHAPP_CONTENT','IMAGE_TAG'),('SPEECHAPP_CONTENT','IMAGE_HINT')]:
    r = db.fetch_one(f'SELECT COUNT(*) AS C FROM \"{s}\".\"{t}\"')
    print(f'{s}.{t}: {r[\"C\"]}')"
echo
echo "=== 앱 로그 에러 확인 ==="
docker logs sesac-admin-page 2>&1 | grep -cE 'ERROR|Traceback' || echo "에러 없음"