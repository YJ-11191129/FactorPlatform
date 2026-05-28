from __future__ import annotations

from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

import fitz
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "pdf"
ASSET_DIR = OUT_DIR / "project_report_assets"
LEGACY_ASSET_DIR = OUT_DIR / "assets"
DERIVED_DIR = OUT_DIR / "project_report_assets_derived"
PREVIEW_DIR = OUT_DIR / "project_report_previews"
PDF_PATH = OUT_DIR / "factorplatform_project_report.pdf"

PAGE_W = 13.333 * inch
PAGE_H = 7.5 * inch
TOTAL_PAGES = 19

BG = colors.HexColor("#F6FAFC")
INK = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#334155")
SUBTLE = colors.HexColor("#526173")
TEAL = colors.HexColor("#009A9A")
TEAL_DARK = colors.HexColor("#0F766E")
TEAL_SOFT = colors.HexColor("#E6F7F7")
NAVY = colors.HexColor("#10233D")
NAVY_SOFT = colors.HexColor("#EAF1F7")
VIOLET = colors.HexColor("#6D5BD0")
VIOLET_SOFT = colors.HexColor("#F0EEFF")
AMBER = colors.HexColor("#D97706")
AMBER_SOFT = colors.HexColor("#FFF6E5")
GREEN = colors.HexColor("#16A34A")
GREEN_SOFT = colors.HexColor("#E9F8EF")
RED = colors.HexColor("#DC2626")
RED_SOFT = colors.HexColor("#FEECEC")
BORDER = colors.HexColor("#D8E5EC")
SURFACE = colors.white


def setup_fonts() -> tuple[str, str]:
    regular_candidates = [
        Path(r"C:\Windows\Fonts\Deng.ttf"),
        Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf"),
        Path(r"C:\Windows\Fonts\msyh.ttc"),
    ]
    bold_candidates = [
        Path(r"C:\Windows\Fonts\Dengb.ttf"),
        Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
    ]
    regular_path = next((p for p in regular_candidates if p.exists()), None)
    bold_path = next((p for p in bold_candidates if p.exists()), regular_path)
    if not regular_path or not bold_path:
        raise RuntimeError("No CJK font found under C:\\Windows\\Fonts")
    pdfmetrics.registerFont(TTFont("ReportCJK", str(regular_path)))
    pdfmetrics.registerFont(TTFont("ReportCJKBold", str(bold_path)))
    return "ReportCJK", "ReportCJKBold"


FONT, FONT_BOLD = setup_fonts()


def pstyle(size: float, color=INK, leading: float | None = None, bold: bool = False, align: int = 0) -> ParagraphStyle:
    return ParagraphStyle(
        name=f"s-{size}-{str(color)}-{bold}-{align}",
        fontName=FONT_BOLD if bold else FONT,
        fontSize=size,
        leading=leading or size * 1.38,
        textColor=color,
        alignment=align,
        wordWrap="CJK",
        spaceAfter=0,
        spaceBefore=0,
    )


def para(text: str, size: float = 10.5, color=INK, leading: float | None = None, bold: bool = False, align: int = 0) -> Paragraph:
    safe = "<br/>".join(escape(line) for line in text.split("\n"))
    return Paragraph(safe, pstyle(size=size, color=color, leading=leading, bold=bold, align=align))


def draw_para(
    c: Canvas,
    text: str,
    x: float,
    y_top: float,
    w: float,
    h: float,
    size: float = 10.5,
    color=INK,
    leading: float | None = None,
    bold: bool = False,
    align: int = 0,
) -> float:
    block = para(text, size=size, color=color, leading=leading, bold=bold, align=align)
    _, used_h = block.wrap(w, h)
    block.drawOn(c, x, y_top - used_h)
    return y_top - used_h


def background(c: Canvas, dark: bool = False) -> None:
    c.setFillColor(colors.HexColor("#07101D") if dark else BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    if not dark:
        c.setFillColor(colors.HexColor("#E8F7F7"))
        c.circle(PAGE_W - 74, PAGE_H - 70, 130, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#EDF4FA"))
        c.circle(30, 46, 92, fill=1, stroke=0)


def footer(c: Canvas, page_no: int, dark: bool = False) -> None:
    c.setFont(FONT, 7.8)
    c.setFillColor(colors.HexColor("#8BA1B5") if dark else SUBTLE)
    c.drawString(42, 22, "FactorPlatform 项目汇报 - 用于产品介绍、方案评审与商业讨论，不构成投资建议")
    c.drawRightString(PAGE_W - 42, 22, f"{page_no:02d}/{TOTAL_PAGES:02d}")


def header(c: Canvas, page_no: int, title: str, eyebrow: str = "PROJECT REPORT") -> None:
    background(c)
    c.setFillColor(TEAL)
    c.roundRect(42, PAGE_H - 80, 5, 38, 2.5, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 22)
    c.drawString(58, PAGE_H - 62, title)
    c.setFillColor(SUBTLE)
    c.setFont(FONT, 9)
    c.drawRightString(PAGE_W - 42, PAGE_H - 57, eyebrow)
    footer(c, page_no)


def card(c: Canvas, x: float, y: float, w: float, h: float, fill=SURFACE, stroke=BORDER, radius: float = 12) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(0.85)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)


def pill(c: Canvas, text: str, x: float, y: float, fill=TEAL_SOFT, stroke=colors.HexColor("#B9E4E4"), text_color=TEAL_DARK) -> float:
    width = max(58, len(text) * 5.5 + 24)
    height = 22
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.roundRect(x, y, width, height, 11, fill=1, stroke=1)
    c.setFont(FONT_BOLD, 8)
    c.setFillColor(text_color)
    c.drawCentredString(x + width / 2, y + 7, text)
    return width


def bullet_list(c: Canvas, items: list[str], x: float, y_top: float, w: float, size: float = 9.2, gap: float = 9) -> float:
    y = y_top
    for item in items:
        c.setFillColor(TEAL)
        c.circle(x + 4, y - 5.5, 2.4, fill=1, stroke=0)
        y = draw_para(c, item, x + 15, y + 1, w - 18, 48, size=size, color=MUTED) - gap
    return y


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as im:
        return im.size


def image_fit(c: Canvas, path: Path, x: float, y: float, w: float, h: float, label: str | None = None, radius: float = 12) -> None:
    card(c, x, y, w, h, radius=radius)
    if not path.exists():
        c.setFillColor(AMBER_SOFT)
        c.roundRect(x + 10, y + 10, w - 20, h - 20, 8, fill=1, stroke=0)
        draw_para(c, f"缺少截图: {path.name}", x + 18, y + h / 2 + 8, w - 36, 36, size=10, color=AMBER, bold=True, align=1)
        return
    iw, ih = image_size(path)
    scale = min((w - 14) / iw, (h - 14) / ih)
    dw, dh = iw * scale, ih * scale
    c.drawImage(str(path), x + (w - dw) / 2, y + (h - dh) / 2, width=dw, height=dh, preserveAspectRatio=True, mask="auto")
    if label:
        c.setFillColor(colors.Color(1, 1, 1, alpha=0.92))
        c.roundRect(x + 12, y + h - 34, len(label) * 5.8 + 24, 22, 11, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont(FONT_BOLD, 8)
        c.drawString(x + 24, y + h - 27, label)


def metric(c: Canvas, x: float, y: float, w: float, value: str, label: str, note: str, tone=TEAL) -> None:
    card(c, x, y, w, 72)
    c.setFont(FONT_BOLD, 18)
    c.setFillColor(tone)
    c.drawString(x + 14, y + 43, value)
    c.setFont(FONT_BOLD, 9)
    c.setFillColor(INK)
    c.drawString(x + 14, y + 27, label)
    draw_para(c, note, x + 14, y + 20, w - 28, 20, size=7.4, color=SUBTLE)


def section_card(c: Canvas, x: float, y: float, w: float, h: float, title: str, body: str, tag: str, tone=TEAL) -> None:
    card(c, x, y, w, h)
    c.setFillColor(tone)
    c.roundRect(x + 14, y + h - 34, 5, 20, 2.5, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 11.4)
    c.drawString(x + 28, y + h - 27, title)
    if h >= 110:
        draw_para(c, body, x + 14, y + h - 48, w - 28, h - 82, size=8.8, color=MUTED)
        pill(c, tag, x + 14, y + 13, fill=NAVY_SOFT, stroke=BORDER, text_color=NAVY)
    else:
        draw_para(c, body, x + 14, y + h - 48, w - 28, h - 52, size=8.3, color=MUTED)


def simple_table(
    c: Canvas,
    x: float,
    y: float,
    widths: list[float],
    row_h: float,
    headers: list[str],
    rows: list[list[str]],
    font_size: float = 7.9,
) -> None:
    total_w = sum(widths)
    c.setStrokeColor(BORDER)
    c.setFillColor(NAVY)
    c.roundRect(x, y + row_h * len(rows), total_w, row_h, 8, fill=1, stroke=0)
    offset = x
    for i, head in enumerate(headers):
        draw_para(c, head, offset + 7, y + row_h * len(rows) + row_h - 9, widths[i] - 14, row_h, size=7.8, color=colors.white, bold=True)
        offset += widths[i]
    for r, row in enumerate(rows):
        yy = y + row_h * (len(rows) - 1 - r)
        c.setFillColor(colors.white if r % 2 == 0 else colors.HexColor("#F2F7FA"))
        c.rect(x, yy, total_w, row_h, fill=1, stroke=0)
        c.setStrokeColor(BORDER)
        c.line(x, yy, x + total_w, yy)
        offset = x
        for i, cell in enumerate(row):
            draw_para(c, cell, offset + 7, yy + row_h - 8, widths[i] - 14, row_h - 6, size=font_size, color=INK if i == 0 else colors.HexColor("#334155"), bold=(i == 0))
            if i > 0:
                c.setStrokeColor(colors.HexColor("#E5EEF3"))
                c.line(offset, yy + 6, offset, yy + row_h - 6)
            offset += widths[i]
    c.setStrokeColor(BORDER)
    c.roundRect(x, y, total_w, row_h * (len(rows) + 1), 8, fill=0, stroke=1)


def flow_box(c: Canvas, x: float, y: float, w: float, h: float, title: str, body: str, tone=TEAL) -> None:
    card(c, x, y, w, h, fill=colors.white)
    c.setFillColor(tone)
    c.roundRect(x + 12, y + h - 32, w - 24, 22, 11, fill=1, stroke=0)
    draw_para(c, title, x + 18, y + h - 16, w - 36, 20, size=8.3, color=colors.white, bold=True, align=1)
    draw_para(c, body, x + 12, y + h - 46, w - 24, h - 50, size=8, color=MUTED, align=1)


def arrow(c: Canvas, x1: float, y1: float, x2: float, y2: float) -> None:
    c.setStrokeColor(colors.HexColor("#9CB4C6"))
    c.setLineWidth(1.4)
    c.line(x1, y1, x2, y2)
    c.setFillColor(colors.HexColor("#9CB4C6"))
    c.circle(x2, y2, 2.6, fill=1, stroke=0)


def prepare_assets() -> None:
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    crops = {
        "dashboard-crop.png": ("dashboard.png", (0, 0, 1440, 1100)),
        "stock-result-crop.png": ("stock-radar.png", (0, 2180, 1440, 2710)),
        "stock-top-crop.png": ("stock-radar.png", (0, 0, 1440, 1660)),
        "macro-crop.png": ("macro-intel.png", (0, 0, 1440, 880)),
    }
    for out_name, (src_name, box) in crops.items():
        src = ASSET_DIR / src_name
        dst = DERIVED_DIR / out_name
        if not src.exists():
            continue
        with Image.open(src) as im:
            crop_box = (
                max(0, box[0]),
                max(0, box[1]),
                min(im.width, box[2]),
                min(im.height, box[3]),
            )
            im.crop(crop_box).save(dst)


def cover(c: Canvas) -> None:
    background(c, dark=True)
    c.setFillColor(colors.HexColor("#22D3EE"))
    c.roundRect(54, PAGE_H - 118, 7, 58, 3.5, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(FONT_BOLD, 33)
    c.drawString(76, PAGE_H - 78, "FactorPlatform")
    c.setFont(FONT_BOLD, 20)
    c.drawString(76, PAGE_H - 112, "AI 金融研究与交易辅助平台项目汇报")
    draw_para(
        c,
        "面向机构投研、量化研究和风险识别场景，把行情看板、AI 选股、宏观情报、策略生成、回测、绩效归因和数据维护整合为一个风险感知的研究工作台。",
        76,
        PAGE_H - 150,
        430,
        90,
        size=11.5,
        color=colors.HexColor("#B6C7D8"),
    )
    x = 76
    pills = [
        ("AI market intelligence", colors.HexColor("#0C3338"), colors.HexColor("#164E63"), colors.HexColor("#67E8F9")),
        ("Risk-aware research", colors.HexColor("#173127"), colors.HexColor("#14532D"), colors.HexColor("#86EFAC")),
        ("Multi-agent analysis", colors.HexColor("#221B3D"), colors.HexColor("#4C1D95"), colors.HexColor("#C4B5FD")),
        ("Not financial advice", colors.HexColor("#3A2710"), colors.HexColor("#92400E"), colors.HexColor("#FCD34D")),
    ]
    for i, (text, fill, stroke, tc) in enumerate(pills):
        if i == 2:
            x = 76
            y = PAGE_H - 256
        elif i == 3:
            y = PAGE_H - 256
        else:
            y = PAGE_H - 224
        if i == 3 and x > 430:
            x = 76
            y = PAGE_H - 256
        x += pill(c, text, x, y, fill=fill, stroke=stroke, text_color=tc) + 8

    metric(c, 76, 132, 126, "10+", "研究模块", "覆盖投研、回测、数据和风控", TEAL)
    metric(c, 216, 132, 126, "CN/US", "数据方向", "支持本地 qlib 与公开行情链路", VIOLET)
    metric(c, 356, 132, 126, "可落地", "部署方式", "Next.js + FastAPI + Postgres/Redis", GREEN)
    c.setFillColor(colors.HexColor("#B6C7D8"))
    c.setFont(FONT, 8.8)
    c.drawString(76, 88, f"生成日期: {date.today().isoformat()}")
    c.drawString(76, 68, "汇报用途: 项目介绍、竞品分析、商业化讨论、模块功能说明")

    image_fit(c, ASSET_DIR / "landing.png", 520, 84, 384, 362, label="官网与 AI Research Terminal")
    footer(c, 1, dark=True)


def executive_summary(c: Canvas) -> None:
    header(c, 2, "01. 项目一句话与汇报结论", "EXECUTIVE SUMMARY")
    draw_para(
        c,
        "FactorPlatform 不是“喊单网站”，而是一个把 AI 市场情报、因子研究、策略验证和风险约束放在同一个工作台里的投研辅助平台。",
        54,
        PAGE_H - 110,
        840,
        38,
        size=14,
        color=INK,
        bold=True,
    )
    cards = [
        ("定位", "AI-assisted decision support", "以概率化信号、情景推演和风险提示辅助研究员判断，不替代投资决策。", TEAL),
        ("核心闭环", "Data - Signal - Backtest - Attribution", "从数据维护到候选池、策略生成、回测、绩效归因和复盘形成可演示闭环。", VIOLET),
        ("差异化", "本地量化 + AI Copilot", "相比纯资讯终端或纯聊天助手，更强调数据可追溯、因子贡献、风险门禁和回测验证。", GREEN),
        ("商业机会", "中小机构和研究团队", "面向私募、投顾、产业研究、金融科技演示和教育实训，先做研究工作台，再扩展企业部署。", AMBER),
    ]
    x0, y0, w, h = 54, 250, 205, 116
    for i, (title, tag, body, tone) in enumerate(cards):
        section_card(c, x0 + i * (w + 16), y0, w, h, title, body, tag, tone=tone)
    simple_table(
        c,
        54,
        50,
        [145, 225, 225, 225],
        38,
        ["汇报关注点", "当前项目回答", "可证明材料", "下一步建议"],
        [
            ["为什么做", "AI 正在重塑投研工作流，但机构仍需要可验证、可审计、可控风险的系统。", "落地页定位、风险提示、模块链路", "把“非投资建议”和模型不确定性作为产品原则"],
            ["做给谁", "中小型投研团队、私募研究员、金融科技售前、财经教育和企业内训。", "看板、选股、宏观、回测、数据维护", "用 3 个细分场景打样: 研究员、风控、销售演示"],
            ["凭什么赢", "不是只做资讯搜索，也不是只做图表，而是连接候选、解释、回测、归因和数据质量。", "AI 选股、宏观情报、策略回测、绩效归因", "强化真实数据接入和审计日志"],
            ["怎么商业化", "SaaS 订阅、企业私有化、数据/模型接入服务、研究模板包。", "模块化架构和前后端分离", "优先做 Pro 版和 Institutional 版"],
        ],
        font_size=6.7,
    )


def problem_users(c: Canvas) -> None:
    header(c, 3, "02. 目标用户、痛点与使用场景", "TARGET USERS")
    left = [
        ("投研研究员", "需要把行情、新闻、因子、候选池和策略验证集中到一个工作流，减少多个工具之间的复制粘贴。"),
        ("量化研究团队", "关注因子定义、数据新鲜度、回测假设、交易成本、归因结果和可复现性。"),
        ("风控/投委会", "需要看清信号依据、风险等级、市场状态、模型不确定性和策略适用环境。"),
        ("销售与培训", "需要一套专业、可演示、可解释的平台，用于客户沟通或金融科技课程。"),
    ]
    for idx, (title, body) in enumerate(left):
        y = PAGE_H - 154 - idx * 94
        section_card(c, 54, y, 360, 72, title, body, f"Persona {idx + 1}", tone=[TEAL, VIOLET, AMBER, GREEN][idx])
    card(c, 448, 86, 458, 376)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 16)
    c.drawString(472, 426, "典型工作流痛点")
    bullets = [
        "资讯、行情、因子、回测和归因分散在多个系统，研究链路难以复盘。",
        "AI 能生成观点，但缺少数据来源、风险边界、触发条件和验证入口。",
        "传统终端强在数据和图表，但对中小机构成本高、定制重、部署门槛高。",
        "开源量化工具灵活，但产品化、权限、可视化和演示体验不足。",
        "内部汇报需要把专业性、风险意识和商业化价值同时讲清楚。",
    ]
    bullet_list(c, bullets, 476, 388, 392, size=10)
    c.setFillColor(NAVY_SOFT)
    c.roundRect(472, 116, 384, 74, 12, fill=1, stroke=0)
    draw_para(c, "项目切入点: 做一个“研究辅助终端”，先服务研究和风控，不承诺收益，不输出确定性预测，把 AI 能力放进可验证的投研流程。", 492, 169, 344, 56, size=10.4, color=NAVY, bold=True)


def architecture(c: Canvas) -> None:
    header(c, 4, "03. 产品架构: 从数据到研究决策支持", "PRODUCT ARCHITECTURE")
    draw_para(c, "平台的价值不在单点页面，而在于把多个研究动作串成闭环: 数据健康 - 市场观察 - 候选筛选 - 策略生成 - 回测验证 - 风险归因 - 汇报复盘。", 54, PAGE_H - 112, 820, 46, size=13, color=MUTED)
    xs = [64, 238, 412, 586, 760]
    boxes = [
        ("数据层", "本地 qlib、OHLCV、新闻源、宏观事件、策略库"),
        ("计算层", "因子计算、信号筛选、状态识别、回测与归因"),
        ("AI 层", "策略生成、事件摘要、情景推演、解释与拒绝理由"),
        ("风控层", "数据门禁、风险等级、模型不确定性、非投资建议"),
        ("交互层", "看板、AI 选股、宏观情报、策略回测、绩效归因"),
    ]
    for i, (title, body) in enumerate(boxes):
        flow_box(c, xs[i], 308, 130, 118, title, body, [TEAL, VIOLET, GREEN, AMBER, NAVY][i])
        if i < len(boxes) - 1:
            arrow(c, xs[i] + 130, 367, xs[i + 1] - 10, 367)
    simple_table(
        c,
        54,
        94,
        [132, 218, 218, 248],
        44,
        ["层级", "现有能力", "技术载体", "汇报价值"],
        [
            ["前端体验", "机构投研工作台、专业 landing、模块导航和深链", "Next.js 14, React, TypeScript, Ant Design", "演示完整、交互可信、可移动到 SaaS"],
            ["后端服务", "因子、信号、新闻、策略、回测、数据维护 API", "FastAPI, Celery, Postgres, Redis", "后续可接真实数据和权限"],
            ["研究数据", "CN/US qlib、本地 OHLCV、公开新闻和 fallback 标注", "本地数据目录和 API 代理", "强调可追溯与数据新鲜度"],
            ["AI 能力", "策略草案、宏观摘要、候选解释、风险提示", "LLM router, 模板兜底, 可替换模型", "在不可用时仍可演示且不误导"],
        ],
        font_size=7.8,
    )


def product_showcase(c: Canvas) -> None:
    header(c, 5, "04. 当前产品形态与第一屏印象", "PRODUCT SHOWCASE")
    image_fit(c, ASSET_DIR / "dashboard.png", 54, 102, 548, 350, label="研究工作台: 市场看板 + AI 选股 + 信息搜集")
    card(c, 628, 102, 278, 350)
    c.setFont(FONT_BOLD, 15)
    c.setFillColor(INK)
    c.drawString(650, 414, "第一屏要传达什么")
    bullet_list(
        c,
        [
            "不像普通 SaaS 首页，而像一个面向研究员的工作台。",
            "行情、候选标的、宏观事件与策略入口在同一屏内出现。",
            "看板在线、数据更新时间、刷新按钮能降低演示风险。",
            "右侧 AI 选股和信息搜集入口已经打通到业务页面。",
            "视觉上采用克制的金融终端风格，避免“暴利信号”叙事。",
        ],
        652,
        378,
        226,
        size=9.5,
        gap=12,
    )
    c.setFillColor(TEAL_SOFT)
    c.roundRect(650, 124, 218, 76, 12, fill=1, stroke=0)
    draw_para(c, "汇报话术: “这是一个 AI 投研工作台。它不是直接告诉用户买什么，而是帮助研究人员把证据、概率和风险放到同一张工作台上。”", 668, 180, 182, 54, size=9.2, color=TEAL_DARK, bold=True)


def competitive_matrix(c: Canvas) -> None:
    header(c, 6, "05. 竞品格局: 传统终端、AI 情报与开源研究工具", "COMPETITOR ANALYSIS")
    simple_table(
        c,
        42,
        82,
        [88, 130, 185, 185, 305],
        52,
        ["类别", "代表产品", "强项", "常见短板", "FactorPlatform 切入方式"],
        [
            ["机构终端", "Bloomberg Terminal, LSEG Workspace, FactSet, Capital IQ Pro", "数据覆盖、新闻、图表、工作流和机构品牌强。", "成本高、定制周期长，对小团队和演示场景较重。", "以轻量本地部署和 AI 研究闭环切入，避免正面对抗全量数据覆盖。"],
            ["AI 市场情报", "AlphaSense, FinChat 等", "对文档、公告、财报和语义搜索友好，能提升信息检索效率。", "和本地因子、回测、绩效归因连接不足，常停留在“回答问题”。", "把 AI 摘要连接到候选池、策略生成和回测，强调可验证输出。"],
            ["图表/交易社区", "TradingView, Koyfin, YCharts", "图表体验、筛选器、市场面板和报告模板成熟。", "更偏观察和筛选，缺少私有数据链路与策略研究闭环。", "保留图表能力，同时补上本地数据、因子贡献、风险门禁和回测。"],
            ["开源量化", "OpenBB, Qlib, Backtrader 等", "扩展性和透明度高，适合工程团队深度改造。", "普通业务用户上手难，产品化、权限和演示体验需要二次开发。", "产品化包装开源研究能力，提供面向投研的工作台和汇报入口。"],
            ["内部工具", "券商/私募自研系统", "贴合内部数据和流程，安全性可控。", "UI、AI 交互和跨模块体验常弱，维护成本高。", "作为模板化底座，支持私有化部署、数据接入和定制模块。"],
        ],
        font_size=7.2,
    )
    draw_para(c, "资料参考: Bloomberg, LSEG, FactSet, S&P Capital IQ Pro, AlphaSense, OpenBB, TradingView, YCharts 官方页面，见参考资料 S1-S8。", 54, 48, 830, 24, size=8.2, color=SUBTLE)


def competitor_deep_dive(c: Canvas) -> None:
    header(c, 7, "06. 竞品拆解: 我们不做“大而全终端”，做研究闭环", "POSITIONING")
    items = [
        ("Bloomberg / LSEG", "机构级数据、新闻和交易生态强，但价格与实施门槛决定了它更适合大型机构。", "避开全市场数据覆盖，强调轻量投研流程和本地数据闭环。", TEAL),
        ("FactSet / Capital IQ Pro", "研究数据、公司财务、筛选和企业级工作流成熟，适合专业金融机构。", "把财务终端思路转为“策略研究与回测验证”工作台。", VIOLET),
        ("AlphaSense / AI Search", "AI 检索文档、公告和研报效率高，强在信息发现和总结。", "把 AI 输出接到候选池、策略草案、回测和归因，避免停留在问答。", GREEN),
        ("TradingView / YCharts", "图表、筛选、报告和市场展示优秀，学习成本低。", "增加数据门禁、因子贡献和风险情景，提升机构汇报可信度。", AMBER),
        ("OpenBB / 开源研究", "可定制、开放、适合工程团队，数据接入灵活。", "用产品化界面降低使用门槛，把开源能力变成可汇报方案。", NAVY),
        ("内部自研", "贴合私有流程和数据，但交互体验、AI 体验和维护成本是痛点。", "提供私有化模板: 先演示，后接数据、权限和模型。", RED),
    ]
    for i, (name, strength, angle, tone) in enumerate(items):
        col = i % 3
        row = i // 3
        x = 54 + col * 286
        y = 288 - row * 170
        card(c, x, y, 262, 142)
        c.setFillColor(tone)
        c.roundRect(x + 14, y + 108, 50, 8, 4, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont(FONT_BOLD, 12)
        c.drawString(x + 14, y + 86, name)
        draw_para(c, "竞品强项: " + strength, x + 14, y + 70, 232, 44, size=8.4, color=MUTED)
        draw_para(c, "切入策略: " + angle, x + 14, y + 34, 232, 36, size=8.4, color=INK, bold=True)


def differentiation(c: Canvas) -> None:
    header(c, 8, "07. 项目特色: 风险感知的 AI 投研闭环", "DIFFERENTIATORS")
    features = [
        ("专业定位", "AI market intelligence, decision support, not financial advice。文案避免夸张收益承诺。"),
        ("深链工作流", "看板一键进入 AI 选股和宏观情报，参数自动带入，减少演示断点。"),
        ("因子可解释", "候选池显示综合分、分位、覆盖率和主要因子贡献，而不是简单“买卖信号”。"),
        ("风险前置", "市场状态、波动、风险等级、数据新鲜度和模型不确定性贯穿各页面。"),
        ("兜底透明", "后端或数据源不可用时展示 read-only fallback，并明确标注，不伪装真实结果。"),
        ("可部署扩展", "Next.js + FastAPI + Postgres/Redis/Celery，便于企业私有化和数据接入。"),
    ]
    for i, (title, body) in enumerate(features):
        x = 54 + (i % 3) * 286
        y = 314 - (i // 3) * 154
        section_card(c, x, y, 262, 126, title, body, f"Feature {i + 1}", tone=[TEAL, VIOLET, GREEN, AMBER, NAVY, RED][i])
    card(c, 54, 82, 836, 74, fill=TEAL_SOFT, stroke=colors.HexColor("#B9E4E4"))
    draw_para(
        c,
        "一句话差异化: 将 AI 生成能力放进“可追溯数据 - 可解释候选 - 可验证回测 - 可复盘归因”的闭环中，用专业风控叙事替代短期收益叙事。",
        78,
        132,
        788,
        42,
        size=13,
        color=TEAL_DARK,
        bold=True,
    )


def business(c: Canvas) -> None:
    header(c, 9, "08. 商业前景: 从轻量 SaaS 到机构私有化", "BUSINESS OUTLOOK")
    metric(c, 54, 360, 172, "趋势上行", "AI + 金融工作流", "AI in FinTech 市场研究显示该方向仍处增长周期，见 S9。", TEAL)
    metric(c, 244, 360, 172, "强需求", "研究效率提升", "投研团队需要摘要、筛选、验证和复盘一体化。", VIOLET)
    metric(c, 434, 360, 172, "可分层", "SaaS / Pro / Enterprise", "按数据接入、模型额度、权限和部署方式分层。", GREEN)
    metric(c, 624, 360, 172, "可演示", "售前价值", "专业工作台可用于客户演示、教学和方案验证。", AMBER)
    simple_table(
        c,
        54,
        88,
        [115, 210, 210, 250],
        45,
        ["客户类型", "核心需求", "付费理由", "推荐产品包"],
        [
            ["私募/投研小组", "快速筛选候选、解释信号、记录研究链路。", "替代手工表格和多工具切换，提高研究效率。", "Pro: AI 选股、宏观情报、策略回测、绩效归因。"],
            ["金融科技售前", "需要一套能展示 AI 金融能力的专业样机。", "演示效果直接影响客户沟通和方案包装。", "Demo/Enterprise: 白标、部署脚本、数据替换。"],
            ["教育与培训", "讲清因子、回测、市场状态和 AI Copilot。", "比纯代码更容易教学和考核。", "Education: 课程模板、案例库、离线数据。"],
            ["企业内部研究", "私有数据、权限、审计、模型可控。", "安全合规和可定制性优先于通用终端。", "Institutional: 私有化部署、SSO、数据连接器。"],
        ],
        font_size=7.7,
    )
    draw_para(c, "商业化原则: 不以收益承诺销售，以研究效率、风险识别、流程留痕、数据整合和企业私有化能力定价。", 54, 54, 830, 28, size=10.2, color=INK, bold=True)


def module_market_stock(c: Canvas) -> None:
    header(c, 10, "09. 模块详解: 市场看板与 AI 选股", "MODULE DETAILS")
    image_fit(c, DERIVED_DIR / "dashboard-crop.png", 54, 226, 392, 222, label="市场看板")
    image_fit(c, DERIVED_DIR / "stock-result-crop.png", 54, 76, 392, 132, label="AI 选股结果")
    section_card(c, 474, 300, 410, 146, "市场看板 Dashboard", "实时行情、指数切换、TradingView 图表、看板在线心跳、AI 选股入口、信息搜集入口和研究模块导航。适合作为汇报第一屏，让听众迅速理解平台不是单点工具，而是投研工作台。", "输入: 市场/标的/新闻源 | 输出: 工作台总览", TEAL)
    section_card(c, 474, 132, 410, 146, "AI 选股雷达 Stock Radar", "按 qlib 因子族群构建候选池，支持市场预设、股票池、因子组合、权重和方向配置。输出综合分、分位、覆盖率、收盘价、成交量和主要贡献因子。后端不可用时展示明确标注的只读候选池。", "输入: 股票池/因子/权重 | 输出: 候选池/贡献解释", VIOLET)
    card(c, 474, 76, 410, 42, fill=AMBER_SOFT, stroke=colors.HexColor("#F7D6A0"))
    draw_para(c, "汇报重点: AI 选股不是“喊单”，而是候选筛选和研究输入；候选结果需要经过回测、风控和人工判断。", 492, 104, 374, 26, size=9, color=AMBER, bold=True)


def module_macro_strategy(c: Canvas) -> None:
    header(c, 11, "10. 模块详解: 宏观情报与 AI 策略生成", "MODULE DETAILS")
    image_fit(c, DERIVED_DIR / "macro-crop.png", 54, 226, 392, 222, label="宏观情报")
    image_fit(c, LEGACY_ASSET_DIR / "02-ai-strategy.png", 54, 76, 392, 132, label="AI 策略生成")
    section_card(c, 474, 300, 410, 146, "宏观情报 Macro Intel", "输入主题、区域、事件和时间窗口，生成新闻摘要、事件影响链路和跨资产情景分析。当前看板已能把“机器人产业链”等主题深链到宏观情报页并自动运行。", "输入: 主题/事件/区域 | 输出: 摘要/链路/报告", GREEN)
    section_card(c, 474, 132, 410, 146, "AI 策略生成 Strategy Builder", "基于市场、策略意图、指标和约束生成策略草案、信号逻辑、参数说明、风险提示和代码/配置雏形。适合把研究假设转成可回测的初始方案。", "输入: 研究假设/标的/约束 | 输出: 策略草案/验证建议", TEAL)
    card(c, 474, 76, 410, 42, fill=NAVY_SOFT, stroke=BORDER)
    draw_para(c, "汇报重点: 宏观情报负责“发生了什么”和“可能影响什么”，策略生成负责把假设转为可验证方案。", 492, 104, 374, 26, size=9, color=NAVY, bold=True)


def module_signal_backtest(c: Canvas) -> None:
    header(c, 12, "11. 模块详解: 信号中心、策略路由与回测工作台", "MODULE DETAILS")
    image_fit(c, LEGACY_ASSET_DIR / "05-signal-center.png", 54, 234, 392, 214, label="信号中心")
    image_fit(c, LEGACY_ASSET_DIR / "04-backtest-result.png", 54, 76, 392, 138, label="回测结果")
    items = [
        ("信号中心 Signal Center", "集中查看市场信号、风险等级、置信度、通知记录、信号详情和历史结果。强调 signal screening，而不是交易喊单。", "输入: 信号/市场状态 | 输出: 筛选队列/详情"),
        ("策略路由 Strategy Router", "根据市场状态、风险 regime 和模板阈值决定策略适用性。适合向投委会解释为什么某个策略被采用或拒绝。", "输入: regime/阈值 | 输出: 策略选择/审计"),
        ("回测工作台 Backtests", "从策略库或因子组合发起回测，记录数据源、时间假设、成本、收益、Sharpe、回撤和组合持仓。", "输入: 策略配置/数据 | 输出: 回测报告"),
    ]
    for i, (title, body, tag) in enumerate(items):
        section_card(c, 474, 312 - i * 108, 410, 88, title, body, tag, tone=[TEAL, VIOLET, GREEN][i])


def module_performance_risk(c: Canvas) -> None:
    header(c, 13, "12. 模块详解: 绩效归因与市场状态识别", "MODULE DETAILS")
    image_fit(c, LEGACY_ASSET_DIR / "08-performance.png", 54, 238, 392, 210, label="绩效归因")
    image_fit(c, LEGACY_ASSET_DIR / "09-regime-monitor.png", 54, 76, 392, 140, label="市场状态")
    section_card(c, 474, 296, 410, 150, "绩效归因 Performance", "把策略结果拆成收益、风险、波动、回撤、因子贡献和时间维度，帮助研究员从“结果好坏”进一步回答“为什么”。适合策略复盘和内部汇报。", "输入: 回测/组合/收益序列 | 输出: 归因视图", VIOLET)
    section_card(c, 474, 128, 410, 150, "市场状态 Regime Monitor", "跟踪低波、高波、风险偏好上行、流动性冲击、冲击后修复等状态，并展示相似历史区间和事件上下文。用于约束策略适用环境。", "输入: 市场特征/事件 | 输出: regime/风险解释", AMBER)
    card(c, 474, 76, 410, 38, fill=RED_SOFT, stroke=colors.HexColor("#F6B7B7"))
    draw_para(c, "汇报重点: 平台把“收益结果”放回市场状态和风险上下文中解释，减少单一收益指标误导。", 492, 101, 374, 24, size=9, color=RED, bold=True)


def module_data_factor(c: Canvas) -> None:
    header(c, 14, "13. 模块详解: 因子分析、数据维护与系统设置", "MODULE DETAILS")
    image_fit(c, LEGACY_ASSET_DIR / "07-factors.png", 54, 238, 392, 210, label="因子分析平台")
    image_fit(c, LEGACY_ASSET_DIR / "06-data-maintenance.png", 54, 76, 392, 140, label="数据维护")
    items = [
        ("因子分析 Factors", "因子库、因子详情、质量状态、推广状态、原因码和批处理入口。后续可扩展 IC 分析、行业中性化、组合打分和因子监控。", "输入: 因子定义/数据 | 输出: 因子质量/分析"),
        ("数据维护 Data Maintenance", "统一管理数据刷新、质量校验、数据源路径、最新日期、滞后天数、行数、标的数和任务状态，是平台可信度底座。", "输入: 数据源/刷新任务 | 输出: 健康审计"),
        ("设置 Settings", "语言切换、高级研究模式、本地开发配置和演示参数。为普通模式和研究模式提供不同信息密度。", "输入: 用户偏好 | 输出: 体验/模式控制"),
    ]
    for i, (title, body, tag) in enumerate(items):
        section_card(c, 474, 312 - i * 108, 410, 88, title, body, tag, tone=[TEAL, GREEN, NAVY][i])


def tech_roadmap(c: Canvas) -> None:
    header(c, 15, "14. 技术栈与产品路线图", "TECH & ROADMAP")
    simple_table(
        c,
        54,
        246,
        [120, 220, 220, 240],
        38,
        ["层级", "当前技术", "已体现能力", "后续增强"],
        [
            ["前端", "Next.js 14, React 18, TypeScript, Ant Design", "专业看板、表格、导航、深链、fallback", "移动端精修、权限态、主题系统"],
            ["后端", "FastAPI, Celery, Postgres, Redis", "因子、策略、回测、新闻、数据维护 API", "统一审计日志、租户隔离、异步任务面板"],
            ["数据", "qlib CN/US、本地 OHLCV、公开新闻源", "候选池、数据新鲜度、宏观摘要", "更多数据供应商、财务数据、研报/公告"],
            ["AI", "LLM router, 模板兜底, 策略生成/摘要", "AI Copilot 和自动解释", "RAG、Agent 协同、引用追踪和评估集"],
        ],
        font_size=7.6,
    )
    phases = [
        ("Phase 1", "演示闭环", "稳定看板、选股、宏观、策略、回测、归因链路"),
        ("Phase 2", "真实数据", "接入财务数据、公告、更多行情源和数据质量审计"),
        ("Phase 3", "企业化", "用户权限、租户、私有部署、模型网关和审计日志"),
        ("Phase 4", "商业包", "行业模板、研究报告导出、销售演示包和教育案例库"),
    ]
    for i, (phase, title, body) in enumerate(phases):
        flow_box(c, 66 + i * 210, 120, 160, 106, phase + " - " + title, body, [TEAL, VIOLET, GREEN, AMBER][i])
        if i < 3:
            arrow(c, 226 + i * 210, 173, 266 + i * 210, 173)


def risk_compliance(c: Canvas) -> None:
    header(c, 16, "15. 风险合规与可信 AI 设计", "RISK & COMPLIANCE")
    cards = [
        ("非投资建议", "所有页面应强调 research support 和 decision support。输出用于辅助研究与风险识别，不构成投资建议。", TEAL),
        ("模型不确定性", "AI 结果需要呈现置信度、数据来源、fallback 状态、拒绝原因和人工复核入口。", VIOLET),
        ("数据新鲜度", "选股、信号和回测必须记录 signal_date、effective_trade_date、数据源状态和更新时间。", GREEN),
        ("审计留痕", "企业化阶段应记录参数、模型版本、数据版本、用户操作和报告生成记录。", AMBER),
        ("监管叙事", "AI 金融产品应避免“稳赚”“确定预测”等表述，避免 AI washing 和误导性营销。", RED),
        ("演示边界", "Demo/fallback 数据必须清晰标注，不能把模拟数据包装成真实投研结论。", NAVY),
    ]
    for i, (title, body, tone) in enumerate(cards):
        x = 54 + (i % 3) * 286
        y = 314 - (i // 3) * 154
        section_card(c, x, y, 262, 126, title, body, "Control", tone=tone)
    draw_para(c, "监管参考: FINRA 对 AI 投资工具风险的投资者教育，以及 SEC 对 AI washing 的执法案例，见 S10-S11。", 54, 52, 830, 28, size=8.8, color=SUBTLE)


def demo_script(c: Canvas) -> None:
    header(c, 17, "16. 汇报演示路径与讲解脚本", "DEMO SCRIPT")
    steps = [
        ("1. Landing", "展示专业定位: AI Market Intelligence for Risk-Aware Trading Research。强调不是收益承诺，而是研究辅助。"),
        ("2. Dashboard", "进入工作台，说明行情、AI 选股、信息搜集和模块导航已经集中。指出看板在线和更新时间。"),
        ("3. AI 选股", "点击开始选股，展示从看板带入 A 股/沪深300/动量预设，候选池自动生成，解释分位和因子贡献。"),
        ("4. 宏观情报", "从看板进入机器人产业链主题，展示新闻摘要、事件链路和 fallback 标注。"),
        ("5. 策略回测", "说明候选和宏观假设如何进入策略生成与回测，强调成本、回撤、归因和市场状态。"),
        ("6. 商业化", "收束到 Pro/Institutional 版本: 数据接入、私有部署、模型网关、审计和模板包。"),
    ]
    for i, (title, body) in enumerate(steps):
        x = 54 + (i % 2) * 426
        y = 360 - (i // 2) * 106
        section_card(c, x, y, 392, 82, title, body, "Talk track", tone=[TEAL, VIOLET, GREEN, AMBER, NAVY, RED][i])
    card(c, 54, 64, 826, 54, fill=TEAL_SOFT, stroke=colors.HexColor("#B9E4E4"))
    draw_para(c, "建议汇报节奏: 3 分钟讲定位，5 分钟讲竞品和差异化，8 分钟走产品演示，4 分钟讲商业化，最后用风险合规收尾。", 76, 100, 780, 34, size=10.2, color=TEAL_DARK, bold=True)


def module_index(c: Canvas) -> None:
    header(c, 18, "17. 模块功能索引", "MODULE INDEX")
    simple_table(
        c,
        38,
        54,
        [96, 165, 170, 170, 300],
        31,
        ["模块", "主要输入", "核心处理", "输出物", "汇报价值"],
        [
            ["市场看板", "市场、指数、新闻、候选标的", "行情展示、在线心跳、深链跳转", "工作台总览", "让项目第一眼像专业投研终端。"],
            ["AI 选股雷达", "股票池、因子、权重、方向", "横截面排序、贡献解释、数据门禁", "候选池与 CSV", "把 AI 选股降级为研究输入，风险叙事更稳。"],
            ["宏观情报", "主题、事件、区域、时间窗口", "新闻摘要、事件链路、跨资产分析", "链路/报告/新闻", "将信息搜集转化为结构化情景分析。"],
            ["AI 策略生成", "研究假设、指标、约束", "LLM 生成策略草案、校验和风险提示", "策略说明/代码雏形", "从想法到可验证策略，缩短研究启动时间。"],
            ["信号中心", "市场状态、信号、通知", "筛选、状态跟踪、详情解释", "信号队列和详情页", "强调 signal screening，不做确定性预测。"],
            ["策略回测", "策略配置、数据源、成本", "回测计算、持仓和交易记录", "回测报告", "验证假设，避免只听 AI 文案。"],
            ["绩效归因", "回测结果、收益序列", "收益/风险/因子/时间维度拆解", "归因面板", "解释为什么有效或失效。"],
            ["市场状态", "波动、流动性、事件", "regime 识别、相似历史区间", "状态解释和风险提示", "把策略放到适用市场环境中讨论。"],
            ["因子分析", "因子定义和数据", "质量检查、分类、批处理", "因子库和质量结果", "体现量化研究深度和扩展性。"],
            ["数据维护", "数据源路径、刷新任务", "新鲜度、行数、滞后、任务状态", "健康审计", "支撑可信演示和企业部署。"],
            ["系统设置", "语言、模式、本地参数", "高级模式、偏好和演示配置", "配置面板", "保证普通演示和研究模式可切换。"],
        ],
        font_size=6.2,
    )


def references(c: Canvas) -> None:
    header(c, 19, "18. 参考资料与声明", "REFERENCES")
    refs = [
        ("S1", "Bloomberg Terminal", "https://www.bloomberg.com/professional/products/bloomberg-terminal/"),
        ("S2", "LSEG Workspace", "https://www.lseg.com/en/data-analytics/products/workspace"),
        ("S3", "FactSet Workstation", "https://www.factset.com/products/workstation"),
        ("S4", "S&P Capital IQ Pro", "https://www.spglobal.com/market-intelligence/en/solutions/products/sp-capital-iq-pro"),
        ("S5", "AlphaSense Platform", "https://www.alpha-sense.com/platform/"),
        ("S6", "OpenBB", "https://openbb.co/"),
        ("S7", "TradingView Features", "https://www.tradingview.com/features/"),
        ("S8", "YCharts Features", "https://ycharts.com/features/"),
        ("S9", "Grand View Research: AI in FinTech market", "https://www.grandviewresearch.com/industry-analysis/artificial-intelligence-ai-fintech-market-report"),
        ("S10", "FINRA: Artificial Intelligence and Investing", "https://www.finra.org/investors/insights/artificial-intelligence-investing"),
        ("S11", "SEC: AI Washing enforcement release", "https://www.sec.gov/newsroom/press-releases/2024-36"),
    ]
    columns = [(54, PAGE_H - 122, refs[:6]), (500, PAGE_H - 122, refs[6:])]
    for x, y, items in columns:
        for sid, title, url in items:
            c.setFillColor(TEAL_SOFT)
            c.roundRect(x, y - 17, 38, 21, 10, fill=1, stroke=0)
            c.setFillColor(TEAL_DARK)
            c.setFont(FONT_BOLD, 8)
            c.drawCentredString(x + 19, y - 10, sid)
            draw_para(c, f"{title}\n{url}", x + 50, y + 2, 370, 36, size=7.4, color=INK)
            y -= 44
    card(c, 54, 54, 826, 62, fill=AMBER_SOFT, stroke=colors.HexColor("#F7D6A0"))
    draw_para(c, "声明: 本报告中的产品说明用于项目汇报和商业讨论。平台定位为研究工具与辅助决策系统，不提供投资建议，不保证收益，不应被理解为确定性市场预测。竞品信息来自公开页面，可能随时间变化。", 76, 98, 782, 40, size=8.8, color=AMBER, bold=True)


PAGES = [
    cover,
    executive_summary,
    problem_users,
    architecture,
    product_showcase,
    competitive_matrix,
    competitor_deep_dive,
    differentiation,
    business,
    module_market_stock,
    module_macro_strategy,
    module_signal_backtest,
    module_performance_risk,
    module_data_factor,
    tech_roadmap,
    risk_compliance,
    demo_script,
    module_index,
    references,
]


def build_pdf() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prepare_assets()
    c = Canvas(str(PDF_PATH), pagesize=(PAGE_W, PAGE_H))
    c.setTitle("FactorPlatform 项目汇报")
    c.setAuthor("FactorPlatform")
    for render in PAGES:
        render(c)
        c.showPage()
    c.save()


def render_previews() -> None:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(PDF_PATH)
    for page_index in range(len(doc)):
        page = doc.load_page(page_index)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.45, 1.45), alpha=False)
        pix.save(PREVIEW_DIR / f"factorplatform_project_report_page_{page_index + 1:02d}.png")
    doc.close()


if __name__ == "__main__":
    build_pdf()
    render_previews()
    print(PDF_PATH)
    print(PREVIEW_DIR)
