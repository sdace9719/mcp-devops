FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN apt-get update && \
    apt install -y wget && \
    wget https://astral.sh/uv/install.sh && \
    chmod +x install.sh && \
    ./install.sh && \
    . $HOME/.local/bin/env && \
    rm install.sh && \
    uv pip install -r /app/requirements.txt --system

COPY app /app/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

