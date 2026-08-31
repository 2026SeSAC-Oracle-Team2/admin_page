#!/bin/bash
# 최종 검증 v4 — 템플릿 수정 후 7 시나리오 (전항목)
set -u
BASE=http://localhost:8501
CK=/tmp/ck_v4.txt
PW=$(grep '^ADMIN_PAGE_PASSWORD=' ~/admin_page/.env | cut -d= -f2)
sql() { docker exec -i sesac-oracle-db sqlplus -s speechapp_admin/SeT54504adu@localhost:1521/XEPDB1; }
AWQ() { echo "$1" | docker exec -i sesac-oracle-db sqlplus -s speechapp_admin/SeT54504adu@localhost:1521/XEPDB1 | grep -vE "^$|^$" | head -1 | tr -d " \n\r"; }

curl -s -c $CK -X POST -d "password=$PW" $BASE/login -o /dev/null

printf '\x89PNG\r\n\x1a\n' > /tmp/v4_a.png; head -c 8000 /dev/urandom >> /tmp/v4_a.png
printf '\x89PNG\r\n\x1a\n' > /tmp/v4_b.png; head -c 4000 /dev/urandom >> /tmp/v4_b.png
printf '{"tags":["v4"]}' > /tmp/v4.tags.json
printf 'garbage' > /tmp/v4.txt

echo "1) 이미지 미선택 제출 → 거부"
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/create" \
  -F 'IMAGE_NAME=V4-noimg' -o /dev/null -w "HTTP %{http_code}  "
echo "행수=[$(AWQ "SELECT COUNT(*) FROM speechapp_content.image_resource WHERE image_name='V4-noimg'")]  (0이어야)"

echo "2) 잘못된 확장자 → 거부"
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/create" \
  -F 'IMAGE_NAME=V4-badext' -F '__file_image__=@/tmp/v4.txt' -o /dev/null -w "HTTP %{http_code}  "
echo "행수=[$(AWQ "SELECT COUNT(*) FROM speechapp_content.image_resource WHERE image_name='V4-badext'")]  (0이어야)"

echo "3) 이미지+태그 제출 → 성공"
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/create" \
  -F 'IMAGE_NAME=V4-정상' -F '__file_image__=@/tmp/v4_a.png' -F '__file_tags__=@/tmp/v4.tags.json' \
  -o /dev/null -w "HTTP %{http_code}\n"
ID=$(AWQ "SELECT MAX(image_id) FROM speechapp_content.image_resource")
ID=${ID//[$'\r\n ']/}
echo "ID=[$ID]"
sql << SQLEOF
SET LINESIZE 250 PAGESIZE 0
SELECT image_id || ' || ' || image_name || ' || ' || image_file_path || ' || tags=' || NVL(image_tag_path,'-') FROM speechapp_content.image_resource WHERE image_id=$ID;
EXIT
SQLEOF

echo "3b) 버킷 실물 확인"
python3 - << PYEOF
import oci, hashlib
conf = oci.config.from_file("/home/opc/.oci/config", "DEFAULT")
c = oci.object_storage.ObjectStorageClient(conf)
ns = c.get_namespace().data
local = open("/tmp/v4_a.png","rb").read()
b = c.get_object(ns, "bucket-team545-problemfiles", "images/$ID/$ID.png").data.content
t = c.get_object(ns, "bucket-team545-problemfiles", "images/$ID/$ID.tags.json").data.content
print("이미지:", len(b), "B /", len(local), "B, MD5동일:", hashlib.md5(b).hexdigest()==hashlib.md5(local).hexdigest())
print("tags.json:", t.decode())
PYEOF

echo "4) 프록시 다운로드 MD5"
curl -sL "$BASE/image-preview?path=$ID/$ID.png" -o /tmp/v4_dl.png -w "HTTP %{http_code} %{size_download}B\n"
A=$(md5sum /tmp/v4_a.png|cut -d' ' -f1); B=$(md5sum /tmp/v4_dl.png|cut -d' ' -f1)
[ "$A" = "$B" ] && echo "MD5 일치✅" || echo "불일치❌ $A/$B"

echo "5) edit에서 새 이미지 교체"
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/update" \
  -F "__pk__IMAGE_ID=$ID" -F 'IMAGE_NAME=V4-수정' -F '__file_image__=@/tmp/v4_b.png' \
  -o /dev/null -w "HTTP %{http_code}\n"
python3 - << PYEOF
import oci, hashlib
conf = oci.config.from_file("/home/opc/.oci/config", "DEFAULT")
c = oci.object_storage.ObjectStorageClient(conf)
ns = c.get_namespace().data
b = c.get_object(ns, "bucket-team545-problemfiles", "images/$ID/$ID.png").data.content
local = open("/tmp/v4_b.png","rb").read()
print("교체 MD5동일:", hashlib.md5(b).hexdigest()==hashlib.md5(local).hexdigest())
PYEOF

echo "6) edit에서 파일 미선택(이름만 수정) → 경로 유지"
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/update" \
  -F "__pk__IMAGE_ID=$ID" -F 'IMAGE_NAME=V4-이름만수정' \
  -o /dev/null -w "HTTP %{http_code}  "
P=$(AWQ "SELECT image_file_path FROM speechapp_content.image_resource WHERE image_id=$ID"); echo "경로유지=[$P]"
echo "7) 행 삭제 → OCI 연동 삭제"
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/delete" \
  --data-urlencode "__pk__IMAGE_ID=$ID" -o /dev/null -w "HTTP %{http_code}  "
R=$(AWQ "SELECT COUNT(*) FROM speechapp_content.image_resource WHERE image_id=$ID"); echo "DB잔존=[$R]"
python3 - << PYEOF
import oci
conf = oci.config.from_file("/home/opc/.oci/config", "DEFAULT")
c = oci.object_storage.ObjectStorageClient(conf)
ns = c.get_namespace().data
objs = [o.name for o in c.list_objects(ns, "bucket-team545-problemfiles", prefix="images/$ID/").data.objects]
print("버킷 잔존:", len(objs), "(0이어야)")
PYEOF

echo "── 테스트 잔재 정리 ──"
python3 - << PYEOF2
import oci
conf = oci.config.from_file("/home/opc/.oci/config", "DEFAULT")
c = oci.object_storage.ObjectStorageClient(conf)
ns = c.get_namespace().data
for o in c.list_objects(ns, "bucket-team545-problemfiles", prefix="tmp/").data.objects:
    c.delete_object(ns, "bucket-team545-problemfiles", o.name)
print("tmp 정리 완료")
PYEOF2
echo "최종 DB:"; sql << SQLEOF2
SET LINESIZE 250 PAGESIZE 0
SELECT image_id || ' || ' || image_name || ' || ' || image_file_path FROM speechapp_content.image_resource ORDER BY image_id;
EXIT
SQLEOF2