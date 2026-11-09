"""Execute the EDA notebook and export a shareable HTML report."""

from pathlib import Path
import os

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
from nbconvert import HTMLExporter

root = Path(__file__).resolve().parents[1]
notebook_path = root / "notebooks/01_macroeconomic_eda.ipynb"
nb = nbformat.read(notebook_path, as_version=4)
ExecutePreprocessor(timeout=180, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(root)}})
nbformat.write(nb, notebook_path)
report_dir = root / "reports"
report_dir.mkdir(exist_ok=True)
html, _ = HTMLExporter().from_notebook_node(nb)
(report_dir / "eda.html").write_text(html)
code_cells = [cell for cell in nb.cells if cell.cell_type == "code"]
assert all(cell.execution_count is not None for cell in code_cells)
assert not any(output.output_type == "error" for cell in code_cells for output in cell.outputs)
print(f"Executed {len(code_cells)} code cells without errors. Exported reports/eda.html.")
