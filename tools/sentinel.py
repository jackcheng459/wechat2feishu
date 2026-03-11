
import json
import time
import os
import sqlite3
import feedparser
from pathlib import Path
import subprocess

# 基础路径配置
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "tools" / "history.db"
CONFIG_PATH = PROJECT_ROOT / "tools" / "sentinel_config.json"
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
        cmd = [str(PYTHON_EXEC), str(PROJECT_ROOT / "scripts" / "main.py")] + args
        print(f"🚀 执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            print(f"❌ 执行失败: {result.stderr.strip()}")
            return False, result.stderr.strip()
    except Exception as e:
        print(f"💥 异常: {e}")
        return False, str(e)


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
                ok1, out1 = run_command(["scrape", url])
                if ok1:
                    # 2. 执行保存 (Save)
                    save_args = ["save", "--dest-type", feed.get("dest_type", "root")]
                    if feed.get("dest_token"):
                        save_args += ["--dest-token", feed["dest_token"]]
                    if feed.get("node_token"):
                        save_args += ["--node-token", feed["node_token"]]
                    
                    ok2, out2 = run_command(save_args)
                    if ok2:
                        mark_as_processed(url, title)
                        print(f"🎉 文章 '{title}' 已全自动入库！")
                        
                        # 尝试提取 Feishu 链接
                        feishu_url = ""
                        try:
                            # main.py 的输出可能包含多行 JSON，我们需要找到最后一行
                            lines = out2.strip().split("\n")
                            for line in reversed(lines):
                                try:
                                    data = json.loads(line)
                                    if "document_url" in data:
                                        feishu_url = data["document_url"]
                                        break
                                except: continue
                        except: pass

                        # 发送通知
                        notify_msg = f"🛰️ 哨兵巡逻报告\n\n新文章：《{title}》\n已成功自动转存至飞书。\n\n🔗 飞书链接: {feishu_url}\n🌐 原文链接: {url}"
                        run_command(["notify", notify_msg])
            else:
                # 已处理过的跳过
                pass

def list_feeds():
    if not CONFIG_PATH.exists():
        print("⚠️ 配置文件不存在。")
        return
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    print("\n🛰️ 当前巡逻中的情报源：")
    for i, feed in enumerate(config.get("feeds", []), 1):
        print(f"{i}. [{feed['name']}] URL: {feed['url']}")
        print(f"   目标: {feed.get('dest_type')} ({feed.get('dest_token', '默认')})")

def add_feed(name, url, dest_type="root", dest_token="", node_token=""):
    if not CONFIG_PATH.exists():
        config = {"feeds": [], "check_interval_minutes": 60}
    else:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    
    config["feeds"].append({
        "name": name,
        "url": url,
        "dest_type": dest_type,
        "dest_token": dest_token,
        "node_token": node_token
    })
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"✅ 已添加情报源: {name}")

def remove_feed(index):
    if not CONFIG_PATH.exists(): return
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    try:
        removed = config["feeds"].pop(index - 1)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"✅ 已移除情报源: {removed['name']}")
    except IndexError:
        print("❌ 索引无效。")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="WeChat2Feishu-Pro 哨兵 (Sentinel)")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("run", help="启动巡逻任务")
    sub.add_parser("run-once", help="运行一次巡逻任务并退出")
    
    sub.add_parser("list-feeds", help="列出所有情报源")
    
    p_add = sub.add_parser("add-feed", help="添加情报源")
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--url", required=True)
    p_add.add_argument("--dest-type", default="root", choices=["root", "folder", "wiki"])
    p_add.add_argument("--dest-token", default="")
    p_add.add_argument("--node-token", default="")
    
    p_rem = sub.add_parser("remove-feed", help="移除情报源")
    p_rem.add_argument("--index", type=int, required=True)

    args = parser.parse_args()

    init_db()
    
    if args.command == "run-once":
        print("🛰️ WeChat2Feishu-Pro Sentinel 启动单次巡逻...")
        check_feeds()
        print("✅ 任务完成。")
    elif args.command == "list-feeds":
        list_feeds()
    elif args.command == "add-feed":
        add_feed(args.name, args.url, args.dest_type, args.dest_token, args.node_token)
    elif args.command == "remove-feed":
        remove_feed(args.index)
    else:
        # 默认运行模式
        print("🛰️ WeChat2Feishu-Pro Sentinel 启动持续巡逻模式...")
        while True:
            check_feeds()
            interval = 60
            try:
                with open(CONFIG_PATH, "r") as f:
                    interval = json.load(f).get("check_interval_minutes", 60)
            except: pass
            print(f"💤 巡逻完毕，{interval} 分钟后再次出发...")
            time.sleep(interval * 60)

