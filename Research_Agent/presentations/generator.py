"""
Presentation Generator.

Generates PptxGenJS JavaScript code for academic/scientific presentations.
Outputs a .js file that can be run with Node.js to produce a .pptx file.

Color schemes and templates are designed for scientific presentations.
"""

import json
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════════════
# COLOR SCHEMES
# ═══════════════════════════════════════════════════════════

COLOR_SCHEMES = {
    "ocean": {
        "primary": "065A82",      # Deep blue
        "secondary": "1C7293",    # Teal
        "accent": "21295C",       # Midnight
        "bg_dark": "0A1628",      # Dark navy
        "bg_light": "F8FAFC",     # Off-white
        "text_dark": "1E293B",    # Slate
        "text_light": "FFFFFF",   # White
        "text_muted": "64748B",   # Muted slate
        "chart_colors": ["065A82", "1C7293", "2E86AB", "48A9A6", "4ECDC4"],
    },
    "forest": {
        "primary": "2C5F2D",
        "secondary": "97BC62",
        "accent": "1B4332",
        "bg_dark": "0D1B0E",
        "bg_light": "F5F7F2",
        "text_dark": "1B2A1B",
        "text_light": "FFFFFF",
        "text_muted": "6B7C6B",
        "chart_colors": ["2C5F2D", "97BC62", "52B788", "40916C", "2D6A4F"],
    },
    "midnight": {
        "primary": "1E2761",
        "secondary": "CADCFC",
        "accent": "408EC6",
        "bg_dark": "0F1535",
        "bg_light": "F0F4FF",
        "text_dark": "1E293B",
        "text_light": "FFFFFF",
        "text_muted": "6B7DB3",
        "chart_colors": ["1E2761", "408EC6", "7B2D8E", "5E60CE", "48BFE3"],
    },
    "teal": {
        "primary": "028090",
        "secondary": "00A896",
        "accent": "02C39A",
        "bg_dark": "012A33",
        "bg_light": "F0FDFA",
        "text_dark": "134E4A",
        "text_light": "FFFFFF",
        "text_muted": "5F9EA0",
        "chart_colors": ["028090", "00A896", "02C39A", "38B000", "008000"],
    },
    "charcoal": {
        "primary": "36454F",
        "secondary": "F2F2F2",
        "accent": "E85D04",
        "bg_dark": "1A1A2E",
        "bg_light": "FAFAFA",
        "text_dark": "212121",
        "text_light": "FFFFFF",
        "text_muted": "757575",
        "chart_colors": ["36454F", "E85D04", "FF8C00", "5C677D", "7D8597"],
    },
    "berry": {
        "primary": "6D2E46",
        "secondary": "A26769",
        "accent": "D4A373",
        "bg_dark": "2D0A1C",
        "bg_light": "FDF6F0",
        "text_dark": "3D1A2B",
        "text_light": "FFFFFF",
        "text_muted": "8B6B73",
        "chart_colors": ["6D2E46", "A26769", "D4A373", "C1666B", "E4C1F9"],
    },
    "sage": {
        "primary": "84B59F",
        "secondary": "69A297",
        "accent": "50808E",
        "bg_dark": "1A2F2A",
        "bg_light": "F5FAF7",
        "text_dark": "2C3E36",
        "text_light": "FFFFFF",
        "text_muted": "6B8F80",
        "chart_colors": ["84B59F", "69A297", "50808E", "3C6E71", "284B63"],
    },
    "coral": {
        "primary": "F96167",
        "secondary": "F9E795",
        "accent": "2F3C7E",
        "bg_dark": "1A1A2E",
        "bg_light": "FFF8F0",
        "text_dark": "2F3C7E",
        "text_light": "FFFFFF",
        "text_muted": "8B8FA3",
        "chart_colors": ["F96167", "F9E795", "2F3C7E", "FF6B6B", "4ECDC4"],
    },
}


# ═══════════════════════════════════════════════════════════
# PRESENTATION TEMPLATES
# ═══════════════════════════════════════════════════════════

@dataclass
class SlideContent:
    """Content for a single slide."""
    title: str
    key_points: list[str] = field(default_factory=list)
    speaker_notes: str = ""
    chart_data: Optional[dict] = None
    chart_type: str = ""
    layout: str = "content"  # title, content, two_column, chart, references


@dataclass
class PresentationSpec:
    """Complete specification for a presentation."""
    title: str
    subtitle: str = ""
    author: str = "BioAgent Research Team"
    date: str = ""
    slides: list[SlideContent] = field(default_factory=list)
    color_scheme: str = "ocean"
    references: list[str] = field(default_factory=list)
    include_references_slide: bool = True


def generate_pptxgenjs_code(spec: PresentationSpec,
                             output_path: str = "/tmp/presentation.pptx") -> str:
    """
    Generate PptxGenJS JavaScript code for a presentation.

    Returns the JS code as a string that can be written to a file and
    executed with Node.js.
    """
    colors = COLOR_SCHEMES.get(spec.color_scheme, COLOR_SCHEMES["ocean"])

    # Build the JavaScript
    js_lines = [
        'const pptxgen = require("pptxgenjs");',
        "",
        "let pres = new pptxgen();",
        'pres.layout = "LAYOUT_16x9";',
        f'pres.author = {json.dumps(spec.author)};',
        f'pres.title = {json.dumps(spec.title)};',
        "",
        "// ═══ Helper functions ═══",
        "",
        "// Factory functions to avoid option object mutation",
        f'const makeShadow = () => ({{ type: "outer", blur: 6, offset: 2, color: "000000", opacity: 0.12 }});',
        "",
    ]

    # ─── Title Slide ───
    js_lines.extend([
        "// ═══ TITLE SLIDE ═══",
        "let titleSlide = pres.addSlide();",
        f'titleSlide.background = {{ color: "{colors["bg_dark"]}" }};',
        "",
        # Title text
        f'titleSlide.addText({json.dumps(spec.title)}, {{',
        f'  x: 0.8, y: 1.5, w: 8.4, h: 1.5,',
        f'  fontSize: 36, fontFace: "Georgia", bold: true,',
        f'  color: "{colors["text_light"]}", align: "left", valign: "middle",',
        f'  margin: 0',
        f'}});',
        "",
    ])

    if spec.subtitle:
        js_lines.extend([
            f'titleSlide.addText({json.dumps(spec.subtitle)}, {{',
            f'  x: 0.8, y: 3.2, w: 8.4, h: 0.8,',
            f'  fontSize: 18, fontFace: "Calibri",',
            f'  color: "{colors["text_muted"]}", align: "left",',
            f'  margin: 0',
            f'}});',
            "",
        ])

    # Accent bar on title slide
    js_lines.extend([
        f'titleSlide.addShape(pres.shapes.RECTANGLE, {{',
        f'  x: 0.8, y: 3.0, w: 2.5, h: 0.04,',
        f'  fill: {{ color: "{colors["accent"]}" }}',
        f'}});',
        "",
    ])

    # Date / author line
    if spec.date or spec.author:
        footer_text = " | ".join(filter(None, [spec.author, spec.date]))
        js_lines.extend([
            f'titleSlide.addText({json.dumps(footer_text)}, {{',
            f'  x: 0.8, y: 4.8, w: 8.4, h: 0.4,',
            f'  fontSize: 12, fontFace: "Calibri",',
            f'  color: "{colors["text_muted"]}", align: "left",',
            f'  margin: 0',
            f'}});',
            "",
        ])

    # ─── Content Slides ───
    for i, slide in enumerate(spec.slides):
        slide_var = f"slide{i+1}"
        js_lines.extend([
            f"// ═══ SLIDE {i+2}: {slide.title} ═══",
            f"let {slide_var} = pres.addSlide();",
            f'{slide_var}.background = {{ color: "{colors["bg_light"]}" }};',
            "",
        ])

        if slide.layout == "chart" and slide.chart_data:
            _add_chart_slide(js_lines, slide_var, slide, colors)
        elif slide.layout == "two_column":
            _add_two_column_slide(js_lines, slide_var, slide, colors)
        else:
            _add_content_slide(js_lines, slide_var, slide, colors)

        # Speaker notes
        if slide.speaker_notes:
            js_lines.append(
                f'{slide_var}.addNotes({json.dumps(slide.speaker_notes)});'
            )
            js_lines.append("")

    # ─── References Slide ───
    if spec.include_references_slide and spec.references:
        js_lines.extend([
            "// ═══ REFERENCES SLIDE ═══",
            "let refSlide = pres.addSlide();",
            f'refSlide.background = {{ color: "{colors["bg_light"]}" }};',
            "",
            f'refSlide.addText("References", {{',
            f'  x: 0.8, y: 0.3, w: 8.4, h: 0.7,',
            f'  fontSize: 28, fontFace: "Georgia", bold: true,',
            f'  color: "{colors["primary"]}", align: "left",',
            f'  margin: 0',
            f'}});',
            "",
        ])

        # Build reference text array
        ref_items = []
        for ref in spec.references[:15]:  # Limit to 15 refs per slide
            ref_items.append(
                f'  {{ text: {json.dumps(ref)}, options: {{ bullet: true, breakLine: true, fontSize: 9 }} }}'
            )

        js_lines.extend([
            f'refSlide.addText([',
            ",\n".join(ref_items),
            f'], {{',
            f'  x: 0.8, y: 1.2, w: 8.4, h: 4.0,',
            f'  fontFace: "Calibri", color: "{colors["text_muted"]}",',
            f'  valign: "top"',
            f'}});',
            "",
        ])

    # ─── Write File ───
    js_lines.extend([
        f'pres.writeFile({{ fileName: {json.dumps(output_path)} }})',
        f'  .then(() => console.log("Presentation saved to {output_path}"))',
        f'  .catch(err => {{ console.error("Error:", err); process.exit(1); }});',
    ])

    return "\n".join(js_lines)


def _add_content_slide(lines: list, var: str, slide: SlideContent, colors: dict):
    """Add a standard content slide with title + bullet points."""
    # Slide title
    lines.extend([
        f'{var}.addText({json.dumps(slide.title)}, {{',
        f'  x: 0.8, y: 0.3, w: 8.4, h: 0.7,',
        f'  fontSize: 28, fontFace: "Georgia", bold: true,',
        f'  color: "{colors["primary"]}", align: "left",',
        f'  margin: 0',
        f'}});',
        "",
    ])

    # Accent bar under title
    lines.extend([
        f'{var}.addShape(pres.shapes.RECTANGLE, {{',
        f'  x: 0.8, y: 1.05, w: 1.5, h: 0.03,',
        f'  fill: {{ color: "{colors["accent"]}" }}',
        f'}});',
        "",
    ])

    if slide.key_points:
        items = []
        for point in slide.key_points:
            items.append(
                f'  {{ text: {json.dumps(point)}, options: {{ bullet: true, breakLine: true }} }}'
            )

        lines.extend([
            f'{var}.addText([',
            ",\n".join(items),
            f'], {{',
            f'  x: 0.8, y: 1.3, w: 8.4, h: 3.8,',
            f'  fontSize: 14, fontFace: "Calibri", lineSpacingMultiple: 1.3,',
            f'  color: "{colors["text_dark"]}", valign: "top"',
            f'}});',
            "",
        ])


def _add_chart_slide(lines: list, var: str, slide: SlideContent, colors: dict):
    """Add a slide with a chart."""
    # Title
    lines.extend([
        f'{var}.addText({json.dumps(slide.title)}, {{',
        f'  x: 0.8, y: 0.3, w: 8.4, h: 0.7,',
        f'  fontSize: 24, fontFace: "Georgia", bold: true,',
        f'  color: "{colors["primary"]}", align: "left",',
        f'  margin: 0',
        f'}});',
        "",
    ])

    if slide.chart_data:
        data = slide.chart_data
        chart_type_map = {
            "bar": "BAR",
            "line": "LINE",
            "pie": "PIE",
            "doughnut": "DOUGHNUT",
            "scatter": "SCATTER",
        }
        pptx_chart_type = chart_type_map.get(slide.chart_type, "BAR")

        # Build series data
        series_js = json.dumps(data.get("series", []))
        chart_colors_js = json.dumps(colors["chart_colors"][:5])

        lines.extend([
            f'{var}.addChart(pres.charts.{pptx_chart_type}, {series_js}, {{',
            f'  x: 0.8, y: 1.2, w: 8.4, h: 3.8,',
            f'  barDir: "col",',
            f'  chartColors: {chart_colors_js},',
            f'  chartArea: {{ fill: {{ color: "FFFFFF" }}, roundedCorners: true }},',
            f'  catAxisLabelColor: "{colors["text_muted"]}",',
            f'  valAxisLabelColor: "{colors["text_muted"]}",',
            f'  valGridLine: {{ color: "E2E8F0", size: 0.5 }},',
            f'  catGridLine: {{ style: "none" }},',
            f'  showValue: true,',
            f'  dataLabelPosition: "outEnd",',
            f'  dataLabelColor: "{colors["text_dark"]}",',
            f'  showLegend: {str(len(data.get("series", [])) > 1).lower()}',
            f'}});',
            "",
        ])


def _add_two_column_slide(lines: list, var: str, slide: SlideContent, colors: dict):
    """Add a two-column layout slide."""
    lines.extend([
        f'{var}.addText({json.dumps(slide.title)}, {{',
        f'  x: 0.8, y: 0.3, w: 8.4, h: 0.7,',
        f'  fontSize: 24, fontFace: "Georgia", bold: true,',
        f'  color: "{colors["primary"]}", align: "left",',
        f'  margin: 0',
        f'}});',
        "",
    ])

    # Split points into two columns
    mid = len(slide.key_points) // 2
    left_points = slide.key_points[:mid] if mid > 0 else slide.key_points
    right_points = slide.key_points[mid:] if mid > 0 else []

    for col, (points, x_pos) in enumerate([
        (left_points, 0.8), (right_points, 5.2)
    ]):
        if points:
            items = []
            for p in points:
                items.append(
                    f'  {{ text: {json.dumps(p)}, options: {{ bullet: true, breakLine: true }} }}'
                )
            lines.extend([
                f'{var}.addText([',
                ",\n".join(items),
                f'], {{',
                f'  x: {x_pos}, y: 1.3, w: 4.0, h: 3.8,',
                f'  fontSize: 13, fontFace: "Calibri",',
                f'  color: "{colors["text_dark"]}", valign: "top"',
                f'}});',
                "",
            ])
