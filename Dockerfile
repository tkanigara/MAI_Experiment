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
COPY dashboard/server.py ./dashboard/server.py
COPY dashboard/slides_report.py ./dashboard/slides_report.py
COPY --from=frontend /app/dashboard/dist ./dashboard/dist

EXPOSE 8000

CMD ["python", "dashboard/server.py"]
