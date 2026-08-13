FROM python:3.12-slim

WORKDIR /app

# Build from the repository root so the demo can include the production-grade
# BOQ writers it reuses for PDF, Excel and CSV downloads.
COPY demo_backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/app/boq ./backend/app/boq
COPY demo_backend ./demo_backend

ENV PORT=8000
ENV PYTHONPATH=/app/backend:/app
EXPOSE 8000

CMD ["/app/demo_backend/start.sh"]
