"""
設定管理モジュール
環境変数を読み込み、クロスプラットフォーム対応の設定を提供
"""
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# 環境変数を読み込む
load_dotenv()

class Config:
    """アプリケーション設定クラス"""
    
    # アプリケーションのルートディレクトリ（このファイルがある場所）
    APP_ROOT = Path(__file__).parent.absolute()
    
    # File System Paths (クロスプラットフォーム対応)
    DATA_DIR = APP_ROOT / os.getenv('KURURIN_DATA_DIR', 'data')
    
    # 一時ディレクトリ（環境変数が指定されていない場合はシステムの一時ディレクトリを使用）
    temp_dir_env = os.getenv('KURURIN_TEMP_DIR', 'temp')
    if temp_dir_env == 'temp':
        TEMP_DIR = APP_ROOT / 'temp'
    elif temp_dir_env.startswith('/') or temp_dir_env.startswith('C:'):
        # 絶対パス
        TEMP_DIR = Path(temp_dir_env)
    else:
        # 相対パス
        TEMP_DIR = APP_ROOT / temp_dir_env
    
    LOG_DIR = APP_ROOT / os.getenv('KURURIN_LOG_DIR', 'logs')
    
    # FFmpeg/FFprobe paths (shutil.whichでシステムパスから検索)
    import shutil
    _ffmpeg_env = os.getenv('FFMPEG_PATH', 'ffmpeg')
    _ffprobe_env = os.getenv('FFPROBE_PATH', 'ffprobe')
    
    if _ffmpeg_env in ['ffmpeg', 'ffprobe']:
        # 環境変数がデフォルト値の場合、システムパスから検索
        FFMPEG_PATH = shutil.which('ffmpeg') or '/usr/local/bin/ffmpeg'
        FFPROBE_PATH = shutil.which('ffprobe') or '/usr/local/bin/ffprobe'
    else:
        # カスタムパスが指定されている場合
        FFMPEG_PATH = _ffmpeg_env
        FFPROBE_PATH = _ffprobe_env
    
    # Network Configuration
    HOST = os.getenv('KURURIN_HOST', '0.0.0.0')
    PORT = int(os.getenv('KURURIN_PORT', 5000))
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_CHAT_MODEL = os.getenv('OPENAI_CHAT_MODEL', 'gpt-4o-mini')
    OPENAI_WHISPER_MODEL = os.getenv('OPENAI_WHISPER_MODEL', 'whisper-1')
    OPENAI_MAX_TOKENS = int(os.getenv('OPENAI_MAX_TOKENS', 16384))
    
    # Retry and Timeout Configuration
    TRANSCRIPTION_MAX_RETRIES = int(os.getenv('TRANSCRIPTION_MAX_RETRIES', 3))
    TRANSCRIPTION_RETRY_WAIT = int(os.getenv('TRANSCRIPTION_RETRY_WAIT', 5))
    
    # Time Configuration (in minutes)
    DEFAULT_MEETING_DURATION = int(os.getenv('DEFAULT_MEETING_DURATION', 30))
    FILE_GROUPING_INTERVAL = int(os.getenv('FILE_GROUPING_INTERVAL', 3))
    FOLLOWER_DETECTION_THRESHOLD = int(os.getenv('FOLLOWER_DETECTION_THRESHOLD', 2))
    TITLE_GENERATION_RANGE = int(os.getenv('TITLE_GENERATION_RANGE', 20))
    
    # Audio Processing
    AUDIO_SEGMENT_DURATION = int(os.getenv('AUDIO_SEGMENT_DURATION', 60))
    
    # Logging
    LOG_RETENTION_DAYS = int(os.getenv('LOG_RETENTION_DAYS', 7))
    DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
    
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY')
    FALLBACK_SECRET_KEY = os.getenv('FALLBACK_SECRET_KEY', 'your-fallback-secret-key')
    
    # Conda Environment
    CONDA_ENV_NAME = os.getenv('CONDA_ENV_NAME', '311')
    
    @classmethod
    def ensure_directories(cls):
        """必要なディレクトリを作成"""
        cls.DATA_DIR.mkdir(exist_ok=True)
        cls.TEMP_DIR.mkdir(exist_ok=True)
        cls.LOG_DIR.mkdir(exist_ok=True)
    
    @classmethod
    def get_user_temp_dir(cls, username):
        """ユーザー専用の一時ディレクトリパスを取得"""
        user_temp = cls.TEMP_DIR / username
        user_temp.mkdir(exist_ok=True)
        return user_temp
    
    @classmethod
    def get_user_data_dir(cls, dirname):
        """ユーザー専用のデータディレクトリパスを取得"""
        return cls.DATA_DIR / dirname
    
    @classmethod
    def get_data_pattern(cls, username):
        """データディレクトリ検索パターンを取得"""
        return str(cls.DATA_DIR / f"{username}:*:000000")
    
    @classmethod
    def validate_config(cls):
        """設定の検証"""
        errors = []
        
        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY is required")
        
        if not cls.SECRET_KEY:
            errors.append("SECRET_KEY is required")
        
        # FFmpegとFFprobeの存在確認
        if not Path(cls.FFMPEG_PATH).exists() and not shutil.which(cls.FFMPEG_PATH):
            errors.append(f"FFmpeg not found at {cls.FFMPEG_PATH}")
        
        if not Path(cls.FFPROBE_PATH).exists() and not shutil.which(cls.FFPROBE_PATH):
            errors.append(f"FFprobe not found at {cls.FFPROBE_PATH}")
        
        return errors

# 設定インスタンス
config = Config()

# アプリケーション起動時にディレクトリを作成
config.ensure_directories()