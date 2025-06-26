# Kururin

## Overview
Kururin is a real-time meeting transcription and summarization tool that helps you capture and organize your meetings efficiently. Using OpenAI's Whisper for speech-to-text and GPT models for summarization, Kururin provides accurate transcriptions and insightful summaries of your meetings, making it easier to review and share important discussions.

## Installation
To install and run Kururin, follow these steps:

1. Clone the repository:
   ```
   git clone https://github.com/daishir0/kururin.git
   cd kururin
   ```

2. Create and activate a virtual environment (recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   - Copy `.env.sample` to `.env`
   - Edit `.env` and add your OpenAI API key and other required settings

5. Create necessary directories:
   ```
   mkdir -p data temp logs
   ```

6. Run the application:
   ```
   python app.py
   ```
   or use the provided scripts:
   ```
   bash debug.sh  # For development
   bash production.sh  # For production
   ```

## Usage
1. Open your browser and navigate to `http://localhost:5000`
2. Log in with your credentials
3. Click "文字おこしを開始する" (Start Transcription) to begin recording
4. Speak clearly into your microphone
5. The application will automatically transcribe your speech in one-minute intervals
6. View the transcription in real-time on the screen
7. Access previous recordings through the "一覧" (List) button
8. Search for specific content using the "検索" (Search) function
9. Generate meeting summaries by selecting a recording and clicking on the minutes option

## Notes
- The application requires an active internet connection to use OpenAI's API services
- FFmpeg is required for audio processing
- For optimal transcription quality, use a good microphone and speak clearly
- The application tracks recording time on a monthly basis
- Multiple users can view the same transcription, but only one user can record at a time

## License
This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements
Special thanks to Tachikawa City for use of Kururin, their mascot character, as the application's icon.

---

# くるりん

## 概要
くるりんは、会議をリアルタイムで文字起こしし、要約するツールです。OpenAIのWhisperによる音声認識とGPTモデルによる要約機能を使用して、会議の正確な文字起こしと洞察に富んだ要約を提供し、重要な議論の振り返りと共有を容易にします。

## インストール方法
くるりんをインストールして実行するには、以下の手順に従ってください：

1. リポジトリをクローンします：
   ```
   git clone https://github.com/daishir0/kururin.git
   cd kururin
   ```

2. 仮想環境を作成してアクティブ化します（推奨）：
   ```
   python -m venv venv
   source venv/bin/activate  # Windowsの場合: venv\Scripts\activate
   ```

3. 必要な依存関係をインストールします：
   ```
   pip install -r requirements.txt
   ```

4. 環境変数を設定します：
   - `.env.sample`を`.env`にコピーします
   - `.env`を編集して、OpenAI APIキーやその他の必要な設定を追加します

5. 必要なディレクトリを作成します：
   ```
   mkdir -p data temp logs
   ```

6. アプリケーションを実行します：
   ```
   python app.py
   ```
   または提供されているスクリプトを使用します：
   ```
   bash debug.sh  # 開発用
   bash production.sh  # 本番用
   ```

## 使い方
1. ブラウザを開き、`http://localhost:5000`にアクセスします
2. 認証情報でログインします
3. 「文字おこしを開始する」ボタンをクリックして録音を開始します
4. マイクに向かってはっきりと話します
5. アプリケーションは1分間隔で自動的に音声を文字起こしします
6. 画面上でリアルタイムに文字起こし結果を確認できます
7. 「一覧」ボタンから過去の録音にアクセスできます
8. 「検索」機能を使用して特定の内容を検索できます
9. 録音を選択して議事録オプションをクリックすると、会議の要約を生成できます

## 注意点
- アプリケーションはOpenAI APIサービスを使用するためにインターネット接続が必要です
- 音声処理にはFFmpegが必要です
- 最適な文字起こし品質を得るには、良質なマイクを使用し、はっきりと話してください
- アプリケーションは月単位で録音時間を追跡します
- 複数のユーザーが同じ文字起こしを閲覧できますが、録音できるのは一度に1人のユーザーのみです

## ライセンス
このプロジェクトはMITライセンスの下でライセンスされています。詳細はLICENSEファイルを参照してください。

## 謝辞
アプリケーションのアイコンとして、大好きな立川市のマスコットキャラクター「くるりん」を使用させていただいております。ありがとうございます。