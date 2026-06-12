import os
import tempfile
import pytest
from docx import Document

from academic_pe.core.sandbox import execute_sandbox_blocks
from academic_pe.tools.docx_renderer import render_paper


def test_matplotlib_and_docx_rendering_e2e():
    img_dir = "exports"
    os.makedirs(img_dir, exist_ok=True)
    img_path = os.path.join(img_dir, "test_matplotlib_e2e_plot.png").replace("\\", "/")
    
    # Ensure clean state
    if os.path.exists(img_path):
        os.remove(img_path)
        
    markdown_content = f"""
Here is a matplotlib graph generated in the sandbox:
```python-run
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.figure()
plt.plot([1, 2, 3], [4, 5, 6])
plt.title("E2E Test Plot")
plt.savefig("{img_path}")
plt.close()
print("![E2E Test Plot]({img_path})")
```
"""

    # 1. Execute sandbox block
    evaluated_content = execute_sandbox_blocks(markdown_content)
    
    # 2. Check that the output tag matches and file is generated
    assert f"![E2E Test Plot]({img_path})" in evaluated_content
    assert "python-run" not in evaluated_content
    assert os.path.exists(img_path)
    
    # 3. Render the DOCX file
    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = os.path.join(tmpdir, "test_e2e_output.docx")
        render_paper({"theory": evaluated_content}, docx_path)
        
        assert os.path.exists(docx_path)
        
        # 4. Verify the image is embedded in the DOCX file
        doc = Document(docx_path)
        
        # doc.inline_shapes stores all embedded pictures
        assert len(doc.inline_shapes) == 1
        
        # Verify text captions
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "Figure: E2E Test Plot" in full_text
        assert "Image Not Found" not in full_text

    # 5. Cleanup the generated plot
    if os.path.exists(img_path):
        os.remove(img_path)
