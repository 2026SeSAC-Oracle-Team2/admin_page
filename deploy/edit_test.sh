#!/bin/bash
# 행 편집 폼 + 수정 + 삭제 확인
set -e
BASE=http://127.0.0.1:8501
JAR=/tmp/ck9.txt
rm -f $JAR
PW=$(grep '^ADMIN_PAGE_PASSWORD=' ~/admin_page/.env | cut -d= -f2-)
curl -s -o /dev/null -c $JAR -X POST -d "password=$PW" $BASE/login

# 유저 생성
curl -s -o /dev/null -b $JAR -X POST \
  --data-urlencode 'UUID=editcheck' \
  --data-urlencode 'FIREBASE_UID=editcheck' \
  --data-urlencode 'EMAIL=edit@check.com' \
  $BASE/table/SPEECHAPP_USER/APP_USER/row/create
EID=$(curl -s -b $JAR -X POST --data-urlencode "sql=SELECT ID FROM SPEECHAPP_USER.APP_USER WHERE UUID='editcheck'" $BASE/sql | grep -oE '<td>[0-9]+</td>' | head -1 | tr -dc '0-9')
echo "edit_id=$EID"

# 편집 폼 GET
curl -s -b $JAR "$BASE/table/SPEECHAPP_USER/APP_USER/row/edit?ID=$EID" -o /tmp/edit.html -w 'edit_form:%{http_code}\n'
echo "input_count: $(grep -c 'value=' /tmp/edit.html)"
grep -o 'edit@check.com' /tmp/edit.html | head -1

# 수정 POST
curl -s -b $JAR -X POST \
  --data-urlencode "__pk__ID=$EID" \
  --data-urlencode 'UUID=editcheck' \
  --data-urlencode 'FIREBASE_UID=editcheck' \
  --data-urlencode 'EMAIL=edited@check.com' \
  $BASE/table/SPEECHAPP_USER/APP_USER/row/update -o /dev/null -w 'update:%{http_code}\n'

# 수정 확인
curl -s -b $JAR -X POST --data-urlencode "sql=SELECT EMAIL FROM SPEECHAPP_USER.APP_USER WHERE ID=$EID" $BASE/sql | grep -oE '<td>[^<]*</td>' | head -1

# 삭제 (정리)
curl -s -b $JAR -X POST --data-urlencode "__pk__ID=$EID" $BASE/table/SPEECHAPP_USER/APP_USER/row/delete -o /dev/null -w 'delete:%{http_code}\n'
rm -f $JAR /tmp/edit.html