
import json
import time
import os
import sqlite3
import feedparser
from pathlib import Path
import subprocess

# 基础路径配置
PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / "history.db"
CONFIG_PATH = PROJECT_ROOT / "sentinel_config.json"
PYTHON_EXEC = PROJECT_ROOT / ".venv" / "bin" / "python"

def init_db():
    """初始化历史记录数据库，防止重复转存"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS processed_articles
                 (url TEXT PRIMARY KEY, title TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def is_processed(url):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM processed_articles WHERE url=?", (url,))
    res = c.fetchone()
    conn.close()
    return res is not None

def mark_as_processed(url, title):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO processed_articles (url, title) VALUES (?, ?)", (url, title))
    conn.commit()
    conn.close()

def run_command(args):
    """通过 subprocess 调用 main.py"""
    try:
        cmd = [str(PYTHON_EXEC), str(PROJECT_ROOT / "main.py")] + args
        print(f"🚀 执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ 执行成功: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ 执行失败: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"💥 异常: {e}")
        return False

def check_feeds():
    if not CONFIG_PATH.exists():
        print(f"⚠️ 配置文件不存在: {CONFIG_PATH}")
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    for feed in config.get("feeds", []):
        print(f"🔍 正在巡逻: {feed['name']}")
        d = feedparser.parse(feed["url"])
        
        for entry in d.entries:
            url = entry.link
            title = entry.title
            
            if not is_processed(url):
                print(f"🆕 发现新文章: {title}")
                
                # 1. 执行抓取 (Scrape)
                if run_command(["scrape", url]):
                    # 2. 执行保存 (Save)
                    save_args = ["save", "--dest-type", feed.get("dest_type", "root")]
                    if feed.get("dest_token"):
                        save_args += ["--dest-token", feed["dest_token"]]
                    if feed.get("node_token"):
                        save_args += ["--node-token", feed["node_token"]]
                    
                    if run_command(save_args):
                        mark_as_processed(url, title)
                        print(f"🎉 文章 '{title}' 已全自动入库！")
            else:
                # 已处理过的跳过
                pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="只运行一次巡逻")
    args = parser.parse_args()

    init_db()
    print("🛰️ WeChat2Feishu-Pro Sentinel 启动...")
    
    if args.once:
        check_feeds()
        print("✅ 单次巡逻任务完成。")
    else:
        while True:
            check_feeds()
            # 根据配置设定检查间隔
            interval = 60 # 默认 1 小时
            try:
                with open(CONFIG_PATH, "r") as f:
                    interval = json.load(f).get("check_interval_minutes", 60)
            except: pass
            
            print(f"💤 巡逻完毕，{interval} 分钟后再次出发...")
            time.sleep(interval * 60)

