"""외장 SSD를 들고 다닐 때 데이터 경로가 흔들리지 않는지 확인합니다.

`.env`에 상대경로를 넣으면 실행 위치(CWD)가 아니라 저장소 루트를 기준으로
해석되어야 합니다. 그렇지 않으면 IDE나 수동 uvicorn으로 띄웠을 때 서버가
엉뚱한 위치에 빈 DB를 조용히 새로 만듭니다.
"""

from app.core.config import REPO_ROOT, Settings


def test_relative_data_root_anchors_to_repo_root(monkeypatch, tmp_path):
    monkeypatch.setenv("SITEGIT_DATA_ROOT", "../SiteGitData")
    monkeypatch.chdir(tmp_path)
    settings = Settings()
    assert settings.sitegit_data_root == (REPO_ROOT.parent / "SiteGitData").resolve()


def test_dot_relative_data_root_stays_inside_repo(monkeypatch, tmp_path):
    monkeypatch.setenv("SITEGIT_DATA_ROOT", "./runtime")
    monkeypatch.chdir(tmp_path)
    settings = Settings()
    assert settings.sitegit_data_root == (REPO_ROOT / "runtime").resolve()


def test_absolute_data_root_is_preserved(monkeypatch, tmp_path):
    monkeypatch.setenv("SITEGIT_DATA_ROOT", str(tmp_path))
    settings = Settings()
    assert settings.sitegit_data_root == tmp_path.resolve()


def test_database_url_follows_resolved_data_root(monkeypatch, tmp_path):
    monkeypatch.setenv("SITEGIT_DATA_ROOT", "../SiteGitData")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.chdir(tmp_path)
    settings = Settings()
    expected = (REPO_ROOT.parent / "SiteGitData" / "database" / "sitegit.db").resolve()
    assert settings.resolved_database_url == f"sqlite:///{expected.as_posix()}"


def test_backend_and_isaac_adapter_agree(monkeypatch, tmp_path):
    """Backend와 map_publisher가 같은 상대경로를 같은 폴더로 해석해야 합니다."""
    from isaac_adapter.map_publisher import _resolved_data_root

    monkeypatch.setenv("SITEGIT_DATA_ROOT", "../SiteGitData")
    monkeypatch.chdir(tmp_path)
    assert Settings().sitegit_data_root == _resolved_data_root()
