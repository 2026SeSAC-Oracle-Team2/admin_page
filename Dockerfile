# ============================================================
# SeSAC Admin Page 컨테이너 이미지
# ============================================================
FROM python:3.11-slim

WORKDIR /app

# 의존성 설치 (레이어 캐시)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]