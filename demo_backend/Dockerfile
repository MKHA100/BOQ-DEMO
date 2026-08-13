FROM python:3.12-slim

WORKDIR /app

# Railway builds this service with `demo_backend` as its root directory.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . ./demo_backend

ENV PORT=8000
EXPOSE 8000

CMD ["/app/demo_backend/start.sh"]
