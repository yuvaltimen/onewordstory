FROM python:3.13-slim

WORKDIR /app
COPY app/ ./
COPY .env ./.env
RUN pip install -r requirements.txt



CMD ["python", "main.py"]