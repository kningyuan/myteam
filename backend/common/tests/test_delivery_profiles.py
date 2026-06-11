#!/usr/bin/env python3
"""delivery_profiles + registry 合并 + PromptComposer。"""
from __future__ import annotations

import pytest

from common.delivery_profiles import (
    get_delivery_profile,
    invalidate_delivery_profiles_cache,
    merge_file_exists,
)
from common.registry import get_spec, invalidate_registry_cache


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


def test_requirements_spec_has_light_profile():
    spec = get_spec("requirements")
    assert spec is not None
    assert spec.delivery_profile == "light_v1"
    assert "align.md" in spec.file_exists
    assert "verify.log" in spec.file_exists


def test_diagram_build_spec_all_v1():
    spec = get_spec("diagram-build")
    assert spec is not None
    assert spec.delivery_profile == "all_v1"
    assert "plan.md" in spec.file_exists
    assert "ledger.entry.yaml" in spec.file_exists


def test_research_legacy_no_profile():
    spec = get_spec("research")
    assert spec is not None
    assert spec.delivery_profile == "none"
    assert "align.md" not in spec.file_exists


def test_arch_research_spec():
    spec = get_spec("arch-research")
    assert spec is not None
    assert spec.delivery_profile == "light_v1"
    assert "align.md" in spec.file_exists


def test_product_research_spec():
    spec = get_spec("product-research")
    assert spec is not None
    assert spec.delivery_profile == "light_v1"
    assert "调研背景" in spec.required_sections
