#!/bin/bash
# 최종 검증 v3 — 리팩토링 후 7 시나리오 (부트캠프 VM)
BASE=http://localhost:8501
CK=/tmp/ck_final.txt
PW=$(grep '^ADMIN_PAGE_PASSWORD=' ~/admin_page/.env | cut -d= -f2)
CNT() { docker exec -i sesac-oracle-db sqlplus -s speechapp_admin/SeT54504adu@localhost:1521/XEPDB1 << SQLEOF | tr -d ' \n'
SET HEAD OFF FEED OFF PAGESIZE 0
$1
EXIT
SQLEOF
}

curl -s -c $CK -X POST -d "password=$PW" $BASE/login -o /dev/null -w "로그인: %{http_code}\n"

# 테스트 자산: 유효 png + 유효 json + 유잘못된 json
printf '\x89PNG\r\n\x1a\n' > /tmp/final_a.png; head -c 8000 /dev/urandom >> /tmp/final_a.png
printf '\x89PNG\r\n\x1a\n' > /tmp/final_b.png; head -c 5000 /dev/urandom >> /tmp/final_b.png
printf '{"tags":["최종검증"]}' > /tmp/final.tags.json
printf 'not json' > /tmp/final.bad.txt

echo "════ 1) 이미지 미선택 제출 → 거부(행 없음, 오류 플래시) ════"
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/create" \
  -F 'IMAGE_NAME=FINAL-noimg' -o /dev/null -w "HTTP %{http_code} / "
echo "행수: $(CNT "SELECT COUNT(*) FROM speechapp_content.image_resource WHERE image_name='FINAL-noimg'")"

echo "════ 2) 잘못된 확장자(.txt를 이미지로) → 거부 ════"
printf '\x89PNG\r\n\x1a\n' > /tmp/final_bad.png; head -c 1000 /dev/urandom >> /tmp/final_bad.png
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/create" \
  -F 'IMAGE_NAME=FINAL-badext' -F '__file_image__=@/tmp/final.bad.txt' \
  -o /dev/null -w "HTTP %{http_code} / "
echo "행수: $(CNT "SELECT COUNT(*) FROM speechapp_content.image_resource WHERE image_name='FINAL-badext'")"

echo "════ 3) 이미지+태그 정상 제출 → 성공+ID 일치+버킷 실존 ════"
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/create" \
  -F 'IMAGE_NAME=FINAL-정상' \
  -F '__file_image__=@/tmp/final_a.png' \
  -F '__file_tags__=@/tmp/final.tags.json' \
  -o /dev/null -w "HTTP %{http_code}\n"
ID=$(CNT "SELECT image_id FROM speechapp_content.image_resource WHERE image_name='FINAL-정상'")
ID=$(echo $ID | tr -d ' \n')
echo "생성 ID: [$ID]"
docker exec -i sesac-oracle-db sqlplus -s speechapp_admin/SeT54504adu@localhost:1521/XEPDB1 << SQLEOF
SET LINESIZE 250 PAGESIZE 0
SELECT image_id || ' | ' || image_name || ' | ' || image_file_path || ' | tags=' || NVL(image_tag_path,'-') FROM speechapp_content.image_resource WHERE image_id=$ID;
EXIT
SQLEOF

echo "════ 4) 프록시 실측 (PAR 다운로드 → 원본과 바이트 일치) ════"
curl -sL "$BASE/image-preview?path=$ID/$ID.png" -o /tmp/final_dl.png -w "HTTP %{http_code} %{size_download}B\n"
H1=$(md5sum /tmp/final_a.png | cut -d' ' -f1); H2=$(md5sum /tmp/final_dl.png | cut -d' ' -f1)
[ "$H1" = "$H2" ] && echo "MD5 일치 ✅ ($H1)" || echo "MD5 불일치 ❌ ($H1 vs $H2)"

echo "════ 5) 행 수정: 새 이미지로 교체 ════"
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/update" \
  -F "__pk__IMAGE_ID=$ID" -F 'IMAGE_NAME=FINAL-정상-수정됨' \
  -F '__file_image__=@/tmp/final_b.png' \
  -o /dev/null -w "HTTP %{http_code}\n"
docker exec -i sesac-oracle-db sqlplus -s speechapp_admin/SeSAC 2>/dev/null
docker exec -i sesac-oracle-db sqlplus -s speechapp_admin/SeT54504adu@localhost:1521/XEPDB1 << SQLEOF
SET LINESIZE 250 PAGESIZE 0
SELECT image_id || ' | ' || image_name || ' | ' || image_file_path FROM speechapp_content.image_resource WHERE image_id=$ID;
EXIT
SQLEOF
curl -sL "$BASE/image-preview?path=$ID/$ID.png" -o /tmp/final_dl2.png -w "HTTP %{http_code} %{size_download}B\n"
H3=$(md5sum /tmp/final_b.png | cut -d' ' -f1); H4=$(md5sum /tmp/final_dl2.png | cut -d' ' -f1)
[ "$H3" = "$H4" ] && echo "수정 후 MD5 일치 ✅" || echo "수정 후 MD5 불일치 ❌"

echo "════ 6) 행 삭제 → OCI 연동 삭제 ════"
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/delete" \
  --data-urlencode "__pk__IMAGE_ID=$ID" -o /dev/null -w "HTTP %{http_code} / "
echo "DB 잔존: $(CNT "SELECT COUNT(*) FROM speechapp_content.image_resource WHERE image_id=$ID") (0이어야)"