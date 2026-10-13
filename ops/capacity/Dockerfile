FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /probe
COPY ops/capacity/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY ops/capacity/monitor.py ./monitor.py
USER 65534:65534
CMD ["python", "monitor.py"]
