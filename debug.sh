#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Conda初期化 (スクリプトでcondaコマンドを使用できるようにする)
source $(conda info --base)/etc/profile.d/conda.sh

# Conda環境をアクティベート
conda activate ${CONDA_ENV_NAME:-311}

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

# アプリケーションをデバッグモードで起動（フォアグラウンドで実行）
echo "Starting python app.py in debug mode"
export DEBUG_MODE=true
python app.py

# 以下の行はフォアグラウンド実行では実行されません
echo "Application started in debug mode. Check logs/kururin.log for output."
