import os
from dotenv import load_dotenv
# 環境変数を読み込む
load_dotenv()

import logger_utils
from config import config

from openai import OpenAI
import openai
import httpx
import subprocess
from datetime import datetime
from flask import session
import time


def convert_to_mp3(input_file_path, output_format="mp3", timestamp=None, dirname=''):
    directory = str(config.get_user_data_dir(dirname))
    output_file_path = f"{directory}/{timestamp}.{output_format}"
    command = [config.FFMPEG_PATH, "-i", input_file_path, "-acodec", "libmp3lame", output_file_path]
    subprocess.run(command, check=True)
    return output_file_path


def save_temporary_file(audio_file_stream, format="aac", timestamp=None, dirname=''): # AAC形式をデフォルトとして受け付けます。
    directory = str(config.get_user_data_dir(dirname))
    temp_file = f"{directory}/temp_audio_file_{timestamp}." + format
    audio_file_stream.save(temp_file)
    return temp_file

def save_transcription(text, timestamp=None, dirname=''):
    logger_utils.info(f"save_transcription START - timestamp: {timestamp}, dirname: {dirname}")
    logger_utils.debug(f"Text length: {len(text) if text else 0} characters")
    
    directory = str(config.get_user_data_dir(dirname))  # PosixPathを文字列に変換
    logger_utils.debug(f"Target directory: {directory}")
    logger_utils.debug(f"Directory exists: {os.path.exists(directory)}")
    
    filename = f"{directory}/{timestamp}.txt"
    logger_utils.info(f"Attempting to save transcription to: {filename}")
    
    try:
        # テキストファイルとして保存
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(text)
        logger_utils.info(f"Transcription successfully saved to {filename}")
        logger_utils.debug(f"File size after save: {os.path.getsize(filename)} bytes")
    except Exception as e:
        logger_utils.error(f"Failed to save transcription to {filename}: {e}")
        raise

def transcribe(audio_file_stream, timestamp=None, dirname=''):
    logger_utils.info("transcribe START (real-time recording)")
    logger_utils.debug(f"timestamp: {timestamp}, dirname: {dirname}")
    
    # リアルタイム録音では一時ディレクトリを使用
    temp_dir = str(config.get_user_temp_dir(dirname))
    os.makedirs(temp_dir, exist_ok=True)
    
    # Save the AAC file temporarily in temp directory
    aac_file = f"{temp_dir}/temp_audio_file_{timestamp}.aac"
    audio_file_stream.save(aac_file)
    logger_utils.debug(f"Temporary AAC file saved: {aac_file}")
    
    # Convert AAC to MP3 in temp directory
    mp3_file = f"{temp_dir}/{timestamp}.mp3"
    command = [config.FFMPEG_PATH, "-i", aac_file, "-acodec", "libmp3lame", mp3_file]
    subprocess.run(command, check=True)
    logger_utils.debug(f"MP3 file created: {mp3_file}")
    
    # サブプロセス方式でEventlet互換性問題を回避
    try:
        transcribed_text = transcribe_mp3_subprocess(mp3_file, timestamp, dirname)
        logger_utils.info(f"Transcription successful. Length: {len(transcribed_text)} characters")
    except Exception as e:
        logger_utils.error(f"Transcription failed: {e}")
        raise
    
    # リアルタイム録音では正しいユーザーディレクトリを見つけて保存
    import glob
    import shutil
    
    # dirnameが既に完全なディレクトリ名かどうかチェック
    direct_path = str(config.DATA_DIR / dirname)
    if os.path.exists(direct_path):
        # 完全なディレクトリ名の場合は直接使用
        directories = [direct_path]
        logger_utils.debug(f"Using direct directory path: {direct_path}")
    else:
        # 部分的なユーザー名の場合はパターン検索
        pattern = config.get_data_pattern(dirname)
        directories = glob.glob(pattern)
        logger_utils.debug(f"Pattern search for: {pattern}, Found: {directories}")
    
    if directories:
        target_directory = directories[0]
        txt_file = f"{target_directory}/{timestamp}.txt"
        mp3_final_file = f"{target_directory}/{timestamp}.mp3"
        
        logger_utils.info(f"Saving transcription to: {txt_file}")
        logger_utils.info(f"Copying MP3 file to: {mp3_final_file}")
        
        try:
            # テキストファイルを保存
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(transcribed_text)
            logger_utils.info(f"Real-time transcription saved successfully: {txt_file}")
            
            # MP3ファイルをコピー
            if os.path.exists(mp3_file):
                shutil.copy2(mp3_file, mp3_final_file)
                logger_utils.info(f"MP3 file copied successfully: {mp3_final_file}")
            else:
                logger_utils.warning(f"MP3 file not found for copying: {mp3_file}")
                
        except Exception as e:
            logger_utils.error(f"Failed to save real-time files: {e}")
            raise
    else:
        logger_utils.error(f"No target directory found")
        raise Exception(f"Target directory not found for user: {dirname}")
    
    # 一時ファイルをクリーンアップ（最後に実行）
    try:
        if os.path.exists(aac_file):
            os.remove(aac_file)
            logger_utils.debug(f"Removed temporary AAC file: {aac_file}")
        if os.path.exists(mp3_file):
            os.remove(mp3_file)
            logger_utils.debug(f"Removed temporary MP3 file: {mp3_file}")
    except Exception as e:
        logger_utils.error(f"Failed to remove temporary files: {e}")
        logger_utils.error(f"Failed cleanup files - AAC: {aac_file}, MP3: {mp3_file}")
    
    logger_utils.info("transcribe COMPLETE (real-time recording)")

    # Return the transcription text
    return transcribed_text

# （変換された後の）MP3ファイルを文字おこしする
def transcribe_mp3_old(file_path, timestamp=None, dirname=''):
    # Initialize the OpenAI client
    client = OpenAI(
        api_key=config.OPENAI_API_KEY
    )

    # Open the MP3 file and transcribe it using the OpenAI API
    with open(file_path, 'rb') as mp3_file:
        transcript = client.audio.transcriptions.create(
            model=config.OPENAI_WHISPER_MODEL,
            file=mp3_file,
            response_format="text"
        )
        # テキスト形式で直接返されるためtranscriptがそのまま文字列
        transcribed_text = transcript

    # Return the transcription text
    return transcribed_text


# （変換された後の）MP3ファイルを文字おこしする,リトライ実装20240113
def transcribe_mp3(file_path, timestamp=None, dirname=''):
    logger_utils.info("transcribe_mp3 START")
    logger_utils.debug(f"File path: {file_path}")
    logger_utils.debug(f"File exists: {os.path.exists(file_path)}")
    if os.path.exists(file_path):
        logger_utils.debug(f"File size: {os.path.getsize(file_path)} bytes")
    
    # Eventlet環境での互換性問題を回避するため、別プロセスで実行
    return transcribe_mp3_subprocess(file_path, timestamp, dirname)

def transcribe_mp3_subprocess(file_path, timestamp=None, dirname=''):
    """Eventletとの互換性問題を回避するため、サブプロセスでOpenAI APIを呼び出す"""
    import subprocess
    import sys
    import json
    
    logger_utils.info("Using subprocess for transcription to avoid Eventlet conflicts")
    
    # Pythonスクリプトを文字列として作成
    script = f'''
import sys
import os
import json
# サブプロセスでは__file__が定義されていないため、カレントディレクトリを使用
current_dir = os.getcwd()
sys.path.append(current_dir)
from config import config
from openai import OpenAI
import time

def transcribe_file():
    try:
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        
        attempts = 0
        max_retries = config.TRANSCRIPTION_MAX_RETRIES
        wait_time = config.TRANSCRIPTION_RETRY_WAIT
        
        while attempts < max_retries:
            try:
                with open("{file_path}", "rb") as mp3_file:
                    transcript = client.audio.transcriptions.create(
                        model=config.OPENAI_WHISPER_MODEL,
                        file=mp3_file,
                        response_format="text"
                    )
                    return {{"success": True, "text": transcript}}
            except Exception as e:
                attempts += 1
                if attempts < max_retries:
                    time.sleep(wait_time)
                else:
                    return {{"success": False, "error": str(e)}}
        
        return {{"success": False, "error": "Max retries exceeded"}}
        
    except Exception as e:
        return {{"success": False, "error": str(e)}}

result = transcribe_file()
print(json.dumps(result))
'''
    
    try:
        logger_utils.debug("Starting subprocess transcription")
        # サブプロセスでスクリプトを実行
        result = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True,
            text=True,
            timeout=300  # 5分のタイムアウト
        )
        
        if result.returncode != 0:
            logger_utils.error(f"Subprocess failed with return code {result.returncode}")
            logger_utils.error(f"STDERR: {result.stderr}")
            raise Exception(f"Subprocess transcription failed: {result.stderr}")
        
        # JSON結果をパース
        response_data = json.loads(result.stdout.strip())
        
        if response_data.get("success"):
            transcribed_text = response_data["text"]
            logger_utils.info(f"Subprocess transcription successful. Length: {len(transcribed_text)} characters")
            logger_utils.debug(f"Text preview: {transcribed_text[:100]}...")
            return transcribed_text
        else:
            error_msg = response_data.get("error", "Unknown error")
            logger_utils.error(f"Subprocess transcription failed: {error_msg}")
            raise Exception(f"Transcription failed: {error_msg}")
            
    except subprocess.TimeoutExpired:
        logger_utils.error("Subprocess transcription timed out")
        raise Exception("Transcription timed out")
    except json.JSONDecodeError as e:
        logger_utils.error(f"Failed to parse subprocess output: {e}")
        logger_utils.error(f"Raw output: {result.stdout}")
        raise Exception(f"Failed to parse transcription result: {e}")
    except Exception as e:
        logger_utils.error(f"Subprocess transcription error: {e}")
        raise
