#!/bin/bash
# VM에서만 실행됨 — speechapp_admin 비밀번호를 DB 컨테이너 init SQL에서 추출해 .env 생성
set -e
cd ~/admin_page

# speechapp_admin 비밀번호 추출 (init SQL에서)
DB_PW=$(grep -i "CREATE USER speechapp_admin IDENTIFIED BY" \
  ~/containers/SeSAC_SpeechApp_Container_DB/init/01_create_schemas.sql \
  | sed -E "s/.*IDENTIFIED BY [\"']?([^\"' ]+).*/\1/" | tr -d '\r')

if [ -z "$DB_PW" ]; then
  echo "ERROR: speechapp_admin 비밀번호 추출 실패"
  exit 1
fi

# 웹 로그인 비밀번호 (기존 .env 없으면 새로 생성)
if [ -f .env ]; then
  echo ".env 이미 존재 — 유지함"
else
  ADMIN_PW=$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 16)
  SESSION_SECRET=$(openssl rand -hex 32)
  umask 177
  cat > .env <<EOF
DB_PASSWORD=$DB_PW
ADMIN_PAGE_PASSWORD=$ADMIN_PW
SESSION_SECRET=$SESSION_SECRET
EOF
  chmod 600 .env
  echo ".env 생성 완료 (권한 600)"
fi
# 값 검증 없이 키만 확인
grep -oE '^[A-Z_]+' .env