#!/usr/bin/env python3
import argparse
import getpass
import json
import os


CONFIG_DIR = os.environ.get("ZECTRIX_NBA_CONFIG_DIR", os.path.expanduser("~/.config/zectrix-nba-board"))
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def main():
    parser = argparse.ArgumentParser(description="初始化 Zectrix NBA 看板配置")
    parser.add_argument("--api-key")
    parser.add_argument("--device")
    parser.add_argument("--page", default="3")
    args = parser.parse_args()
    api_key = args.api_key or getpass.getpass("Zectrix API Key（zt_ 开头）：")
    device = args.device or input("设备 ID（MAC）：").strip()
    if not api_key or not device:
        parser.error("API Key 和设备 ID 都不能为空")
    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as handle:
        json.dump({"api_key": api_key, "device_id": device, "page": str(args.page)}, handle, ensure_ascii=False, indent=2)
    os.chmod(CONFIG_FILE, 0o600)
    print("配置已写入：%s" % CONFIG_FILE)


if __name__ == "__main__":
    main()
