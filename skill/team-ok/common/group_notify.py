#!/usr/bin/env python3
"""群通报模块 — 发送 Telegram 群通知。"""

import sys
from pathlib import Path
import os
import json
import subprocess
from datetime import datetime

sys.path.insert(0, str(Path.home() / '.openclaw' / 'skills' / 'team-ok'))
from common.config import GROUP_NOTIFY_URL_TIMEOUT, GROUP_NOTIFY_TIMEOUT


def send_group_notification(project_id: str, message: str):
    """发送群通报到 Telegram。"""
    try:
        from common.logger import get_skill_logger
        skill_logger = get_skill_logger(project_id)
        skill_logger.info(f"[GROUP_NOTIFY_START] project={project_id}, msg_len={len(message)}", extra={'skill_name': 'GROUP_NOTIFY'})
    except Exception:
        skill_logger = None

    # 获取项目目录
    project_dir = Path.home() / f".openclaw/tasks/projects/{project_id}"

    # 构建 Telegram 通知消息
    telegram_message = f"""🤖 团队协作通知

{message}

项目 ID: {project_id}
时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}"""

    # 方法 1: 通过 Telegram Bot API 直接发送
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if telegram_token and telegram_chat_id:
        import urllib.request
        import urllib.parse

        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": telegram_chat_id,
            "text": telegram_message,
            "parse_mode": "Markdown"
        }).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=GROUP_NOTIFY_URL_TIMEOUT) as response:
                result = json.loads(response.read().decode("utf-8"))
                if result.get("ok"):
                    if skill_logger:
                        skill_logger.info(f"[GROUP_NOTIFY_TELEGRAM_SUCCESS] project={project_id}", extra={'skill_name': 'GROUP_NOTIFY'})
                    print(f"✅ 群通报已发送: {message[:50]}...")
                    return True
                else:
                    err_desc = result.get('description', 'unknown')
                    if skill_logger:
                        skill_logger.error(f"[GROUP_NOTIFY_TELEGRAM_FAIL] project={project_id}, error={err_desc}", extra={'skill_name': 'GROUP_NOTIFY'})
                    print(f"❌ Telegram API 返回错误: {err_desc}")
        except Exception as e:
            if skill_logger:
                skill_logger.error(f"[GROUP_NOTIFY_TELEGRAM_EXCEPTION] project={project_id}, error={str(e)}", extra={'skill_name': 'GROUP_NOTIFY'})
            print(f"❌ 发送群通报失败: {e}")

    # 方法 2: 通过 notify-telegram skill（如果存在）
    notify_telegram_script = Path.home() / ".openclaw/skills/team-ok/notify-telegram/scripts/notify.py"
    if notify_telegram_script.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(notify_telegram_script), project_id, "group_notify", message],
                capture_output=True, text=True, timeout=GROUP_NOTIFY_TIMEOUT
            )
            rc, stdout, stderr = result.returncode, result.stdout, result.stderr

            if rc == 0:
                if skill_logger:
                    skill_logger.info(f"[GROUP_NOTIFY_SKILL_SUCCESS] project={project_id}", extra={'skill_name': 'GROUP_NOTIFY'})
                print(f"✅ 群通报已发送（通过 notify-telegram）: {message[:50]}...")
                return True
            else:
                if skill_logger:
                    skill_logger.error(f"[GROUP_NOTIFY_SKILL_FAIL] project={project_id}, error={stderr[:200]}", extra={'skill_name': 'GROUP_NOTIFY'})
                print(f"❌ notify-telegram 返回错误: {stderr}")
        except Exception as e:
            if skill_logger:
                skill_logger.error(f"[GROUP_NOTIFY_SKILL_EXCEPTION] project={project_id}, error={str(e)}", extra={'skill_name': 'GROUP_NOTIFY'})
            print(f"❌ 调用 notify-telegram 失败: {e}")

    # 方法 3: 回退到日志记录
    log_path = project_dir / "group-notifications.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] {message}\n")

    print(f"⚠️ 未配置 Telegram，群通报已记录到日志: {log_path}")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="发送群通报")
    parser.add_argument("command", choices=["send"])
    parser.add_argument("project_id")
    parser.add_argument("message")

    args = parser.parse_args()

    if args.command == "send":
        success = send_group_notification(args.project_id, args.message)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
