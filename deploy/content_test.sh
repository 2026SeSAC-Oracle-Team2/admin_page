#!/bin/bash
# IMAGE_RESOURCE / IMAGE_TAG / IMAGE_HINT CRUD 확인 (팀원 주 사용 시나리오)
set -e
BASE=http://127.0.0.1:8501
JAR=/tmp/ck10.txt
rm -f $JAR
PW=$(grep '^ADMIN_PAGE_PASSWORD=' ~/admin_page/.env | cut -d= -f2-)
curl -s -o /dev/null -c $JAR -X POST -d "password=$PW" $BASE/login

echo "--- IMAGE_RESOURCE 폼 GET ---"
curl -s -b $JAR "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/new" -o /tmp/new.html -w 'form:%{http_code}\n'
grep -oE 'name="[A-Z_]+"' /tmp/new.html | sort -u

echo "--- IMAGE_RESOURCE 추가 ---"
curl -s -b $JAR -X POST \
  --data-urlencode 'IMAGE_NAME=스모크문제.png' \
  --data-urlencode 'BUCKET_PATH=oci://bucket/problems/smoke.png' \
  --data-urlencode 'PROBLEM_TYPE=WORD' \
  $BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/create -o /dev/null -w 'create:%{http_code}\n'

RID=$(curl -s -b $JAR -X POST --data-urlencode "sql=SELECT IMAGE_ID FROM SPEECHAPP_CONTENT.IMAGE_RESOURCE WHERE IMAGE_NAME = '스모크문제.png'" $BASE/sql | grep -oE '<td>[0-9]+</td>' | head -1 | tr -dc '0-9')
echo "resource_id=$RID"

echo "--- IMAGE_TAG 추가 ---"
curl -s -b $JAR -X POST \
  --data-urlencode "IMAGE_ID=$RID" \
  --data-urlencode 'TAG_TEXT=동물' \
  $BASE/table/SPEECHAPP_CONTENT/IMAGE_TAG/row/create -o /dev/null -w 'tag_create:%{http_code}\n'

echo "--- IMAGE_HINT 추가 ---"
curl -s -b $JAR -X POST \
  --data-urlencode "IMAGE_ID=$RID" \
  --data-urlencode 'HINT_TYPE=TEXT' \
  --data-urlencode 'HINT_TEXT=멍멍 짖는 동물' \
  $BASE/table/SPEECHAPP_CONTENT/IMAGE_HINT/row/create -o /dev/null -w 'hint_create:%{http_code}\n'

echo "--- FK 링크 확인 (IMAGE_TAG 목록에서 부모 링크) ---"
curl -s -b $JAR "$BASE/table/SPEECHAPP_CONTENT/IMAGE_TAG" | grep -o 'IMAGE_RESOURCE' | head -1

echo "--- 정리 (자식→부모 순) ---"
TID=$(curl -s -b $JAR -X POST --data-urlencode "sql=SELECT TAG_ID FROM SPEECHAPP_CONTENT.IMAGE_TAG WHERE IMAGE_ID = $RID" $BASE/sql | grep -oE '<td>[0-9]+</td>' | head -1 | tr -dc '0-9')
HID=$(curl -s -b $JAR -X POST --data-urlencode "sql=SELECT HINT_ID FROM SPEECHAPP_CONTENT.IMAGE_HINT WHERE IMAGE_ID = $RID" $BASE/sql | grep -oE '<td>[0-9]+</td>' | head -1 | tr -dc '0-9')
curl -s -b $JAR -X POST --data-urlencode "__pk__TAG_ID=$TID" $BASE/table/SPEECHAPP_CONTENT/IMAGE_TAG/row/delete -o /dev/null -w 'tag_del:%{http_code}\n'
curl -s -b $JAR -X POST --data-urlencode "__pk__HINT_ID=$HID" $BASE/table/SPEECHAPP_CONTENT/IMAGE_HINT/row/delete -o /dev/null -w 'hint_del:%{http_code}\n'
curl -s -b $JAR -X POST --data-urlencode "__pk__IMAGE_ID=$RID" $BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/delete -o /dev/null -w 'res_del:%{http_code}\n'
rm -f $JAR /tmp/new.html