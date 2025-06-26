import os
import re
from collections import defaultdict

def count_txt_files_by_date(directory):
    # 日付ごとのファイルカウントを保持する辞書
    date_counts = defaultdict(int)
    
    # 指定ディレクトリ内の全ファイルを走査
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if filename.endswith('.txt'):
                # ファイル名から日付部分を抽出（YYYYMMDD形式）
                match = re.search(r'\d{8}', filename)
                if match:
                    date = match.group(0)
                    date_counts[date] += 1
    
    return date_counts

def main():
    base_directory = './data'  # ターゲットとする基本ディレクトリを設定
    
    # base_directory内のサブディレクトリを走査
    for item in os.listdir(base_directory):
        item_path = os.path.join(base_directory, item)
        if os.path.isdir(item_path):
            # サブディレクトリ内の.txtファイルの日付ごとのカウントを取得
            date_counts = count_txt_files_by_date(item_path)
            if date_counts:  # サブディレクトリに.txtファイルが存在する場合のみ表示
                print(f"サブディレクトリ: {item}")
                # 日付の降順で結果を表示
                for date, count in sorted(date_counts.items(), reverse=True):
                    print(f"{date}: {count}個")
                print("----------------------------")

if __name__ == '__main__':
    main()
