"""Project zip export / import + conversation event persistence."""

from __future__ import annotations

from pathlib import Path

from codeagent.desktop.project_pack import (
    FEATURE_NAME,
    MANIFEST_NAME,
    PACK_FORMAT,
    README_NAME,
    export_project_zip,
    import_project_zip,
)
from codeagent.desktop.projects import (
    ProjectStore,
    append_event,
    append_message,
    load_conversation,
)


def test_append_thinking_and_tool_events(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "codeagent.desktop.projects.PROJECTS_INDEX", tmp_path / "idx.json"
    )
    store = ProjectStore()
    proj = store.create("事件测试", base=str(tmp_path / "proj"))
    cid = "20260101-000000-abcd"
    append_message(proj, cid, "user", "帮我看下代码")
    append_event(proj, cid, "thinking", text="先列目录")
    append_event(proj, cid, "tool", name="list_dir")
    append_message(proj, cid, "assistant", "看完了")
    msgs = load_conversation(proj, cid)
    roles = [m["role"] for m in msgs]
    assert roles == ["user", "thinking", "tool", "assistant"]
    md = (Path(proj.path) / "conversations" / f"{cid}.md").read_text(encoding="utf-8")
    assert "思考" in md and "list_dir" in md


def test_export_import_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "codeagent.desktop.projects.PROJECTS_INDEX", tmp_path / "idx.json"
    )
    store = ProjectStore()
    proj = store.create("导出样例", base=str(tmp_path / "src"), category="工作")
    cid = "20260101-120000-ef01"
    append_message(proj, cid, "user", "写个脚本")
    append_event(proj, cid, "thinking", text="用 python")
    append_event(proj, cid, "tool", name="bash")
    append_message(proj, cid, "assistant", "写好了")
    (Path(proj.path) / "files" / "note.txt").write_text("hello", encoding="utf-8")
    (Path(proj.path) / "main.py").write_text("print(1)\n", encoding="utf-8")

    zip_path = tmp_path / "pack.zip"
    export_project_zip(proj, zip_path, app_version="0.70.0")
    assert zip_path.is_file()

    import zipfile

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert MANIFEST_NAME in names
        assert README_NAME in names
        assert FEATURE_NAME in names
        assert "conversations/20260101-120000-ef01.jsonl" in names
        assert "main.py" in names
        manifest = __import__("json").loads(zf.read(MANIFEST_NAME))
        assert manifest["format"] == PACK_FORMAT

    dest_store = ProjectStore()
    imported = import_project_zip(dest_store, zip_path, base=str(tmp_path / "dst"))
    assert imported.name == "导出样例"
    assert dest_store.active == imported.id
    assert (Path(imported.path) / "main.py").is_file()
    assert (Path(imported.path) / README_NAME).is_file()
    msgs = load_conversation(imported, cid)
    assert any(m.get("role") == "thinking" for m in msgs)
    assert any(m.get("name") == "bash" for m in msgs)


def test_list_disk_roots_includes_home():
    from codeagent.desktop import projects as proj_mod
    from codeagent.desktop.projects import list_disk_roots

    roots = list_disk_roots(force=True)
    assert roots
    assert any(r["label"] == "用户目录" for r in roots)
    assert all("path" in r and "label" in r and "kind" in r for r in roots)
    # 短 TTL 内应命中缓存（防设置页反复扫盘卡顿）
    cached_at = proj_mod._DISK_ROOTS_CACHE[0]
    again = list_disk_roots()
    assert again == roots
    assert proj_mod._DISK_ROOTS_CACHE[0] == cached_at


def test_is_network_storage_path_unc_and_local(tmp_path):
    from codeagent.desktop.projects import is_network_storage_path

    assert is_network_storage_path(r"\\192.168.1.5\share\wiki")
    assert is_network_storage_path("//nas.local/share/wiki")
    assert not is_network_storage_path(tmp_path)
