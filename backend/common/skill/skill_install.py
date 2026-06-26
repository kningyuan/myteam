#!/usr/bin/env python3
"""URL-based Skill Installer — 从互联网查找并安装 Skill。

支持三种来源：
1. GitHub 仓库（https://github.com/owner/repo）
2. 原始 SKILL.md 文件 URL（支持 raw.githubusercontent.com 等）
3. Git 仓库地址（任意 git clone 源）

安装流程：
  1. 下载/克隆到 _pending 目录
  2. 验证包含 SKILL.md 且 frontmatter 合法
  3. 复制到 business/skills/<id>/
  4. 注册到 catalog.yaml（可选）
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import yaml

from common.paths import MYTEAM_ROOT
from common.skill.skill_catalog import SKILLS_DIR
from common.skill.skill_catalog import get_skill_library_entry

logger = logging.getLogger("common.skill_install")

PENDING_DIR = SKILLS_DIR / "_pending"
CATALOG_PATH = SKILLS_DIR / "catalog.yaml"

# GitHub raw content 常见前缀
_RAW_PREFIXES = (
    "https://raw.githubusercontent.com/",
    "https://raw.githubusercontent.com/",
)

_GIT_RE = re.compile(r"^https?://.+\.git$|^git@")
_GITHUB_REPO_RE = re.compile(
    r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/)?$"
)


def _ensure_pending_dir() -> Path:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    return PENDING_DIR


def _slugify(text: str) -> str:
    return re.sub(r"[^\w\-]+", "-", text.strip().lower()).strip("-") or "skill"


def _validate_skill_dir(skill_dir: Path) -> Optional[str]:
    """验证一个目录是否包含合法的 SKILL.md。返回 skill_id 或 None。"""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        logger.warning("目录 %s 缺少 SKILL.md", skill_dir)
        return None
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    # 解析 frontmatter
    from common.skill.skill_catalog import _parse_frontmatter as parse_fm
    meta = parse_fm(text)
    sid = meta.get("id") or meta.get("name") or skill_dir.name
    if not sid:
        logger.warning("SKILL.md 缺少 id/name frontmatter")
        return None
    # 检查有实际内容，不仅是 frontmatter
    body = re.sub(r"^---.*?---\s*", "", text, count=1, flags=re.DOTALL).strip()
    if len(body) < 50:
        logger.warning("SKILL.md 正文过短（%d 字符），可能不合法", len(body))
        return None
    return sid.strip()


def _download_raw_skill(url: str) -> Optional[dict]:
    """从原始 SKILL.md URL 下载并提取元信息。"""
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("下载失败 %s: %s", url, e)
        return None

    from common.skill.skill_catalog import _parse_frontmatter as parse_fm
    meta = parse_fm(text)
    sid = meta.get("id") or _slugify(Path(url).stem or "skill")
    body = re.sub(r"^---.*?---\s*", "", text, count=1, flags=re.DOTALL).strip()
    if len(body) < 50:
        logger.warning("Raw SKILL.md 正文过短")
        return None

    return {"skill_id": sid, "text": text, "meta": meta, "body": body}


def _github_raw_url(repo_url: str, branch: str = "main") -> Optional[str]:
    """从 GitHub 仓库 URL 构造 SKILL.md 的 raw URL。"""
    m = _GITHUB_REPO_RE.match(repo_url)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2).rstrip("/")
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/SKILL.md"


def _clone_repo(url: str, target_dir: Path) -> bool:
    """克隆 git 仓库到目标目录（浅克隆，单分支）。"""
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", url, str(target_dir)],
            capture_output=True, text=True, timeout=120,
        )
        return target_dir.is_dir() and (target_dir / "SKILL.md").is_file()
    except Exception as e:
        logger.warning("git clone 失败 %s: %s", url, e)
        return False


def _add_to_catalog(skill_id: str, skill_dir: Path) -> bool:
    """将 skill 添加到 catalog.yaml（如果尚不存在）。"""
    if not CATALOG_PATH.is_file():
        # 创建基本 catalog
        CATALOG_PATH.write_text(
            json.dumps({"skills": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    try:
        data = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {"skills": []}
    if not isinstance(data, dict):
        data = {"skills": []}
    skills = data.get("skills") or []

    # 检查是否已存在
    existing_ids = {s.get("id") for s in skills if isinstance(s, dict)}
    if skill_id in existing_ids:
        return True  # 已注册

    # 从 SKILL.md 读取描述
    skill_md = skill_dir / "SKILL.md"
    from common.skill.skill_catalog import _parse_frontmatter as parse_fm
    meta = parse_fm(skill_md.read_text(encoding="utf-8"))
    description = meta.get("description", f"从网络安装的 Skill: {skill_id}")
    task_types = meta.get("task_types", "")

    router = f"business/skills/{skill_id}"
    entry = {
        "id": skill_id,
        "description": description,
        "router": router,
    }
    if task_types:
        entry["task_types"] = [t.strip() for t in task_types.split(",") if t.strip()]

    skills.append(entry)
    data["skills"] = skills
    CATALOG_PATH.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    return True


def install_skill_from_url(
    url: str,
    *,
    force: bool = False,
    register_catalog: bool = True,
) -> dict:
    """从 URL 安装 Skill。

    Args:
        url: 安装源（GitHub 仓库 URL、raw SKILL.md URL、git 仓库 URL）
        force: 是否覆盖已存在的 skill
        register_catalog: 是否自动添加到 catalog.yaml

    Returns:
        {"success": bool, "skill_id": str, "path": str, "error": str}
    """
    url = url.strip()
    temp_dir = None
    skill_id = None

    try:
        # 处理不同 URL 类型
        if "raw.githubusercontent.com" in url and url.endswith("SKILL.md"):
            # 直接下载 raw SKILL.md
            result = _download_raw_skill(url)
            if not result:
                return {"success": False, "error": f"无法从 {url} 下载有效的 SKILL.md"}
            skill_id = result["skill_id"]
            target = SKILLS_DIR / skill_id
            if target.exists() and not force:
                return {
                    "success": False,
                    "skill_id": skill_id,
                    "error": f"Skill '{skill_id}' 已存在，使用 force=True 覆盖",
                }
            target.mkdir(parents=True, exist_ok=True)
            (target / "SKILL.md").write_text(result["text"], encoding="utf-8")

        elif _GITHUB_REPO_RE.match(url):
            # GitHub 仓库 URL — 先尝试 raw，再 fallback 到 clone
            raw_url = _github_raw_url(url)
            if raw_url:
                result = _download_raw_skill(raw_url)
                if result:
                    skill_id = result["skill_id"]
                    target = SKILLS_DIR / skill_id
                    if target.exists() and not force:
                        return {
                            "success": False,
                            "skill_id": skill_id,
                            "error": f"Skill '{skill_id}' 已存在",
                        }
                    target.mkdir(parents=True, exist_ok=True)
                    (target / "SKILL.md").write_text(result["text"], encoding="utf-8")
                    rel_router = f"business/skills/{skill_id}/SKILL.md"
                    if register_catalog:
                        _add_to_catalog(skill_id, target)
                    return {
                        "success": True,
                        "skill_id": skill_id,
                        "path": rel_router,
                    }

            # fallback: clone 整个仓库
            temp_dir = Path(tempfile.mkdtemp(dir=str(_ensure_pending_dir())))
            if not _clone_repo(url, temp_dir):
                return {"success": False, "error": f"无法克隆仓库 {url}"}
            sid = _validate_skill_dir(temp_dir)
            if not sid:
                return {"success": False, "error": f"仓库 {url} 根目录缺少合法 SKILL.md"}
            skill_id = sid
            target = SKILLS_DIR / skill_id
            if target.exists() and not force:
                return {
                    "success": False,
                    "skill_id": skill_id,
                    "error": f"Skill '{skill_id}' 已存在",
                }
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(temp_dir, target, dirs_exist_ok=True)
            return {
                "success": True,
                "skill_id": skill_id,
                "path": f"business/skills/{skill_id}/SKILL.md",
            }

        elif "github.com" in url:
            # 其他 GitHub 路径（非仓库根）
            skill_id = _slugify(Path(url).stem or "github-skill")
            temp_dir = Path(tempfile.mkdtemp(dir=str(_ensure_pending_dir())))
            if not _clone_repo(url, temp_dir):
                return {"success": False, "error": f"无法克隆 {url}"}
            sid = _validate_skill_dir(temp_dir)
            if not sid:
                return {"success": False, "error": "克隆仓库缺少合法 SKILL.md"}
            skill_id = sid
            target = SKILLS_DIR / skill_id
            if target.exists() and not force:
                return {
                    "success": False,
                    "skill_id": skill_id,
                    "error": "Skill 已存在",
                }
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(temp_dir, target, dirs_exist_ok=True)
        else:
            return {"success": False, "error": f"不支持的 URL 格式: {url}"}

        # 最终验证
        if not skill_id:
            return {"success": False, "error": "无法识别 skill_id"}
        install_path = SKILLS_DIR / skill_id
        if not install_path.is_dir() or not (install_path / "SKILL.md").is_file():
            return {"success": False, "error": f"安装后验证失败: {skill_id} 缺少 SKILL.md"}

        if register_catalog:
            _add_to_catalog(skill_id, install_path)

        logger.info("Skill '%s' 从 %s 安装成功", skill_id, url)
        return {
            "success": True,
            "skill_id": skill_id,
            "path": f"business/skills/{skill_id}/SKILL.md",
        }

    except Exception as e:
        logger.exception("安装 skill 失败")
        return {"success": False, "error": str(e)}

    finally:
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def search_and_install(
    query: str,
    *,
    register_catalog: bool = True,
) -> dict:
    """搜索并安装 Skill（先搜索，再安装最佳匹配）。

    搜索范围：
    - 本地已安装的 skill
    - GitHub 上标记为 "claude-skill" 的仓库（通过 GitHub API）

    Args:
        query: 搜索关键词（如 "产品需求文档"、"竞品分析"）

    Returns:
        {"success": bool, "skill_id": str|None, "matched_local": bool, "results": list}
    """
    results: list[dict] = []

    # 1. 搜索本地
    local_matches = []
    for p in sorted(SKILLS_DIR.iterdir()):
        if not p.is_dir() or p.name.startswith(".") or p.name.startswith("_"):
            continue
        skill_md = p / "SKILL.md"
        if not skill_md.is_file():
            continue
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        if query.lower() in text.lower():
            from common.skill.skill_catalog import _parse_frontmatter as parse_fm
            meta = parse_fm(text)
            name = meta.get("name") or p.name
            description = meta.get("description", "")
            local_matches.append({
                "skill_id": p.name,
                "name": name,
                "description": description,
                "source": "local",
            })

    if local_matches:
        results.extend(local_matches)
        best = local_matches[0]
        return {
            "success": True,
            "skill_id": best["skill_id"],
            "matched_local": True,
            "results": results,
            "message": f"找到本地匹配的 Skill: {best['name']} ({best['skill_id']})",
        }

    # 2. GitHub 搜索（通过 GitHub API 查找 skill 仓库）
    try:
        import urllib.request
        search_url = (
            f"https://api.github.com/search/repositories?"
            f"q={urllib.request.quote(query)}+topic:claude-skill"
            f"&sort=stars&order=desc&per_page=10"
        )
        req = urllib.request.Request(
            search_url,
            headers={"Accept": "application/vnd.github.v3+json",
                     "User-Agent": "myteam-skill-installer"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        for item in data.get("items", []):
            repo_url = item.get("clone_url") or item.get("html_url", "")
            results.append({
                "skill_id": item.get("name", ""),
                "name": item.get("name", ""),
                "description": item.get("description", "") or "",
                "stars": item.get("stargazers_count", 0),
                "url": item.get("html_url", ""),
                "source": "github",
            })
    except Exception as e:
        logger.warning("GitHub 搜索失败: %s", e)

    if not results:
        return {"success": False, "matched_local": False, "results": [],
                "message": f"未找到匹配 '{query}' 的 Skill"}

    return {
        "success": True,
        "matched_local": False,
        "results": results,
        "message": f"在 GitHub 上找到 {len(results)} 个相关仓库。",
    }


def list_available_skills() -> list[dict]:
    """列出所有可用的 Skill（本地已安装 + 待安装候选）。"""
    # 本地 Skill
    local = []
    for p in sorted(SKILLS_DIR.iterdir()):
        if not p.is_dir() or p.name.startswith(".") or p.name.startswith("_"):
            continue
        skill_md = p / "SKILL.md"
        if not skill_md.is_file():
            continue
        from common.skill.skill_catalog import get_skill_library_entry
        entry = get_skill_library_entry(p.name)
        if entry:
            local.append(entry)
    return local


def list_pending_skills() -> list[dict]:
    """列出 _pending 目录中待处理的 Skill 草案。"""
    items = []
    if not PENDING_DIR.is_dir():
        return items
    for p in sorted(PENDING_DIR.iterdir()):
        if not p.is_dir() or p.name.startswith("."):
            continue
        skill_md = p / "SKILL.md"
        if not skill_md.is_file():
            continue
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        from common.skill.skill_catalog import _parse_frontmatter as parse_fm
        meta = parse_fm(text)
        items.append({
            "id": p.name,
            "name": meta.get("name") or p.name,
            "description": meta.get("description", ""),
            "path": str(p),
            "file_count": len([f for f in p.rglob("*") if f.is_file()]),
        })
    return items