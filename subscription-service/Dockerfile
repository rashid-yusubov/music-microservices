FROM python:3.12-slim
WORKDIR /service
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY subscription_service/ ./subscription_service/
RUN mkdir -p /data
EXPOSE 8005
CMD ["uvicorn", "subscription_service.main:app", "--host", "0.0.0.0", "--port", "8005"]
