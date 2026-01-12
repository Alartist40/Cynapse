FROM debian:bullseye-slim

# Install required packages for CTF
RUN apt-get update && apt-get install -y --no-install-recommends \
    sudo \
    libcap2-bin \
    curl \
    ca-certificates \
    docker.io \
    net-tools \
    procps \
    vim \
    less \
    && rm -rf /var/lib/apt/lists/*

# Create the escape user
RUN useradd -m -s /bin/bash escape && \
    echo "escape:escape" | chpasswd && \
    usermod -aG sudo escape

# Copy rootfs structure
COPY rootfs/ /

# Make scripts executable
RUN chmod +x /start.sh /opt/checkredact.sh /exploits/setup.sh

# Run exploit setup to configure the 10 escape paths
RUN /exploits/setup.sh

# Create start time file location
RUN mkdir -p /tmp && chmod 1777 /tmp

# Switch to escape user (non-root)
USER escape
WORKDIR /home/escape

# Entry point
ENTRYPOINT ["/start.sh"]
