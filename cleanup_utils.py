#!/usr/bin/env python3
import os
import glob
import time
from datetime import datetime, timedelta
import logger_utils
from config import config

def cleanup_old_temp_files(max_age_hours=24):
    """
    一時ファイルの自動クリーンアップ機能
    指定された時間より古い一時ファイルを削除する
    """
    logger_utils.info(f"Starting automatic cleanup of temp files older than {max_age_hours} hours")
    
    cleanup_count = 0
    cutoff_time = time.time() - (max_age_hours * 3600)
    
    # 削除対象のパターン
    # クロスプラットフォーム対応のためにパスを相対的に設定
    app_root = os.path.dirname(os.path.abspath(__file__))
    patterns = [
        os.path.join(app_root, "temp", "*", "temp_audio_file_*.aac"),
        os.path.join(app_root, "temp", "*", "temp_audio_file_*.mp3"),
        os.path.join(app_root, "temp", "uploads", "*-uploaded.*"),
        os.path.join(app_root, "data", "*", "temp_audio_file_*.aac"),
        os.path.join(app_root, "data", "*", "temp_audio_file_*.mp3")
    ]
    
    for pattern in patterns:
        logger_utils.debug(f"Searching pattern: {pattern}")
        files = glob.glob(pattern)
        
        for file_path in files:
            try:
                file_stat = os.stat(file_path)
                if file_stat.st_mtime < cutoff_time:
                    logger_utils.info(f"Deleting old temp file: {file_path}")
                    os.remove(file_path)
                    cleanup_count += 1
                else:
                    logger_utils.debug(f"Keeping recent file: {file_path}")
            except Exception as e:
                logger_utils.error(f"Failed to delete temp file {file_path}: {e}")
    
    logger_utils.info(f"Cleanup completed. Deleted {cleanup_count} old temp files")
    return cleanup_count

def cleanup_specific_user_temp_files(username, max_age_hours=1):
    """
    特定ユーザーの一時ファイルをクリーンアップ
    """
    logger_utils.info(f"Cleaning up temp files for user: {username}")
    
    cleanup_count = 0
    cutoff_time = time.time() - (max_age_hours * 3600)
    
    # ユーザー固有の一時ディレクトリパターン
    user_temp_dir = str(config.get_user_temp_dir(username))
    patterns = [
        f"{user_temp_dir}/temp_audio_file_*.aac",
        f"{user_temp_dir}/temp_audio_file_*.mp3",
        f"{user_temp_dir}/*.tmp"
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        for file_path in files:
            try:
                file_stat = os.stat(file_path)
                if file_stat.st_mtime < cutoff_time:
                    logger_utils.info(f"Deleting user temp file: {file_path}")
                    os.remove(file_path)
                    cleanup_count += 1
            except Exception as e:
                logger_utils.error(f"Failed to delete user temp file {file_path}: {e}")
    
    return cleanup_count

def get_temp_file_stats():
    """
    一時ファイルの統計情報を取得
    """
    # クロスプラットフォーム対応のためにパスを相対的に設定
    app_root = os.path.dirname(os.path.abspath(__file__))
    patterns = [
        os.path.join(app_root, "temp", "*", "temp_audio_file_*.*"),
        os.path.join(app_root, "temp", "uploads", "*"),
        os.path.join(app_root, "data", "*", "temp_audio_file_*.*")
    ]
    
    total_files = 0
    total_size = 0
    old_files = 0
    cutoff_time = time.time() - (24 * 3600)  # 24時間前
    
    for pattern in patterns:
        files = glob.glob(pattern)
        for file_path in files:
            try:
                file_stat = os.stat(file_path)
                total_files += 1
                total_size += file_stat.st_size
                if file_stat.st_mtime < cutoff_time:
                    old_files += 1
            except Exception:
                pass
    
    return {
        "total_files": total_files,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "old_files_24h": old_files
    }

if __name__ == "__main__":
    # スタンドアロン実行時のクリーンアップ
    stats = get_temp_file_stats()
    print(f"Temp file stats: {stats}")
    
    if stats["old_files_24h"] > 0:
        cleaned = cleanup_old_temp_files(24)
        print(f"Cleaned up {cleaned} old temp files")
    else:
        print("No old temp files to clean")