# SeSAC Admin Page — Oracle DB 웹 관리 콘솔

팀원들이 SQL/CLI 없이 브라우저에서 SeSAC 프로젝트 DB(Oracle XE)를 조회·추가·수정·삭제할 수 있는 관리자 페이지.

- **스택**: FastAPI + python-oracledb(thin) + Jinja2, Docker 컨테이너
- **접속**: `127.0.0.1:8501` (VM 내부 전용) — SSH 터널로 접근
- **DB 계정**: `speechapp_admin` (SPEECHAPP_USER / SPEECHAPP_CONTENT 전체 권한)

## 빠른 시작 (VM에서)

```bash
cd ~/admin_page

# 1. .env 생성 (최초 1회, 서버에서만 작업 — 시크릿은 절대 커밋/전송 금지)
cat > .env <<'EOF'
DB_PASSWORD=<speechapp_admin 비밀번호 — DB 컨테이너 init SQL 참조>
ADMIN_PAGE_PASSWORD=<웹 로그인 비밀번호 — 팀원에게 공유>
SESSION_SECRET=<openssl rand -hex 32 결과>
EOF
chmod 600 .env

# 2. 빌드 + 기동
docker compose up -d --build

# 3. 확인
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8501/login   # 200 이면 OK
```

## 팀원 접속 방법 (각자 WSL에서)

```bash
ssh -i <키파일> -L 8501:localhost:8501 opc@<VM_IP>
```

터널을 켜둔 상태에서 브라우저로 `http://localhost:8501` 접속 → 관리자 비밀번호 입력.

## 기능

| 기능 | 설명 |
|------|------|
| 테이블 목록 | SPEECHAPP 스키마의 테이블 자동 조회 (행 수 표시) |
| 행 조회 | 페이지네이션, 문자열 컬럼 검색, FK 링크로 부모 행 이동 |
| 행 추가/수정/삭제 | 컬럼 메타데이터 기반 자동 폼 (PK·IDENTITY 자동 제외) |
| 제약 에러 안내 | FK/NOT NULL/UNIQUE 위반을 한국어로 표시 |
| SQL 콘솔 | 기본 SELECT 전용, 체크 시 DML 허용 |
| 로그인 | 세션 쿠키 (12시간), 비밀번호는 .env에서 관리 |

## 구조

```
admin_page/
├── app/
│   ├── main.py        # FastAPI 라우트
│   ├── db.py          # 커넥션 풀 + 쿼리 헬퍼
│   ├── meta.py        # 테이블 메타데이터 (all_tables 기반 동적)
│   ├── crud.py        # 동적 CRUD (바인딩, 식별자 인용)
│   ├── auth.py        # 세션 토큰/비밀번호 검증
│   ├── config.py      # 환경변수 로딩
│   ├── templating.py  # Jinja 필터
│   ├── templates/     # base/login/home/table/row_form/sql
│   └── static/style.css
├── Dockerfile
├── docker-compose.yml # Oracle 네트워크 조인, 127.0.0.1 바인딩
└── .env.example
```

## 주의

- **.env는 절대 커밋하지 마세요.** (.gitignore에 포함됨)
- 포트가 `127.0.0.1` 에만 바인딩되어 있어 외부 노출이 없습니다. 공개 포트로 바꾸지 마세요.
- Oracle 컨테이너(`sesac-oracle-db`)가 먼저 떠 있어야 합니다.
- 삭제 시 다른 테이블이 참조 중이면(FK) 서버가 거절하고 안내를 표시합니다.