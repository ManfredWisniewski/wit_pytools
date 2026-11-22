#!/bin/bash

# Install Tailscale on Ubuntu Jammy
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.noarmor.gpg | \
  sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg > /dev/null

curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.tailscale-keyring.list | \
  sudo tee /etc/apt/sources.list.d/tailscale.list > /dev/null

sudo apt update
sudo apt install tailscale -y
sudo systemctl enable --now tailscaled
sudo tailscale up
