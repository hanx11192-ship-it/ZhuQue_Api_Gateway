#!/bin/bash
set -e

DATA_DIR="${DATA_DIR:-/srv/gateway/data}"
mkdir -p "$DATA_DIR/scripts"

SSH_KEYS_DIR="$DATA_DIR/ssh_keys"
mkdir -p "$SSH_KEYS_DIR"

if [ ! -f "$SSH_KEYS_DIR/ssh_host_ed25519_key" ]; then
  ssh-keygen -q -t ed25519 -f "$SSH_KEYS_DIR/ssh_host_ed25519_key" -N ''
fi
if [ ! -f "$SSH_KEYS_DIR/ssh_host_rsa_key" ]; then
  ssh-keygen -q -t rsa -b 3072 -f "$SSH_KEYS_DIR/ssh_host_rsa_key" -N ''
fi
chmod 600 "$SSH_KEYS_DIR"/ssh_host_*_key

ROOT_PASSWORD="${ROOT_PASSWORD:-changeme}"
echo "root:${ROOT_PASSWORD}" | chpasswd

cat > /etc/ssh/sshd_config <<EOF
Port 22
ListenAddress 0.0.0.0
PermitRootLogin yes
PasswordAuthentication yes
PubkeyAuthentication yes
UsePAM no
StrictModes no
HostKey $SSH_KEYS_DIR/ssh_host_ed25519_key
HostKey $SSH_KEYS_DIR/ssh_host_rsa_key
EOF

/usr/sbin/sshd

echo "Gateway container ready. SSH: root@<host> -p <mapped> | Web: :8000"

cd /srv/gateway
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
