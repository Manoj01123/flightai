FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements/base.txt requirements/mcp-prediction.txt ./
RUN pip install -r base.txt -r mcp-prediction.txt
COPY services/ ./services/
# Python can't import hyphenated directory names; create an underscore alias
RUN ln -sf /app/services/mcp-prediction /app/services/mcp_prediction
EXPOSE 8080
CMD ["uvicorn", "services.mcp_prediction.main:app", "--host", "0.0.0.0", "--port", "8080"]
