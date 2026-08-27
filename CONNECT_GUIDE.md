# SeSAC DB 관리자 페이지 — 접속 가이드

VM의 Oracle DB를 브라우저에서 조회 / 추가 / 수정 / 삭제할 수 있는 관리자 페이지입니다.
VM 외부에는 노출되어 있지 않고, **SSH 터널로만 접속**됩니다.

## 0. 준비물

- WSL 터미널 (Ubuntu 등)
- VM 접속용 SSH 키 파일 (팀 공유분)
- 브라우저

## 1. SSH 키 준비 (최초 1회)

```bash
# 키 파일은 반드시 WSL 안(~/)으로 복사해서 쓰세요. /mnt/c/... 에 두면 권한 오류가 납니다.
mkdir -p ~/.ssh
cp /mnt/c/Users/<윈도우계정>/Downloads/<키파일명> ~/.ssh/
chmod 400 ~/.ssh/<키파일명>
```

## 2. 터널 연결 (사용할 때마다)

```bash
ssh -i ~/.ssh/<키파일명> -N -L 8501:localhost:8501 opc@<VM_IP>
```

- `-N` : 셸 접속 없이 터널만 유지
- `-L 8501:localhost:8501` : 내 PC의 8501 포트 → VM의 8501 포트로 연결
- 실행하면 아무 출력 없이 멈춘 것처럼 보여도 **정상**입니다. 창을 켜둔 채로 두세요.
- 끊을 때는 `Ctrl+C`

> `<VM_IP>`, `<키파일명>` 부분은 실제 값으로 바꿔주세요. (IP는 팀 채널 공유 자료 참고)

### (선택) SSH config 등록하면 더 간단

`~/.ssh/config` 파일에 아래 내용을 추가하면:

```
Host sesac-admin
    HostName <VM_IP>
    User opc
    IdentityFile ~/.ssh/<키파일명>
    LocalForward 8501 localhost:8501
    ServerAliveInterval 60
```

다음부터는 한 줄이면 됩니다:

```bash
ssh -N sesac-admin
```

## 3. 브라우저 접속

터널이 켜져 있는 상태에서:

1. 브라우저 주소창에 **http://localhost:8501**
2. 로그인 비밀번호 입력 (팀 채널로 공유된 비밀번호)
3. 로그인 세션은 12시간 유지되고, 이후에는 다시 로그인

> WSL에서 터널을 열면 Windows 브라우저에서도 `localhost:8501` 로 접속됩니다.

## 4. 사용법 요약

| 하고 싶은 것 | 방법 |
|---|---|
| 데이터 보기 | 테이블 카드 클릭 → 목록 |
| 검색 | 상단 검색바 (컬럼 선택 + 검색어) |
| 데이터 추가 | **+ 행 추가** → 폼 작성 → 추가 |
| 데이터 수정 | 행의 **수정** 버튼 |
| 데이터 삭제 | 행의 **삭제** 버튼 → 확인창 |
| 부모 데이터 보기 | 보라색 FK 링크 클릭 (예: USER_PROFILE의 USER_ID → APP_USER) |
| SQL 직접 실행 | 상단 **SQL 콘솔** (기본은 SELECT만, DML은 체크 후 실행) |

### 문제 이미지 리소스 추가 (예시)

1. `IMAGE_RESOURCE` → **+ 행 추가**
2. IMAGE_NAME / BUCKET_PATH / PROBLEM_TYPE 입력
   - PROBLEM_TYPE은 `DESCRIBE` 또는 `GUESS` 중에서만 선택 가능
3. 태그는 `IMAGE_TAG`, 힌트는 `IMAGE_HINT` 에 추가 — 이때 IMAGE_ID에 위에서 만든 리소스의 IMAGE_ID 입력

### 주의

- **삭제는 복구 불가입니다.** 신중하게 누르세요.
- 다른 데이터가 참조 중인 행은 서버가 삭제를 거절합니다 (FK 보호). 자식(태그/힌트/프로필)을 먼저 지우세요.
- 새로고침/브라우저 닫기 후 12시간이 지나면 재로그인이 필요합니다.

## 5. 문제 해결

| 증상 | 해결 |
|---|---|
| `Address already in use` | 내 PC에서 8501 포트가 이미 사용 중 → `-L 8502:localhost:8501` 로 숫자만 바꾸고, 브라우저도 `localhost:8502` |
| `UNPROTECTED PRIVATE KEY FILE` | 키를 `~/.ssh` 로 옮기고 `chmod 400 <키파일명>` 실행 |
| `Permission denied (publickey)` | 키 파일 경로/이름 오타 확인, 팀 공유 키가 맞는지 확인 |
| `Connection timed out` | VM이 꺼졌거나 네트워크 문제 → 관리자에게 문의 |
| 페이지는 열리는데 "Oracle DB에 연결할 수 없습니다" 경고 | Oracle 컨테이너 문제 → 관리자에게 문의 |
| WSL에선 되는데 Windows 브라우저에서 안 됨 | WSL 터미널을 완전히 종료 후 재시작하고 터널 재연결 |

## 6. (관리자용) 웹 비밀번호 변경

```bash
# VM에서
nano ~/admin_page/.env          # ADMIN_PAGE_PASSWORD 줄 수정
cd ~/admin_page
docker compose up -d            # 재적용
```