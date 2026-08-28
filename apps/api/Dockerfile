FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
COPY apps/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY apps/api /app
COPY scripts /app/scripts
COPY packages /packages
EXPOSE 8000
CMD ["sh", "-c", "python -m app.migrations && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
