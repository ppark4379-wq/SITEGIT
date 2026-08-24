"""Viewport-only Isaac presentation-mode contract checks."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "isaac_adapter"
if str(ADAPTER) not in sys.path:
    sys.path.insert(0, str(ADAPTER))

from presentation_mode import enable_viewport_only_mode, simulation_app_config


def test_presentation_config_hides_ui_only_for_visible_window() -> None:
    assert simulation_app_config(headless=False, presentation=True) == {
        "headless": False,
        "hide_ui": True,
    }
    assert simulation_app_config(headless=False, presentation=False) == {
        "headless": False,
    }
    assert simulation_app_config(headless=True, presentation=True) == {
        "headless": True,
    }


def test_judge_and_standalone_demo_launchers_enable_presentation_mode() -> None:
    judge = (ROOT / "ops" / "scripts" / "start_sitegit_judge_demo.ps1").read_text(
        encoding="utf-8"
    )
    isaac = (ROOT / "ops" / "scripts" / "start_sitegit_isaac_portable.ps1").read_text(
        encoding="utf-8"
    )

    assert "[switch]$EditorUi" in judge
    assert '$isaacArguments += "-Presentation"' in judge
    assert "[switch]$Presentation" in isaac
    assert '$arguments += "--presentation"' in isaac

    for name in (
        "start_sitegit_excavator_demo.ps1",
        "start_sitegit_pipeline_demo.ps1",
        "start_sitegit_backfill_demo.ps1",
    ):
        source = (ROOT / "ops" / "scripts" / name).read_text(encoding="utf-8")
        assert "[switch]$EditorUi" in source
        assert '$arguments += "--presentation"' in source


def test_all_visible_demo_entry_points_use_shared_presentation_helper() -> None:
    for name in (
        "isaac_runner.py",
        "three_excavator_demo.py",
        "pipeline_installation_demo.py",
        "pipeline_backfill_demo.py",
    ):
        source = (ADAPTER / name).read_text(encoding="utf-8")
        assert '"--presentation"' in source
        assert "simulation_app_config(" in source
        assert "enable_viewport_only_mode(" in source


def test_presentation_defaults_to_a_maximized_normal_window() -> None:
    defaults = enable_viewport_only_mode.__kwdefaults__

    assert defaults["fullscreen"] is False
    assert defaults["maximized"] is True
    source = (ADAPTER / "presentation_mode.py").read_text(encoding="utf-8")
    assert "window.set_fullscreen(False)" in source
    assert "window.maximize_window()" in source
    assert "Alt+Tab: switch to Web" in source
