FROM python:3.12-slim
WORKDIR /service
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY catalog_service/ ./catalog_service/
RUN mkdir -p /data
EXPOSE 8003
CMD ["uvicorn", "catalog_service.main:app", "--host", "0.0.0.0", "--port", "8003"]
