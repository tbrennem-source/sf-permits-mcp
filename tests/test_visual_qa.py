"""Unit tests for visual QA comparison and filmstrip logic.

No Playwright needed — tests only the image comparison engine
and filmstrip generator using synthetic Pillow images.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from scripts.visual_qa import compare_screenshots, make_filmstrip


@pytest.fixture
def tmp_img_dir(tmp_path: Path) -> Path:
    """Create a temp directory for test images."""
    return tmp_path / "images"


def _make_solid_image(path: Path, color: tuple, size: tuple = (100, 100)) -> Path:
    """Create a solid-color PNG."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, color)
    img.save(str(path))
    return path


class TestCompareScreenshots:
    """Tests for compare_screenshots()."""

    def test_identical_images_pass(self, tmp_img_dir: Path):
        current = _make_solid_image(tmp_img_dir / "current.png", (100, 150, 200))
        golden = _make_solid_image(tmp_img_dir / "golden.png", (100, 150, 200))
        diff_path = tmp_img_dir / "diff.png"

        status, diff_pct, diff_img = compare_screenshots(current, golden, diff_path)

        assert status == "pass"
        assert diff_pct == 0.0
        assert diff_img is None
        assert not diff_path.exists()

    def test_different_images_fail(self, tmp_img_dir: Path):
        current = _make_solid_image(tmp_img_dir / "current.png", (255, 0, 0))
        golden = _make_solid_image(tmp_img_dir / "golden.png", (0, 0, 255))
        diff_path = tmp_img_dir / "diff.png"

        status, diff_pct, diff_img = compare_screenshots(current, golden, diff_path)

        assert status == "fail"
        assert diff_pct == 100.0
        assert diff_img is not None
        assert Path(diff_img).exists()

    def test_missing_golden_returns_new_baseline(self, tmp_img_dir: Path):
        current = _make_solid_image(tmp_img_dir / "current.png", (100, 100, 100))
        golden = tmp_img_dir / "nonexistent_golden.png"
        diff_path = tmp_img_dir / "diff.png"

        status, diff_pct, diff_img = compare_screenshots(current, golden, diff_path)

        assert status == "new_baseline"
        assert diff_pct == 0.0
        assert diff_img is None

    def test_size_mismatch_resizes_golden(self, tmp_img_dir: Path):
        current = _make_solid_image(
            tmp_img_dir / "current.png", (100, 100, 100), size=(200, 200)
        )
        golden = _make_solid_image(
            tmp_img_dir / "golden.png", (100, 100, 100), size=(100, 100)
        )
        diff_path = tmp_img_dir / "diff.png"

        status, diff_pct, diff_img = compare_screenshots(current, golden, diff_path)

        assert status == "pass"
        assert diff_pct == 0.0

    def test_antialiasing_tolerance_passes(self, tmp_img_dir: Path):
        """Small per-pixel differences within tolerance should pass."""
        current = _make_solid_image(tmp_img_dir / "current.png", (100, 100, 100))
        # Differ by 20 per channel — within default tolerance of 30
        golden = _make_solid_image(tmp_img_dir / "golden.png", (120, 120, 120))
        diff_path = tmp_img_dir / "diff.png"

        status, diff_pct, diff_img = compare_screenshots(
            current, golden, diff_path, pixel_tolerance=30
        )

        assert status == "pass"
        assert diff_pct == 0.0

    def test_custom_threshold(self, tmp_img_dir: Path):
        """A 50% different image should pass with threshold_pct=60."""
        size = (100, 100)
        # Create current: top half red, bottom half blue
        current_img = Image.new("RGB", size, (255, 0, 0))
        for x in range(100):
            for y in range(50, 100):
                current_img.putpixel((x, y), (0, 0, 255))
        current_path = tmp_img_dir / "current.png"
        current_path.parent.mkdir(parents=True, exist_ok=True)
        current_img.save(str(current_path))

        # Golden: all red
        golden = _make_solid_image(tmp_img_dir / "golden.png", (255, 0, 0), size)
        diff_path = tmp_img_dir / "diff.png"

        # With default 1% threshold -> fail
        status1, pct1, _ = compare_screenshots(
            current_path, golden, diff_path, pixel_tolerance=0
        )
        assert status1 == "fail"
        assert 49.0 < pct1 < 51.0

        # With 60% threshold -> pass
        status2, pct2, _ = compare_screenshots(
            current_path, golden, tmp_img_dir / "diff2.png",
            threshold_pct=60.0, pixel_tolerance=0,
        )
        assert status2 == "pass"
        assert 49.0 < pct2 < 51.0

    def test_diff_image_shows_differences(self, tmp_img_dir: Path):
        """Diff image should exist and have hot pink pixels where images differ."""
        current = _make_solid_image(tmp_img_dir / "current.png", (255, 0, 0))
        golden = _make_solid_image(tmp_img_dir / "golden.png", (0, 255, 0))
        diff_path = tmp_img_dir / "diff.png"

        status, _, diff_img = compare_screenshots(
            current, golden, diff_path, pixel_tolerance=0
        )

        assert status == "fail"
        diff = Image.open(diff_img)
        # Check a pixel is hot pink (255, 0, 80)
        px = diff.getpixel((0, 0))
        assert px == (255, 0, 80)


class TestMakeFilmstrip:
    """Tests for make_filmstrip()."""

    def test_basic_filmstrip(self, tmp_img_dir: Path):
        imgs = []
        for i, color in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255)]):
            p = _make_solid_image(tmp_img_dir / f"img{i}.png", color, size=(100, 200))
            imgs.append(p)

        output = tmp_img_dir / "strip.png"
        result = make_filmstrip(imgs, output, frame_height=100)

        assert Path(result).exists()
        strip = Image.open(result)
        assert strip.height == 100
        # 3 frames at 50px each (100 * 100/200) + 2 gaps of 4px
        assert strip.width == 50 * 3 + 4 * 2

    def test_empty_input_creates_placeholder(self, tmp_img_dir: Path):
        output = tmp_img_dir / "empty_strip.png"
        result = make_filmstrip([], output)

        assert Path(result).exists()
        strip = Image.open(result)
        assert strip.height == 400
        assert strip.width == 200

    def test_missing_files_skipped(self, tmp_img_dir: Path):
        real = _make_solid_image(tmp_img_dir / "real.png", (100, 100, 100), size=(100, 100))
        missing = tmp_img_dir / "ghost.png"
        output = tmp_img_dir / "strip.png"

        result = make_filmstrip([real, missing], output, frame_height=100)

        assert Path(result).exists()
        strip = Image.open(result)
        # Only one frame: 100px wide scaled to 100px height = 100px
        assert strip.width == 100

    def test_filmstrip_preserves_aspect_ratio(self, tmp_img_dir: Path):
        # Wide image: 400x100
        wide = _make_solid_image(tmp_img_dir / "wide.png", (200, 200, 200), size=(400, 100))
        output = tmp_img_dir / "strip.png"

        make_filmstrip([wide], output, frame_height=200)
        strip = Image.open(output)

        assert strip.height == 200
        # 400x100 scaled to height 200 -> width 800
        assert strip.width == 800
