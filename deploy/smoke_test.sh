#!/bin/bash
# VM 내부에서 실행하는 스모크 테스트 (시크릿을 출력에 노출하지 않음)
set -e
BASE=http://127.0.0.1:8501
JAR=/tmp/cookies.txt
rm -f $JAR

PW=$(grep '^ADMIN_PAGE_PASSWORD=' ~/admin_page/.env | cut -d= -f2-)

echo "== 1. 로그인 페이지 =="
curl -s -o /dev/null -w '%{http_code}\n' $BASE/login

echo "== 2. 로그인 (잘못된 비번 → 401 기대) =="
curl -s -o /dev/null -w '%{http_code}\n' -X POST -d 'password=wrong' $BASE/login

echo "== 3. 로그인 (올바른 비번 → 303 기대) =="
curl -s -o /dev/null -w '%{http_code}\n' -c $JAR -X POST -d "password=$PW" $BASE/login

echo "== 4. 홈 (테이블 목록, 200 기대) =="
curl -s -o /tmp/home.html -w '%{http_code}\n' -b $JAR $BASE/
grep -o 'APP_USER\|USER_PROFILE\|IMAGE_RESOURCE\|IMAGE_TAG\|IMAGE_HINT' /tmp/home.html | sort -u

echo "== 5. 테이블 조회 (SPEECHAPP_USER.APP_USER) =="
curl -s -o /tmp/t.html -w '%{http_code}\n' -b $JAR "$BASE/table/SPEECHAPP_USER/APP_USER"
grep -c '<tr' /tmp/t.html

echo "== 6. 행 추가 (APP_USER 테스트 유저) =="
curl -s -o /dev/null -w '%{http_code}\n' -b $JAR -X POST \
  --data-urlencode 'UUID=test-smoke-uuid-0001' \
  --data-urlencode 'FIREBASE_UID=smoke-fb-uid-0001' \
  --data-urlencode 'SOCIAL_PROVIDER=GOOGLE' \
  --data-urlencode 'SOCIAL_ID=smoke-social-0001' \
  --data-urlencode 'EMAIL=smoke-test@example.com' \
  $BASE/table/SPEECHAPP_USER/APP_USER/row/create

echo "== 7. 추가된 행이 목록에 보이는지 =="
curl -s -b $JAR "$BASE/table/SPEECHAPP_USER/APP_USER?search_col=EMAIL&search=smoke-test" | grep -o 'smoke-test@example.com' | head -1

echo "== 8. USER_PROFILE 추가 (FK로 방금 유저 참조) =="
# APP_USER 의 ID 조회는 SQL 콘솔 API 를 통해
curl -s -b $JAR -X POST --data-urlencode 'sql=SELECT ID FROM SPEECHAPP_USER.APP_USER WHERE UUID = '"'"'test-smoke-uuid-0001'"'"'' $BASE/sql -o /tmp/sql1.html
UID_VAL=$(grep -oE '<td>[0-9]+</td>' /tmp/sql1.html | head -1 | tr -d '<td>/ ')
echo "조회된 APP_USER.ID = $UID_VAL"
curl -s -o /dev/null -w '%{http_code}\n' -b $JAR -X POST \
  --data-urlencode "USER_ID=$UID_VAL" \
  --data-urlencode 'NICKNAME=스모크닉네임' \
  $BASE/table/SPEECHAPP_USER/USER_PROFILE/row/create

echo "== 9. FK 위반 삭제 시도 (APP_USER 삭제 → 참조 중이라 거절 기대) =="
curl -s -b $JAR -X POST --data-urlencode "__pk__ID=$UID_VAL" $BASE/table/SPEECHAPP_USER/APP_USER/row/delete -o /dev/null -D /tmp/hdr.txt
grep -i 'flash=err\|set-cookie: flash' /tmp/hdr.txt | head -1

echo "== 10. PROFILE 삭제 → 유저 삭제 (정리) =="
PID=$(curl -s -b $JAR -X POST --data-urlencode 'sql=SELECT ID FROM SPEECHAPP_USER.USER_PROFILE WHERE NICKNAME = '"'"'스모크닉네임'"'"'' $BASE/sql -o /tmp/sql2.html; grep -oE '<td>[0-9]+</td>' /tmp/sql2.html | head -1 | tr -d '<td>/ ')
echo "USER_PROFILE.ID = $PID"
curl -s -o /dev/null -w 'profile_delete:%{http_code}\n' -b $JAR -X POST --data-urlencode "__pk__ID=$PID" $BASE/table/SPEECHAPP_USER/USER_PROFILE/row/delete
curl -s -o /dev/null -w 'user_delete:%{http_code}\n' -b $JAR -X POST --data-urlencode "__pk__ID=$UID_VAL" $BASE/table/SPEECHAPP_USER/APP_USER/row/delete

echo "== 11. SQL 콘솔 SELECT =="
curl -s -b $JAR -X POST --data-urlencode 'sql=SELECT COUNT(*) AS CNT FROM SPEECHAPP_USER.APP_USER' $BASE/sql -o /tmp/sql3.html
grep -oE '<td>[0-9]+</td>' /tmp/sql3.html | head -1

echo "== 12. SQL 콘솔 DML 차단 (체크 없이 UPDATE → 에러 기대) =="
curl -s -b $JAR -X POST --data-urlencode 'sql=UPDATE SPEECHAPP_USER.APP_USER SET EMAIL = '"'"'x'"'"'' $BASE/sql | grep -o 'SELECT만 허용됩니다' | head -1

echo "== 13. 미인증 접근 차단 (→303 /login 기대) =="
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/"

echo "== 완료 =="
rm -f $JAR /tmp/home.html /tmp/t.html /tmp/sql*.html /tmp/hdr.txt