"""
generate_pdf.py — NeuroGuide 仿真报告生成模块
"""

import os, io, time, tempfile
from pathlib import Path
import numpy as np

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        Image as RLImage, PageBreak
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

_CJK_FONT_NAME = "Helvetica"

def _init_font_and_colors():
    global _CJK_FONT_NAME, BLACK, WHITE, DARK_BG, LIGHT_BG, BORDER, ACCENT, GRAY
    if REPORTLAB_AVAILABLE:
        for _name, _path in [("SimHei","C:/Windows/Fonts/simhei.ttf"),
                             ("Microsoft YaHei","C:/Windows/Fonts/msyh.ttc"),
                             ("Microsoft YaHei Bold","C:/Windows/Fonts/msyhbd.ttc")]:
            if os.path.exists(_path):
                try: pdfmetrics.registerFont(TTFont(_name, _path)); _CJK_FONT_NAME = _name; break
                except Exception: continue
    BLACK  = HexColor("#000000") if REPORTLAB_AVAILABLE else None
    WHITE  = HexColor("#FFFFFF") if REPORTLAB_AVAILABLE else None
    DARK_BG= HexColor("#222530") if REPORTLAB_AVAILABLE else None
    LIGHT_BG=HexColor("#F0F0F0") if REPORTLAB_AVAILABLE else None
    BORDER = HexColor("#CCCCCC") if REPORTLAB_AVAILABLE else None
    GRAY   = HexColor("#888888") if REPORTLAB_AVAILABLE else None
BLACK = WHITE = DARK_BG = LIGHT_BG = BORDER = GRAY = ACCENT = None

def _format_coord(affine, x, y, z):
    if affine is None: return f"({x},{y},{z}) voxel"
    mni = affine @ np.array([x,y,z,1])
    return f"({mni[0]:.1f}, {mni[1]:.1f}, {mni[2]:.1f}) mm"

def _add_header_footer(c, doc):
    c.saveState(); c.setFont(_CJK_FONT_NAME,7); c.setFillColor(GRAY)
    c.drawCentredString(A4[0]/2,10*mm,f"NeuroGuide 仿真报告 · 生成时间 {time.strftime('%Y-%m-%d %H:%M:%S')}")
    c.restoreState()

def _make_tbl(f):
    return TableStyle([
        ("FONTNAME",(0,0),(-1,-1),f),("BACKGROUND",(0,0),(-1,0),DARK_BG),
        ("TEXTCOLOR",(0,0),(-1,0),WHITE),("BACKGROUND",(0,1),(-1,-1),LIGHT_BG),
        ("TEXTCOLOR",(0,1),(-1,-1),BLACK),("FONTSIZE",(0,0),(-1,-1),8),
        ("ALIGN",(0,0),(-1,-1),"LEFT"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("GRID",(0,0),(-1,-1),0.5,BORDER),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[LIGHT_BG,HexColor("#FAFAFA")]),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)])

def _make_table(data, col_widths, tbl_style):
    t = Table(data, colWidths=col_widths)
    t.setStyle(tbl_style)
    return t

def _add_image_page(story, title, fig, page_w, page_h, h2_style):
    """将一张 matplotlib figure 的截图以标题+等比缩放图片的形式附加到story末尾"""
    story.append(Paragraph(title, h2_style))
    try:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor(), edgecolor="none")
        buf.seek(0)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(buf.read())
            tmp_path = tmp.name
        from PIL import Image as PILImage
        with PILImage.open(tmp_path) as pi:
            pw_px, ph_px = pi.size
        pw_pt = pw_px * 0.75
        ph_pt = ph_px * 0.75
        scale = min(page_w / pw_pt, page_h / ph_pt, 1.0)
        story.append(RLImage(tmp_path, width=pw_pt * scale, height=ph_pt * scale))
        story.append(Spacer(1, 4 * mm))
    except Exception:
        story.append(Paragraph("（图片生成失败）",
            ParagraphStyle("X", fontName=_CJK_FONT_NAME, fontSize=9, textColor=BLACK)))


def generate_report(engine, base_path, disease, target,
                    output_path=None, canvases=None, patient_info=None):
    if not REPORTLAB_AVAILABLE: return False, "缺少 reportlab 库。请执行: pip install reportlab"
    if engine.data is None:     return False, "无加载底图，无法生成报告。"
    _init_font_and_colors()
    if patient_info is None: patient_info = {}

    if output_path is None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        pn = patient_info.get("name", "")
        prefix = f"NeuroGuide_{pn}_" if pn else "NeuroGuide_"
        output_path = str(Path.home() / "Desktop" / f"{prefix}{ts}.pdf")

    try:
        doc = SimpleDocTemplate(
            output_path, pagesize=A4,
            leftMargin=15 * mm, rightMargin=15 * mm,
            topMargin=18 * mm, bottomMargin=15 * mm,
        )
        styles = getSampleStyleSheet()
        fn = _CJK_FONT_NAME
        title_style = ParagraphStyle("T", parent=styles["Title"], fontName=fn,
            fontSize=18, textColor=BLACK, spaceAfter=4*mm, alignment=TA_CENTER)
        h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName=fn,
            fontSize=14, textColor=BLACK, spaceBefore=4*mm, spaceAfter=2*mm)
        body = ParagraphStyle("B", parent=styles["Normal"], fontName=fn,
            fontSize=9, textColor=BLACK, leading=14)
        ts = _make_tbl(fn)
        page_w = A4[0] - 30 * mm
        page_h = A4[1] - 33 * mm

        story = []

        # ============ 第一页 ============
        story.append(Paragraph(f"NeuroGuide 仿真报告 — {patient_info.get('name','') or '未知患者'}", title_style))
        story.append(Spacer(1, 2*mm))

        # 1. 患者基本信息
        story.append(Paragraph("1. 患者基本信息", h2))
        story.append(_make_table(
            [["项目","内容"],
             ["患者姓名", patient_info.get("name","") or "未填写"],
             ["患者年龄", patient_info.get("age","") or "未填写"],
             ["患者性别", patient_info.get("gender","") or "未填写"],
             ["患者头围", patient_info.get("head_circumference","") or "未填写"],
             ["患病类型", patient_info.get("disease_type","") or "未填写"]],
            [50*mm, 120*mm], ts))
        story.append(Spacer(1, 3*mm))

        # 2. 仿真设置
        story.append(Paragraph("2. 仿真设置", h2))
        story.append(_make_table(
            [["项目","内容"],
             ["靶区", target or "未选择"],
             ["刺激电流", patient_info.get("current","") or "未填写"]],
            [50*mm, 120*mm], ts))
        story.append(Spacer(1, 3*mm))

        # 3. 电极位置图（适度大小）
        ep = patient_info.get("electrode_map_path")
        if ep and os.path.exists(ep):
            story.append(Paragraph("3. 电极位置图", h2))
            try:
                from PIL import Image as PILImage
                with PILImage.open(ep) as pi: ipw, iph = pi.size
                ipt_w = ipw * 0.75
                ipt_h = iph * 0.75
                sc = min(page_w / ipt_w, page_h * 0.30 / ipt_h, 1.0)
                story.append(RLImage(ep, width=ipt_w * sc, height=ipt_h * sc))
            except Exception:
                story.append(Paragraph("（电极图加载失败）", body))
        story.append(Spacer(1, 4*mm))

        # 分页到第二页
        story.append(PageBreak())

        # ============ 第二页 ============
        # 4. 解剖底图信息
        story.append(Paragraph("4. 解剖底图信息", h2))
        sh = engine.data.shape
        sp = [np.linalg.norm(engine.affine[0:3,i]) for i in range(3)] if engine.affine is not None else [1,1,1]
        dmin = engine.display_min if engine.display_min is not None else 0.0
        dmax = engine.display_max if engine.display_max is not None else 1.0
        story.append(_make_table(
            [["属性","值"],
             ["文件路径", str(base_path)],
             ["体素尺寸", f"{sh[0]} × {sh[1]} × {sh[2]}"],
             ["物理间距", f"{sp[0]:.3f} × {sp[1]:.3f} × {sp[2]:.3f} mm"],
             ["显示范围", f"[{dmin:.2f}, {dmax:.2f}]"]],
            [60*mm, 110*mm], ts))
        story.append(Spacer(1, 3*mm))

        # 5. 叠加图层概览
        story.append(Paragraph("5. 叠加图层概览", h2))
        if engine.overlays:
            rows = [["#","图层名称","类型","数据范围","色表","透明度"]]
            for i, ov in enumerate(engine.overlays):
                omi = ov.get('min') if ov.get('min') is not None else 0.0
                oma = ov.get('max') if ov.get('max') is not None else 1.0
                oal = ov.get('alpha') if ov.get('alpha') is not None else 0.7
                rows.append([str(i+1), ov.get("name","")[:30],
                    "图谱" if ov.get("is_atlas") else "仿真实场",
                    f"[{omi:.3f}, {oma:.3f}]", str(ov.get("cmap") or "jet"), f"{oal:.1f}"])
            story.append(_make_table(rows, [10*mm,50*mm,25*mm,45*mm,18*mm,18*mm], ts))
        else:
            story.append(Paragraph("（无叠加图层）", body))
        story.append(Spacer(1, 3*mm))

        # 6. MNI 坐标快照
        story.append(Paragraph("6. 当前视点 MNI 坐标快照", h2))
        story.append(Paragraph(f"中心体素 MNI 坐标: {_format_coord(engine.affine, sh[0]//2, sh[1]//2, sh[2]//2)}", body))

        # ============ 第 3/4/5 页：视图截图 ============
        if canvases:
            captions = {
                "sagittal": "视图截图 — 矢状面 (Sagittal)",
                "coronal":  "视图截图 — 冠状面 (Coronal)",
                "axial":    "视图截图 — 轴状面 (Axial)",
            }
            for key in ("sagittal","coronal","axial"):
                canvas = canvases.get(key)
                if canvas is None or canvas.fig is None:
                    continue
                story.append(PageBreak())
                _add_image_page(story, captions[key], canvas.fig, page_w, page_h, h2)

        doc.build(story, onFirstPage=_add_header_footer, onLaterPages=_add_header_footer)

        import glob
        for tf in glob.glob(os.path.join(tempfile.gettempdir(), "tmp*.png")):
            try: os.unlink(tf)
            except Exception: pass
        return True, output_path

    except Exception as e:
        import traceback
        return False, f"生成报告失败: {e}\n\n详细错误:\n{traceback.format_exc()}"