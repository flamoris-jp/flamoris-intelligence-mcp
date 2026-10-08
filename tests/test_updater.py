import pytest
from flamoris_update_core.resources import TreeBinding, TreeResource

from flamoris_intelligence.updater import inspect_domain


def tree(tmp_path, name):
    path = tmp_path / name
    path.mkdir()
    return TreeResource(TreeBinding(id=name, path=str(path), max_files=20, max_bytes=4096))


def test_owner_validates_config_without_provider_and_binds_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("FLAMORIS_INTELLIGENCE_PROVIDER_URL", "https://provider.invalid")
    resource = tree(tmp_path, "configuration")
    (resource.root / "settings").write_text("first")
    before = inspect_domain(None, {"configuration": resource})
    assert not before.active_work and not before.unknown_work
    (resource.root / "settings").write_text("second")
    assert (
        inspect_domain(None, {"configuration": resource}).configuration_digest
        != before.configuration_digest
    )
    monkeypatch.setenv("FLAMORIS_INTELLIGENCE_PROVIDER_URL", "file:///untrusted")
    with pytest.raises(ValueError):
        inspect_domain(None, {"configuration": resource})
