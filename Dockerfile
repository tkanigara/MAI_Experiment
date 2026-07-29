FROM node:20-slim AS frontend

WORKDIR /app/dashboard

COPY dashboard/package.json ./
RUN npm install

COPY dashboard/index.html ./
COPY dashboard/vite.config.js ./
COPY dashboard/src ./src
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DASHBOARD_HOST=0.0.0.0
ENV PORT=8000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY generate_slides_example.py ./generate_slides_example.py
COPY preview_report_charts.py ./preview_report_charts.py
COPY dashboard/repositories ./dashboard/repositories
COPY dashboard/services ./dashboard/services
COPY dashboard/routes ./dashboard/routes
COPY dashboard/config.py ./dashboard/config.py
COPY dashboard/db.py ./dashboard/db.py
COPY dashboard/schemas.py ./dashboard/schemas.py
COPY dashboard/main.py ./dashboard/main.py
COPY dashboard/server.py ./dashboard/server.py
COPY dashboard/slides_report.py ./dashboard/slides_report.py
COPY agentic ./agentic
COPY --from=frontend /app/dashboard/dist ./dashboard/dist

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn dashboard.main:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
