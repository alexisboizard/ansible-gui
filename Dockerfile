FROM python:3.12-slim

ARG VERSION=dev
ENV APP_VERSION=${VERSION}

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ansible \
        openssh-client \
        sshpass \
        iputils-ping \
        python3-lxml \
        libxml2-dev \
        libxslt-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/instance

# Write version to file
RUN echo "${VERSION}" > /app/VERSION

EXPOSE 5000

# Use eventlet for WebSocket support
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--worker-class", "eventlet", "run:app"]
