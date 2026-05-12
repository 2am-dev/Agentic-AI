FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    nodejs \
    npm \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages available in sandbox
RUN pip install --no-cache-dir \
    requests \
    beautifulsoup4 \
    numpy \
    pandas \
    matplotlib \
    seaborn \
    scikit-learn \
    flask \
    fastapi \
    httpx \
    aiohttp \
    pillow \
    pytest \
    black \
    pylint

# Create isolated workspace
RUN useradd -m -u 1000 sandbox && \
    mkdir -p /sandbox/workspace && \
    chown -R sandbox:sandbox /sandbox

WORKDIR /sandbox/workspace
USER sandbox

# No network by default - will be controlled per-run
CMD ["/bin/bash"]
