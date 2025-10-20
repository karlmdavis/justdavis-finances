"""Tests for Analysis flow node OutputInfo implementations."""

import tempfile
from pathlib import Path

from finances.analysis.flow import CashFlowAnalysisFlowNode


def test_cash_flow_output_info_is_data_ready_returns_true_with_png_files():
    """Verify is_data_ready returns True when chart PNG files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        charts_dir = data_dir / "cash_flow" / "charts"
        charts_dir.mkdir(parents=True)

        # Create chart file
        (charts_dir / "dashboard.png").write_bytes(b"PNG_DATA")

        node = CashFlowAnalysisFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True


def test_cash_flow_output_info_get_output_files_returns_png_files():
    """Verify get_output_files returns PNG chart files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        charts_dir = data_dir / "cash_flow" / "charts"
        charts_dir.mkdir(parents=True)

        # Create chart files
        (charts_dir / "dashboard.png").write_bytes(b"PNG_DATA")
        (charts_dir / "trend.png").write_bytes(b"PNG_DATA")

        node = CashFlowAnalysisFlowNode(data_dir)
        info = node.get_output_info()
        files = info.get_output_files()

        assert len(files) == 2
        assert all(f.path.suffix == ".png" for f in files)
        assert all(f.record_count == 1 for f in files)  # 1 chart per file
