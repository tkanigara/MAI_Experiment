FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DASHBOARD_HOST=0.0.0.0
ENV DASHBOARD_PORT=8000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dashboard ./dashboard

EXPOSE 8000

CMD ["python", "dashboard/server.py"]
