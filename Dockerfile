FROM python:3.12-slim

WORKDIR /app

COPY app.py .
COPY static/ static/
COPY data/ seed-data/

RUN mkdir -p data .cache

VOLUME ["/app/data", "/app/.cache"]

ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD ["python", "app.py"]
