FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements/base.txt requirements/notifier.txt ./
RUN pip install -r base.txt -r notifier.txt
COPY services/ ./services/
RUN ln -sf /app/services/mcp-notifier /app/services/mcp_notifier
EXPOSE 8080
CMD ["uvicorn", "services.mcp_notifier.main:app", "--host", "0.0.0.0", "--port", "8080"]
