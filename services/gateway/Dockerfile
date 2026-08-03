FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install fastapi uvicorn[standard] httpx
COPY services/gateway/main.py ./services/gateway/main.py
EXPOSE 8080
CMD ["uvicorn", "services.gateway.main:app", "--host", "0.0.0.0", "--port", "8080"]
