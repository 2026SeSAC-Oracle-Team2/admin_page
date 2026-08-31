#!/bin/bash
# 리팩토링 후 전체 E2E (v2) — create 3종 + edit + delete + 버킷 대조
BASE=http://localhost:8501
CK=/tmp/ck_e2e.txt
SQL() { docker exec -i sesac-oracle-db sqlplus -s speechapp_admin/SeT54504adu@localhost:1521/XEPDB1; }
CNT() { docker exec sesac-oracle-db sqlplus -s speechapp_admin/SeT54504adu@localhost:1521/XEPDB1 <<-EOF | tr -d ' \n'
	SET HEAD OFF FEED OFF PAGESIZE 0
	$1
	EXIT;
	EOF
}

head -c 9000 /dev/urandom > /tmp/rf.bin
printf '\x89PNG\r\n\x1a\n' | cat - /tmp/rf_body.bin > /dev/null 2>&1
cp /tmp/rf.bin /tmp/rf_a.png 2>/dev/null || true
printf '\x89PNG\r\n\x1a\n' > /tmp/rf_a.png; head -c 9000 /dev/urandom >> /tmp/rf_a.png
printf '{"tags":["E2EV2"]}' > /tmp/rf.tags.json

echo "== 1) 이미지 없이 제출 → 거부 =="
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/create" \
  -F 'IMAGE_NAME=V2-noimg' -o /dev/null -w "HTTP %{http_code}\n"
echo "행수(0이어야): $(CNT "SELECT COUNT(*) FROM speechapp_content.image_resource WHERE image_name='V2-noimg'")"

echo "== 2) 이미지+태그 → 생성 =="
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/create" \
  -F 'IMAGE_NAME=V2-정상' \
  -F '__file_image__=@/tmp/rf_a.png' \
  -F '__file_tags__=@/tmp/rf.tags.json' -o /dev/null -w "HTTP %{http_code}\n"

docker exec -i sesac-oracle-db sqlplus -s speechapp_admin/SeT54504adu@localhost:1521/XEPDB1 << 'SQLEOF'
SET LINESIZE 200 PAGESIZE 0
SELECT image_id || ' | ' || image_name || ' | ' || image_file_path || ' | tags=' || NVL(image_tag_path,'-') FROM speechapp_content.image_resource WHERE image_name='V2-정상';
EXIT
SQLEOF

ID="$(CNT "SELECT image_id FROM speechapp_content.image_resource WHERE image_name='V2-정상'")"
ID=$(echo $ID | tr -d ' \n')
echo "== 3) 프록시 다운로드 (path=$ID/$ID.png) =="
curl -sL "$BASE/image-preview?path=$ID/$ID.png" -o /tmp/v2_dl.png -w "HTTP %{http_code} %{size_download}B\n"
md5sum /tmp/rf_a.png /tmp/v2_dl.png 2>/dev/null | awk '{print $1}' | uniq -c

echo "== 4) 행 삭제 → OCI 연동 삭제 =="
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/delete" \
  --data-urlencode "__pk__IMAGE_ID=$ID" -o /dev/null -w "HTTP %{http_code}\n"