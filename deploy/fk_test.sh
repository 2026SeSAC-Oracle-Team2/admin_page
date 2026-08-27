#!/bin/bash
# FK 에러 메시지 확인 (재배포 후)
set -e
BASE=http://127.0.0.1:8501
JAR=/tmp/ck3.txt
rm -f $JAR
PW=$(grep '^ADMIN_PAGE_PASSWORD=' ~/admin_page/.env | cut -d= -f2-)
curl -s -o /dev/null -c $JAR -X POST -d "password=$PW" $BASE/login

# 유저 생성
curl -s -o /dev/null -b $JAR -X POST \
  --data-urlencode 'UUID=fkchk' \
  --data-urlencode 'FIREBASE_UID=fkchk' \
  --data-urlencode 'EMAIL=fkchk@x.com' \
  $BASE/table/SPEECHAPP_USER/APP_USER/row/create

USER_ID_VAL=$(curl -s -b $JAR -X POST --data-urlencode "sql=SELECT ID FROM SPEECHAPP_USER.APP_USER WHERE UUID = 'fkchk'" $BASE/sql | grep -oE '<td>[0-9]+</td>' | head -1 | tr -dc '0-9')
echo "USER_ID=$USER_ID_VAL"

# 프로필 생성 (FK 자식)
curl -s -o /dev/null -b $JAR -X POST \
  --data-urlencode "USER_ID=$UID" \
  --data-urlencode 'NICKNAME=부모삭제테스트' \
  $BASE/table/SPEECHAPP_USER/USER_PROFILE/row/create

# FK 위반: 부모 삭제 시도 → flash 에러 쿠키 내용 출력
curl -s -b $JAR -X POST --data-urlencode "__pk__ID=$USER_ID_VAL" $BASE/table/SPEECHAPP_USER/APP_USER/row/delete -D - -o /dev/null | grep -i 'set-cookie: flash' | head -1

# 정리
PID=$(curl -s -b $JAR -X POST --data-urlencode "sql=SELECT ID FROM SPEECHAPP_USER.USER_PROFILE WHERE USER_ID = $USER_ID_VAL" $BASE/sql | grep -oE '<td>[0-9]+</td>' | head -1 | tr -dc '0-9')
curl -s -o /dev/null -b $JAR -X POST --data-urlencode "__pk__ID=$PID" $BASE/table/SPEECHAPP_USER/USER_PROFILE/row/delete
curl -s -o /dev/null -b $JAR -X POST --data-urlencode "__pk__ID=$USER_ID_VAL" $BASE/table/SPEECHAPP_USER/APP_USER/row/delete
echo "정리 완료"
rm -f $JAR