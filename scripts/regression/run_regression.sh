#!/usr/bin/env bash
# 回归测试主入口（本地 + CI 通用）
# 用法: ./scripts/regression/run_regression.sh [--suite unit|reg02|reg04|reg05|k2|k7|k16|k17|o8|l3skill|framework|l2|l3|all]
# 退出码: 0=全通过, 1=部分失败

set -e

SUITE="all"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --suite) SUITE="$2"; shift 2 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export MYTEAM_ROOT="$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/backend"
export NO_PROXY="localhost,127.0.0.1,::1"
# dogfooding REG 默认给足 token，避免规划期误触 paused（大元帅约定）
export REG_DEFAULT_BUDGET="${REG_DEFAULT_BUDGET:-5000000}"

echo "=== myteam 回归测试 suite=$SUITE ==="
echo "MYTEAM_ROOT=$MYTEAM_ROOT"

UNIT_PASS=0
REG02_PASS=0
REG02_SKIP=0
REG04_PASS=0
REG05_PASS=0
REG05_SKIP=0
REG_K2_PASS=0
REG_K7_PASS=0
REG_K16_PASS=0
REG_K17_PASS=0
REG_K14_PASS=0
REG_O8_PASS=0
REG_C9_PASS=0
REG_L3_SKILL_PASS=0
REG_RULES_PASS=0
REG_D_PASS=0
REG_B_PASS=0
REG_C_PASS=0
REG_L2_PASS=0
REG_L2_SKIP=0
REG_L3_PASS=0
REG_L3_SKIP=0

# ---- Phase 1: 单元测试 ----
if [[ "$SUITE" == "unit" || "$SUITE" == "all" ]]; then
    echo ""
    echo "=== Phase 1: 单元测试 ==="
    set +e
    "$REPO_ROOT/venv/bin/python3" -m pytest \
        backend/common/tests/test_agent_port.py \
        backend/common/tests/test_claude_parser.py \
        backend/common/tests/test_recovery.py \
        backend/common/tests/test_agent_transport.py \
        backend/common/tests/test_process.py \
        backend/common/tests/test_dag_dispatch.py \
        backend/common/tests/test_store_concurrency.py \
        backend/common/tests/test_workspace_gc.py \
        -q --tb=short
    UNIT_EXIT=$?
    set -e
    if [[ $UNIT_EXIT -eq 0 ]]; then
        echo "Phase 1: PASS"
        UNIT_PASS=1
    else
        echo "Phase 1: FAIL (exit=$UNIT_EXIT)"
    fi
fi

# ---- Phase 2: REG-02 dogfooding KPI（仅读 state.db，不重跑 kernel）----
if [[ "$SUITE" == "reg02" || "$SUITE" == "all" ]]; then
    echo ""
    echo "=== Phase 2: REG-02 dogfooding KPI ==="
    set +e
    REG02_CHECK_ONLY=1 "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_02_parallel.py
    REG02_EXIT=$?
    set -e
    if [[ $REG02_EXIT -eq 0 ]]; then
        echo "Phase 2 (REG-02): PASS"
        REG02_PASS=1
    elif [[ $REG02_EXIT -eq 2 ]]; then
        echo "Phase 2 (REG-02): SKIP (无 live/归档数据)"
        REG02_SKIP=1
    else
        echo "Phase 2 (REG-02): FAIL (exit=$REG02_EXIT)"
    fi
    if [[ -f "$REPO_ROOT/scripts/regression/check_kpis.py" ]] && [[ -f "$REPO_ROOT/business/tasks/state.db" ]]; then
        echo "  K8 摘要:"
        "$REPO_ROOT/venv/bin/python3" "$REPO_ROOT/scripts/regression/check_kpis.py" \
            --db "$REPO_ROOT/business/tasks/state.db" --project reg-parallel-4leaf \
            2>/dev/null | "$REPO_ROOT/venv/bin/python3" -c "import sys,json; d=json.load(sys.stdin); print(f\"    k8={d.get('k8','N/A')} k8_pass={d.get('k8_pass','N/A')}\")" \
            || true
    fi
fi

# ---- Phase 3: REG-04 孤儿回收 E2E ----
if [[ "$SUITE" == "reg04" || "$SUITE" == "all" ]]; then
    echo ""
    echo "=== Phase 3: REG-04 孤儿回收 E2E ==="
    set +e
    "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_04_orphan.py
    REG04_EXIT=$?
    set -e
    if [[ $REG04_EXIT -eq 0 ]]; then
        echo "Phase 3 (REG-04): PASS"
        REG04_PASS=1
    else
        echo "Phase 3 (REG-04): FAIL (exit=$REG04_EXIT)"
    fi
fi

# ---- Phase 4: REG-05 budget 护栏 E2E ----
if [[ "$SUITE" == "reg05" || "$SUITE" == "all" ]]; then
    echo ""
    echo "=== Phase 4: REG-05 budget 护栏 E2E ==="
    set +e
    "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_05_budget.py
    REG05_EXIT=$?
    set -e
    if [[ $REG05_EXIT -eq 0 ]]; then
        echo "Phase 4 (REG-05): PASS"
        REG05_PASS=1
    elif [[ $REG05_EXIT -eq 2 ]]; then
        echo "Phase 4 (REG-05): SKIP (无 CLI)"
        REG05_SKIP=1
    else
        echo "Phase 4 (REG-05): FAIL (exit=$REG05_EXIT)"
    fi
fi

# ---- Phase 4a: REG-K2 Gate 首次通过率（CHECK_ONLY）----
if [[ "$SUITE" == "k2" || "$SUITE" == "all" ]]; then
    echo ""
    echo "=== Phase 4a: REG-K2 Gate 首次通过率 ==="
    set +e
    "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_k2_gate.py
    REG_K2_EXIT=$?
    set -e
    if [[ $REG_K2_EXIT -eq 0 ]]; then
        echo "Phase 4a (REG-K2): PASS"
        REG_K2_PASS=1
    else
        echo "Phase 4a (REG-K2): FAIL (exit=$REG_K2_EXIT)"
    fi
fi

# ---- Phase 4b: REG-K7 triage 有效决策率（CHECK_ONLY）----
if [[ "$SUITE" == "k7" || "$SUITE" == "framework" || "$SUITE" == "all" ]]; then
    echo ""
    echo "=== Phase 4b: REG-K7 triage 有效决策率 ==="
    set +e
    "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_k7_triage.py
    REG_K7_EXIT=$?
    set -e
    if [[ $REG_K7_EXIT -eq 0 ]]; then
        echo "Phase 4b (REG-K7): PASS"
        REG_K7_PASS=1
    else
        echo "Phase 4b (REG-K7): FAIL (exit=$REG_K7_EXIT)"
    fi
fi

# ---- Phase 4c: 框架 P0 CHECK_ONLY（D/B/C/K17）----
if [[ "$SUITE" == "k17" || "$SUITE" == "framework" || "$SUITE" == "all" ]]; then
    echo ""
    echo "=== Phase 4c: 框架 P0 CHECK_ONLY（D/B/C/K17）==="
    set +e
    "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_d_config_linkage.py
    REG_D_EXIT=$?
    "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_b_budget_degrade.py
    REG_B_EXIT=$?
    "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_c_k7_kernel.py
    REG_C_EXIT=$?
    "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_k17_gate_retry.py
    REG_K17_EXIT=$?
    "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_k14_per_agent_backend.py
    REG_K14_EXIT=$?
    "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_k16_recurring_trigger.py
    REG_K16_EXIT=$?
    if [[ "$SUITE" == "framework" || "$SUITE" == "all" ]]; then
        "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_rules_injection.py
        REG_RULES_EXIT=$?
        "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_o8_audit_log.py
        REG_O8_EXIT=$?
        "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_c9_skill_config_api.py
        REG_C9_EXIT=$?
        "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_l3_skill_extract.py
        REG_L3_SKILL_EXIT=$?
    else
        REG_RULES_EXIT=0
        REG_O8_EXIT=0
        REG_C9_EXIT=0
        REG_L3_SKILL_EXIT=0
    fi
    set -e
    if [[ $REG_D_EXIT -eq 0 ]]; then REG_D_PASS=1; fi
    if [[ $REG_B_EXIT -eq 0 ]]; then REG_B_PASS=1; fi
    if [[ $REG_C_EXIT -eq 0 ]]; then REG_C_PASS=1; fi
    if [[ $REG_K17_EXIT -eq 0 ]]; then REG_K17_PASS=1; fi
    if [[ $REG_K14_EXIT -eq 0 ]]; then REG_K14_PASS=1; fi
    if [[ $REG_K16_EXIT -eq 0 ]]; then REG_K16_PASS=1; fi
    if [[ $REG_RULES_EXIT -eq 0 ]]; then REG_RULES_PASS=1; fi
    if [[ $REG_O8_EXIT -eq 0 ]]; then REG_O8_PASS=1; fi
    if [[ $REG_C9_EXIT -eq 0 ]]; then REG_C9_PASS=1; fi
    if [[ $REG_L3_SKILL_EXIT -eq 0 ]]; then REG_L3_SKILL_PASS=1; fi
    echo "  REG-D:   $([ $REG_D_PASS -eq 1 ] && echo PASS || echo FAIL)"
    echo "  REG-B:   $([ $REG_B_PASS -eq 1 ] && echo PASS || echo FAIL)"
    echo "  REG-C:   $([ $REG_C_PASS -eq 1 ] && echo PASS || echo FAIL)"
    echo "  REG-K17: $([ $REG_K17_PASS -eq 1 ] && echo PASS || echo FAIL)"
    echo "  REG-K14: $([ $REG_K14_PASS -eq 1 ] && echo PASS || echo FAIL)"
    echo "  REG-K16: $([ $REG_K16_PASS -eq 1 ] && echo PASS || echo FAIL)"
    [[ "$SUITE" == "framework" || "$SUITE" == "all" ]] && echo "  REG-RULES: $([ $REG_RULES_PASS -eq 1 ] && echo PASS || echo FAIL)"
    [[ "$SUITE" == "framework" || "$SUITE" == "all" ]] && echo "  REG-O8:  $([ $REG_O8_PASS -eq 1 ] && echo PASS || echo FAIL)"
    [[ "$SUITE" == "framework" || "$SUITE" == "all" ]] && echo "  REG-C9:  $([ $REG_C9_PASS -eq 1 ] && echo PASS || echo FAIL)"
    [[ "$SUITE" == "framework" || "$SUITE" == "all" ]] && echo "  REG-L3-SKILL: $([ $REG_L3_SKILL_PASS -eq 1 ] && echo PASS || echo FAIL)"
fi

# ---- Phase 4e: REG-K16 外部 recurring 触发入口（CHECK_ONLY）----
if [[ "$SUITE" == "k16" ]]; then
    echo ""
    echo "=== Phase 4e: REG-K16 外部 recurring 触发入口 ==="
    set +e
    "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_k16_recurring_trigger.py
    REG_K16_EXIT=$?
    set -e
    if [[ $REG_K16_EXIT -eq 0 ]]; then
        echo "Phase 4e (REG-K16): PASS"
        REG_K16_PASS=1
    else
        echo "Phase 4e (REG-K16): FAIL (exit=$REG_K16_EXIT)"
    fi
fi

# ---- Phase 4d: REG-O8 结构化审计日志（CHECK_ONLY）----
if [[ "$SUITE" == "o8" ]]; then
    echo ""
    echo "=== Phase 4d: REG-O8 结构化审计日志 ==="
    set +e
    "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_o8_audit_log.py
    REG_O8_EXIT=$?
    set -e
    if [[ $REG_O8_EXIT -eq 0 ]]; then
        echo "Phase 4d (REG-O8): PASS"
        REG_O8_PASS=1
    else
        echo "Phase 4d (REG-O8): FAIL (exit=$REG_O8_EXIT)"
    fi
fi

# ---- Phase 4f: REG-L3-SKILL Skill 自动抽提（CHECK_ONLY）----
if [[ "$SUITE" == "l3skill" ]]; then
    echo ""
    echo "=== Phase 4f: REG-L3-SKILL Skill 自动抽提 ==="
    set +e
    "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_l3_skill_extract.py
    REG_L3_SKILL_EXIT=$?
    set -e
    if [[ $REG_L3_SKILL_EXIT -eq 0 ]]; then
        echo "Phase 4f (REG-L3-SKILL): PASS"
        REG_L3_SKILL_PASS=1
    else
        echo "Phase 4f (REG-L3-SKILL): FAIL (exit=$REG_L3_SKILL_EXIT)"
    fi
fi

# ---- Phase 5: REG-L2 三角色并行评审（L2 发版门禁）----
if [[ "$SUITE" == "l2" || "$SUITE" == "all" ]]; then
    echo ""
    echo "=== Phase 5: REG-L2 三角色并行评审 ==="
    set +e
    if [[ "$SUITE" == "all" ]]; then
        REG_L2_CHECK_ONLY=1 "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_l2_3role.py
        REG_L2_EXIT=$?
    else
        "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_l2_3role.py
        REG_L2_EXIT=$?
    fi
    set -e
    if [[ $REG_L2_EXIT -eq 0 ]]; then
        echo "Phase 5 (REG-L2): PASS"
        REG_L2_PASS=1
    elif [[ $REG_L2_EXIT -eq 2 ]]; then
        echo "Phase 5 (REG-L2): SKIP (无 CLI)"
        REG_L2_SKIP=1
    else
        echo "Phase 5 (REG-L2): FAIL (exit=$REG_L2_EXIT)"
    fi
    if [[ -f "$REPO_ROOT/scripts/regression/check_kpis.py" ]] && [[ -f "$REPO_ROOT/business/tasks/state.db" ]]; then
        echo "  K8 摘要:"
        "$REPO_ROOT/venv/bin/python3" "$REPO_ROOT/scripts/regression/check_kpis.py" \
            --db "$REPO_ROOT/business/tasks/state.db" --project reg-l2-3role \
            2>/dev/null | "$REPO_ROOT/venv/bin/python3" -c "import sys,json; d=json.load(sys.stdin); print(f\"    k1={d.get('k1','N/A')} k8={d.get('k8','N/A')} k8_pass={d.get('k8_pass','N/A')}\")" \
            || true
    fi
fi

# ---- Phase 6: REG-L3 self-upgrade scaffold（CHECK_ONLY 在 suite all 中非阻塞）----
if [[ "$SUITE" == "l3" || "$SUITE" == "all" ]]; then
    echo ""
    echo "=== Phase 6: REG-L3 self-upgrade scaffold ==="
    set +e
    if [[ "$SUITE" == "all" ]]; then
        REG_L3_CHECK_ONLY=1 "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_l3_self_upgrade.py
        REG_L3_EXIT=$?
        REG_L3_CC_EXIT=0
        if [[ $REG_L3_EXIT -eq 0 ]]; then
            REG_L3_CHECK_ONLY=1 "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_l3_content_campaign.py
            REG_L3_CC_EXIT=$?
        fi
    else
        "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_l3_self_upgrade.py
        REG_L3_EXIT=$?
        REG_L3_CC_EXIT=0
        if [[ $REG_L3_EXIT -eq 0 ]]; then
            "$REPO_ROOT/venv/bin/python3" scripts/regression/reg_l3_content_campaign.py
            REG_L3_CC_EXIT=$?
        fi
    fi
    set -e
    if [[ $REG_L3_EXIT -eq 0 && $REG_L3_CC_EXIT -eq 0 ]]; then
        echo "Phase 6 (REG-L3): PASS"
        REG_L3_PASS=1
    elif [[ $REG_L3_EXIT -eq 2 || $REG_L3_CC_EXIT -eq 2 ]]; then
        echo "Phase 6 (REG-L3): SKIP (无 CLI / E2E 未实现)"
        REG_L3_SKIP=1
    else
        echo "Phase 6 (REG-L3): FAIL (self_upgrade exit=$REG_L3_EXIT content_campaign exit=$REG_L3_CC_EXIT)"
    fi
fi

echo ""
echo "=== 汇总 ==="
[[ "$SUITE" == "unit" || "$SUITE" == "all" ]] && echo "  单元测试: $([ $UNIT_PASS -eq 1 ] && echo PASS || echo FAIL)"
if [[ "$SUITE" == "reg02" || "$SUITE" == "all" ]]; then
    if [[ $REG02_SKIP -eq 1 ]]; then
        echo "  REG-02:   SKIP"
    else
        echo "  REG-02:   $([ $REG02_PASS -eq 1 ] && echo PASS || echo FAIL)"
    fi
fi
[[ "$SUITE" == "reg04" || "$SUITE" == "all" ]] && echo "  REG-04:   $([ $REG04_PASS -eq 1 ] && echo PASS || echo FAIL)"
if [[ "$SUITE" == "reg05" || "$SUITE" == "all" ]]; then
    if [[ $REG05_SKIP -eq 1 ]]; then
        echo "  REG-05:   SKIP"
    else
        echo "  REG-05:   $([ $REG05_PASS -eq 1 ] && echo PASS || echo FAIL)"
    fi
fi
[[ "$SUITE" == "k2" || "$SUITE" == "all" ]] && echo "  REG-K2:   $([ $REG_K2_PASS -eq 1 ] && echo PASS || echo FAIL)"
[[ "$SUITE" == "k7" || "$SUITE" == "framework" || "$SUITE" == "all" ]] && echo "  REG-K7:   $([ $REG_K7_PASS -eq 1 ] && echo PASS || echo FAIL)"
if [[ "$SUITE" == "k17" || "$SUITE" == "framework" || "$SUITE" == "all" ]]; then
    echo "  REG-D:    $([ $REG_D_PASS -eq 1 ] && echo PASS || echo FAIL)"
    echo "  REG-B:    $([ $REG_B_PASS -eq 1 ] && echo PASS || echo FAIL)"
    echo "  REG-C:    $([ $REG_C_PASS -eq 1 ] && echo PASS || echo FAIL)"
    echo "  REG-K17:  $([ $REG_K17_PASS -eq 1 ] && echo PASS || echo FAIL)"
    echo "  REG-K14:  $([ $REG_K14_PASS -eq 1 ] && echo PASS || echo FAIL)"
    echo "  REG-K16:  $([ $REG_K16_PASS -eq 1 ] && echo PASS || echo FAIL)"
    [[ "$SUITE" == "framework" || "$SUITE" == "all" ]] && echo "  REG-RULES: $([ $REG_RULES_PASS -eq 1 ] && echo PASS || echo FAIL)"
    [[ "$SUITE" == "framework" || "$SUITE" == "all" ]] && echo "  REG-O8:   $([ $REG_O8_PASS -eq 1 ] && echo PASS || echo FAIL)"
    [[ "$SUITE" == "framework" || "$SUITE" == "all" ]] && echo "  REG-C9:   $([ $REG_C9_PASS -eq 1 ] && echo PASS || echo FAIL)"
    [[ "$SUITE" == "framework" || "$SUITE" == "all" ]] && echo "  REG-L3-SKILL: $([ $REG_L3_SKILL_PASS -eq 1 ] && echo PASS || echo FAIL)"
fi
[[ "$SUITE" == "k16" ]] && echo "  REG-K16:  $([ $REG_K16_PASS -eq 1 ] && echo PASS || echo FAIL)"
[[ "$SUITE" == "o8" ]] && echo "  REG-O8:   $([ $REG_O8_PASS -eq 1 ] && echo PASS || echo FAIL)"
[[ "$SUITE" == "l3skill" ]] && echo "  REG-L3-SKILL: $([ $REG_L3_SKILL_PASS -eq 1 ] && echo PASS || echo FAIL)"
if [[ "$SUITE" == "l2" || "$SUITE" == "all" ]]; then
    if [[ $REG_L2_SKIP -eq 1 ]]; then
        echo "  REG-L2:   SKIP"
    else
        echo "  REG-L2:   $([ $REG_L2_PASS -eq 1 ] && echo PASS || echo FAIL)"
    fi
fi
if [[ "$SUITE" == "l3" || "$SUITE" == "all" ]]; then
    if [[ $REG_L3_SKIP -eq 1 ]]; then
        echo "  REG-L3:   SKIP"
    else
        echo "  REG-L3:   $([ $REG_L3_PASS -eq 1 ] && echo PASS || echo FAIL)"
    fi
fi

if [[ $UNIT_PASS -eq 0 && ("$SUITE" == "unit" || "$SUITE" == "all") ]]; then
    exit 1
fi
if [[ $REG02_PASS -eq 0 && $REG02_SKIP -eq 0 && ("$SUITE" == "reg02" || "$SUITE" == "all") ]]; then
    exit 1
fi
if [[ $REG04_PASS -eq 0 && ("$SUITE" == "reg04" || "$SUITE" == "all") ]]; then
    exit 1
fi
if [[ $REG05_PASS -eq 0 && $REG05_SKIP -eq 0 && ("$SUITE" == "reg05" || "$SUITE" == "all") ]]; then
    exit 1
fi
if [[ $REG_K2_PASS -eq 0 && ("$SUITE" == "k2" || "$SUITE" == "all") ]]; then
    exit 1
fi
if [[ $REG_K7_PASS -eq 0 && ("$SUITE" == "k7" || "$SUITE" == "framework" || "$SUITE" == "all") ]]; then
    exit 1
fi
if [[ $REG_D_PASS -eq 0 && ("$SUITE" == "k17" || "$SUITE" == "framework" || "$SUITE" == "all") ]]; then
    exit 1
fi
if [[ $REG_B_PASS -eq 0 && ("$SUITE" == "k17" || "$SUITE" == "framework" || "$SUITE" == "all") ]]; then
    exit 1
fi
if [[ $REG_C_PASS -eq 0 && ("$SUITE" == "k17" || "$SUITE" == "framework" || "$SUITE" == "all") ]]; then
    exit 1
fi
if [[ $REG_K17_PASS -eq 0 && ("$SUITE" == "k17" || "$SUITE" == "framework" || "$SUITE" == "all") ]]; then
    exit 1
fi
if [[ $REG_K14_PASS -eq 0 && ("$SUITE" == "k17" || "$SUITE" == "framework" || "$SUITE" == "all") ]]; then
    exit 1
fi
if [[ $REG_K16_PASS -eq 0 && ("$SUITE" == "k16" || "$SUITE" == "k17" || "$SUITE" == "framework" || "$SUITE" == "all") ]]; then
    exit 1
fi
if [[ $REG_RULES_PASS -eq 0 && ("$SUITE" == "framework" || "$SUITE" == "all") ]]; then
    exit 1
fi
if [[ $REG_O8_PASS -eq 0 && ("$SUITE" == "o8" || "$SUITE" == "framework" || "$SUITE" == "all") ]]; then
    exit 1
fi
if [[ $REG_C9_PASS -eq 0 && ("$SUITE" == "framework" || "$SUITE" == "all") ]]; then
    exit 1
fi
if [[ $REG_L3_SKILL_PASS -eq 0 && ("$SUITE" == "l3skill" || "$SUITE" == "framework" || "$SUITE" == "all") ]]; then
    exit 1
fi
if [[ $REG_L2_PASS -eq 0 && $REG_L2_SKIP -eq 0 && ("$SUITE" == "l2" || "$SUITE" == "all") ]]; then
    exit 1
fi
if [[ $REG_L3_PASS -eq 0 && $REG_L3_SKIP -eq 0 && ("$SUITE" == "l3" || "$SUITE" == "all") ]]; then
    exit 1
fi
exit 0
