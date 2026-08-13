FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Railway should use demo_backend as this service's root directory. Copying it
# into a package directory preserves imports such as `demo_backend.router`.
COPY . /app/demo_backend

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "uvicorn demo_backend.main:app --host 0.0.0.0 --port ${PORT}"]
