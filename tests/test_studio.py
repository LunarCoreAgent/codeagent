"""Director desk: parse shots, persist, assemble without a live Comfy."""

from __future__ import annotations

from pathlib import Path

import pytest

from codeagent.desktop.api import DesktopAPI
from codeagent.desktop.ui import HTML
from codeagent.videoops import VideoOpsConfig, bundled_library
from codeagent.videoops.studio import (
    Desk,
    Shot,
    apply_desk_patch,
    assemble_desk,
    load_desk,
    parse_script_shots,
    save_desk,
)
from codeagent.videoops.tools import VideoStudioTool, video_ops_tools


@pytest.fixture
def studio_ws(tmp_path, monkeypatch):
    monkeypatch.setattr("codeagent.videoops.CONFIG_PATH", tmp_path / "videoops.json")
    cfg = VideoOpsConfig(path=str(tmp_path / "ws"), enabled=True)
    cfg.save()
    return tmp_path / "ws"


@pytest.fixture
def api(studio_ws, tmp_path, monkeypatch):
    monkeypatch.setattr("codeagent.desktop.api.DESKTOP_CONFIG_PATH", tmp_path / "desktop.json")
    a = DesktopAPI(root=tmp_path)
    return a


def test_parse_numbered_and_heading_shots():
    shots = parse_script_shots(
        "1. 夜雨巷，近景\n女人撑伞\n2. 积水倒影\n## 收束\n远景走入深巷"
    )
    assert len(shots) == 3
    assert "夜雨巷" in shots[0].title
    assert "撑伞" in shots[0].prompt
    assert shots[2].title == "收束"


def test_desk_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("codeagent.videoops.studio.desk_root", lambda workspace=None: tmp_path)
    desk = Desk(title="雨巷", engine="comfy", shots=[Shot(title="开场", prompt="雨")])
    save_desk(desk, tmp_path)
    loaded = load_desk(tmp_path)
    assert loaded.title == "雨巷"
    assert loaded.shots[0].prompt == "雨"


def test_apply_patch_keeps_shots():
    desk = Desk(shots=[Shot(prompt="A")])
    apply_desk_patch(desk, {"title": "T", "engine": "wan"})
    assert desk.title == "T" and desk.engine == "wan" and len(desk.shots) == 1


def test_assemble_requires_clips():
    desk = Desk(shots=[Shot(prompt="x", status="draft")])
    r = assemble_desk(desk)
    assert not r["ok"] and "镜头" in r["error"]


def test_assemble_uses_ffmpeg(tmp_path, monkeypatch):
    monkeypatch.setattr("codeagent.videoops.studio.ensure_desk_workspace", lambda: tmp_path)
    monkeypatch.setattr("codeagent.videoops.studio.desk_root", lambda workspace=None: tmp_path)
    monkeypatch.setattr("codeagent.videoops.studio.append_pipeline", lambda *a, **k: None)
    clip = tmp_path / "a.mp4"
    clip.write_bytes(b"fake")
    desk = Desk(shots=[Shot(prompt="x", clip=str(clip), status="done")])

    class _Ran:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(cmd, **_kw):
        Path(cmd[-1]).write_bytes(b"out")
        return _Ran()

    monkeypatch.setattr("codeagent.videoops.studio.shutil.which", lambda n: "/usr/bin/ffmpeg")
    monkeypatch.setattr("codeagent.videoops.studio.subprocess.run", fake_run)
    r = assemble_desk(desk)
    assert r["ok"] and Path(r["path"]).is_file()


def test_ui_has_studio_between_chat_and_lead():
    chat = HTML.find('data-page="chat"')
    studio = HTML.find('data-page="studio"')
    lead = HTML.find('data-page="lead"')
    assert 0 < chat < studio < lead
    assert 'id="page-studio"' in HTML
    assert "导演台" in HTML
    assert "pywebview.api.get_studio" in HTML
    assert "studio_generate_shot" in HTML
    assert "docs.comfy.org/zh" in HTML
    assert "Comfy-Org/ComfyUI" in HTML
    assert "st_duration" in HTML
    assert "collectShots" in HTML
    dash = HTML.find("onclick=\"go('studio')\"")
    lead_q = HTML.find("onclick=\"go('lead')\"")
    assert 0 < dash < lead_q


def test_studio_api_import(api, studio_ws):
    r = api.studio_import_script("1. 第一镜\n近景\n2. 第二镜\n远景")
    assert r["ok"] and r["added"] == 2
    st = api.get_studio()
    assert st["ok"] and len(st["desk"]["shots"]) == 2
    gone = api.studio_remove_shot(st["desk"]["shots"][0]["id"])
    assert gone["ok"] and len(gone["desk"]["shots"]) == 1
    saved = api.save_studio({"title": "雨巷", "duration_sec": 36})
    assert saved["ok"] and saved["desk"]["title"] == "雨巷"
    assert saved["desk"]["duration_sec"] == 36
    assert len(saved["desk"]["shots"]) == 1


def test_video_studio_tool(studio_ws):
    import asyncio

    tool = VideoStudioTool()
    names = {t.name for t in video_ops_tools(VideoOpsConfig.load())}
    assert "video_studio" in names
    out = asyncio.run(tool.execute(action="import_script", script="1. 巷口\n近景\n2. 深巷\n远景"))
    assert "导入 2" in out
    st = asyncio.run(tool.execute(action="status"))
    assert "shots: 2" in st
    saved = asyncio.run(tool.execute(action="save", title="雨巷短剧"))
    assert "雨巷短剧" in saved


def test_director_desk_skill_in_bundled():
    lib = bundled_library()
    assert "director-desk" in {s.name for s in lib}
    hits = lib.search("导演台 分镜 Comfy 合成")
    assert {s.name for s in hits} & {"director-desk", "video-ops-pipeline"}
