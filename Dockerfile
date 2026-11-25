FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN mkdir /data && chown 10001:10001 /data
COPY bot.py server.py channels.json /app/

USER 10001:10001
CMD ["python", "server.py"]
