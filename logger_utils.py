"""
共通ログユーティリティモジュール
過去1週間分のログファイルを保持し、デバッグフラグに基づいてログレベルを制御
"""
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from dotenv import load_dotenv

# 環境変数を読み込む
load_dotenv()

class KururinLogger:
    _loggers = {}
    
    @classmethod
    def get_logger(cls, name="kururin"):
        """ロガーインスタンスを取得（シングルトンパターン）"""
        if name not in cls._loggers:
            cls._loggers[name] = cls._create_logger(name)
        return cls._loggers[name]
    
    @classmethod
    def _create_logger(cls, name):
        """ロガーを作成"""
        logger = logging.getLogger(name)
        
        # 既にハンドラが設定されている場合はそのまま返す
        if logger.handlers:
            return logger
        
        # デバッグフラグを確認
        debug_mode = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
        log_level = logging.DEBUG if debug_mode else logging.INFO
        
        logger.setLevel(log_level)
        
        # ログディレクトリの作成
        log_dir = os.path.join(os.path.dirname(__file__), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # ログファイルパスの設定
        log_file = os.path.join(log_dir, f'{name}.log')
        
        # ログファイルが存在しない場合は空ファイルを作成
        if not os.path.exists(log_file):
            try:
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.write('')  # 空ファイルを作成
            except Exception as e:
                # ファイル作成に失敗した場合はコンソールに出力
                print(f"Warning: Could not create log file {log_file}: {e}")
        
        # ファイルハンドラ（環境変数で指定された日数分のログを保持）
        backup_count = int(os.getenv('LOG_RETENTION_DAYS', 7))
        file_handler = TimedRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        # フォーマッタ
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        # コンソールハンドラ（デバッグモードの場合のみ）
        if debug_mode:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        logger.addHandler(file_handler)
        
        return logger

def _ensure_log_file_exists(logger_name="kururin"):
    """ログファイルが存在することを確認し、必要に応じて作成"""
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    log_file = os.path.join(log_dir, f'{logger_name}.log')
    
    if not os.path.exists(log_file):
        try:
            os.makedirs(log_dir, exist_ok=True)
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write('')  # 空ファイルを作成
        except Exception as e:
            print(f"Warning: Could not ensure log file {log_file}: {e}")

def log_info(message, logger_name="kururin"):
    """情報ログを出力"""
    logger = KururinLogger.get_logger(logger_name)
    _ensure_log_file_exists(logger_name)
    logger.info(message)

def log_debug(message, logger_name="kururin"):
    """デバッグログを出力（DEBUG_MODE=trueの場合のみ）"""
    logger = KururinLogger.get_logger(logger_name)
    _ensure_log_file_exists(logger_name)
    logger.debug(message)

def log_warning(message, logger_name="kururin"):
    """警告ログを出力"""
    logger = KururinLogger.get_logger(logger_name)
    _ensure_log_file_exists(logger_name)
    logger.warning(message)

def log_error(message, logger_name="kururin"):
    """エラーログを出力"""
    logger = KururinLogger.get_logger(logger_name)
    _ensure_log_file_exists(logger_name)
    logger.error(message)

def log_critical(message, logger_name="kururin"):
    """クリティカルログを出力"""
    logger = KururinLogger.get_logger(logger_name)
    _ensure_log_file_exists(logger_name)
    logger.critical(message)

# エイリアス関数（より簡潔な使用のため）
def info(message, logger_name="kururin"):
    log_info(message, logger_name)

def debug(message, logger_name="kururin"):
    log_debug(message, logger_name)

def warning(message, logger_name="kururin"):
    log_warning(message, logger_name)

def error(message, logger_name="kururin"):
    log_error(message, logger_name)

def critical(message, logger_name="kururin"):
    log_critical(message, logger_name)