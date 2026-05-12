FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python, Node, Go, Rust, and utilities
RUN apt-get update && apt-get install -y \
    python3.11 python3-pip python3-venv \
    nodejs npm \
    golang \
    curl git jq build-essential wget \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /workspace
CMD ["tail", "-f", "/dev/null"]