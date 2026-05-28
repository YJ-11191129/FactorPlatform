from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

import fitz
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "pdf"
ASSET_DIR = OUT_DIR / "assets"
PREVIEW_DIR = OUT_DIR / "previews"
PDF_PATH = OUT_DIR / "factorplatform_showcase.pdf"
RUNTIME_PATH = ROOT / "data" / "runtime" / "demo_lan.pids.json"

PAGE_W = 13.333 * inch
PAGE_H = 7.5 * inch
TOTAL_PAGES = 17

NAVY = colors.HexColor("#0F172A")
INK = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#526173")
SUBTLE = colors.HexColor("#7B8794")
TEAL = colors.HexColor("#008B8B")
TEAL_DARK = colors.HexColor("#0F766E")
TEAL_SOFT = colors.HexColor("#E7F7F6")
MINT = colors.HexColor("#F0FAF8")
BG = colors.HexColor("#F8FBFC")
BORDER = colors.HexColor("#D6E4EC")
SURFACE = colors.white
AMBER = colors.HexColor("#D97706")
AMBER_SOFT = colors.HexColor("#FFF7E6")
VIOLET = colors.HexColor("#6D5BD0")
VIOLET_SOFT = colors.HexColor("#F1F0FF")
SLATE_SOFT = colors.HexColor("#EEF4F7")
GREEN = colors.HexColor("#16A34A")


def setup_fonts() -> str:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return "STSong-Light"


FONT = setup_fonts()


def paragraph(text: str, size: int = 12, color=NAVY, leading: int | None = None) -> Paragraph:
    safe_lines = [escape(line) for line in text.split("\n")]
    return Paragraph(
        "<br/>".join(safe_lines),
        ParagraphStyle(
            name=f"p-{size}-{color}",
            fontName=FONT,
            fontSize=size,
            leading=leading or max(13, int(size * 1.45)),
            textColor=color,
            spaceAfter=0,
        ),
    )


def draw_para(
    c: Canvas,
    text: str,
    x: float,
    y_top: float,
    w: float,
    h: float,
    size: int = 12,
    color=NAVY,
    leading: int | None = None,
) -> float:
    p = paragraph(text, size=size, color=color, leading=leading)
    _, used_h = p.wrap(w, h)
    p.drawOn(c, x, y_top - used_h)
    return y_top - used_h


def read_runtime() -> dict[str, str]:
    if not RUNTIME_PATH.exists():
        return {}
    try:
        raw = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {str(k): str(v) for k, v in raw.items()}


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as im:
        return im.size


def background(c: Canvas) -> None:
    c.setFillColor(BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#EAF6F5"))
    c.circle(PAGE_W - 70, PAGE_H - 60, 130, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#F5FAFC"))
    c.circle(40, 50, 95, fill=1, stroke=0)


def footer(c: Canvas, page_no: int) -> None:
    c.setFillColor(SUBTLE)
    c.setFont(FONT, 8)
    c.drawString(42, 22, "用于路演展示与研究流程说明 - 非投资建议")
    c.drawRightString(PAGE_W - 42, 22, f"{page_no:02d}/{TOTAL_PAGES:02d}")


def header(c: Canvas, title: str, subtitle: str, page_no: int) -> None:
    background(c)
    c.setFillColor(TEAL)
    c.roundRect(42, PAGE_H - 78, 5, 35, 2.5, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont(FONT, 23)
    c.drawString(58, PAGE_H - 61, title)
    c.setFillColor(MUTED)
    c.setFont(FONT, 9.5)
    c.drawRightString(PAGE_W - 42, PAGE_H - 56, subtitle)
    footer(c, page_no)


def pill(
    c: Canvas,
    text: str,
    x: float,
    y: float,
    fill=TEAL_SOFT,
    stroke=colors.HexColor("#BFE4E2"),
    text_color=TEAL_DARK,
) -> float:
    pad_x = 11
    width = max(56, len(text) * 6.2 + pad_x * 2)
    height = 22
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(0.8)
    c.roundRect(x, y, width, height, 11, fill=1, stroke=1)
    c.setFillColor(text_color)
    c.setFont(FONT, 8.8)
    c.drawCentredString(x + width / 2, y + 7, text)
    return width


def card(c: Canvas, x: float, y: float, w: float, h: float, radius: float = 12, fill=SURFACE) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.9)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)


def draw_image_fit(c: Canvas, path: Path, x: float, y: float, w: float, h: float, radius: float = 12) -> None:
    card(c, x, y, w, h, radius=radius)
    if not path.exists():
        c.setFillColor(AMBER_SOFT)
        c.roundRect(x + 10, y + 10, w - 20, h - 20, max(4, radius - 4), fill=1, stroke=0)
        c.setFillColor(AMBER)
        c.setFont(FONT, 11)
        c.drawCentredString(x + w / 2, y + h / 2, f"缺少截图: {path.name}")
        return
    iw, ih = image_size(path)
    scale = min((w - 14) / iw, (h - 14) / ih)
    dw = iw * scale
    dh = ih * scale
    dx = x + (w - dw) / 2
    dy = y + (h - dh) / 2
    c.drawImage(str(path), dx, dy, width=dw, height=dh, preserveAspectRatio=True, mask="auto")


def metric_tile(c: Canvas, x: float, y: float, w: float, label: str, value: str, note: str, color=TEAL) -> None:
    card(c, x, y, w, 72, radius=10)
    c.setFillColor(color)
    c.setFont(FONT, 16)
    c.drawString(x + 16, y + 43, value)
    c.setFillColor(NAVY)
    c.setFont(FONT, 9.5)
    c.drawString(x + 16, y + 26, label)
    c.setFillColor(MUTED)
    c.setFont(FONT, 8)
    c.drawString(x + 16, y + 11, note)


def bullet_list(c: Canvas, items: list[str], x: float, y_top: float, w: float, size: int = 9.6, gap: float = 11) -> float:
    y = y_top
    for item in items:
        c.setFillColor(TEAL)
        c.circle(x + 4, y - 5, 2.5, fill=1, stroke=0)
        y = draw_para(c, item, x + 16, y + 1, w - 18, 50, size=size, color=INK) - gap
    return y


def section_card(c: Canvas, x: float, y: float, w: float, h: float, title: str, body: str, tag: str, tone=TEAL) -> None:
    card(c, x, y, w, h, radius=12)
    c.setFillColor(tone)
    c.roundRect(x + 16, y + h - 34, 5, 20, 2.5, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont(FONT, 12)
    c.drawString(x + 30, y + h - 28, title)
    draw_para(c, body, x + 16, y + h - 50, w - 32, max(24, h - 84), size=9.2, color=MUTED)
    pill(c, tag, x + 16, y + 14, fill=SLATE_SOFT, stroke=BORDER, text_color=TEAL_DARK)


def cover(c: Canvas, runtime: dict[str, str]) -> None:
    background(c)
    lan_host = runtime.get("lan_host", "192.168.10.109")
    mode = runtime.get("mode", "REAL")
    c.setFillColor(TEAL)
    c.roundRect(54, PAGE_H - 114, 7, 52, 3.5, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont(FONT, 34)
    c.drawString(76, PAGE_H - 82, "FactorPlatform")
    c.setFont(FONT, 21)
    c.drawString(76, PAGE_H - 116, "AI 金融研究与回测平台路演材料")
    draw_para(
        c,
        "面向机构投研与量化研究流程的本地化演示版本。平台把数据维护、AI 策略生成、因子研究、qLib 回测、信号筛选、绩效归因和市场状态监控统一到一个可路演的研究工作台中。",
        76,
        PAGE_H - 155,
        405,
        92,
        size=12,
        color=MUTED,
    )
    x = 76
    for label, fill, stroke, color in [
        (f"MODE={mode}", TEAL_SOFT, colors.HexColor("#BFE4E2"), TEAL_DARK),
        ("qlib CN/US", VIOLET_SOFT, colors.HexColor("#DAD6FF"), VIOLET),
        ("DeepSeek + qwen3", TEAL_SOFT, colors.HexColor("#BFE4E2"), TEAL_DARK),
        ("Risk-aware", AMBER_SOFT, colors.HexColor("#FAD7A0"), AMBER),
    ]:
        x += pill(c, label, x, PAGE_H - 238, fill=fill, stroke=stroke, text_color=color) + 8

    metric_tile(c, 76, 137, 126, "核心链路", "7", "研究模块闭环", TEAL)
    metric_tile(c, 215, 137, 126, "演示方式", "LAN", "其他电脑浏览器访问", VIOLET)
    metric_tile(c, 354, 137, 126, "兜底模式", "Read-only", "显式标记 mock", AMBER)

    c.setFillColor(NAVY)
    c.setFont(FONT, 11)
    c.drawString(76, 101, "演示入口")
    c.setFillColor(MUTED)
    c.setFont(FONT, 9.2)
    c.drawString(76, 82, "本机: http://127.0.0.1:3001/dashboard")
    c.drawString(76, 65, f"局域网: http://{lan_host}:3001/dashboard")
    c.setFillColor(AMBER)
    c.setFont(FONT, 8.6)
    c.drawString(76, 47, "只开放前端地址；后端 API、docs、模型密钥和本地数据留在主机本机。")

    draw_image_fit(c, ASSET_DIR / "01-dashboard.png", 520, 82, 386, 323, radius=14)
    footer(c, 1)


def executive_summary(c: Canvas) -> None:
    header(c, "路演叙事主线", "from product value to verifiable research workflow", 2)
    draw_para(
        c,
        "这份材料不只展示界面，而是说明一个可运行的投研闭环：用户用自然语言提出策略需求，系统生成结构化策略方案，使用已更新的 qlib CN/US 数据进行可审计回测，再把信号、绩效和市场状态放到同一条证据链中。",
        64,
        PAGE_H - 112,
        820,
        56,
        size=12,
        color=INK,
    )
    cards = [
        ("给业务方看的价值", "把策略想法从口头描述推进到可执行、可回测、可解释的研究样本，减少现场演示时的割裂感。", "Product Story", TEAL),
        ("给技术方看的可信度", "强调本地 Docker DB、API 代理、qLib 数据源、provider readiness 和健康检查，让演示不是静态 mock。", "Engineering Proof", VIOLET),
        ("给风控方看的边界", "所有结论都以研究辅助、概率判断、风险约束和人工复核为前提，不做收益承诺或投资建议。", "Risk Boundary", AMBER),
    ]
    x = 64
    for title, body, tag, tone in cards:
        section_card(c, x, 257, 255, 135, title, body, tag, tone)
        x += 279
    section_card(
        c,
        64,
        96,
        818,
        108,
        "现场讲解建议",
        "先用项目概览建立整体地图，再进入 AI 策略生成和回测结果；接着展示因子研究、信号中心、绩效归因与 Regime Monitor，最后切到数据维护和 LAN 路演机制。这样听众能看到从想法到证据再到部署的完整路径。",
        "10-15 分钟主线",
        TEAL,
    )


def pain_points(c: Canvas) -> None:
    header(c, "为什么需要这个平台", "research workflow gaps before integration", 3)
    points = [
        ("策略想法分散", "自然语言想法、研究假设、参数、数据源和回测脚本通常散落在不同工具中，难以复盘。"),
        ("数据新鲜度难控", "回测失败常来自数据源过期或路径不一致；现场演示尤其需要一键诊断和可解释降级。"),
        ("AI 生成缺少约束", "大模型可以生成策略，但必须经过字段校验、时序假设、交易成本和数据可用性检查。"),
        ("结果解释不完整", "只给收益曲线不够，需要把数据源、费用、换手、风险区间、市场状态和拒绝原因一起呈现。"),
    ]
    y = PAGE_H - 128
    for i, (title, body) in enumerate(points, start=1):
        tone = [TEAL, VIOLET, AMBER, GREEN][i - 1]
        card(c, 72, y - 68, 812, 58, radius=12)
        c.setFillColor(tone)
        c.roundRect(92, y - 50, 34, 30, 8, fill=1, stroke=0)
        c.setFillColor(SURFACE)
        c.setFont(FONT, 14)
        c.drawCentredString(109, y - 39, str(i))
        c.setFillColor(NAVY)
        c.setFont(FONT, 12)
        c.drawString(148, y - 28, title)
        draw_para(c, body, 148, y - 43, 665, 28, size=9.5, color=MUTED)
        y -= 76
    draw_para(
        c,
        "FactorPlatform 的展示重点，是把这些阻塞点变成可看见、可检查、可兜底的产品能力。",
        72,
        76,
        720,
        24,
        size=11,
        color=TEAL_DARK,
    )


def architecture_slide(c: Canvas) -> None:
    header(c, "技术架构", "Docker DB + local API + Next.js LAN frontend", 4)
    layers = [
        ("数据层", ["qlib CN/US daily", "Postgres metadata", "Redis tasks/cache", "Data freshness audit"], TEAL),
        ("后端服务", ["FastAPI on 8003", "Auth key guard", "Backtest/Factor APIs", "AI provider probes"], VIOLET),
        ("AI 与研究", ["DeepSeek v4/pro key local", "Ollama qwen3:14b", "StrategySpec validator", "qLib execution adapter"], AMBER),
        ("前端展示", ["Next production app", "LAN only 3001", "Dashboard shell", "Read-only fallback banner"], GREEN),
    ]
    x_positions = [58, 282, 506, 730]
    for x, (title, items, tone) in zip(x_positions, layers):
        card(c, x, 188, 178, 224, radius=14)
        c.setFillColor(tone)
        c.roundRect(x + 16, 374, 44, 24, 8, fill=1, stroke=0)
        c.setFillColor(SURFACE)
        c.setFont(FONT, 10)
        c.drawCentredString(x + 38, 382, title)
        bullet_list(c, items, x + 18, 346, 140, size=8.9, gap=7)
    c.setStrokeColor(colors.HexColor("#9FCFCC"))
    c.setLineWidth(1.5)
    for x in [236, 460, 684]:
        c.line(x + 8, 300, x + 40, 300)
        c.line(x + 32, 307, x + 40, 300)
        c.line(x + 32, 293, x + 40, 300)
    card(c, 72, 73, 812, 88, radius=12)
    c.setFillColor(TEAL)
    c.roundRect(94, 126, 5, 22, 2.5, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont(FONT, 12)
    c.drawString(112, 133, "安全边界")
    pill(c, "LAN frontend only", 735, 124, fill=TEAL_SOFT, stroke=colors.HexColor("#BFE4E2"), text_color=TEAL_DARK)
    draw_para(
        c,
        "路演方案 A 只把 Next 前端暴露到局域网；前端代理仍访问主机本机的 127.0.0.1:8003。真实 key、后端 docs、数据库端口和模型服务不对外分享。",
        94,
        108,
        740,
        36,
        size=9.2,
        color=MUTED,
    )


def workflow_slide(c: Canvas) -> None:
    header(c, "AI 策略到回测的闭环", "prompt -> StrategySpec -> qlib backtest -> evidence", 5)
    steps = [
        ("用户需求", "自然语言描述策略目标、资产范围、持仓周期和风险偏好。", TEAL),
        ("策略结构化", "大模型生成 StrategySpec，系统校验字段、参数和时序假设。", VIOLET),
        ("受控回测", "默认接入已更新 qlib CN/US；费用、换手和数据源写入结果。", AMBER),
        ("证据沉淀", "结果进入绩效、信号、Regime 与数据健康页面，方便复盘。", GREEN),
    ]
    y = PAGE_H - 135
    for i, (title, body, tone) in enumerate(steps, start=1):
        x = 82 + (i - 1) * 210
        c.setFillColor(tone)
        c.roundRect(x, y, 54, 54, 16, fill=1, stroke=0)
        c.setFillColor(SURFACE)
        c.setFont(FONT, 19)
        c.drawCentredString(x + 27, y + 20, str(i))
        c.setFillColor(NAVY)
        c.setFont(FONT, 13)
        c.drawString(x - 2, y - 28, title)
        draw_para(c, body, x - 2, y - 46, 150, 70, size=9, color=MUTED)
        if i < len(steps):
            c.setStrokeColor(colors.HexColor("#9FCFCC"))
            c.setLineWidth(1.5)
            c.line(x + 74, y + 27, x + 164, y + 27)
            c.line(x + 154, y + 35, x + 164, y + 27)
            c.line(x + 154, y + 19, x + 164, y + 27)
    section_card(
        c,
        64,
        95,
        250,
        118,
        "可解释性",
        "回测结果连同数据源、时序保护、成本、换手、风险暴露和诊断日志一起展示。",
        "Audit trail",
        TEAL,
    )
    section_card(
        c,
        354,
        95,
        250,
        118,
        "可演示性",
        "主机运行服务，其他电脑浏览器访问；异常时切到只读 Demo fallback。",
        "Roadshow mode",
        VIOLET,
    )
    section_card(
        c,
        644,
        95,
        250,
        118,
        "风控边界",
        "定位为研究辅助，需要人工复核、样本外验证和风险约束。",
        "Not advice",
        AMBER,
    )


def screenshot_slide(c: Canvas, page_no: int, title: str, subtitle: str, shot: str, points: list[str], tags: list[str]) -> None:
    header(c, title, subtitle, page_no)
    draw_image_fit(c, ASSET_DIR / shot, 322, 76, 592, 360, radius=14)
    card(c, 54, 99, 236, 321, radius=12)
    c.setFillColor(TEAL)
    c.setFont(FONT, 12)
    c.drawString(75, 391, "展示重点")
    bullet_list(c, points, 74, 358, 186, size=8.9, gap=9)
    x = 74
    y = 129
    for tag in tags:
        width = pill(c, tag, x, y, fill=SLATE_SOFT, stroke=BORDER, text_color=TEAL_DARK)
        x += width + 6
        if x > 244:
            x = 74
            y -= 28


def data_governance_slide(c: Canvas) -> None:
    header(c, "数据治理与健康检查", "freshness, lineage, and roadshow readiness", 14)
    draw_image_fit(c, ASSET_DIR / "06-data-maintenance.png", 372, 125, 535, 299, radius=14)
    section_card(
        c,
        58,
        294,
        270,
        130,
        "为什么要单独展示数据维护",
        "回测可信度的第一关是数据新鲜度和数据源一致性。此前 stale Wind parquet 会阻塞 AI 回测，因此现在默认把本地 AI 回测切到已更新的 qlib CN/US。",
        "Freshness first",
        TEAL,
    )
    section_card(
        c,
        58,
        145,
        270,
        125,
        "路演前检查",
        "通过健康脚本确认 Docker DB、API、前端代理、qLib 路径、AI provider 和 fallback 状态，现场失败时能快速定位是数据、服务还是网络问题。",
        "Preflight",
        VIOLET,
    )
    card(c, 372, 66, 535, 42, radius=12, fill=AMBER_SOFT)
    c.setFillColor(AMBER)
    c.setFont(FONT, 10)
    c.drawString(394, 91, "展示口径")
    c.setFillColor(MUTED)
    c.setFont(FONT, 8.6)
    c.drawString(394, 76, "过期数据不包装成真实结果；fallback 必须显式标记 mock/demo/read-only。")


def deployment_slide(c: Canvas, runtime: dict[str, str]) -> None:
    header(c, "路演部署方案 A", "host runs services, audience opens browser", 16)
    lan_host = runtime.get("lan_host", "192.168.10.109")
    mode = runtime.get("mode", "REAL")
    steps = [
        ("1. 主机准备", "打开 Docker Desktop，启动 Postgres/Redis，本地 API 使用 8003，前端使用 production next start。"),
        ("2. 健康检查", "确认 /backend/health、qLib CN/US、新鲜度、DeepSeek/local provider 和 Signal Center 都可用。"),
        ("3. 现场访问", f"主机访问 127.0.0.1:3001；其他电脑访问 http://{lan_host}:3001/dashboard。"),
        ("4. 兜底策略", "如网络或数据链路异常，显式进入 DEMO FALLBACK / MOCK DATA / READ ONLY，不伪装成真实链路。"),
    ]
    y = PAGE_H - 130
    for title, body in steps:
        card(c, 72, y - 60, 812, 52, radius=12)
        c.setFillColor(TEAL_SOFT)
        c.roundRect(92, y - 47, 124, 27, 9, fill=1, stroke=0)
        c.setFillColor(TEAL_DARK)
        c.setFont(FONT, 10)
        c.drawCentredString(154, y - 38, title)
        draw_para(c, body, 240, y - 22, 585, 28, size=9.4, color=INK)
        y -= 67
    card(c, 72, 66, 812, 54, radius=12, fill=AMBER_SOFT)
    c.setFillColor(AMBER)
    c.setFont(FONT, 11)
    c.drawString(92, 98, "当前演示模式")
    c.setFillColor(NAVY)
    c.setFont(FONT, 15)
    c.drawString(202, 96, f"MODE={mode}")
    c.setFillColor(MUTED)
    c.setFont(FONT, 9)
    c.drawString(92, 78, "不要分享后端 docs、API key、模型 key 或数据库端口；其他电脑只需要浏览器。")


def roadmap_slide(c: Canvas) -> None:
    header(c, "后续完善方向", "what makes the demo feel less thin", 17)
    items = [
        ("更强策略库", "沉淀可复用 StrategySpec 模板、参数边界、失败样例和回测解释模板。", "Near-term"),
        ("因子工作流", "把因子挖掘、选股雷达、组合构建与回测结果之间的跳转链路做得更顺。", "Near-term"),
        ("报告自动化", "回测完成后自动生成研究摘要、风险提示、参数说明和可导出的 PDF 附件。", "Mid-term"),
        ("多环境演示", "准备离线 demo 包、Docker compose 全量路径和一键 fallback，降低现场网络风险。", "Mid-term"),
    ]
    x = 68
    y = 302
    for i, (title, body, tag) in enumerate(items):
        section_card(c, x, y, 385, 122, title, body, tag, [TEAL, VIOLET, AMBER, GREEN][i])
        x = 506 if x < 200 else 68
        if x == 68:
            y -= 150
    card(c, 68, 58, 823, 86, radius=14, fill=SLATE_SOFT)
    c.setFillColor(NAVY)
    c.setFont(FONT, 14)
    c.drawString(92, 113, "合规与风险说明")
    draw_para(
        c,
        "本平台用于研究辅助、风险识别和流程演示，不构成投资建议。模型输出、信号筛选和回测结果都需要人工复核、样本外验证、交易成本约束与风险限额管理。",
        92,
        94,
        748,
        40,
        size=10,
        color=MUTED,
    )


def build_pdf() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    runtime = read_runtime()
    c = Canvas(str(PDF_PATH), pagesize=(PAGE_W, PAGE_H))
    c.setTitle("FactorPlatform Showcase")
    c.setAuthor("FactorPlatform")
    c.setSubject("AI financial research and backtest platform roadshow deck")

    cover(c, runtime)
    c.showPage()
    executive_summary(c)
    c.showPage()
    pain_points(c)
    c.showPage()
    architecture_slide(c)
    c.showPage()
    workflow_slide(c)
    c.showPage()
    screenshot_slide(
        c,
        6,
        "项目概览入口",
        "module gateway without left sidebar",
        "01-dashboard.png",
        [
            "无左侧菜单的项目概览页，适合路演从全局地图进入模块。",
            "量化研究、AI 工具、数据产品和效率工具使用统一卡片风格。",
            "顶部状态清晰展示 API、Snapshot 和 Production/Demo 模式。",
        ],
        ["Dashboard", "Production", "统一入口"],
    )
    c.showPage()
    screenshot_slide(
        c,
        7,
        "AI 策略生成",
        "natural language to validated StrategySpec",
        "02-ai-strategy.png",
        [
            "用户用自然语言描述策略需求，系统转成结构化 StrategySpec。",
            "DeepSeek 与本地 qwen3 provider 可检查 readiness，但真实 key 不输出到文档。",
            "先校验字段、时序和可执行性，再进入受控回测。",
        ],
        ["DeepSeek", "qwen3:14b", "Validator"],
    )
    c.showPage()
    screenshot_slide(
        c,
        8,
        "因子分析平台",
        "factor registry, qlib status, and mining readiness",
        "07-factors.png",
        [
            "Factor registry 先可用，qLib mining 状态作为局部模块提示，不拖垮整页。",
            "因子元数据、分类、表达式和运行入口放在一个研究工作台中。",
            "适合向技术听众解释因子研究从目录到执行的链路。",
        ],
        ["Factor Registry", "qlib", "Mining"],
    )
    c.showPage()
    screenshot_slide(
        c,
        9,
        "选股雷达",
        "cross-sectional factor ranking with qlib families",
        "10-stock-radar.png",
        [
            "按 qlib 因子族群构建多因子横截面排序，因子仅使用 signal_date 及以前数据。",
            "展示动量、趋势、低波、量价配合等快速组合，更贴近业务研究场景。",
            "作为因子研究到候选标的筛选的中间层。",
        ],
        ["Stock Radar", "Factor Families", "Signal Date"],
    )
    c.showPage()
    screenshot_slide(
        c,
        10,
        "回测工作台",
        "qlib data source and controlled execution",
        "03-backtest-lab.png",
        [
            "普通策略和 qlib 因子组合在统一工作台发起，避免脚本分散。",
            "默认数据源切到已更新 qlib CN/US，过期 Wind parquet 只作为 fallback。",
            "运行结果记录数据源、成本、换手和一根 bar 延迟的时序假设。",
        ],
        ["qLib CN/US", "Backtest", "Cost"],
    )
    c.showPage()
    screenshot_slide(
        c,
        11,
        "回测结果证据",
        "not only return curves",
        "04-backtest-result.png",
        [
            "结果页展示收益、Sharpe、回撤、日均换手和交易成本。",
            "净值明细包含 gross return、net return、turnover 和 cost。",
            "页面明确数据源与时序保护，便于解释结果可信度。",
        ],
        ["Evidence", "Sharpe", "Turnover"],
    )
    c.showPage()
    screenshot_slide(
        c,
        12,
        "信号中心",
        "regime-aware screening and shadow validation",
        "05-signal-center.png",
        [
            "信号中心强调筛选和验证，不做喊单式展示。",
            "Router decision、shadow candidates、performance evidence 放在同一界面。",
            "现场可以解释为什么信号被放行、降权或阻断。",
        ],
        ["Router", "Shadow", "Evidence"],
    )
    c.showPage()
    screenshot_slide(
        c,
        13,
        "绩效归因与市场状态",
        "performance attribution plus regime context",
        "08-performance.png",
        [
            "绩效页用于把信号输出和实际跟踪结果连接起来。",
            "按 regime、symbol、source 等维度拆解，便于讨论风险暴露。",
            "与 Regime Monitor 配合说明平台是风险感知的研究终端。",
        ],
        ["Attribution", "Regime", "Tracking"],
    )
    c.showPage()
    data_governance_slide(c)
    c.showPage()
    screenshot_slide(
        c,
        15,
        "市场状态监控",
        "current regime, timeline, and shock context",
        "09-regime-monitor.png",
        [
            "展示当前风险状态、市场结构、相似区间和近期冲击事件。",
            "用于解释策略或信号为什么在不同 regime 下应被调整。",
            "把宏观状态、风险状态和历史相似样本接入同一套研究流程。",
        ],
        ["Regime", "Timeline", "Shock Context"],
    )
    c.showPage()
    deployment_slide(c, runtime)
    c.showPage()
    roadmap_slide(c)
    c.save()


def render_previews() -> None:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    for old in PREVIEW_DIR.glob("factorplatform_showcase_page_*.png"):
        old.unlink()
    doc = fitz.open(PDF_PATH)
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        pix.save(PREVIEW_DIR / f"factorplatform_showcase_page_{i:02d}.png")
    doc.close()


if __name__ == "__main__":
    build_pdf()
    render_previews()
    print(PDF_PATH)
