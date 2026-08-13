FROM python:3.12-slim

WORKDIR /app

COPY demo_backend/requirements.txt ./demo_backend/requirements.txt
RUN pip install --no-cache-dir -r demo_backend/requirements.txt

COPY demo_backend ./demo_backend

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn demo_backend.main:app --host 0.0.0.0 --port $PORT"]
