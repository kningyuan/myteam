#!/usr/bin/env python3
"""delivery_profiles + registry 合并 + PromptComposer。

历史遗留测试曾期望 requirements/diagram-build/arch-research/product-research
等早期 task_type，现对齐当前 task_type 集（research=light_v1）。
机制不变：profile 合并 file_exists、profile 字段读取。
"""
from __future__ import annotations

import pytest

from common.delivery.delivery_profiles import (
    invalidate_delivery_profiles_cache,
    merge_file_exists,
)
from common.gate.registry import get_spec, invalidate_registry_cache


@pytest.fixture(autouse=True)
def _clear_caches():
    invalidate_registry_cache()
    invalidate_delivery_profiles_cache()
    yield
    invalidate_registry_cache()
    invalidate_delivery_profiles_cache()


def test_light_v1_merges_process_artifacts():
    files = merge_file_exists([], "light_v1")
    assert files == ["align.md", "verify.log"]


def test_all_v1_merges_with_business_files():
    files = merge_file_exists(["diagram.drawio", "diagram.png"], "all_v1")
    assert "align.md" in files
    assert "plan.md" in files
    assert "diagram.drawio" in files


def test_research_spec_has_light_profile():
    """research task_type 用 light_v1 profile：含 align.md/verify.log。"""
    spec = get_spec("research")
    assert spec is not None
    assert spec.delivery_profile == "light_v1"
    assert "align.md" in spec.file_exists
    assert "verify.log" in spec.file_exists


def test_section_review_spec_no_profile():
    """section-review task_type 用 none profile：无过程产物。"""
    spec = get_spec("section-review")
    assert spec is not None
    assert spec.delivery_profile == "none"
    assert "align.md" not in spec.file_exists


def test_publish_post_spec_no_profile():
    """publish-post（action 形态）用 none profile。"""
    spec = get_spec("publish-post")
    assert spec is not None
    assert spec.delivery_profile == "none"
