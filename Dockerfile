FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home accessflow \
    && mkdir -p /var/lib/accessflow && chown accessflow:accessflow /var/lib/accessflow
COPY config ./config
USER accessflow
CMD ["python", "-m", "accessflow", "serve"]
