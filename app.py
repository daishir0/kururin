# eventletを最初にインポートし、socketを除外してmonkey_patch
import eventlet
# socketモジュールのモンキーパッチングを無効化
eventlet.monkey_patch(socket=False, time=True, thread=True)

from flask import Flask, request, render_template, jsonify, send_from_directory, abort, flash
import openai
from openai import OpenAI
import json
import os
import re

# OpenAI APIキーの設定
openai.api_key = os.getenv('OPENAI_API_KEY')
from datetime import datetime, timedelta
from flask_socketio import SocketIO, join_room
import transcription_service
import os
import sys
from flask_cors import CORS
from flask_mail import Mail, Message
from dotenv import load_dotenv
from config import config
from flask import session, redirect, url_for
from functools import wraps
import hashlib
from collections import defaultdict
import re
from datetime import datetime, timedelta
import subprocess
from werkzeug.utils import secure_filename
import math
import threading
import shutil
import glob
from markupsafe import Markup
from flask import abort
from flask import Response
import base64
import os.path
import time



# 環境変数を読み込む
load_dotenv()

# グローバル変数としてsocketioを定義
socketio = None

def create_app():
    global socketio
    
    app = Flask(__name__)
    CORS(app)  # 全ルートでCORSを有効化
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    # ロギングの設定
    import logger_utils
    logger_utils.info('Application startup')
    
    # BrokenPipeErrorを処理するためのエラーハンドラ
    @app.errorhandler(BrokenPipeError)
    def handle_broken_pipe_error(e):
        logger_utils.warning("BrokenPipeError occurred - client disconnected")
        return "Client disconnected", 499  # 499はNginxのClient Closed Requestステータスコード
    
    # セッションの秘密鍵の設定
    app.secret_key = os.getenv('SECRET_KEY')  # ここに安全なランダムな値を設定
    
    # 以下のルートやその他の設定を追加
    
    return app

# 直接実行用のアプリケーションインスタンスを作成
app = create_app()

# ロギングの設定
import logger_utils
logger_utils.info('Application startup')

# BrokenPipeErrorを処理するためのエラーハンドラ
@app.errorhandler(BrokenPipeError)
def handle_broken_pipe_error(e):
    logger_utils.warning("BrokenPipeError occurred - client disconnected")
    return "Client disconnected", 499  # 499はNginxのClient Closed Requestステータスコード

# セッションの秘密鍵の設定
app.secret_key = os.getenv('SECRET_KEY')  # ここに安全なランダムな値を設定

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'dirname' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def before_request():
    if 'dirname' not in session and request.endpoint not in ['login', 'static', 'admin']:
        return redirect(url_for('login'))
    
    
def generate_timestamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def read_meeting_transcripts(start_datetime, end_datetime):
    directory = os.path.join('./data/', session['dirname'])
    # datetimeオブジェクトへの変換
    start_datetime = datetime.strptime(start_datetime, '%Y%m%d-%H%M%S')
    
    # end_datetimeがNoneでなければ変換、そうでなければNoneのままにする
    if end_datetime is not None:
        end_datetime = datetime.strptime(end_datetime, '%Y%m%d-%H%M%S')
    
    transcripts = ""
    for filename in sorted(os.listdir(directory)):
        if filename.endswith(".txt"):
            date_time_part = filename[:-4]
            try:
                file_datetime = datetime.strptime(date_time_part, '%Y%m%d-%H%M%S')
                # end_datetimeがNoneの場合はstart_datetime以降のすべてのファイルを対象にする
                if end_datetime is None:
                    if file_datetime >= start_datetime:
                        with open(os.path.join(directory, filename), 'r') as file:
                            transcripts += file.read() + "\n"
                # それ以外の場合は通常通り期間をチェックする
                elif start_datetime <= file_datetime <= end_datetime:
                    with open(os.path.join(directory, filename), 'r') as file:
                        transcripts += file.read() + "\n"
            except ValueError as e:
                print(f"Error parsing date from file: {filename}, error: {e}")
    return transcripts

def calculate_monthly_recording_time(dirname, target_month=None):
    """
    指定された月の合計録音時間を計算
    target_month: None の場合は今月、'prev' の場合は先月
    戻り値: 合計分数
    """
    directory = os.path.join('./data/', dirname)
    total_minutes = 0
    
    # 今月/先月の開始日と終了日を設定
    now = datetime.now()
    if target_month == 'prev':
        # 先月の初日
        start_date = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
        # 先月の末日
        end_date = now.replace(day=1) - timedelta(days=1)
    else:
        # 今月の初日
        start_date = now.replace(day=1)
        # 今月の末日（今日まで）
        end_date = now

    # ファイルを走査
    for filename in os.listdir(directory):
        if filename.endswith('.txt'):
            try:
                # ファイル名から日時を抽出（YYYYmmdd-HHMMSS形式）
                file_date = datetime.strptime(filename[:15], '%Y%m%d-%H%M%S')
                
                # 指定月内かチェック
                if start_date <= file_date <= end_date:
                    total_minutes += 1  # 1ファイル = 1分
                    
            except ValueError:
                continue
                
    return total_minutes

def format_recording_time(minutes):
    """
    分数を「XX時間XX分」形式に変換
    """
    hours = minutes // 60
    remaining_minutes = minutes % 60
    return f"{hours}時間{remaining_minutes}分"

@app.route('/')
@login_required
def index():
    # 今月の記録時間を計算
    current_month_minutes = calculate_monthly_recording_time(session['dirname'])
    # 先月の記録時間を計算
    prev_month_minutes = calculate_monthly_recording_time(session['dirname'], 'prev')
    
    # 表示用に整形
    current_month_time = format_recording_time(current_month_minutes)
    prev_month_time = format_recording_time(prev_month_minutes)
    
    # 最終アクセス時間を記録
    if 'dirname' in session:
        access_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dirpath = os.path.join('./data/', session['dirname'])
        access_log_path = os.path.join(dirpath, "access_log.txt")
        try:
            with open(access_log_path, 'w') as f:
                f.write(access_time)
        except Exception as e:
            logger_utils.error(f"Failed to write access log: {e}")
    
    return render_template('index.html',
                         current_month_time=current_month_time,
                         prev_month_time=prev_month_time)

@app.route('/2')
@login_required
def index2():
    return render_template('index2.html')

@app.route('/archives')
@login_required
def archives():
    # クエリパラメータ's'から日時を取得
    datetime_str = request.args.get('s', None)

    # datetime_strが有効な形式か確認
    if datetime_str:
        try:
            datetime.strptime(datetime_str, '%Y%m%d-%H%M%S')
        except ValueError:
            # 無効な日時データの場合、エラーメッセージを表示するか、
            # デフォルトの動作を実行する
            return "Error: Invalid datetime format", 400

    return render_template('archives.html', datetime_str=datetime_str)


@app.route('/minutes')
@login_required
def get_minutes():
    default_start_datetime = (datetime.now() - timedelta(minutes=30)).strftime('%Y%m%d-%H%M%S')
    start_datetime = request.args.get('s', default_start_datetime)

    # 日本の日付フォーマットに変換 (例: 11月12日 15時45分)
    start_datetime_obj = datetime.strptime(start_datetime, '%Y%m%d-%H%M%S')
    
    # 終了日時を取得、もし指定されていない場合は開始時刻から30分後を設定
    end_datetime = request.args.get('e', None)
    if end_datetime is None:
        end_datetime_obj = start_datetime_obj + timedelta(minutes=30)
        end_datetime = end_datetime_obj.strftime('%Y%m%d-%H%M%S')

    # 日本の日付フォーマットに変換 (例: 11月12日 15時45分)
    start_datetime_obj = datetime.strptime(start_datetime, '%Y%m%d-%H%M%S')
    # 曜日を取得
    days = ["月", "火", "水", "木", "金", "土", "日"]
    weekday = days[start_datetime_obj.weekday()]

    # formatted_datetime = start_datetime_obj.strftime('%m月%d日 %H時%M分')
    formatted_datetime = start_datetime_obj.strftime(f'%m月%d日({weekday}) %H時%M分')

    # ここでtranscripts変数を取得するread_meeting_transcripts関数を呼び出し
    transcripts = read_meeting_transcripts(start_datetime, end_datetime)
    print(start_datetime)
    print(end_datetime)
    #print(transcripts)
    
    client = OpenAI()
    response = client.chat.completions.create(
        #model="gpt-4-1106-preview",
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "あなたはフォーマット通りに文章を要約することが得意なエディターです"},
            {"role": "user", "content": "{発言録テキスト}は会議の発言録テキストです。"
            + "#これらから、会議の主要なトピックを、行頭に番号を付与してリストして下さい。"
            + "#次にそれらのトピックタイトルごとに、2, 3文程度で要約してください"
            + "#話題になったアクションアイテムがあれば、全てを行頭に番号を付与しリストしてください。"
            + "#次回の会議で話題になりそうなことがあれば、全てを行頭に番号を付与しリストしてください。"
            + "#最後に会議のタイトルを決めて明示してください。"
            + "#発言録テキスト=\"" + transcripts + "\""
            + "#フォーマット:◼︎トピック：{改行}{主要なトピックをリスト}{改行}{改行} ◼︎トピックごとの要約：{改行}{トピックごとの要約}{改行}{改行} ◼︎アクションアイテム（Todo）：{改行}{アクションアイテムをリスト} ◼︎次回の会議の話題：{改行}{次回の会議で話題になりそうなこと} ◼︎会議のタイトル：{改行}{会議のタイトル}"
            },
        ]

    )

    summary = response.choices[0].message.content
    return render_template('minutes.html', summary=summary, day=formatted_datetime, transcripts=transcripts)


@app.route('/hc')
def hc():
    return app.send_static_file('hc.html')
    
    
@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if session.get('follower') == 1:
        # フォロワーの場合、アップロードを拒否
        flash('録音できるのは1人までです。録音している人が終わって、ログインをしなおしてください', 'warning')
        return jsonify({"message": "Upload not allowed for followers"}), 400

    if request.method == 'POST':
        audio_file = request.files['audio_data']
        if audio_file:
            timestamp = generate_timestamp()  # ここでタイムスタンプを生成
            directory = os.path.join('./data/', session['dirname'])
            text = transcription_service.transcribe(audio_file, timestamp=timestamp, dirname=session['dirname'])
            if text:
                socketio.emit('transcription', {'text': text, 'timestamp': timestamp}, room=session['user_id'])
                return jsonify({"message": "File transcribed successfully"}), 200
            else:
                return jsonify({"message": "Transcription failed"}), 400
        else:
            return jsonify({"message": "No file found"}), 400

@app.route('/update_transcription', methods=['POST'])
@login_required
def update_transcription():
    data = request.json
    filename = data['filename']
    text = data['text']

    try:
        directory = os.path.join('./data/', session['dirname'])
        with open(os.path.join(directory, f'{filename}.txt'), 'w', encoding='utf-8') as file:
            file.write(Markup.escape(text))
        return jsonify({"message": "File updated successfully"}), 200
    except IOError as e:
        return jsonify({"message": f"Failed to update file: {e}"}), 500

@app.route('/audio/<filename>')
@login_required
def audio_file(filename):
    """指定されたオーディオファイルを返す"""
    directory = os.path.join('./data/', session['dirname'])
    return send_from_directory(directory, filename)

@app.route('/img/<filename>')
@login_required
def img(filename):
    """指定されたファイルを返す"""
    directory = os.path.join('./data/', session['dirname'])
    return send_from_directory(directory, filename)

from PIL import Image
import os

@app.route('/thumbimg/<filename>')
@login_required
def thumbimg(filename):
    directory = os.path.join('./data/', session['dirname'])
    original_path = os.path.join(directory, filename)
    
    if filename.startswith("thumb_"):
        thumb_path = original_path  # サムネイルファイル名が既にthumb_で始まっている場合
    else:
        thumb_path = os.path.join(directory, f"thumb_{filename}")

    print(f"ディレクトリ: {directory}")
    print(f"オリジナル画像パス: {original_path}")
    print(f"サムネイルパス: {thumb_path}")

    if not os.path.exists(original_path):
        print("オリジナル画像が存在しません。")
        return "オリジナル画像が見つかりません", 404

    if not os.path.exists(thumb_path):
        print("サムネイルが存在しません。作成を開始します。")
        try:
            with Image.open(original_path) as img:
                img.thumbnail((100, 100))
                os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
                img.save(thumb_path, "PNG")
                print("サムネイルを保存しました。")
        except IOError as e:
            print(f"サムネイルの作成に失敗しました: {e}")
            return "サムネイルの作成に失敗しました", 500

    return send_from_directory(directory, os.path.basename(thumb_path))

@app.route('/logs')
@login_required
def get_logs():
    directory = os.path.join('./data/', session['dirname'])
    start_datetime = request.args.get('s', None)
    if not start_datetime:
        return jsonify({"error": "No start date provided"}), 400

    end_datetime = (datetime.strptime(start_datetime, '%Y%m%d-%H%M%S') + timedelta(minutes=60)).strftime('%Y%m%d-%H%M%S')

    transcripts = []
    for filename in sorted(os.listdir(directory)):
        # ファイルが.txtまたは.pngで終わるかどうかをチェック
        if (filename.endswith(".txt") or filename.endswith(".png")) and not any(suffix in filename for suffix in ['_title', '_mermaid']):
            file_datetime_str = filename[:-4]  # ファイル名から日時部分を抽出
            # ファイルの日時が指定された範囲内にあるかどうかをチェック
            if start_datetime <= file_datetime_str <= end_datetime:
                if filename.endswith(".txt"):
                    with open(f'{directory}/{filename}', 'r') as file:
                        content = file.read()
                        content = Markup.escape(content)  # .txtファイルの場合、内容をエスケープ処理
                else:
                    content = filename  # .pngファイルの場合、ファイル名をそのまま使用

                transcripts.append({'filename': file_datetime_str, 'content': content})

# transcriptsリストはファイル名に基づいて自動的に昇順でソートされます
# これは、ファイル名が日時情報を含むため、sorted(os.listdir(directory))によって保証されます
# return transcripts

    return jsonify(transcripts)

@app.route('/all_logs')
@login_required
def get_all_logs():
    directory = os.path.join('./data/', session['dirname'])
    start_datetime_str = request.args.get('s', None)
    if not start_datetime_str:
        return "No start date provided", 400
    
    # get_continuous_filesを使用
    text, file_count, total_minutes = get_continuous_files(
        start_datetime_str,
        directory,
        debug=False
    )
    
    if text:
        return format_transcripts(Markup.escape(text))
    return "No content found", 404

@app.route('/important_logs')
@login_required
def get_important_logs():
    directory = os.path.join('./data/', session['dirname'])
    start_datetime_str = request.args.get('s', None)
    if not start_datetime_str:
        return "No start date provided", 400
    
    try:
        # get_continuous_filesを使用
        text, file_count, total_minutes = get_continuous_files(
            start_datetime_str,
            directory,
            debug=False
        )
        
        if text:
            # 【と】で囲まれたテキストを抜き出す
            pattern = r'【(.*?)】'
            matches = re.findall(pattern, format_transcripts(Markup.escape(text)))
            return matches
        return []
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/latest_log')
@login_required
def get_latest_log():
    directory = os.path.join('./data/', session['dirname'])
    
    # ファイル名の日時部分を抽出するための正規表現パターン
    pattern = re.compile(r'(\d{8}-\d{6})\.txt$')

    # ディレクトリ内のファイル名をソートして最新のファイルを取得
    sorted_filenames = sorted(os.listdir(directory), reverse=True) # 最新のファイルが先頭に来るように逆順でソート
    for filename in sorted_filenames:
        match = pattern.match(filename)
        if match:
            # 最新のファイルを開いて内容を読み込む
            with open(os.path.join(directory, filename), 'r', encoding='utf-8', errors='ignore') as file:
                content = file.read()
                return format_transcripts(Markup.escape(content)) # 最新のファイルの内容を返す

    return "No valid log file found", 404 # 有効なログファイルが見つからなかった場合


def format_transcripts(text):
    # 特定の表現の後に句点と改行を挿入
    patterns_to_replace = {
        r'です ': 'です。<br>',
        r'です。 ': 'です。<br>',
        r'ですね ': 'ですね。<br>',
        r'ですね。 ': 'ですね。<br>',
        r'ます ': 'ます。<br>',
        r'ます。 ': 'ます。<br>',
        r'ません ': 'ません。<br>',
        r'ません。 ': 'ません。<br>',
        r'ますね ': 'ますね。<br>',
        r'ますね。 ': 'ますね。<br>',
        r'さい ': 'さい。<br>',
        r'さい。 ': 'さい。<br>',
        r'さいね ': 'さいね。<br>',
        r'さいね。 ': 'さいね。<br>',
        r'した ': 'した。<br>',
        r'した。 ': 'した。<br>',
        r'したね ': 'したね。<br>',
        r'したね。 ': 'したね。<br>',
        r'からね ': 'からね。<br>',
        r'からね。 ': 'からね。<br>',
        r'よね ': 'よね。<br>',
        r'よね。 ': 'よね。<br>',
        r'？ ': '？<br>',
        r'\? ': '?<br>',
    }
    
    for pattern, replacement in patterns_to_replace.items():
        text = re.sub(pattern, replacement, text)
    
    # 残りの半角空白を削除
    # text = re.sub(r' ', '、', text)

    # 行頭に】が来る場合の処理
    text = re.sub(r'<br>】', '】<br>', text)

    return text
    
# ログインページのルートを設定
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'dirname' in session:
        # メインページへ
        return redirect('/')
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # SHA-256ハッシュの生成
        hash_object = hashlib.sha256((username+password).encode())
        hashed_password = hash_object.hexdigest()

        # ディレクトリの存在チェック
        dirname = f"{username}:{hashed_password}:000000"
        dirpath = "./data/" + dirname
        if os.path.exists(dirpath):
            session['dirname'] = dirname
            session['user_id'] = dirname  # ログインしたユーザーのIDをセッションに保存
            session['username'] = username
            
            # 現在時刻より2分前を計算
            two_minutes_ago = datetime.now() - timedelta(minutes=2)

            # followerのデフォルト値を設定
            session['follower'] = 0
            
            # ログイン時間を記録
            login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            login_log_path = os.path.join(dirpath, "login_log.txt")
            try:
                with open(login_log_path, 'w') as f:
                    f.write(login_time)
            except Exception as e:
                logger_utils.error(f"Failed to write login log: {e}")

            # ディレクトリ内のファイル名をチェック
            for filename in os.listdir(dirpath):
                if filename.endswith('.txt'):
                    # ファイル名が正しい形式かチェック（8桁の数字-6桁の数字.txt）
                    if re.match(r'^\d{8}-\d{6}\.txt$', filename):
                        file_datetime_str = filename[:15]  # 'yyyymmdd-hhmmss'部分を取得
                        try:
                            file_datetime = datetime.strptime(file_datetime_str, '%Y%m%d-%H%M%S')
                            
                            if file_datetime > two_minutes_ago:
                                # session['follower'] = 1 # フォローワーをなくした
                                break
                        except ValueError:
                            # 日時のパースに失敗した場合はスキップ
                            logger_utils.warning(f"Invalid datetime format in filename: {filename}")
                            continue

            return redirect('/')
        else:
            return "ログイン失敗", 401

    # GETリクエストの場合はログインページを表示
    return render_template('login.html')

# SocketIOの接続時に呼び出される
@socketio.on('connect')
def on_connect():
    if 'dirname' in session:
        join_room(session['dirname'])

    
@app.route('/logout')
@login_required
def logout():
    # セッションからユーザー情報を削除
    session.pop('dirname', None)

    # ログインページにリダイレクト
    return redirect(url_for('login'))

@app.route('/lists')
@login_required
def lists():
    search_query = request.args.get('search', '')  # URLパラメータから検索クエリを取得

    directory = os.path.join('./data/', session['dirname'])
    files = sorted(os.listdir(directory))

    formatted_files = []
    prev_datetime = None
    days_jp = ["月", "火", "水", "木", "金", "土", "日"]

    # _title.txt を除外したファイルリストを作成
    audio_files = [f for f in files if not f.endswith('_title.txt')]

    current_group = []
    current_group_start = None

    for file in audio_files:
        try:
            file_datetime = datetime.strptime(file, '%Y%m%d-%H%M%S.txt')
            
            if not current_group_start:
                current_group_start = file_datetime
                current_group = [file]
            elif (file_datetime - prev_datetime) <= timedelta(minutes=3):
                current_group.append(file)
            else:
                # 現在のグループを処理
                if current_group:
                    formatted_datetime = current_group_start.strftime('%m月%d日(%%s) %H時%M分') % days_jp[current_group_start.weekday()]
                    base_file = current_group[0]
                    title_file = f"{'.'.join(base_file.split('.')[:-1])}_title.txt"

                    title = ""
                    if title_file in files:
                        with open(os.path.join(directory, title_file), 'r', encoding='utf-8') as f:
                            title = f.read().strip()

                    if search_query.lower() in title.lower() or search_query == '':
                        # グループの合計時間（分）を計算
                        total_minutes = len(current_group)
                        formatted_files.append((base_file[:-4], formatted_datetime, title, total_minutes))

                # 新しいグループを開始
                current_group_start = file_datetime
                current_group = [file]

            prev_datetime = file_datetime
        except ValueError:
            continue

    # 最後のグループを処理
    if current_group:
        formatted_datetime = current_group_start.strftime('%m月%d日(%%s) %H時%M分') % days_jp[current_group_start.weekday()]
        base_file = current_group[0]
        title_file = f"{'.'.join(base_file.split('.')[:-1])}_title.txt"

        title = ""
        if title_file in files:
            with open(os.path.join(directory, title_file), 'r', encoding='utf-8') as f:
                title = f.read().strip()

        if search_query.lower() in title.lower() or search_query == '':
            total_minutes = len(current_group)
            formatted_files.append((base_file[:-4], formatted_datetime, title, total_minutes))

    return render_template('lists.html', formatted_files=formatted_files, search_query=search_query)


@app.route('/summary')
@login_required
def summary():
    start_datetime_str = request.args.get('s')
    if not start_datetime_str:
        return "Error: No start date provided", 400

    try:
        start_datetime = datetime.strptime(start_datetime_str, '%Y%m%d-%H%M%S')
    except ValueError:
        return "Error: Invalid date format", 400

    directory = os.path.join('./data/', session['dirname'])
    files = sorted(os.listdir(directory))

    combined_text = ""
    prev_datetime = None
    group_started = False

    for file in files:
        if file.endswith('.txt'):
            file_name = file[:-4]
            try:
                file_datetime = datetime.strptime(file_name, '%Y%m%d-%H%M%S')
                if file_datetime < start_datetime:
                    continue  # 開始日時より前のファイルは無視する

                # print("Processing file:", file, "with datetime:", file_datetime)  # ファイルと日時のデバッグプリント

                if not prev_datetime or file_datetime - prev_datetime <= timedelta(minutes=3):
                    if not group_started:
                        start_datetime = prev_datetime or file_datetime
                        group_started = True
                    with open(os.path.join(directory, file), 'r', encoding='utf-8') as f:
                        file_text = f.read()
                        print("Adding text from file:", file)  # テキストを追加するファイルのデバッグプリント
                        combined_text += file_text + "\n"
                else:
                    print("Breaking loop, more than 3 minutes gap")  # ループ終了のデバッグプリント
                    break
                prev_datetime = file_datetime
            except ValueError:
                continue

    print("Combined text:", combined_text)  # 結合されたテキストのデバッグプリント

    # 【】で囲まれたテキストを抽出
    bracketed_texts = re.findall(r'【(.*?)】', combined_text)

    return jsonify({'bracketed_texts': bracketed_texts})


@app.route('/bulk_upload', methods=['GET', 'POST'])
@login_required
def bulk_upload():
    if request.method == 'POST':
        # ユーザーのディレクトリにファイルが存在するかチェック
        # if check_files_in_directory(session['username']):
            # for file in glob.glob(f"/tmp/{session['username']}/*"):
            #     os.remove(file)
            # return render_template('bulk_upload.html', message="変換中のファイルがありました。削除しましたので、しばらく経って再度アップロードしてください")
            # return render_template('bulk_upload.html', message="変換中のファイルがありました。")

        # 日時とファイルを取得
        date = request.form['date']  # YYYY-MM-DD
        time = request.form['time']  # HH:MM or HH:MM:SS
        audio_file = request.files['audio_file']

        # 時間文字列に秒が含まれていない場合、秒を追加
        if len(time) == 5:
            time += ":00"

        # 日時の文字列を適切な形式で生成
        datetime_format = f"{date} {time}"
        datetime_obj = datetime.strptime(datetime_format, '%Y-%m-%d %H:%M:%S')

        # ファイル名の生成（元のファイル名部分を無視）
        datetime_str = datetime_obj.strftime('%Y%m%d-%H%M%S')
        file_extension = os.path.splitext(secure_filename(audio_file.filename))[1]
        filename = f"/tmp/{session['username']}-{datetime_str}-uploaded{file_extension}"
        audio_file.save(filename)

        # 音声ファイルを1分毎に分割
        # split_audio_files(filename, datetime_str)

        # 非同期に音声ファイルを分割
        split_audio_files_async(filename, datetime_str, session['username'])

        # 即時に応答を返す
        # return render_template('bulk_upload.html', message="アップロードを完了しました。現在処理中です")

        # 処理が完了したら、bulk_uploadルートにリダイレクトしてページを更新
        return redirect(url_for('bulk_upload'))

    else:
        # ユーザーのディレクトリ内の.mp3ファイルの個数と合計容量を計算
        mp3_files = glob.glob(f"/tmp/{session['username']}/*.mp3")
        num_mp3_files = len(mp3_files)

        # ファイルの個数が0より大きい場合のみメッセージを設定
        if num_mp3_files > 0:
            total_size = sum(os.path.getsize(f) for f in mp3_files)
            total_size_mb = total_size / (1024*1024)  # 合計容量をMBで表示
            message = f"{num_mp3_files}個までのmp3ファイルが分割処理中で、合計{total_size_mb:.2f}MBです。"
            
            # ログに記録
            logger_utils.info(f"Temporary files found in /tmp/{session['username']}: {num_mp3_files} files, {total_size_mb:.2f}MB")
            
            # 処理が完了していない可能性があることを示すメッセージを追加
            # flash("処理が完了していない可能性があります。しばらく待ってから再度確認してください。", "warning")
            
            # ユーザーディレクトリにファイルが移動されているか確認
            pattern = config.get_data_pattern(session['username'])
            directories = glob.glob(pattern)
            if directories:
                target_directory = directories[0]
                # 最新のファイルの作成日時を確認
                try:
                    latest_file = max(mp3_files, key=os.path.getctime)
                    latest_time = os.path.getctime(latest_file)
                    current_time = time.time()
                    # 最新のファイルが5分以上前に作成された場合、処理が停止している可能性がある
                    if current_time - latest_time > 300:  # 5分 = 300秒
                        flash("処理が停止している可能性があります。クリーンアップボタンを押して一時ファイルを削除してください。", "danger")
                        logger_utils.warning(f"Processing may be stuck. Latest file created {(current_time - latest_time)/60:.1f} minutes ago.")
                except Exception as e:
                    logger_utils.error(f"Error checking file creation time: {e}")
        else:
            message = None  # ファイルが存在しない場合はメッセージを設定しない

        return render_template('bulk_upload.html', message=message)

@app.route('/cleanup_tmp', methods=['POST'])
@login_required
def cleanup_tmp():
    """一時ディレクトリ内のファイルをクリーンアップする"""
    username = session['username']
    tmp_directory = f"/tmp/{username}"
    
    if os.path.exists(tmp_directory):
        try:
            # ユーザーディレクトリを検索
            pattern = config.get_data_pattern(username)
            directories = glob.glob(pattern)
            
            if directories:
                target_directory = directories[0]
                logger_utils.info(f"Found target directory for cleanup: {target_directory}")
                
                # 一時ディレクトリ内のファイルをユーザーディレクトリに移動
                try:
                    moved_files = move_files_to_directory(tmp_directory, target_directory)
                    if moved_files > 0:
                        flash(f"{moved_files}個のファイルをユーザーディレクトリに移動しました", "success")
                        logger_utils.info(f"Moved {moved_files} files from {tmp_directory} to {target_directory} during cleanup")
                except Exception as e:
                    logger_utils.error(f"ファイル移動中にエラーが発生しました: {e}")
                    flash(f"ファイル移動中にエラーが発生しました: {e}", "danger")
            
            # 残りのファイルを削除
            remaining_files = 0
            for file in os.listdir(tmp_directory):
                file_path = os.path.join(tmp_directory, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    remaining_files += 1
            
            if remaining_files > 0:
                logger_utils.info(f"Removed {remaining_files} remaining files from {tmp_directory}")
            
            # ディレクトリ自体を削除
            os.rmdir(tmp_directory)
            
            flash("一時ファイルのクリーンアップが完了しました", "success")
            logger_utils.info(f"Temporary directory {tmp_directory} removed")
        except Exception as e:
            error_msg = f"クリーンアップ中にエラーが発生しました: {e}"
            logger_utils.error(error_msg)
            flash(error_msg, "danger")
            flash(f"クリーンアップ中にエラーが発生しました: {e}", "danger")
    else:
        flash("クリーンアップするファイルはありませんでした", "info")
    
    return redirect(url_for('bulk_upload'))

def check_files_in_directory(username):
    directory = f"/tmp/{username}"
    if not os.path.exists(directory):
        return False
    for filename in os.listdir(directory):
        if filename.endswith('.mp3') or filename.endswith('.txt'):
            return True
    return False

def split_audio_files(file_path, datetime_str, username):
    # 音声ファイルの全長を取得
    total_duration = get_audio_duration(file_path)
    # 必要な分割回数を計算（切り上げ）
    split_count = math.ceil(total_duration / 60)

    dirname = username

    # 分割したファイルの保存先ディレクトリ
    save_directory = f"/tmp/{username}"
    os.makedirs(save_directory, exist_ok=True)

    # ファイルの開始時刻
    start_time = datetime.strptime(datetime_str, '%Y%m%d-%H%M%S')

    for i in range(split_count):
        current_segment_start = start_time + timedelta(minutes=i)
        segment_filename = current_segment_start.strftime('%Y%m%d-%H%M%S.mp3')
        segment_path = os.path.join(save_directory, segment_filename)
        
        # テキストファイルが既に存在するかチェック
        text_filename = segment_filename.replace('.mp3', '.txt')
        text_path = os.path.join(save_directory, text_filename)
        if os.path.exists(text_path):
            print(f"Skipping transcription for {segment_filename} as the text file already exists.")
            continue  # 既に存在する場合は、このセグメントの処理をスキップ

        try:
            command = ["ffmpeg", "-y", "-i", file_path, "-acodec", "libmp3lame", "-ss", str(i * 60), "-t", "60", segment_path]
            subprocess.run(command, check=True, stderr=subprocess.PIPE)
            
            # 文字起こし処理（前回と同じ）
            transcribed_text = transcription_service.transcribe_mp3(segment_path, segment_filename, dirname=dirname)
            
            # テキストファイルの保存
            with open(text_path, 'w') as text_file:
                text_file.write(transcribed_text)

        except subprocess.CalledProcessError as e:
            print(f"Error during FFmpeg processing: {e.stderr}")
            break



    # すべての処理が完了したらファイルを移動

    # パターンに基づいてディレクトリを検索
    pattern = config.get_data_pattern(username)
    directories = glob.glob(pattern)

    # 最初に一致したディレクトリを取得（複数ある場合は最初のものが選ばれます）
    if directories:
        target_directory = directories[0]
        print("Found directory:", target_directory)
        logger_utils.info(f"Moving files from {save_directory} to {target_directory}")

        try:
            move_files_to_directory(save_directory, target_directory)
            logger_utils.info(f"Files moved successfully from {save_directory} to {target_directory}")
        except Exception as e:
            logger_utils.error(f"Error moving files from {save_directory} to {target_directory}: {e}")
            print(f"Error moving files: {e}")

    else:
        error_msg = f"No matching directory found for pattern: {pattern}"
        logger_utils.error(error_msg)
        print(error_msg)


def split_audio_files_async(file_path, datetime_str, username):
    # 新しいスレッドで split_audio_files 関数を実行
    threading.Thread(target=split_audio_files, args=(file_path, datetime_str, username)).start()

def move_files_to_directory(source_directory, target_directory):
    moved_files = 0
    for file_pattern in ['*.mp3', '*.txt']:
        for file_path in glob.glob(os.path.join(source_directory, file_pattern)):
            try:
                logger_utils.debug(f"Moving file: {file_path} to {target_directory}")
                shutil.move(file_path, target_directory)
                moved_files += 1
                logger_utils.debug(f"File moved successfully: {file_path}")
            except Exception as e:
                logger_utils.error(f"Error moving file {file_path} to {target_directory}: {e}")
                raise  # 例外を再スローして呼び出し元で処理できるようにする
    
    logger_utils.info(f"Total files moved: {moved_files}")
    return moved_files

def get_audio_duration(file_path):
    try:
        # FFmpegを使用してファイルの長さを取得
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        # 出力を浮動小数点数として解析
        duration = float(result.stdout)
        return duration
    except Exception as e:
        print(f"Error while getting audio duration: {e}")
        return 0


@app.route('/update_title', methods=['POST'])
@login_required
def update_title():
    data = request.json
    file = data['file']
    title = data['title']
    
    print(data)
    print(file)
    print(title)
    
    # `_title.txt` ファイルのパスを構築
    directory = os.path.join('./data/', session['dirname'])
    title_file_path = os.path.join(directory, f"{file}_title.txt")
    
    print(directory)
    print(title_file_path)
    
    # 新しいタイトルでファイルを更新
    try:
        with open(title_file_path, 'w', encoding='utf-8') as f:
            f.write(Markup.escape(title))
        return jsonify({"message": "Success"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    
@app.route('/generate_title', methods=['POST'])
@login_required
def generate_title():
    print("=== generate_title called ===")
    logger_utils.info("=== generate_title function started ===")
    # OpenAIクライアントのみをインポート（reとjsonはグローバルにインポート済み）
    from openai import OpenAI
    
    try:
        data = request.json
        print(f"Received data: {data}")
        logger_utils.info(f"Received data: {data}")
        file = data['file']
        print(f"File: {file}")
        logger_utils.info(f"Processing file: {file}")
        
        # テキストファイルの内容を読み取る
        directory = os.path.join('./data/', session['dirname'])
        text_file_path = os.path.join(directory, f"{file}.txt")
        title_file_path = os.path.join(directory, f"{file}_title.txt")
        
        print(f"Directory: {directory}")
        print(f"Text file path: {text_file_path}")
        print(f"Title file path: {title_file_path}")
        logger_utils.info(f"Directory: {directory}")
        logger_utils.info(f"Text file path: {text_file_path}")
        logger_utils.info(f"Title file path: {title_file_path}")
        
        # 指定されたファイルの時刻を取得
        file_datetime = datetime.strptime(file, '%Y%m%d-%H%M%S')
        logger_utils.info(f"File datetime: {file_datetime}")
        
        # 開始時刻から20分後までの範囲を設定
        start_datetime = file_datetime.strftime('%Y%m%d-%H%M%S')
        end_datetime = (file_datetime + timedelta(minutes=20)).strftime('%Y%m%d-%H%M%S')
        logger_utils.info(f"Time range: {start_datetime} to {end_datetime}")
        
        # テキストを収集
        transcripts = []
        last_valid_datetime = None
        
        # ファイル名の日時部分を抽出するための正規表現パターン
        pattern = re.compile(r'(\d{8}-\d{6})\.txt$')
        
        # ディレクトリ内のファイルを時系列順に処理
        sorted_filenames = sorted(os.listdir(directory))
        logger_utils.info(f"Found {len(sorted_filenames)} files in directory")
        for filename in sorted_filenames:
            match = pattern.match(filename)
            if match:
                current_datetime_str = match.group(1)
                current_datetime = datetime.strptime(current_datetime_str, '%Y%m%d-%H%M%S')
                logger_utils.debug(f"Checking file: {filename}, datetime: {current_datetime_str}")
                
                # 開始時刻以降、終了時刻以前のファイルを処理
                if start_datetime <= current_datetime_str <= end_datetime:
                    logger_utils.debug(f"File {filename} is within time range")
                    # 3分以上の間隔があれば、そこで終了
                    if last_valid_datetime and (current_datetime - last_valid_datetime).total_seconds() > 180:
                        logger_utils.info(f"Breaking loop due to time gap > 3 minutes after {last_valid_datetime}")
                        break
                    
                    last_valid_datetime = current_datetime
                    try:
                        with open(os.path.join(directory, filename), 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            logger_utils.debug(f"Read {len(content)} characters from {filename}")
                            transcripts.append(content)
                    except Exception as e:
                        logger_utils.error(f"Error reading file {filename}: {e}")
        
        # 全テキストを結合
        text_content = ''.join(transcripts)
        print(f"Combined text content length: {len(text_content)}")
        logger_utils.info(f"Combined {len(transcripts)} files, total text length: {len(text_content)}")
        
        # テキストが空の場合はエラーを返す
        if len(text_content.strip()) == 0:
            logger_utils.error("No text content collected for title generation")
            return jsonify({"error": "No text content available for title generation"}), 400
        
        # OpenAIのAPIを使用してタイトルを生成（サブプロセスを使用）
        print("Calling OpenAI API using subprocess...")
        logger_utils.info("Calling OpenAI API for title generation using subprocess")
        
        try:
            # サブプロセスで実行するPythonスクリプト
            script = """
import os
import json
import sys
from openai import OpenAI

def generate_title(text_content):
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return {"error": "OpenAI API key is not configured"}
            
        client = OpenAI(api_key=api_key)
        
        system_prompt = "You are an expert at generating appropriate titles from meeting content. Always generate titles in Japanese."
        user_prompt = f"Please analyze the following meeting transcript and generate a concise Japanese title (max 50 characters) that represents the main topics and purpose. Respond in this JSON format: {{\\\"title\\\": \\\"your title here\\\"}}"
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt + "\\n\\nTranscript:\\n" + text_content}
            ]
        )
        
        response_text = response.choices[0].message.content
        
        # JSONを抽出
        import re
        json_match = re.search(r'\\{[\\s\\S]*\\}', response_text)
        if json_match:
            json_str = json_match.group()
            title_data = json.loads(json_str)
            
            if 'title' not in title_data:
                return {"error": "Invalid response format from OpenAI API"}
                
            return {"title": title_data['title']}
        else:
            return {"error": "Failed to extract title from response"}
            
    except Exception as e:
        return {"error": str(e)}

# 標準入力からテキストを読み込む
text_content = sys.stdin.read()
result = generate_title(text_content)
print(json.dumps(result))
"""
            
            # 一時ファイルにスクリプトを書き込む
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
                f.write(script.encode('utf-8'))
                script_path = f.name
            
            # サブプロセスでスクリプトを実行
            import subprocess
            logger_utils.info(f"Running script in subprocess: {script_path}")
            process = subprocess.Popen(
                [sys.executable, script_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # テキストをサブプロセスに送信
            stdout, stderr = process.communicate(input=text_content)
            
            # 一時ファイルを削除
            os.unlink(script_path)
            
            if stderr:
                logger_utils.error(f"Subprocess error: {stderr}")
                return jsonify({"error": f"Error in subprocess: {stderr}"}), 500
            
            try:
                result = json.loads(stdout)
                logger_utils.info(f"Subprocess result: {result}")
                
                if "error" in result:
                    logger_utils.error(f"Error in title generation: {result['error']}")
                    return jsonify({"error": result["error"]}), 500
                
                title = result["title"]
                logger_utils.info(f"Generated title: {title}")
                
                # タイトルをファイルに保存
                try:
                    with open(title_file_path, 'w', encoding='utf-8') as f:
                        f.write(title)
                    logger_utils.info(f"Title saved to file: {title_file_path}")
                except Exception as e:
                    logger_utils.error(f"Error saving title to file: {e}")
                    # ファイル保存に失敗してもタイトルは返す
                
                return jsonify({"title": title}), 200
                
            except json.JSONDecodeError as e:
                logger_utils.error(f"JSON parsing error: {e}, stdout: {stdout}")
                return jsonify({"error": f"Failed to parse subprocess output: {e}"}), 500
                
        except Exception as e:
            logger_utils.error(f"Error in subprocess execution: {e}")
            logger_utils.error(f"Error type: {type(e)}")
            return jsonify({"error": str(e)}), 500
            
    except Exception as e:
        print(f"Error generating title: {e}")
        print(f"Error type: {type(e)}")
        logger_utils.error(f"Error in generate_title function: {e}")
        logger_utils.error(f"Error type: {type(e)}")
        return jsonify({"error": str(e)}), 500
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({"message": str(e)}), 500


@app.route('/delete_file', methods=['DELETE'])
@login_required
def delete_file():
    """指定されたオーディオファイルと関連ファイルを削除する"""
    filename = request.args.get('filename')
    if not filename:
        return jsonify({'error': 'ファイル名が指定されていません'}), 400

    # セッションからディレクトリ名を取得
    directory = os.path.join('./data/', session['dirname'])

    # セキュリティのため、実際に存在するファイルパスを確認
    audio_path = os.path.join(directory, filename + '.mp3')
    text_path = os.path.join(directory, filename + '.txt')

    # ファイルが存在するかチェック
    if not os.path.exists(audio_path) or not os.path.exists(text_path):
        return jsonify({'error': 'ファイルが見つかりません'}), 404

    # ファイルの削除
    try:
        os.remove(audio_path)
        os.remove(text_path)
        return jsonify({'message': 'ファイルが正常に削除されました'}), 200
    except Exception as e:
        return jsonify({'error': 'ファイルの削除中にエラーが発生しました', 'details': str(e)}), 500

@app.route('/search', methods=['GET'])
@login_required
def search():
    return render_template('search.html')

@app.route('/search_logs', methods=['GET'])
@login_required
def search_logs():
    search_query = request.args.get('s', None)
    if search_query:
        transcripts = []
        directory = os.path.join('./data/', session['dirname'])
        # ファイル名を逆順にソートして新しいものから古いものへと並べ替える
        for filename in sorted(os.listdir(directory), reverse=True):
            if filename.endswith(".txt") and '_title' not in filename:
                with open(f'{directory}/{filename}', 'r') as file:
                    content = file.read()
                    # コンテンツをエスケープ
                    escaped_content = Markup.escape(content)
                    if search_query.lower() in escaped_content.lower():
                        transcripts.append({'filename': filename[:-4], 'content': escaped_content})
        return jsonify(transcripts)

@app.route('/md', methods=['GET'])
@login_required
def md():
    try:
        # クエリパラメータから必要な情報を取得
        filename = request.args.get('s')
        if not filename:
            abort(400, description="Start time parameter 's' is required")
            
        # 会議テキストを取得
        meeting_text = get_meeting_text(filename)
        
        # Markdownを生成
        markdown_content = generate_mermaid_markdown(meeting_text)
        
        # content辞書を作成
        content = {
            'filename': filename,
            'markdown': markdown_content
        }
        
        return render_template('md.html', content=content)
    except Exception as e:
        # 例外をログに記録（BrokenPipeErrorはグローバルハンドラで処理される）
        app.logger.error(f"Error in /md route: {str(e)}")
        return f"エラーが発生しました: {str(e)}", 500

@app.route('/ask_question', methods=['POST'])
@login_required
def ask_question():
    try:
        data = request.get_json()
        start_time = data.get('start_time')
        question = data.get('question')

        if not start_time or not question:
            return jsonify({"error": "開始時刻と質問文が必要です"}), 400

        # 会議テキストの取得
        directory = os.path.join('./data/', session['dirname'])
        text, _, _ = get_continuous_files(start_time, directory, debug=False)
        
        if not text:
            return jsonify({"error": "会議テキストが見つかりません"}), 404

        # GPT-4に質問を投げる（サブプロセスを使用）
        logger_utils.info("Using subprocess for OpenAI API call to avoid Eventlet conflicts")
        
        # サブプロセスで実行するPythonスクリプト
        script = """
import os
import json
import sys
from openai import OpenAI

def ask_question(text, question):
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        prompt = f'''
以下は会議の発言録です。この内容を理解した上で、ユーザーからの質問に丁寧に回答してください。

会議内容：
{text}

質問：
{question}

回答は簡潔で分かりやすい日本語で、会議の内容に基づいて具体的に答えてください。
'''

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは会議アシスタントです。会議の内容について質問に答えます。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        answer = response.choices[0].message.content.strip()
        return {"success": True, "answer": answer}
    except Exception as e:
        return {"success": False, "error": str(e)}

# 標準入力からJSONを読み込む
input_data = json.loads(sys.stdin.read())
result = ask_question(input_data["text"], input_data["question"])
print(json.dumps(result))
"""
        
        # 一時ファイルにスクリプトを書き込む
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
            f.write(script.encode('utf-8'))
            script_path = f.name
        
        # サブプロセスでスクリプトを実行
        import subprocess
        import sys
        import json
        
        logger_utils.info(f"Running script in subprocess: {script_path}")
        process = subprocess.Popen(
            [sys.executable, script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # データをサブプロセスに送信
        input_data = json.dumps({"text": text, "question": question})
        stdout, stderr = process.communicate(input=input_data)
        
        # 一時ファイルを削除
        os.unlink(script_path)
        
        if stderr:
            logger_utils.error(f"Subprocess error: {stderr}")
            return jsonify({"error": "回答の取得に失敗しました"}), 500
        
        try:
            result = json.loads(stdout)
            logger_utils.info(f"Subprocess result: {result}")
            
            if not result.get("success"):
                logger_utils.error(f"Error in question answering: {result.get('error')}")
                return jsonify({"error": "回答の取得に失敗しました"}), 500
            
            answer = result["answer"]
            return jsonify({"answer": answer})
        except Exception as e:
            logger_utils.error(f"Failed to parse result from subprocess: {str(e)}")
            return jsonify({"error": "回答の解析に失敗しました"}), 500
    
    except Exception as e:
        logger_utils.error(f"Unexpected error in ask_question: {str(e)}")
        return jsonify({"error": "予期しないエラーが発生しました"}), 500


def get_continuous_files(start_datetime_str, base_dir, debug=True):  # デバッグを常に有効に
    """
    指定された開始時刻から3分以内の間隔で続くファイルをグループ化し、その内容を結合する汎用関数
    
    Args:
        start_datetime_str (str): 開始時刻（YYYYmmdd-HHMMSS形式）
        base_dir (str): ファイルが格納されているディレクトリのパス
        debug (bool): デバッグ情報を出力するかどうか（デフォルトはFalse）
    
    Returns:
        tuple: (結合されたテキスト, ファイル数, 合計時間（分）)
               ファイルが見つからない場合は (None, 0, 0)
    """
    if debug:
        print(f"=== 連続ファイル処理開始 ===")
        print(f"Start datetime: {start_datetime_str}")
        print(f"Base directory: {base_dir}")

    # ディレクトリ内のファイルを取得
    try:
        files = sorted(os.listdir(base_dir))
    except OSError as e:
        if debug:
            print(f"Error reading directory: {e}")
        return None, 0, 0

    # _title.txt を除外したファイルリストを作成
    txt_files = [f for f in files if f.endswith('.txt')
                 and not f.endswith('_title.txt')
                 and not f.endswith('_mermaid.txt')]
    if debug:
        print(f"filtered txt_files: {len(txt_files)} files found")
    
    try:
        target_datetime = datetime.strptime(start_datetime_str, '%Y%m%d-%H%M%S')
    except ValueError as e:
        if debug:
            print(f"Error parsing start datetime: {e}")
        return None, 0, 0

    current_group = []
    prev_datetime = None
    found_target = False
    
    if debug:
        print(f"=== get_continuous_files ===")
        print(f"start_datetime_str: {start_datetime_str}")
        print(f"Number of txt_files: {len(txt_files)}")
    
    # ファイルをグループ化
    for file in txt_files:
        try:
            file_datetime = datetime.strptime(file[:-4], '%Y%m%d-%H%M%S')
            if debug:
                print(f"checking file: {file}, datetime: {file_datetime}")
            
            # 対象のファイルを見つけた場合、そこから処理を開始
            if file[:-4] == start_datetime_str:
                found_target = True
                current_group = [file]
                prev_datetime = file_datetime
                print(f"Found target file: {file}")
                continue
            
            # 対象ファイルを見つけた後の処理
            if found_target:
                # 前のファイルから3分以内なら同じグループ
                if (file_datetime - prev_datetime) <= timedelta(minutes=3):
                    current_group.append(file)
                    if debug:
                        print(f"Adding file: {file} (interval: {(file_datetime - prev_datetime).seconds / 60:.1f} min)")
                    prev_datetime = file_datetime
                else:
                    if debug:
                        print(f"Breaking at file: {file} (interval: {(file_datetime - prev_datetime).seconds / 60:.1f} min)")
                    break
            
        except ValueError:
            continue
    
    if not current_group:
        if debug:
            print("No files found in group")
            print(f"found_target: {found_target}")
        return None, 0, 0
    
    # グループ内のすべてのファイルの内容を結合（ファイル名でソート）
    all_text = ""
    total_chars = 0
    
    if debug:
        print(f"\n=== ファイル処理（昇順）===")
        print(f"Total files: {len(current_group)}")
    
    for txt_file in sorted(current_group):
        try:
            with open(os.path.join(base_dir, txt_file), 'r', encoding='utf-8') as f:
                content = f.read()
                all_text += content + "\n"
                total_chars += len(content)
                if debug:
                    print(f"Read: {txt_file} ({len(content)} chars)")
        except IOError as e:
            if debug:
                print(f"Error reading file {txt_file}: {e}")
            continue
    
    if debug:
        print(f"Total text length: {total_chars} characters")
    
    return all_text, len(current_group), len(current_group)  # 1ファイル = 1分

def get_meeting_text(filename):
    """指定された会議の発言録を取得（3分以内の間隔のファイルをまとめて）"""
    directory = os.path.join('data/', session['dirname'])
    text, _, _ = get_continuous_files(filename, directory, debug=False)
    return text

def generate_mermaid_markdown(text, filename=None):
    """会議の発言録からMermaid形式のMarkdownを生成"""
    if not text:
        return "会議の内容が見つかりません。"

    directory = os.path.join('data/', session['dirname'])
    
    # キャッシュファイルのパスを生成
    timestamp = filename or request.args.get('s')
    if not timestamp:
        return "タイムスタンプが指定されていません。"
    
    cache_filename = timestamp + '_mermaid.txt'
    cache_path = os.path.join(directory, cache_filename)
    
    # キャッシュが存在する場合はそれを返す
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    # キャッシュがない場合は新規生成
    # サブプロセスでOpenAI APIを呼び出す
    import subprocess
    import sys
    import json
    
    logger_utils.info("Using subprocess for OpenAI API call to avoid Eventlet conflicts")
    
    # Pythonスクリプトを文字列として作成
    script = f'''
import sys
import os
import json
from openai import OpenAI
import time

def generate_markdown():
    try:
        client = OpenAI(api_key="{os.getenv('OPENAI_API_KEY')}")
        
        prompt = """以下の会議発言録を分析し、Mermaid形式のグラフで構造化してください。

要件：
1. ルートノードは1つとし、会議全体のテーマを表現してください
2. 階層の深さは固定せず、トピックの性質に応じて柔軟に設定してください：
   - 全体の流れを、明確に章・節・項に分け、ノードとして短く簡潔に表現すること
   - 末端のノードは**50文字以上**で詳細に表現すること（厳守）
3. mermaidはgraph LRで作成してください。graph TBは使わないでください。


例：
```mermaid
graph LR
  Root[会議テーマ] --> A[重要トピック]
  Root --> B[シンプルな議題]
  
  A --> A1(詳細項目1)
  A --> A2(詳細項目2)
  A1 --> A1a[結論：具体的な実施事項]
  A1 --> A1b[結論：検討事項]
  A2 --> A2a[結論：決定事項]
  
  B --> B1[結論：即時対応事項]
```

会議発言録：
{text}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {{
                    "role": "system",
                    "content": "あなたは会議の発言録を分析し、Mermaid形式のグラフで構造化することが得意なアシスタントです。"
                }},
                {{
                    "role": "user",
                    "content": prompt
                }}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        return {{"success": True, "content": response.choices[0].message.content}}
    except Exception as e:
        return {{"success": False, "error": str(e)}}

result = generate_markdown()
print(json.dumps(result))
'''
    
    try:
        logger_utils.debug("Starting subprocess for OpenAI API call")
        # サブプロセスでスクリプトを実行
        result = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True,
            text=True,
            timeout=60  # 60秒のタイムアウト
        )
        
        if result.returncode != 0:
            logger_utils.error(f"Subprocess failed with return code {result.returncode}")
            logger_utils.error(f"STDERR: {result.stderr}")
            raise Exception(f"OpenAI API call failed: {result.stderr}")
        
        # JSON結果をパース
        response_data = json.loads(result.stdout.strip())
        
        if response_data.get("success"):
            markdown_content = response_data["content"]
            
            # キャッシュに保存
            with open(cache_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
                
            return markdown_content
        else:
            error_msg = response_data.get("error", "Unknown error")
            logger_utils.error(f"OpenAI API call failed: {error_msg}")
            raise Exception(f"OpenAI API call failed: {error_msg}")
            
    except subprocess.TimeoutExpired:
        logger_utils.error("OpenAI API call timed out")
        raise Exception("OpenAI API call timed out")
    except json.JSONDecodeError as e:
        logger_utils.error(f"Failed to parse subprocess output: {e}")
        logger_utils.error(f"Raw output: {result.stdout}")
        raise Exception(f"Failed to parse OpenAI API response: {e}")
    except Exception as e:
        logger_utils.error(f"Error generating Mermaid markdown: {e}")
        raise


# Basic認証を実装する関数
def check_auth(username, password):
    """Basic認証のユーザー名とパスワードを検証する"""
    return username == os.getenv('ADMIN_USERNAME') and password == os.getenv('ADMIN_PASSWORD')

def authenticate():
    """Basic認証を要求するレスポンスを返す"""
    return Response(
        'Basic認証が必要です', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    """Basic認証を要求するデコレータ"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# ユーザー情報を取得する関数
def get_user_info():
    """すべてのユーザーの情報を取得する"""
    users = []
    data_dir = "./data/"
    
    # dataディレクトリ内のすべてのディレクトリを取得
    for dirname in os.listdir(data_dir):
        dirpath = os.path.join(data_dir, dirname)
        if os.path.isdir(dirpath) and ":" in dirname:
            parts = dirname.split(":")
            if len(parts) >= 2:
                username = parts[0]
                
                # ファイル数とストレージ使用量を計算
                file_count = 0
                storage_usage = 0
                file_dates = defaultdict(int)
                last_access_time = None
                latest_file_mtime = 0
                
                # ディレクトリ内のファイルを走査
                for filename in os.listdir(dirpath):
                    filepath = os.path.join(dirpath, filename)
                    if os.path.isfile(filepath):
                        file_count += 1
                        storage_usage += os.path.getsize(filepath)
                        
                        # 最新のファイルの更新日時を取得
                        file_mtime = os.path.getmtime(filepath)
                        if file_mtime > latest_file_mtime:
                            latest_file_mtime = file_mtime
                        
                        # 日付ごとのファイル数を集計
                        if filename.endswith('.txt') or filename.endswith('.mp3'):
                            try:
                                date_part = filename[:8]  # YYYYMMDDの部分を取得
                                file_dates[date_part] += 1
                            except:
                                pass
                
                # 最終アクセス時間を設定（最新のファイルの更新日時）
                if latest_file_mtime > 0:
                    last_access_time = datetime.fromtimestamp(latest_file_mtime).strftime("%Y-%m-%d %H:%M:%S")
                
                # ユーザー情報を追加
                users.append({
                    'username': username,
                    'file_count': file_count,
                    'storage_usage': f"{storage_usage / (1024 * 1024):.2f} MB",
                    'file_dates': dict(sorted(file_dates.items(), reverse=True)),
                    'last_access': last_access_time or "記録なし"
                })
    
    return sorted(users, key=lambda x: x['username'])

# ユーザー管理ページのルート
@app.route('/admin')
@requires_auth
def admin():
    """ユーザー管理ページを表示する"""
    users = get_user_info()
    return render_template('admin.html', users=users)

# ユーザー追加
@app.route('/admin/add_user', methods=['POST'])
@requires_auth
def add_user():
    """新規ユーザーを追加する"""
    username = request.form.get('username')
    password = request.form.get('password')
    
    if not username or not password:
        flash('ユーザー名とパスワードは必須です', 'error')
        return redirect(url_for('admin'))
    
    # SHA-256ハッシュの生成
    hash_object = hashlib.sha256((username+password).encode())
    hashed_password = hash_object.hexdigest()
    
    # ディレクトリ名の作成
    dirname = f"{username}:{hashed_password}:000000"
    dirpath = os.path.join('./data/', dirname)
    
    # 既存ユーザーのチェック
    if os.path.exists(dirpath):
        flash('そのユーザー名は既に使用されています', 'error')
        return redirect(url_for('admin'))
    
    try:
        # ユーザーディレクトリの作成
        os.makedirs(dirpath, exist_ok=True)
        logger_utils.info(f"新規ユーザーを作成しました: {username}")
        flash(f'ユーザー {username} を追加しました', 'success')
    except Exception as e:
        logger_utils.error(f"ユーザー作成エラー: {e}")
        flash('ユーザー作成中にエラーが発生しました', 'error')
    
    return redirect(url_for('admin'))

# パスワード再設定
@app.route('/admin/reset_password', methods=['POST'])
@requires_auth
def reset_password():
    """ユーザーのパスワードを再設定する"""
    username = request.form.get('username')
    new_password = request.form.get('new_password')
    
    if not username or not new_password:
        flash('ユーザー名と新しいパスワードは必須です', 'error')
        return redirect(url_for('admin'))
    
    # 既存のユーザーディレクトリを検索
    data_dir = './data/'
    user_dir = None
    
    for dirname in os.listdir(data_dir):
        dirpath = os.path.join(data_dir, dirname)
        if os.path.isdir(dirpath) and dirname.startswith(f"{username}:"):
            user_dir = dirname
            break
    
    if not user_dir:
        flash('指定されたユーザーが見つかりません', 'error')
        return redirect(url_for('admin'))
    
    # 新しいハッシュの生成
    hash_object = hashlib.sha256((username+new_password).encode())
    new_hashed_password = hash_object.hexdigest()
    
    # 新しいディレクトリ名
    old_dirpath = os.path.join(data_dir, user_dir)
    new_dirname = f"{username}:{new_hashed_password}:000000"
    new_dirpath = os.path.join(data_dir, new_dirname)
    
    try:
        # ディレクトリ名を変更
        os.rename(old_dirpath, new_dirpath)
        logger_utils.info(f"ユーザーのパスワードを再設定しました: {username}")
        flash(f'ユーザー {username} のパスワードを再設定しました', 'success')
    except Exception as e:
        logger_utils.error(f"パスワード再設定エラー: {e}")
        flash('パスワード再設定中にエラーが発生しました', 'error')
    
    return redirect(url_for('admin'))

# ユーザー削除
@app.route('/admin/delete_user', methods=['POST'])
@requires_auth
def delete_user():
    """ユーザーとそのデータを削除する"""
    username = request.form.get('username')
    
    if not username:
        flash('ユーザー名は必須です', 'error')
        return redirect(url_for('admin'))
    
    # 既存のユーザーディレクトリを検索
    data_dir = './data/'
    user_dir = None
    
    for dirname in os.listdir(data_dir):
        dirpath = os.path.join(data_dir, dirname)
        if os.path.isdir(dirpath) and dirname.startswith(f"{username}:"):
            user_dir = dirname
            break
    
    if not user_dir:
        flash('指定されたユーザーが見つかりません', 'error')
        return redirect(url_for('admin'))
    
    dirpath = os.path.join(data_dir, user_dir)
    
    try:
        # ディレクトリとその中身を削除
        shutil.rmtree(dirpath)
        logger_utils.info(f"ユーザーを削除しました: {username}")
        flash(f'ユーザー {username} を削除しました', 'success')
    except Exception as e:
        logger_utils.error(f"ユーザー削除エラー: {e}")
        flash('ユーザー削除中にエラーが発生しました', 'error')
    
    return redirect(url_for('admin'))

@app.route('/edit_md/<filename>', methods=['GET', 'POST'])
def edit_md(filename):
    md_path = os.path.join('data/' , session['dirname'], filename + '_mermaid.txt')
    print(md_path)
    
    if request.method == 'POST':
        content = request.form['content']
        with open(md_path, 'w') as f:
            f.write(content)
        return redirect(url_for('md', s=filename))

    content = ""
    if os.path.exists(md_path):
        with open(md_path, 'r') as f:
            content = f.read()
    
    # ファイルが存在しないか、ファイルが空の場合
    if not os.path.exists(md_path) or not content.strip():
        # 新規Markdown生成
        meeting_text = get_meeting_text(filename)
        if meeting_text:
            content = generate_mermaid_markdown(meeting_text, filename)
            # mdディレクトリが存在しない場合は作成
            os.makedirs(os.path.dirname(md_path), exist_ok=True)
            # 生成したMarkdownを保存
            with open(md_path, 'w') as f:
                f.write(content)
            # /mdにリダイレクト
            return redirect(url_for('md', s=filename))

    return render_template('edit_md.html', filename=filename, content=content)


# データディレクトリの作成
if not os.path.exists("./data"):
    os.makedirs("./data")

# 開発サーバー起動（python app.pyで直接実行した場合のみ）
if __name__ == '__main__':
    # ソケットオプションを直接設定
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    
    # ポート5000をバインドしてリッスン
    try:
        sock.bind(('0.0.0.0', 5000))
        sock.listen(5)
        print("Socket bound successfully")
    except OSError as e:
        print(f"Socket binding failed: {e}")
        # すでにバインドされている場合は、既存のソケットを閉じる
        import os, signal
        for pid in os.popen(f"lsof -t -i:5000").read().split():
            try:
                os.kill(int(pid), signal.SIGTERM)
                print(f"Killed process {pid}")
            except ProcessLookupError:
                pass
        # 少し待ってから再試行
        import time
        time.sleep(1)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', 5000))
        sock.listen(5)
    
    # ソケットを閉じる（Flask-SocketIOが新しいソケットを作成するため）
    sock.close()
    
    # Eventletを使用してアプリケーションを実行
    # 注：eventletのmonkey_patchはファイルの先頭ですでに実行済み
    # 環境変数DEBUG_MODEがtrueの場合はデバッグモードを有効にする
    debug_mode = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
    socketio.run(app, debug=debug_mode, host="0.0.0.0", port=5000)
