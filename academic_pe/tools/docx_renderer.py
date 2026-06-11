from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
import re
from typing import Dict, List, Optional


def set_font_style(run, font_name='Times New Roman', font_size=14, bold=False, italic=False, subscript=False):
    run.font.name = font_name
    run._element.rPr.rFonts.set(qn('w:eastAsia'), font_name)
    run.font.size = Pt(font_size)
    run.bold = bold
    run.italic = italic
    run.font.subscript = subscript


def set_paragraph_format(paragraph, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY, first_line_indent_cm=1.25, line_spacing=1.5, space_after=0):
    paragraph.alignment = alignment
    paragraph_format = paragraph.paragraph_format
    paragraph_format.first_line_indent = Cm(first_line_indent_cm)
    paragraph_format.line_spacing = line_spacing
    paragraph_format.space_after = Pt(space_after)


def parse_math_content(paragraph, text, font_name='Times New Roman', font_size=14, bold=False, italic=False):
    text = text.replace(r'\times', '×')
    pattern = re.compile(r'(_\{[^}]+\})|(_.)')
    last_pos = 0
    while True:
        match = pattern.search(text, pos=last_pos)
        if not match:
            remaining = text[last_pos:]
            if remaining:
                run = paragraph.add_run(remaining)
                set_font_style(run, font_name=font_name, font_size=font_size, bold=bold, italic=italic)
            break
        if match.start() > last_pos:
            pre = text[last_pos:match.start()]
            run = paragraph.add_run(pre)
            set_font_style(run, font_name=font_name, font_size=font_size, bold=bold, italic=italic)
        group = match.group()
        if group.startswith('_{'):
            sub_text = group[2:-1]
        else:
            sub_text = group[1:]
        run = paragraph.add_run(sub_text)
        set_font_style(run, font_name=font_name, font_size=font_size, bold=bold, italic=italic, subscript=True)
        last_pos = match.end()


def add_formatted_text(paragraph, text, font_name='Times New Roman', font_size=14):
    bold_parts = re.split(r'(\*\*[^*]+\*\*)', text)
    for b_part in bold_parts:
        if not b_part: continue
        is_bold = False
        content_to_process = b_part
        if b_part.startswith('**') and b_part.endswith('**'):
            is_bold = True
            content_to_process = b_part[2:-2]
        italic_parts = re.split(r'(\*[^*]+\*)', content_to_process)
        for i_part in italic_parts:
            if not i_part: continue
            is_italic = False
            inner_content = i_part
            if i_part.startswith('*') and i_part.endswith('*'):
                is_italic = True
                inner_content = i_part[1:-1]
            math_parts = re.split(r'(\$\$[^$]+\$\$|\$[^$]+\$)', inner_content)
            for m_part in math_parts:
                if not m_part: continue
                if m_part.startswith('$'):
                    math_content = m_part.strip('$')
                    parse_math_content(paragraph, math_content, font_name=font_name, font_size=font_size, bold=is_bold, italic=is_italic)
                else:
                    run = paragraph.add_run(m_part)
                    set_font_style(run, font_name=font_name, font_size=font_size, bold=is_bold, italic=is_italic)


def create_chart_image(output_path: str):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6, 3.5))
        x = [1, 2, 3, 4, 5]
        y1 = [10, 15, 25, 40, 55]
        y2 = [8, 12, 18, 28, 38]
        ax.plot(x, y1, marker='o', color='#0d9488', linewidth=2.5, label='Writer Agent')
        ax.plot(x, y2, marker='s', color='#0f766e', linewidth=2, linestyle='--', label='Reviewer Agent')
        ax.set_title('Agent Performance Metrics', fontsize=12, fontweight='bold', color='#1f2937')
        ax.set_xlabel('Iterations / Run ID', fontsize=10, color='#4b5563')
        ax.set_ylabel('Efficiency Index (%)', fontsize=10, color='#4b5563')
        ax.grid(True, linestyle=':', alpha=0.6)
        ax.legend()
        plt.tight_layout()
        plt.savefig(output_path, dpi=300)
        plt.close(fig)
        import logging
        logging.getLogger(__name__).info("Successfully created chart image at %s", output_path)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Failed to create chart image: %s", e)


def create_table(doc, headers: List[str], rows: List[List[str]], font_name='Times New Roman', font_size=11):
    try:
        table = doc.add_table(rows=1, cols=len(headers))
        table.style = 'Table Grid'
        hdr_cells = table.rows[0].cells
        for i, header in enumerate(headers):
            hdr_cells[i].text = header.strip()
            for paragraph in hdr_cells[i].paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in paragraph.runs:
                    set_font_style(run, font_name=font_name, font_size=font_size, bold=True)
        
        for row_data in rows:
            row_cells = table.add_row().cells
            for i in range(len(headers)):
                val = row_data[i] if i < len(row_data) else ""
                row_cells[i].text = val.strip()
                for paragraph in row_cells[i].paragraphs:
                    for run in paragraph.runs:
                        set_font_style(run, font_name=font_name, font_size=font_size)
        
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        import logging
        logging.getLogger(__name__).info("Successfully created table with %d rows", len(rows))
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Failed to create table: %s", e)


def render_table_block(doc, table_lines: List[str], font_name='Times New Roman'):
    if not table_lines:
        return
    
    parsed_rows = []
    for line in table_lines:
        parts = [p.strip() for p in line.split('|')]
        if len(parts) > 1:
            if parts[0] == "":
                parts = parts[1:]
            if parts and parts[-1] == "":
                parts = parts[:-1]
            parsed_rows.append(parts)
            
    if not parsed_rows:
        return

    headers = parsed_rows[0]
    data_rows = parsed_rows[1:]
    if data_rows and any(all(c in '-:| ' for c in cell) for cell in data_rows[0]):
        data_rows = data_rows[1:]
        
    create_table(doc, headers, data_rows, font_name=font_name)


def render_paper(content: Dict[str, str], output_filename: str = "Output.docx", config: Optional[any] = None):
    import os
    import tempfile
    import logging
    logger = logging.getLogger(__name__)

    font_name = "Times New Roman"
    font_size = 14
    title_font_size = 20
    line_spacing = 1.5
    first_line_indent_cm = 1.25
    alignment_str = "justify"
    title_text = "GENERATED ACADEMIC PAPER"
    
    order = ['theory', 'calculation', 'conclusion']
    
    if config is not None:
        if hasattr(config, "style") and config.style is not None:
            font_name = getattr(config.style, "font_name", font_name)
            font_size = getattr(config.style, "font_size", font_size)
            title_font_size = getattr(config.style, "title_font_size", title_font_size)
            line_spacing = getattr(config.style, "line_spacing", line_spacing)
            first_line_indent_cm = getattr(config.style, "first_line_indent_cm", first_line_indent_cm)
            alignment_str = getattr(config.style, "alignment", alignment_str)
        if hasattr(config, "pipeline") and config.pipeline is not None:
            title_text = getattr(config.pipeline, "title", title_text)
            if hasattr(config.pipeline, "sections") and config.pipeline.sections:
                order = [s.name for s in config.pipeline.sections]

    alignment_map = {
        'left': WD_ALIGN_PARAGRAPH.LEFT,
        'center': WD_ALIGN_PARAGRAPH.CENTER,
        'right': WD_ALIGN_PARAGRAPH.RIGHT,
        'justify': WD_ALIGN_PARAGRAPH.JUSTIFY
    }
    align_val = alignment_map.get(alignment_str.lower(), WD_ALIGN_PARAGRAPH.JUSTIFY)

    doc = Document()

    # Title Page
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(100)
    run = p.add_run(f"{title_text}\n")
    set_font_style(run, font_name=font_name, font_size=title_font_size, bold=True)
    doc.add_page_break()

    for section in order:
        if section in content:
            text_block = content[section]
            lines = text_block.split('\n')
            
            in_table = False
            table_lines = []

            for line in lines:
                stripped = line.strip()
                
                if stripped.startswith('|'):
                    in_table = True
                    table_lines.append(stripped)
                    continue
                else:
                    if in_table:
                        render_table_block(doc, table_lines, font_name=font_name)
                        in_table = False
                        table_lines = []

                if not stripped: continue

                if stripped.startswith('# '):
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    p.paragraph_format.space_before = Pt(12)
                    p.paragraph_format.space_after = Pt(12)
                    run = p.add_run(stripped[2:])
                    set_font_style(run, font_name=font_name, font_size=font_size + 2, bold=True)
                elif stripped.startswith('## '):
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    p.paragraph_format.space_before = Pt(10)
                    p.paragraph_format.space_after = Pt(10)
                    run = p.add_run(stripped[3:])
                    set_font_style(run, font_name=font_name, font_size=font_size + 1, bold=True)
                elif stripped.startswith('### '):
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    p.paragraph_format.space_before = Pt(8)
                    p.paragraph_format.space_after = Pt(8)
                    run = p.add_run(stripped[4:])
                    set_font_style(run, font_name=font_name, font_size=font_size, bold=True)
                elif '[Chart]' in stripped or '[Chart:' in stripped:
                    temp_dir = tempfile.gettempdir()
                    chart_path = os.path.join(temp_dir, f"chart_{section}.png")
                    create_chart_image(chart_path)
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = p.add_run()
                    run.add_picture(chart_path, width=Cm(14))
                    
                    caption_text = "Figure 1: Generated Chart Output"
                    match = re.search(r'\[Chart:\s*(.*?)\]', stripped)
                    if match:
                        caption_text = f"Figure: {match.group(1)}"
                    p_cap = doc.add_paragraph()
                    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run_cap = p_cap.add_run(caption_text)
                    set_font_style(run_cap, font_name=font_name, font_size=font_size - 2, italic=True)
                else:
                    p = doc.add_paragraph()
                    set_paragraph_format(
                        p, 
                        alignment=align_val, 
                        first_line_indent_cm=first_line_indent_cm, 
                        line_spacing=line_spacing
                    )
                    add_formatted_text(p, stripped, font_name=font_name, font_size=font_size)
            
            if in_table:
                render_table_block(doc, table_lines, font_name=font_name)

    try:
        doc.save(output_filename)
        logger.info("Saved document successfully to %s", output_filename)
    except Exception as e:
        logger.error("Failed to save generated document to %s: %s", output_filename, e)
        raise

    return output_filename
