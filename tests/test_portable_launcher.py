"""Portable SSD launcher regression checks."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_portable_setup_installs_requirements_without_starting_services() -> None:
    batch = (ROOT / "start_sitegit_portable.bat").read_text(encoding="utf-8")
    script = (ROOT / "ops" / "scripts" / "start_sitegit_portable.ps1").read_text(
        encoding="utf-8"
    )
    common = (
        ROOT / "ops" / "scripts" / "sitegit_portable_common.ps1"
    ).read_text(encoding="utf-8")

    assert "-ExecutionPolicy Bypass" in batch
    assert "start_sitegit_portable.ps1" in batch
    assert 'Python.Python.3.12' in script
    assert 'Ollama.Ollama' in script
    assert 'pip install -r $context.RequirementsFile' in script
    assert '& $context.OllamaExecutable pull $context.OllamaModel' in script
    assert 'app.main:app' not in script
    assert 'isaac_runner.py' not in script
    assert '$ssdRoot = Split-Path -Parent $repoRoot' in common
    assert 'tooling\\venvs\\' in common
    assert '$env:COMPUTERNAME' in common
    assert '$env:SITEGIT_DATA_ROOT = $Context.DataRoot' in common
    assert '$env:TEMP = $Context.PortableTemp' in common
    assert '$env:TMP = $Context.PortableTemp' in common
    assert '$env:SITEGIT_EQUIPMENT_ASSET = $Context.EquipmentAsset' in common
    assert '$env:SITEGIT_SENSOR_REFERENCE_USD = $Context.SensorReference' in common
    assert '$env:OLLAMA_MODELS = $Context.OllamaModels' in common
    assert 'http://127.0.0.1:11435' in common


def test_backend_and_isaac_have_separate_portable_launchers() -> None:
    backend_batch = (ROOT / "start_sitegit_backend.bat").read_text(encoding="utf-8")
    isaac_batch = (ROOT / "start_sitegit_isaac.bat").read_text(encoding="utf-8")
    backend_script = (
        ROOT / "ops" / "scripts" / "start_sitegit_backend_portable.ps1"
    ).read_text(encoding="utf-8")
    isaac_script = (
        ROOT / "ops" / "scripts" / "start_sitegit_isaac_portable.ps1"
    ).read_text(encoding="utf-8")

    assert "start_sitegit_backend_portable.ps1" in backend_batch
    assert "start_sitegit_isaac_portable.ps1" in isaac_batch
    assert '"app.main:app"' in backend_script
    assert "Start-Process $localUrl" in backend_script
    assert '"isaac_adapter\\isaac_runner.py"' in isaac_script
    assert '"--site"' in isaac_script
    assert '"--equipment"' in isaac_script


def test_isaac_runner_keeps_real_process_environment_above_dotenv_files() -> None:
    runner = (ROOT / "isaac_adapter" / "isaac_runner.py").read_text(
        encoding="utf-8"
    )

    assert "_PROCESS_ENVIRONMENT = dict(os.environ)" in runner
    assert "os.environ.update(_PROCESS_ENVIRONMENT)" in runner


def test_judge_demo_launcher_resets_only_mutable_run_state() -> None:
    batch = (ROOT / "start_sitegit_judge_demo.bat").read_text(encoding="utf-8")
    launcher = (
        ROOT / "ops" / "scripts" / "start_sitegit_judge_demo.ps1"
    ).read_text(encoding="utf-8")
    reset = (
        ROOT / "ops" / "scripts" / "reset_sitegit_demo_state.ps1"
    ).read_text(encoding="utf-8")

    assert "start_sitegit_judge_demo.ps1" in batch
    assert "reset_sitegit_demo_state.ps1" in launcher
    assert "start_sitegit_backend_portable.ps1" in launcher
    assert "start_sitegit_isaac_portable.ps1" in launcher
    assert "[switch]$EditorUi" in launcher
    assert '"-Presentation"' in launcher
    assert "-WindowStyle Hidden" in launcher
    assert 'database\\sitegit.db' in reset
    assert 'evidence\\work-packages' in reset
    assert 'isaac\\branches\\' in reset
    assert 'isaac\\pending\\' in reset
    assert 'published_stage_baseline_' in reset
    assert 'stage_inventory_' in reset
    assert 'backups\\demo-runs\\' in reset
    assert '"isaac/assets"' in reset
    assert '"isaac/site-work-map"' in reset


def test_manual_demo_reset_has_a_separate_launcher() -> None:
    batch = (ROOT / "reset_sitegit_demo.bat").read_text(encoding="utf-8")

    assert "reset_sitegit_demo_state.ps1" in batch
    assert "start_sitegit_backend.bat" in batch
    assert "start_sitegit_isaac.bat" in batch
