#!/usr/bin/env python3
"""生成分层架构 PPT 与完整产品规划 Word（迪诺链专项）。"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

# 产品架构四层
PRODUCT_LAYERS: list[tuple[str, list[str], str]] = [
    (
        "L4 业务产品平台层",
        [
            "存证平台",
            "溯源平台",
            "协作平台",
            "运营监管平台",
            "数据共享平台",
            "RWA资产平台",
            "合约集市平台",
            "政务协同平台",
        ],
        "1A5276",
    ),
    (
        "L3 通用系统层",
        [
            "数字身份关系系统",
            "访问控制系统",
            "开发者服务系统",
            "区块链BaaS系统",
            "资产管理系统",
            "运营监控系统",
            "风控阻断系统",
            "开放服务系统",
            "联盟治理系统",
            "跨链互联系统",
            "合约生命周期系统",
            "密钥托管系统",
        ],
        "1565C0",
    ),
    (
        "L2 组件层",
        [
            "数字身份组件",
            "属性组件",
            "存证组件",
            "溯源组件",
            "消息组件",
            "资产组件",
            "合约研发组件",
            "合约部署组件",
            "合约测试组件",
            "权限组件",
            "加密组件",
            "索引组件",
            "网关组件",
            "隐私计算组件",
            "共识组件",
            "节点管理组件",
            "密钥管理组件",
            "审计组件",
            "通知组件",
            "数据同步组件",
        ],
        "3949AB",
    ),
    (
        "L1 基础设施层",
        ["区块链核心", "双足预言机", "跨链协议", "内容存储系统"],
        "263238",
    ),
]

# 系统架构（部署视图）
SYSTEM_LAYERS: list[tuple[str, list[str], str]] = [
    (
        "接入层",
        ["应用SDK", "REST API", "Web UI", "密钥解锁API"],
        "00695C",
    ),
    (
        "区块链网关",
        ["应用对接", "业务适配", "接口限流", "多链路由", "链上链下融合"],
        "00838F",
    ),
    (
        "开放服务（无状态）",
        [
            "数字身份服务",
            "资产索引服务",
            "权限索引服务",
            "ISV插件服务",
        ],
        "1565C0",
    ),
    (
        "协作链服务",
        ["身份互认", "资产索引聚合", "能力注册发现"],
        "3949AB",
    ),
    (
        "工作链 / 行业链",
        ["政务基础链", "医保链", "财政链", "税务链", "司法链"],
        "5C6BC0",
    ),
    (
        "链核心",
        ["共识模块", "合约虚拟机", "密态存储", "交易执行引擎"],
        "263238",
    ),
    (
        "链下适配",
        ["双足预言机", "跨链中继", "内容存储", "业务系统连接器"],
        "37474F",
    ),
    (
        "运维与安全",
        ["监控告警", "日志审计", "密钥HSM", "国密算法模块"],
        "455A64",
    ),
]


def _rgb(hex6: str) -> RGBColor:
    h = hex6.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _add_layered_slide(prs: Presentation, title: str, layers: list[tuple[str, list[str], str]]) -> None:
    blank = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank)
    sw, sh = prs.slide_width, prs.slide_height
    margin_x = Inches(0.35)
    top = Inches(0.25)
    title_h = Inches(0.55)

    tb = slide.shapes.add_textbox(margin_x, top, sw - 2 * margin_x, title_h)
    tf = tb.text_frame
    tf.text = title
    p = tf.paragraphs[0]
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = _rgb("212121")
    p.alignment = PP_ALIGN.CENTER

    layer_top = top + title_h + Inches(0.15)
    usable_h = sh - layer_top - Inches(0.25)
    n = len(layers)
    gap = Inches(0.08)
    layer_h = (usable_h - gap * (n - 1)) / n
    label_w = Inches(1.55)
    inner_x = margin_x + label_w + Inches(0.08)
    inner_w = sw - inner_x - margin_x

    for i, (layer_name, items, color) in enumerate(layers):
        y = layer_top + i * (layer_h + gap)
        # 层标签
        lbl = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE, margin_x, y, label_w, layer_h
        )
        lbl.fill.solid()
        lbl.fill.fore_color.rgb = _rgb(color)
        lbl.line.color.rgb = _rgb("B0BEC5")
        ltf = lbl.text_frame
        ltf.word_wrap = True
        ltf.vertical_anchor = MSO_ANCHOR.MIDDLE
        lp = ltf.paragraphs[0]
        lp.text = layer_name
        lp.font.size = Pt(11)
        lp.font.bold = True
        lp.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        lp.alignment = PP_ALIGN.CENTER

        cols = min(5, max(3, (len(items) + 3) // 4))
        rows = (len(items) + cols - 1) // cols
        box_gap = Inches(0.06)
        box_w = (inner_w - box_gap * (cols - 1)) / cols
        box_h = (layer_h - box_gap * (rows - 1)) / max(rows, 1)

        for idx, name in enumerate(items):
            r, c = divmod(idx, cols)
            bx = inner_x + c * (box_w + box_gap)
            by = y + r * (box_h + box_gap)
            shp = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, bx, by, box_w, box_h)
            shp.fill.solid()
            shp.fill.fore_color.rgb = RGBColor(0xFA, 0xFA, 0xFA)
            shp.line.color.rgb = _rgb(color)
            shp.line.width = Pt(1.25)
            stf = shp.text_frame
            stf.word_wrap = True
            stf.vertical_anchor = MSO_ANCHOR.MIDDLE
            sp = stf.paragraphs[0]
            sp.text = name
            sp.font.size = Pt(9 if len(name) > 8 else 10)
            sp.font.color.rgb = _rgb("212121")
            sp.alignment = PP_ALIGN.CENTER


def build_ppt(path: Path, title: str, layers: list[tuple[str, list[str], str]]) -> None:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    _add_layered_slide(prs, title, layers)
    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(path))


def export_png(pptx: Path, png: Path) -> None:
    try:
        subprocess.run(
            ["officecli", "view", str(pptx), "screenshot", "-o", str(png)],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # 无 officecli screenshot 时跳过
        pass


def build_word(out_docx: Path, ref_docx: Path, tpl_docx: Path, product_png: Path, system_png: Path) -> None:
    """以参考稿为底稿补齐章节，并插入架构图 PNG。"""
    shutil.copy2(ref_docx, out_docx)

    sections = _compose_planning_body("", product_png, system_png)
    import json
    import tempfile

    batch: list[dict] = []
    for heading, body in sections:
        # 在对应 Heading2 标题后插入正文（模版/参考稿共用标题名）
        for para in body.split("\n"):
            para = para.strip()
            if not para:
                continue
            batch.append(
                {
                    "command": "add",
                    "parent": "/body",
                    "type": "paragraph",
                    "after": f"find:{heading}",
                    "props": {"text": para, "style": "Normal"},
                }
            )
        if heading == "产品架构" and product_png.is_file():
            batch.append(
                {
                    "command": "add",
                    "parent": "/body",
                    "type": "image",
                    "after": f"find:{heading}",
                    "props": {"path": str(product_png.resolve()), "width": "16cm"},
                }
            )
        if heading == "系统架构" and system_png.is_file():
            batch.append(
                {
                    "command": "add",
                    "parent": "/body",
                    "type": "image",
                    "after": f"find:{heading}",
                    "props": {"path": str(system_png.resolve()), "width": "16cm"},
                }
            )

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(batch, f, ensure_ascii=False)
        batch_path = f.name
    try:
        result = subprocess.run(
            ["officecli", "batch", str(out_docx), "--input", batch_path],
            check=False,
        )
        if result.returncode != 0:
            print("Warning: batch completed with errors (some headings may be missing in source doc)", file=sys.stderr)
    finally:
        Path(batch_path).unlink(missing_ok=True)


def _compose_planning_body(ref_text: str, product_png: Path, system_png: Path) -> list[tuple[str, str]]:
    """从参考稿提炼并补齐各章节正文。"""
    png_prod = product_png.name if product_png.is_file() else "产品架构图.png"
    png_sys = system_png.name if system_png.is_file() else "系统架构图.png"

    return [
        (
            "目标",
            """总体目标：在技术能力、产品体系丰富度上达到与长安链、趣链科技同等水平；在政务数据共享、现代农业协同等场景打造 2–3 个全国标杆，综合竞争力进入全国区块链厂商前五。

产品方面：以国家区块链网络建设要求与数字合约规模化应用为导向，完善全栈产品体系，强化密码技术核心优势，打造「安全、高效、易用、合规」的自主可控区块链产品。

产品优势：资源消耗较主流竞品降低 40%–50%；全链路国密与分级防护；标准化应用组件覆盖 80% 以上通用场景；原生隐私计算与零知识能力；链上链下协同紧密。

能力方面：轻量节点与边缘部署；复杂网络高可靠传输；多语言合约与安全沙箱；全类型存证；密态与隐私计算；双足预言机多源校验。

技术方面：高性能共识模块化；交易并行执行；合约安全沙箱；全链路密态存储；原生链上隐私；可信预言机网络。

市场宣传方面：对接山东省数字强省与数据要素政策；打造济南政务、潍坊农业标杆；发布白皮书与性能报告；组建产业生态联盟。

应用模式方面：政务统建、产业共建、生态赋能三类模式；省级统筹+地市落地；龙头牵头+联盟共建；平台赋能+共创。""",
        ),
        (
            "产品架构",
            f"""迪诺链产品架构采用四层模型：基础设施层 → 组件层 → 通用系统层 → 业务产品平台层。每一能力单元独立成块，便于组合与演进。

基础设施层包含区块链核心、双足预言机、跨链协议、内容存储系统，为上层提供可信账本、外部数据、跨域互操作与链下内容寻址能力。

组件层将基础能力抽象为可复用组件，包括数字身份、属性、存证、溯源、消息、资产、合约研发/部署/测试，以及权限、加密、索引、网关、隐私计算、共识、节点管理、密钥管理、审计、通知、数据同步等，支撑快速装配行业应用。

通用系统层通过组件组合形成数字身份关系、访问控制、开发者服务、区块链 BaaS、资产管理、运营监控、风控阻断、开放服务、联盟治理、跨链互联、合约生命周期、密钥托管等系统，面向多租户与多联盟场景。

业务产品平台层面向最终用户与监管方，提供存证、溯源、协作、运营监管、数据共享、RWA 资产、合约集市、政务协同等平台化入口。

架构图见：{png_prod}（源文件：产品架构图.pptx）。""",
        ),
        (
            "系统架构",
            f"""系统架构从部署与集成视角描述迪诺链运行形态，与产品架构四层一一对应。

应用通过 SDK/API/UI 接入区块链网关，网关承担应用对接、业务适配、限流与多链路由，并提供链上链下融合、隐私计算等增值能力。

开放服务为无状态服务集群，核心数据上链存证，支持多中心部署；包括数字身份、资产索引、权限索引及 ISV 插件扩展。协作链部署身份互认、资产索引聚合等能力，聚合各工作链开放服务。

工作链/行业链独立运行，满足部门与行业边界；链核心提供共识、合约虚拟机、密态存储与并行执行。链下适配层连接双足预言机、跨链中继、内容存储与业务系统。运维安全层提供监控、审计、HSM 与国密模块。

架构图见：{png_sys}（源文件：系统架构图.pptx）。""",
        ),
        (
            "应用模式",
            """1. 数据开放共享：基于区块链的数据共享、开放、流通模式。
2. 授权模型：一事一授权、协议授权、时间授权、开放授权。
3. 业务协作：跨主体业务协作与合约驱动流程。
4. 密钥使用：人脸、短信等解锁方式，支持免密支付场景。
5. 系统对接：SDK/API/UI 多形态接入，多链适配与安全密钥 API。""",
        ),
        (
            "核心指标",
            """性能：TPS ≥ 5000（典型联盟链配置）；交易确认 P95 < 3s；水平扩展线性度 ≥ 80%。
功能：覆盖存证、溯源、合约、跨链、隐私计算、预言机等全栈能力清单。
安全性：国密算法全链路；密钥分级托管；合约形式化验证与沙箱；等保三级对齐。""",
        ),
        (
            "技术规划",
            """2026 Q3：存证平台 MVP、开放服务 v1、网关多链适配。
2026 Q4：模块化服务化、BaaS 控制台、风控阻断系统 beta。
2027 H1：跨链互联生产级、隐私计算组件 GA、RWA 平台试点。""",
        ),
        (
            "差异化优势与特点",
            """资源消耗低：密码与共识优化，同等硬件资源占用降低 40%–50%。
更安全：存储、传输、合约、密钥全链路国密与分级防护。
链上隐私：零知识、同态与密态计算原生支持。
链上链下协同：网关 + 预言机 + 行为映射，降低业务接入门槛。""",
        ),
        (
            "应用场景",
            """政务数据共享与跨部门协同；医保、财政、税务、司法等行业链；潍坊蔬菜等农业溯源；碳资产与 RWA 资产数字化；供应链金融与合约自动化。""",
        ),
        (
            "产品形态",
            """软件包（链节点 + 控制台）、一体机、私有云、混合云 BaaS、场景 SaaS。支持 X86/ARM，适配信创环境。""",
        ),
        (
            "商业模式",
            """软件许可 + 实施服务；BaaS 订阅；场景套件按年；生态 ISV 分成；标杆项目联合运营。""",
        ),
        (
            "演进计划",
            """1. 存证产品：2026年7–8月，约 1 人月。
2. 开放服务体系：2026年8–10月，约 4 人月。
3. 模块化、服务化：2026年10–12月，约 6 人月。""",
        ),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "../../tasks/project/blockchain-dino-plan/deliverables",
    )
    ap.add_argument("--also-copy-to", type=Path, default=None)
    args = ap.parse_args()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    inputs = Path(__file__).resolve().parents[1]
    ref = inputs / "区块链-产品规划.docx"
    tpl = inputs / "产品规划-模版.docx"

    prod_ppt = out_dir / "产品架构图.pptx"
    sys_ppt = out_dir / "系统架构图.pptx"
    prod_png = out_dir / "产品架构图.png"
    sys_png = out_dir / "系统架构图.png"
    word_out = out_dir / "迪诺链-区块链产品规划.docx"

    build_ppt(prod_ppt, "迪诺链 · 产品架构图", PRODUCT_LAYERS)
    build_ppt(sys_ppt, "迪诺链 · 系统架构图", SYSTEM_LAYERS)
    export_png(prod_ppt, prod_png)
    export_png(sys_ppt, sys_png)
    # officecli screenshot 更可靠
    for ppt, png in ((prod_ppt, prod_png), (sys_ppt, sys_png)):
        if not png.is_file():
            try:
                subprocess.run(
                    ["officecli", "view", str(ppt), "screenshot", "-o", str(png)],
                    check=True,
                    capture_output=True,
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass

    if ref.is_file() and tpl.is_file():
        build_word(word_out, ref, tpl, prod_png, sys_png)

    if args.also_copy_to:
        dest = args.also_copy_to.resolve()
        dest.mkdir(parents=True, exist_ok=True)
        for f in out_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, dest / f.name)

    print(f"Deliverables written to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
