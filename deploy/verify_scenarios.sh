#!/bin/bash
# row_create 3종 시나리오 검증 (부트캠프 VM에서 실행)
BASE=http://localhost:8501
CK=/tmp/ck2.txt

echo "--- 시나리오1: pending 없이 제출 → 거부되어야 함 (행 미생성) ---"
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/create" \
  --data-urlencode 'IMAGE_NAME=시나리오1' -o /dev/null -w "CREATE: %{http_code}\n"

docker exec -i sesac-oracle-db sqlplus -s speechapp_admin/SeT54504adu@localhost:1521/XEPDB1 << SQLEOF
SET LINESIZE 150
SELECT COUNT(*) AS s1_rows FROM speechapp_content.image_resource WHERE image_name='시나리오1';
EXIT
SQLEOF

echo "=== 시나리오2: 이미지 pending 정상 → 성공 + move ==="
R1=$(curl -s -X POST -F 'file=@/tmp/repro.png' $BASE/upload-image)
P1=$(echo "$R1" | grep -o 'tmp/[a-z0-9.]*' | head -1)
echo "pending: $P1"
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/create" \
  --data-urlencode 'IMAGE_NAME=시나리오2검증' \
  --data-urlencode "__pending_image__=$P1" -o /dev/null -w "CREATE: %{http_code}\n"

echo "=== 시나리오3: 이미지+태그 둘 다 ==="
R2=$(curl -s -X POST -F 'file=@/tmp/repro2.tags.json' -F 'kind=tags' $BASE/upload-json)
P2=$(echo "$R2" | grep -o 'tmp/[a-z0-9.]*' | head -1)
echo "pending2: $P2"