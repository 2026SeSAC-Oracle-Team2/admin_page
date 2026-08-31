#!/bin/bash
# IMAGE_RESOURCE 신규/기존/삭제 3종 검증 스크립트
BASE=http://localhost:8501
CK=/tmp/ck_ver.txt
PW=$(grep '^ADMIN_PAGE_PASSWORD=' ~/admin_page/.env | cut -d= -f2)
curl -s -c $CK -X POST -d "password=$PW" $BASE/login -o /dev/null

echo "=== 준비물 준비 ==="
head -c 3000 /dev/urandom > /tmp/test_img.png
printf '{"tags":["고양이","강아지"]}' > /tmp/test_tags.json

echo "=== STEP 1: 폼 열기 (reserved_id 확보) ==="
RESERVE=$(curl -s -b $CK "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/new" | grep -oE 'value="[0-9]+"' | head -1 | grep -oE "[0-9]+")
echo "reserved_id 확보: $RESERVE"

echo "=== STEP 2: 이미지 업로드 → res_path 기록 ==="
R1=$(curl -s -X POST -F "file=@/tmp/test_img.png" -F "image_id=$RESERVE" $BASE/upload-image)
echo "upload-image 응답: $R1"
RP1=$(echo "$R1" | grep -oE 'rel_path[":]+[^,}]+' | sed 's/.*rel_path"[: "]*\(.*\)/\1/' )
REL_PATH=$(echo "$RP1" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read().strip("\"")[0:]) if False else sys.stdin.read().strip())' | grep -oE '[0-9]+/[0-9]+\.[a-z]+' | head -1)
[ -z "$REL_PATH" ] && REL_PATH=$(echo "$R1" | python3 -c 'import sys,json; d=json.loads(sys.stdin.read()); print(d["rel_path"])' 2>/dev/null)
[ -z "$REL_PATH" ] && REL_PATH=$(echo "$R1" | grep -oE '"rel_path"\s*:\s*"([^"]+)"' | sed 's/.*"\([^"]*\)".*/\1/')
echo "rel_path: $REL_PATH"

echo "=== STEP 3: 태그 JSON 업로드 ==="
R2=$(curl -s -X POST -F "file=@/tmp/test_tags.json" -F "image_id=$RESERVE" -F "kind=tags" $BASE/upload-json)
echo "upload-json 태그: $R2"

echo "=== STEP 4: 행 생성 ==="
RP_PATH=$(echo "$RP1" | grep -oE '[0-9]+/[0-9]+\.[a-z]+' | head -1)
curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/create" \
  --data-urlencode "IMAGE_ID=$RESERVE" \
  --data-urlencode "IMAGE_NAME=리팩토링검증" \
  --data-urlencode "rel_ext=png" \
  --data-urlencode "__uploaded_tags__=1" \
  -o /dev/null -w "CREATE: %{http_code}\n"

echo "=== STEP 5: DB 확인 ==="
docker exec -i sesac-oracle-db sqlplus -s speechapp_admin/SeT54504adu@localhost:1521/XEPDB1 << SQLEOF
SET LINESIZE 150
SELECT image_id, image_name, image_file_path, image_tag_path FROM speechapp_content.image_resource WHERE image_name='리팩토링검증';
EXIT
SQLEOF

echo "=== STEP 6: 버킷 확인 ==="
python3 - << PYEOF
import oci
conf = oci.config.from_file("/home/opc/.oci/config", "DEFAULT")
client = oci.object_storage.ObjectStorageClient(conf)
ns = client.get_namespace().data
B = "bucket-team545-problemfiles"
for k in ("images/%s/%s.png" % (RESERVE, RESERVE), "images/%s/%s.tags.json" % (RESERVE, RESERVE)):
    try:
        h = client.head_object(ns, B, k)
        print(k, "존재:", h.headers["Content-Length"], "B")
    except Exception as e:
        print(k, "없음 또는 오류:", str(e)[:100])
# tmp 잔재
objs = [o.name for o in client.list_objects(ns, B, prefix="tmp/").data.objects]
print("tmp 잔재:", objs)
PYEOF

echo "=== STEP 7: 행 삭제 시 연동 삭제 확인 ==="
ID=$(docker exec -i sesac-oracle-db sqlplus -s speechapp_admin/SeT54504adu@localhost:1521/XEPDB1 << 'EOF2' 2>&1 | grep -oE '[0-9]+' | head -1
SELECT image_id FROM speechapp_content.image_resource WHERE image_name='리팩토링검증';
EOF2
)
echo "삭제 대상 image_id: $ID"
if [ -n "$ID" ]; then
  curl -s -b $CK -X POST "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/delete" --data-urlencode "__pk__IMAGE_ID=$ID" -o /dev/null -w "DELETE: %{http_code}\n"
  python3 - << PYEOF
import oci
conf = oci.config.from_file("/home/opc/.oci/config", "DEFAULT")
client = oci.object_storage.ObjectStorageClient(conf)
ns = client.get_namespace().data
B = "bucket-team545-problemfiles"
objs = [o.name for o in client.list_objects(ns, B, prefix="images/$ID/").data.objects]
print("images/$ID/: 삭제 후 남은 객체:", len(objs), "개 (0개가 정상)")
PYEOF
fi

docker exec -i sesac-oracle-db sqlplus -s speechapp_admin/SeT54504adu@localhost:1521/XEPDB1 << SQLEOF
SET LINESIZE 150
SELECT COUNT(*) AS remaining FROM speechapp_content.image_resource WHERE image_name='리팩토링검증';
EXIT
SQLEOF