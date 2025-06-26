#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# ポート5000で実行中のプロセスを探して終了
echo "Checking for processes using port 5000..."
for pid in $(lsof -t -i:5000 2>/dev/null)
do
    echo "Killing process with PID: $pid using port 5000"
    kill -9 $pid 2>/dev/null
done

# 少し待ってポートが解放されるのを確認
sleep 2
echo "Verifying port 5000 is free..."
if [ -n "$(lsof -t -i:5000 2>/dev/null)" ]; then
    echo "Port 5000 is still in use. Trying again..."
    for pid in $(lsof -t -i:5000 2>/dev/null)
    do
        echo "Killing process with PID: $pid using port 5000"
        kill -9 $pid 2>/dev/null
    done
    sleep 1
fi

# systemctlを使用してkururinサービスを再起動
echo "Starting kururin service using systemctl..."
sudo systemctl start kururin

# サービスのステータスを確認
echo "Checking service status..."
sudo systemctl status kururin

echo "Kururin service started."
echo "Check logs with: sudo journalctl -u kururin -f"
