FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bootstrap ./bootstrap
RUN useradd --create-home agentops
USER agentops
ENV PORT=10000
CMD ["sh", "-c", "exec uvicorn bootstrap.main:app --host 0.0.0.0 --port ${PORT} --no-access-log"]
