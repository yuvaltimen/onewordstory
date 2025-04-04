FROM python:3.10-slim

WORKDIR /client
COPY client.py ./
RUN pip install requests

CMD ["python", "client.py"]
