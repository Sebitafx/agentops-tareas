FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bootstrap ./bootstrap
COPY taskapp ./taskapp
RUN useradd --create-home agentops
USER agentops
ENV PORT=10000
CMD ["python", "-m", "bootstrap.serve"]
