FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY . .
EXPOSE 8600
CMD ["uvicorn", "webapp:app", "--host", "0.0.0.0", "--port", "8600"]
