"""Video ops workspace, bundled skills, publish drafts."""

from __future__ import annotations

from codeagent.desktop.ui import HTML
from codeagent.videoops import (
    BUNDLED_SKILLS,
    VideoOpsConfig,
    bootstrap_workspace,
    bundled_library,
    install_bundled_skills,
    is_workspace_ready,
    load_all_skills,
    save_publish_draft,
    workspace_status,
)


def test_bundled_skills_cover_pipeline():
    names = set(BUNDLED_SKILLS)
    assert names >= {
        "video-ops-pipeline",
        "short-drama-script",
        "wan-gradio",
        "libtv-generate",
        "remotion-video",
        "video-edit-zh",
        "ops-analyze",
        "multi-publish",
    }
    lib = bundled_library()
    assert len(lib) == len(BUNDLED_SKILLS)
    assert "点「发布」" in BUNDLED_SKILLS["multi-publish"][1] or "发布" in BUNDLED_SKILLS["multi-publish"][1]


def test_bootstrap_workspace(tmp_path):
    root = tmp_path / "vo"
    r = bootstrap_workspace(root)
    assert r["ok"] and r["ready"]
    assert is_workspace_ready(root)
    assert (root / "01-script").is_dir()
    assert (root / "05-publish" / "draft.json").is_file()
    r2 = bootstrap_workspace(root)
    assert r2["created"] == []


def test_publish_draft_does_not_claim_auto_post(tmp_path):
    root = tmp_path / "vo"
    bootstrap_workspace(root)
    r = save_publish_draft(root, {"title": "测试片", "tags": "a b"})
    assert r["ok"]
    assert r["draft"]["title"] == "测试片"
    assert r["draft"]["confirm_publish"] is True
    st = workspace_status(root)
    assert st["draft"]["title"] == "测试片"


def test_install_and_user_override(tmp_path):
    skills = tmp_path / "skills"
    written = install_bundled_skills(skills)
    assert "remotion-video" in written
    assert (skills / "remotion-video" / "SKILL.md").is_file()
    custom = skills / "remotion-video" / "SKILL.md"
    custom.write_text(
        "---\nname: remotion-video\ndescription: user override\n---\n# custom\n",
        encoding="utf-8",
    )
    lib = load_all_skills(skills)
    assert lib.get("remotion-video").description == "user override"


def test_videoops_config_roundtrip(tmp_path):
    cfg_path = tmp_path / "videoops.json"
    cfg = VideoOpsConfig(path=str(tmp_path / "ws"), enabled=True)
    cfg.save(cfg_path)
    loaded = VideoOpsConfig.load(cfg_path)
    assert loaded.path.endswith("ws")


def test_ui_has_videoops_page():
    assert 'data-page="videoops"' in HTML
    assert 'id="page-videoops"' in HTML
    assert "pywebview.api.bootstrap_video_ops" in HTML
    assert "一键布置" in HTML
    assert "人工确认发布" in HTML
    assert "connectVideoGradio" in HTML
    assert "video_generate" in HTML
    assert "Gradio / WAN" in HTML


def test_normalize_resolution_and_sse():
    from codeagent.videoops.gradio import (
        extract_file,
        normalize_resolution,
        parse_sse_complete,
    )

    assert normalize_resolution("720p") == "720p (1280x720)"
    assert normalize_resolution("1080") == "1080p (1920x1088)"
    payload = parse_sse_complete(
        "event: complete\n"
        'data: [{"path": "/tmp/x.mp4", "url": "/file/x.mp4", "orig_name": "x.mp4"}]\n\n'
    )
    fileinfo = extract_file(payload)
    assert fileinfo["orig_name"] == "x.mp4"


def test_generate_wan_video_mocked(tmp_path, monkeypatch):
    import asyncio

    import httpx

    from codeagent.videoops import gradio as g
    from codeagent.videoops.gradio import generate_wan_video

    dest = tmp_path / "out.mp4"

    def _no_client(*_a, **_k):
        raise ImportError("gradio_client")

    monkeypatch.setattr(g, "_predict_with_client", _no_client)

    class _Resp:
        def __init__(self, status=200, payload=None, content=b""):
            self.status_code = status
            self._payload = payload or {}
            self.content = content

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError("err", request=None, response=None)

    class _Stream:
        def __init__(self, lines):
            self.status_code = 200
            self._lines = lines

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            for line in self._lines:
                yield line

    class _Client:
        def __init__(self, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            assert "generate_video" in url
            return _Resp(200, {"event_id": "evt1"})

        def stream(self, method, url, **kw):
            return _Stream([
                "event: complete",
                'data: [{"path": "/tmp/x.mp4", "url": "http://wan.test/x.mp4", "orig_name": "x.mp4"}]',
                "",
            ])

        async def get(self, url):
            assert url.endswith("x.mp4")
            return _Resp(200, content=b"mp4bytes")

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    r = asyncio.run(generate_wan_video(
        "http://192.168.3.23:7860", "一只猫在阳光下走路", dest=dest
    ))
    assert r["ok"] and dest.read_bytes() == b"mp4bytes"
    assert r["via"] == "http"


def test_generate_uses_official_gradio_client(tmp_path, monkeypatch):
    import asyncio

    from codeagent.videoops import gradio as g

    src = tmp_path / "clip.mp4"
    src.write_bytes(b"from-client")
    dest = tmp_path / "out.mp4"
    seen: dict[str, object] = {}

    def fake_predict(base, prompt, resolution, num_frames, num_inference_steps):
        seen["base"] = base
        seen["prompt"] = prompt
        seen["resolution"] = resolution
        seen["num_frames"] = num_frames
        seen["num_inference_steps"] = num_inference_steps
        return str(src)

    monkeypatch.setattr(g, "_predict_with_client", fake_predict)
    r = asyncio.run(g.generate_wan_video(
        "http://192.168.3.23:7860", "Hello!!", dest=dest
    ))
    assert r["ok"] and r["via"] == "gradio_client"
    assert dest.read_bytes() == b"from-client"
    assert seen["resolution"] == "720p (1280x720)"
    assert seen["prompt"] == "Hello!!"

