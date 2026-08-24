"""Isaac Sim demo-window presentation helpers.

The normal SiteGit Isaac launcher keeps the complete editor UI for debugging.
Judge and standalone scenario launchers can opt into a viewport-only window so
the audience sees the construction scene instead of Stage, Property, Content,
and editor tool panels.

This module deliberately imports Kit modules only inside
``enable_viewport_only_mode``.  It can therefore be imported by ordinary unit
tests that do not run inside Isaac Sim.
"""

from __future__ import annotations

from typing import Any


def simulation_app_config(*, headless: bool, presentation: bool) -> dict[str, bool]:
    """Build the small ``SimulationApp`` config shared by demo entry points."""

    config = {"headless": bool(headless)}
    if presentation and not headless:
        # Isaac Sim 5.1 maps this to /app/window/hideUi during application boot.
        # Boot-time application is more reliable than hiding docked panels one
        # by one after the viewport has already been laid out.
        config["hide_ui"] = True
    return config


def enable_viewport_only_mode(
    simulation_app: Any,
    *,
    enabled: bool,
    fullscreen: bool = False,
    maximized: bool = True,
) -> None:
    """Hide editor chrome and enlarge the movable Isaac application window.

    The setting remains user-toggleable while the demo runs: Isaac Sim's
    built-in F7 shortcut restores/hides the UI and F11 can still toggle true
    fullscreen when explicitly wanted.  The default is a maximized *normal*
    window so the Windows taskbar, Alt+Tab, title bar and window movement remain
    available during a judge presentation.  Failures are non-fatal so a
    presentation can still continue on a Kit build whose window API differs.
    """

    if not enabled:
        return

    try:
        import carb

        carb.settings.get_settings().set("/app/window/hideUi", True)
    except Exception as error:  # pragma: no cover - requires Isaac runtime
        print(f"[presentation] UI hiding failed: {error}", flush=True)

    try:
        import omni.appwindow

        window = omni.appwindow.get_default_app_window()
        if window is not None:
            if fullscreen:
                if not window.is_fullscreen():
                    window.set_fullscreen(True)
            else:
                # A previous F11/fullscreen preference can survive between Kit
                # runs.  Explicitly restore a normal OS window before maximizing.
                if window.is_fullscreen():
                    window.set_fullscreen(False)
                    simulation_app.update()
                if maximized and not window.is_maximized():
                    window.maximize_window()
    except Exception as error:  # pragma: no cover - requires Isaac runtime
        print(f"[presentation] window setup failed: {error}", flush=True)

    # Let the viewport consume the newly available main-window area before the
    # scene-loading work begins.
    try:
        simulation_app.update()
        simulation_app.update()
    except Exception as error:  # pragma: no cover - requires Isaac runtime
        print(f"[presentation] viewport refresh skipped: {error}", flush=True)

    print("=" * 68, flush=True)
    print("SiteGit presentation mode: viewport only · maximized movable window", flush=True)
    print(
        "Alt+Tab: switch to Web · title bar: restore/move · "
        "F7: editor UI · F11: optional fullscreen",
        flush=True,
    )
    print("=" * 68, flush=True)
