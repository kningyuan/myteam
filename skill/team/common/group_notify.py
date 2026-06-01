#!/usr/bin/env python3
"""群通报模块 — 向 myteam 项目协作群发送进度消息。"""

from datetime import datetime

from common.paths import project_dir
from common.skill_settings import is_project_group_enabled


def send_group_notification(project_id: str, message: str, event_type: str = "group_notify") -> bool:
    """发送群通报到 myteam 项目群；Telegram 仅在 skill_config 显式开启时尝试。"""
    try:
        from common.logger import get_skill_logger

        skill_logger = get_skill_logger(project_id)
        skill_logger.info(
            f"[GROUP_NOTIFY_START] project={project_id}, event={event_type}, msg_len={len(message)}",
            extra={"skill_name": "GROUP_NOTIFY"},
        )
    except Exception:
        skill_logger = None

    posted = False
    if is_project_group_enabled():
        try:
            from bridge.myteam_notify import post_project_group_message

            ok, _ = post_project_group_message(
                project_id,
                event_type,
                message=message,
            )
            posted = ok
            if ok and skill_logger:
                skill_logger.info(
                    f"[GROUP_NOTIFY_MYTEAM_OK] project={project_id}",
                    extra={"skill_name": "GROUP_NOTIFY"},
                )
        except Exception as e:
            if skill_logger:
                skill_logger.warning(
                    f"[GROUP_NOTIFY_MYTEAM_FAIL] project={project_id}, error={e}",
                    extra={"skill_name": "GROUP_NOTIFY"},
                )

    if posted:
        return True

    log_path = project_dir(project_id) / "group-notifications.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] [{event_type}] {message}\n")
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
        import sys
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
