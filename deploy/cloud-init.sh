#!/bin/sh
# Vultr user data: install Docker, open the web ports. The app itself is copied over SSH.
set -e
curl -fsSL https://get.docker.com | sh
ufw allow 22/tcp || true
ufw allow 80/tcp || true
ufw allow 443/tcp || true
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab
touch /root/cloud-init-done
