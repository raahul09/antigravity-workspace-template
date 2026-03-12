from src.sandbox.factory import get_sandbox
from src.sandbox.local import LocalSandbox
from src.sandbox.microsandbox_exec import MicrosandboxSandbox


def test_factory_default_local(monkeypatch):
    monkeypatch.delenv("SANDBOX_TYPE", raising=False)
    s = get_sandbox()
    assert isinstance(s, LocalSandbox)


def test_factory_microsandbox_resolution(monkeypatch):
    # When microsandbox is requested, factory should return MicrosandboxSandbox instance
    monkeypatch.setenv("SANDBOX_TYPE", "microsandbox")
    s = get_sandbox()
    assert isinstance(s, MicrosandboxSandbox)


def test_factory_legacy_docker_value_falls_back_to_local(monkeypatch):
    monkeypatch.setenv("SANDBOX_TYPE", "docker")
    s = get_sandbox()
    assert isinstance(s, LocalSandbox)
