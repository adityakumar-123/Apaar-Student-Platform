FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a normal user; /data holds the database volume
RUN useradd --create-home app && mkdir /data && chown app:app /data
USER app

EXPOSE 8000

# Apply migrations, create demo users (skipped if they exist), then start the API
CMD ["sh", "-c", "python -m alembic upgrade head && python seed_users.py && python -m uvicorn main:app --host 0.0.0.0 --port 8000"]