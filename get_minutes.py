import sys
import os
from dotenv import load_dotenv
# 環境変数を読み込む
load_dotenv()

from datetime import datetime
from openai import OpenAI
import openai
import httpx

def read_meeting_transcripts(start_datetime, end_datetime, directory):
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

def main(start_datetime, end_datetime):
    transcripts = read_meeting_transcripts(start_datetime, end_datetime, './data/')
    # print("会議の発言録テキスト：\n", transcripts)

    client = OpenAI(
        api_key=os.getenv('OPENAI_API_KEY')
    )
    response = client.chat.completions.create(
        model=os.getenv('OPENAI_CHAT_MODEL', 'gpt-4o-mini'),
        messages=[
            {"role": "system", "content": "あなたは文章を要約することが得意なエディターです"},
            {"role": "user", "content": "以下のテキストは会議の発言録テキストです。"
             + "１）これらから、会議の主要なトピックタイトルを提示して下さい。"
             + "２）その後にそれらのトピックタイトルごとに、要約してそれぞれ300文字程度でおもしろくまとめてください"
             + "３）その後、もしこの会議で話題になったアクションアイテムがあれば、(TODO)を行頭において、全てをリストで提示してください"
             + "４）最後に、この会議を効率化する改善案をだしてください。"
             + transcripts},
        ]
    )

    # APIからの応答を表示
    print(response.choices[0].message.content)

if __name__ == "__main__":
    # Take command line arguments for the start datetime, and optional for the end datetime
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python get_minutes.py yyyymmdd-hhmmss [yyyymmdd-hhmmss]")
        sys.exit(1)

    start_datetime_arg = sys.argv[1]
    end_datetime_arg = sys.argv[2] if len(sys.argv) == 3 else None  # Optional end datetime
    
    main(start_datetime_arg, end_datetime_arg)
