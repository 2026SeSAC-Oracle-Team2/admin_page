#!/bin/bash
# 새 구조 E2E 검증 (부트캠프 VM) — 4 시나리오
BASE=http://localhost:8501
CK=/tmp/ck_e2e.txt
PW=$(grep '^ADMIN_PAGE_PASSWORD=' ~/admin_page/.env | cut -d= -f2)
SQL() { docker exec -i sesac-oracle-db sqlplus -s speechapp_admin/SeT54504adu@localhost:1521/XEPDB1; }

curl -s -c $CK -X POST -d "password=$PW" $BASE/login -o /dev/null
# 테스트 파일 준비 (부트캠프 VM /tmp 는 유지됨)
[ -f /tmp/e2e.png ] || { head -c 12000 /dev/urandom > /tmp/e2e_body; printf '\x89PNG\r\n\x1a\n' | cat - /tmp/e2e_body > /tmp/e2e.png; }
printf '{"tags":["테스트"]}' > /tmp/e2e.tags.json

echo "════ 시나리오 1: 이미지 없이 제출 → 반드시 거부 (행 0) ════"
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/create" \
  -F 'IMAGE_NAME=E2E-무이미지' -o /dev/null -w "HTTP %{http_code}\n"
N=$(docker exec sesac-oracle-db sqlplus -s speechapp_admin/SeT54504adu@localhost:1521/XEPDB1 <<< "SET HEAD OFF FEEDBACK OFF
SELECT COUNT(*) FROM speechapp_content.image_resource WHERE image_name='E2E-무이미지';
EXIT;")
echo "행 수: $(echo $N | tr -d ' \n') (0이어야 함)"

echo "════ 시나리오 2: 이미지 + 태그 JSON → 성공 + ID/경로 일치 + 버킷 실존 ════"
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/create" \
  -F 'IMAGE_NAME=E2E-정상' \
  -F '__file_image__=@/tmp/e2e.png;filename=newimg.png' \
  -F '__file_tags__=@/tmp/e2e.tags.json;filename=newimg.tags.json' \
  -o /dev/null -w "HTTP %{http_code}\n"

docker exec -i sesac-oracle-db sqlplus -s speechapp_admin/SeT54504adu@localhost:1521/XEPDB1 << SQLEOF
SET LINESIZE 150
SELECT image_id, image_name, image_file_path, image_tag_path FROM speechapp_content.image_resource WHERE image_name='E2E-정상';
EXIT
SQLEOF

NEWID=$(docker exec sesac-oracle-db sqlplus -s speechapp_admin/SeT54504adu@localhost:1521/XEPDB1 <<< "SET HEAD OFF FEED OFF
SELECT image_id FROM speechapp_content.image_resource WHERE image_name='E2E-정상';" | tr -d ' \n')
echo "생성된 ID: $NEWID"

echo "════ 시나리오 3: 미리보기 프록시 (생성된 이미지) ════"
curl -sL "$BASE/image-preview?path=$NEWID/$NEWID.png" -o /tmp/e2e_dl.png -w "HTTP %{http_code} %{size_download}B\n"

echo "════ 시나리오 4: 행 삭제 → OCI 객체 연동 삭제 ════"
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/delete" \
  --data-urlencode "__pk__IMAGE_ID=$NEWID" -o /dev/null -w "HTTP %{http_code}\n"
sleep 1
LEFT=$(docker exec sesac-oracle-db sqlplus -s speechapp_admin/SeT54504adu@localhost:1521/XEPDB1 <<< "SET HEAD OFF FEED OFF
SELECT COUNT(*) FROM speechapp_content.image_resource WHERE image_id=$NEWID;" | tr -d ' \n')
echo "DB 잔존: $LEFT (0이어야 함)"