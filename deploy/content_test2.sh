#!/bin/bash
# IMAGE_RESOURCE 완전 CRUD 재검증 (드롭다운 반영 후)
set -e
BASE=http://127.0.0.1:8501
JAR=/tmp/ck11.txt
rm -f $JAR
PW=$(grep '^ADMIN_PAGE_PASSWORD=' ~/admin_page/.env | cut -d= -f2-)
curl -s -o /dev/null -c $JAR -X POST -d "password=$PW" $BASE/login

echo "--- 폼에 select 있는지 ---"
curl -s -b $JAR "$BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/new" | grep -oE '<select[^>]*id="f-PROBLEM_TYPE"' | head -1

echo "--- 올바른 값으로 추가 ---"
curl -s -b $JAR -X POST \
  --data-urlencode 'IMAGE_NAME=스모크문제.png' \
  --data-urlencode 'BUCKET_PATH=oci://bucket/problems/smoke.png' \
  --data-urlencode 'PROBLEM_TYPE=DESCRIBE' \
  $BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/create -o /dev/null -w 'create:%{http_code}\n'

RID=$(curl -s -b $JAR -X POST --data-urlencode "sql=SELECT IMAGE_ID FROM SPEECHAPP_CONTENT.IMAGE_RESOURCE WHERE IMAGE_NAME = '스모크문제.png'" $BASE/sql | grep -oE '<td>[0-9]+</td>' | head -1 | tr -dc '0-9')
echo "resource_id=$RID"

echo "--- IMAGE_TAG 추가 ---"
curl -s -b $JAR -X POST --data-urlencode "IMAGE_ID=$RID" --data-urlencode 'TAG_TEXT=동물' $BASE/table/SPEECHAPP_CONTENT/IMAGE_TAG/row/create -o /dev/null -w 'tag:%{http_code}\n'

echo "--- IMAGE_HINT 추가 (드롭다운 값 CHOSUNG) ---"
curl -s -b $JAR -X POST --data-urlencode "IMAGE_ID=$RID" --data-urlencode 'HINT_TYPE=CHOSUNG' --data-urlencode 'HINT_TEXT=멍멍' $BASE/table/SPEECHAPP_CONTENT/IMAGE_HINT/row/create -o /dev/null -w 'hint:%{http_code}\n'

echo "--- FK 위반: IMAGE_RESOURCE 삭제 시도 (태그가 참조 중) ---"
curl -s -b $JAR -X POST --data-urlencode "__pk__IMAGE_ID=$RID" $BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/delete -D - -o /dev/null | grep -i 'set-cookie: flash' | head -1 | python3 -c "import sys,urllib.parse; line=sys.stdin.read(); import re; m=re.search(r'flash=(err|ok)\|([^;]*)', line); print(m.group(1), '|', urllib.parse.unquote(m.group(2)) if m else 'none')"

echo "--- 정리 ---"
TID=$(curl -s -b $JAR -X POST --data-urlencode "sql=SELECT TAG_ID FROM SPEECHAPP_CONTENT.IMAGE_TAG WHERE IMAGE_ID = $RID" $BASE/sql | grep -oE '<td>[0-9]+</td>' | head -1 | tr -dc '0-9')
HID=$(curl -s -b $JAR -X POST --data-urlencode "sql=SELECT HINT_ID FROM SPEECHAPP_CONTENT.IMAGE_HINT WHERE IMAGE_ID = $RID" $BASE/sql | grep -oE '<td>[0-9]+</td>' | head -1 | tr -dc '0-9')
curl -s -b $JAR -X POST --data-urlencode "__pk__TAG_ID=$TID" $BASE/table/SPEECHAPP_CONTENT/IMAGE_TAG/row/delete -o /dev/null
curl -s -b $JAR -X POST --data-urlencode "__pk__HINT_ID=$HID" $BASE/table/SPEECHAPP_CONTENT/IMAGE_HINT/row/delete -o /dev/null
curl -s -b $JAR -X POST --data-urlencode "__pk__IMAGE_ID=$RID" $BASE/table/SPEECHAPP_CONTENT/IMAGE_RESOURCE/row/delete -o /dev/null -w 'res_del:%{http_code}\n'
echo done
rm -f $JAR