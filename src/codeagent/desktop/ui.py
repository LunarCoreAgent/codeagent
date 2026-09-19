"""Desktop UI: single-page HTML/CSS/JS loaded into the webview window.

Design language follows LunarCore Claw (LCA): shadcn-style zinc dark theme,
grouped left sidebar, white primary accent, 10px radius, lucide-style icons.
"""

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>CodeCoreAgent</title>
<style>
:root {
  /* shadcn/ui dark (zinc) — 默认主题 */
  --bg: #09090b; --sidebar: #101013; --card: #101013; --elev: #18181c;
  --hover: #1d1d22; --border: #27272a; --border-hi: #3f3f46;
  --text: #fafafa; --muted: #a1a1aa; --faint: #52525b;
  --primary: #fafafa; --primary-fg: #18181b;
  --blue: #3b82f6; --ok: #4ade80; --warn: #facc15; --bad: #f87171;
  --code-bg: #060608; --code-inline: rgba(250,250,250,.09);
  --code-inline-user: rgba(0,0,0,.12); --active-bg: rgba(250,250,250,.09);
  --scroll: #27272a;
  --pill-green: #34d399; --pill-red: #f87171; --pill-amber: #fbbf24;
  --pill-blue: #38bdf8; --pill-purple: #a78bfa;
  --radius: 10px;
}
body.light {
  /* shadcn/ui light (zinc) — 同名变量整体翻转 */
  --bg: #ffffff; --sidebar: #fafafa; --card: #ffffff; --elev: #f4f4f5;
  --hover: #ececef; --border: #e4e4e7; --border-hi: #d4d4d8;
  --text: #09090b; --muted: #71717a; --faint: #a1a1aa;
  --primary: #18181b; --primary-fg: #fafafa;
  --blue: #2563eb; --ok: #16a34a; --warn: #ca8a04; --bad: #dc2626;
  --code-bg: #f4f4f5; --code-inline: rgba(0,0,0,.07);
  --code-inline-user: rgba(255,255,255,.22); --active-bg: rgba(24,24,27,.08);
  --scroll: #d4d4d8;
  --pill-green: #059669; --pill-red: #dc2626; --pill-amber: #b45309;
  --pill-blue: #0284c7; --pill-purple: #7c3aed;
}
* { box-sizing: border-box; margin: 0; }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: var(--scroll); border-radius: 4px; }
::-webkit-scrollbar-track { background: transparent; }
body {
  font-family: -apple-system, "PingFang SC", "Helvetica Neue", "Microsoft YaHei", sans-serif;
  background: var(--bg); color: var(--text); height: 100vh; display: flex;
  overflow: hidden; font-size: 14px; -webkit-font-smoothing: antialiased;
}

/* ---------- sidebar (LCA style: grouped, wide) ---------- */
#sidebar {
  width: 216px; background: var(--sidebar); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; flex-shrink: 0; padding: 14px 10px;
  min-height: 0; overflow-y: auto;
}
#sidebar .brand {
  display: flex; flex-direction: column; align-items: flex-start; gap: 6px;
  padding: 4px 8px 14px;
  border-bottom: 1px solid var(--border); margin-bottom: 12px;
}
/* 品牌标：CCA 横版字标。按宽度缩放，保持字标比例。 */
#sidebar .brand .brandlogo img {
  width: 148px; height: auto; max-width: 100%; object-fit: contain; display: block;
}
#sidebar .brand .brandlogo .logo-dark { display: none; }
body:not(.light) #sidebar .brand .brandlogo .logo-light { display: none; }
body:not(.light) #sidebar .brand .brandlogo .logo-dark { display: block; }
#sidebar .brand .ver { font-size: 10.5px; color: var(--faint); padding-left: 2px; }
.nav-group { margin-bottom: 14px; }
.navbtn.proj { font-size: 12.5px; }
.navbtn.proj .p-name { flex: 1; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; text-align: left; }
.proj-cat { font-size: 10.5px; color: var(--faint); padding: 8px 10px 3px;
  letter-spacing: .4px; }
.navbtn.proj .p-del { opacity: 0; color: var(--faint); font-size: 14px;
  padding: 0 2px; flex-shrink: 0; }
.navbtn.proj:hover .p-del { opacity: 1; }
.navbtn.proj .p-del:hover { color: var(--bad); }
.nav-group .g-label {
  font-size: 11px; color: var(--faint); padding: 0 10px 6px;
  letter-spacing: .5px;
}
.navbtn {
  width: 100%; display: flex; align-items: center; gap: 10px;
  padding: 7px 10px; border: none; background: transparent; color: var(--muted);
  border-radius: 8px; cursor: pointer; font-size: 13px; text-align: left;
  transition: background .12s ease, color .12s ease;
}
.navbtn svg { width: 16px; height: 16px; stroke-width: 1.8; flex-shrink: 0; }
.navbtn:hover { background: var(--hover); color: var(--text); }
.navbtn.active { background: var(--active-bg); color: var(--primary); font-weight: 550; }
#sidebar .spacer { flex: 1; }
#sidebar .foot { border-top: 1px solid var(--border); padding-top: 10px; }
#sidebar .status { display: flex; align-items: center; gap: 7px;
  padding: 6px 10px; font-size: 11.5px; color: var(--faint); }
#sidebar .status .dot { width: 7px; height: 7px; border-radius: 50%;
  background: var(--ok); }

/* ---------- pages ---------- */
#main { flex: 1; display: flex; flex-direction: column; min-width: 0;
        min-height: 0; overflow: hidden; }
.page { flex: 1; display: none; flex-direction: column; min-height: 0; }
.page.active { display: flex; }
.page-head {
  padding: 16px 26px 13px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 12px; flex-shrink: 0;
}
.page-head h1 { font-size: 15.5px; font-weight: 650; flex-shrink: 0; }
.page-head .sub { color: var(--muted); font-size: 12px; min-width: 0;
                  max-width: 240px; overflow: hidden; text-overflow: ellipsis;
                  white-space: nowrap; }
.page-head .spacer { flex: 1; min-width: 8px; }
.page-head select, .page-head .btn { flex-shrink: 0; }
.page-body { flex: 1; overflow-y: auto; overflow-x: hidden; padding: 20px 26px;
             min-height: 0; -webkit-overflow-scrolling: touch; }

/* ---------- primitives (shadcn) ---------- */
.card { background: var(--card); border: 1px solid var(--border);
        border-radius: var(--radius); padding: 16px 18px; }
.card h3 { font-size: 12px; color: var(--muted); font-weight: 600;
           margin-bottom: 12px; letter-spacing: .4px; }
.btn { background: var(--elev); border: 1px solid var(--border); color: var(--text);
       border-radius: 8px; padding: 7px 14px; font-size: 12.5px; cursor: pointer;
       transition: all .12s; }
.btn:hover { border-color: var(--border-hi); background: var(--hover); }
.btn.primary { background: var(--primary); color: var(--primary-fg);
               border: none; font-weight: 600; }
.btn.primary:hover { opacity: .88; }
.btn.primary:disabled { opacity: .4; cursor: default; }
.btn.danger { color: var(--bad); }
input, select, textarea {
  background: var(--bg); color: var(--text); border: 1px solid var(--border);
  border-radius: 8px; padding: 8px 11px; font-size: 13px; font-family: inherit;
  transition: border-color .12s; }
input:focus, select:focus, textarea:focus { outline: none; border-color: var(--faint); }
.badge { font-size: 10.5px; padding: 2px 9px; border-radius: 999px;
         border: 1px solid var(--border); color: var(--muted); }
.badge.on { border-color: rgba(74,222,128,.4); color: var(--ok); }
.empty { color: var(--faint); font-size: 12.5px; text-align: center; padding: 26px 0; }

/* ---------- dashboard ---------- */
.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr);
             gap: 14px; max-width: 1000px; margin: 0 auto 16px; width: 100%; }
.stat .s-label { font-size: 12px; color: var(--muted); }
.stat .s-value { font-size: 24px; font-weight: 700; margin-top: 6px;
                 letter-spacing: -.5px; }
.stat .s-sub { font-size: 11px; color: var(--faint); margin-top: 3px; }
.dash-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 14px;
             max-width: 1000px; margin: 0 auto; width: 100%; }
.quick { display: flex; align-items: center; gap: 12px; width: 100%;
  padding: 11px 13px; background: var(--elev); border: 1px solid var(--border);
  border-radius: 9px; color: var(--text); font-size: 13px; cursor: pointer;
  margin-bottom: 8px; transition: all .12s; text-align: left; }
.quick:hover { border-color: var(--border-hi); background: var(--hover); }
.quick svg { width: 15px; height: 15px; color: var(--muted); }
.quick .q-sub { margin-left: auto; font-size: 11px; color: var(--faint); }

/* ---------- internal browser ---------- */
.browser-page { display: flex; flex-direction: column; gap: 12px;
                max-width: 1100px; margin: 0 auto; width: 100%;
                flex: 1; min-height: 0; }
.browser-bar { display: flex; gap: 8px; align-items: center; }
.browser-bar input { flex: 1; font-size: 13px; }
.browser-meta { font-size: 12px; color: var(--muted); line-height: 1.5; }
.browser-split { display: flex; gap: 14px; flex: 1; min-height: 220px; }
.browser-split .card { overflow: auto; min-height: 0; }
.browser-pre { white-space: pre-wrap; font-size: 12px; color: var(--muted);
               line-height: 1.6; font-family: inherit; }
.browser-node { font-size: 12px; padding: 5px 0; border-bottom: 1px solid var(--border);
                display: flex; gap: 8px; align-items: baseline; }
.browser-node code { color: var(--blue); font-size: 11px; }

/* ---------- chat ---------- */
#page-chat { padding: 0; }
#page-chat .msg, #page-chat .chip, #page-chat .fb-row {
  -webkit-user-select: text; user-select: text; cursor: text; }
#page-chat textarea, #page-chat input {
  -webkit-user-select: text; user-select: text; }
#page-chat .msg-actions, #page-chat .ma-btn, #page-chat .fb-btn {
  -webkit-user-select: none; user-select: none; cursor: pointer; }
#chat { flex: 1; overflow-y: auto; padding: 22px 0; min-height: 0; }
.chat-col { max-width: 1040px; margin: 0 auto; display: flex;
            flex-direction: column; gap: 12px; padding: 0 28px; width: 100%;
            box-sizing: border-box; }
.msg { max-width: 88%; padding: 11px 15px; border-radius: 14px;
       line-height: 1.7; white-space: pre-wrap; word-break: break-word;
       animation: pop .16s ease; font-size: 13.5px; }
@keyframes pop { from { opacity: 0; transform: translateY(5px); } }
.msg.user { align-self: flex-end; background: var(--primary);
            color: var(--primary-fg); border-bottom-right-radius: 4px; }
.msg.bot { align-self: flex-start; background: var(--card);
           border: 1px solid var(--border); border-bottom-left-radius: 4px; }
.msg pre { background: var(--code-bg); border: 1px solid var(--border);
           border-radius: 8px; padding: 11px; overflow-x: auto;
           margin: 9px 0 4px; font-size: 12px; }
.msg code { font-family: "SF Mono", Menlo, Consolas, monospace;
            background: var(--code-inline); border-radius: 4px;
            padding: 1px 5px; font-size: .92em; }
.msg.user code { background: var(--code-inline-user); }
.msg pre code { background: none; padding: 0; }
.msg strong { font-weight: 650; }
.chip { align-self: flex-start; font-size: 11.5px; color: var(--muted);
        border: 1px dashed var(--border-hi); border-radius: 999px;
        padding: 3px 12px; animation: pop .16s ease; }
.chip.error { color: var(--bad); border-color: rgba(248,113,113,.5); }
.chip.status { color: var(--blue); border-color: rgba(59,130,246,.5); }
.think-block { align-self: flex-start; max-width: min(720px, 92%);
  width: 100%; margin: 2px 0 8px; padding: 8px 12px;
  border: 1px solid var(--border); border-radius: 12px;
  background: var(--elev); color: var(--muted); font-size: 12.5px; }
.think-block > summary { cursor: pointer; list-style: none;
  color: var(--muted); font-size: 12px; user-select: none; }
.think-block > summary::-webkit-details-marker { display: none; }
.think-block > summary::before { content: "▸ "; color: var(--faint); }
.think-block[open] > summary::before { content: "▾ "; }
.think-block .think-body { margin-top: 8px; color: var(--muted); }
.think-block .think-reason { white-space: pre-wrap; line-height: 1.55; }
.think-block .think-tools { list-style: none; margin: 0; padding: 0; }
.think-block .think-reason + .think-tools {
  margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--border);
}
.think-block .think-tools li {
  font-size: 12px; line-height: 1.5; color: var(--faint);
  font-family: ui-monospace, Menlo, monospace; padding: 1px 0;
}
#composer { padding: 13px 22px 16px; border-top: 1px solid var(--border);
            background: var(--sidebar); flex-shrink: 0; }
.composer-inner { max-width: 1040px; margin: 0 auto; display: flex;
                  flex-direction: column; gap: 8px; width: 100%;
                  box-sizing: border-box; }
#input { width: 100%; resize: none; border-radius: 12px; padding: 11px 13px;
         line-height: 1.55; }
.composer-tools { display: flex; gap: 8px; align-items: center; }
.composer-tools .spacer { flex: 1; }
.composer-video { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.composer-video .toolsel { flex: 1; min-width: 140px; max-width: none; }
.composer-video.is-off { display: none; }
#dualWrap { display: flex; flex: 1; min-height: 0; }
.dual-col { display: flex; flex-direction: column; flex: 1; min-width: 0; min-height: 0; }
.page-chat-dual #colA { border-right: 1px solid var(--border); }
.dual-head { padding: 9px 22px 4px; display: flex; align-items: center; gap: 10px;
             flex-shrink: 0; }
.dual-label { color: var(--blue); font-size: 12px; font-weight: 600; flex-shrink: 0; }
.dual-head .spacer { flex: 1; min-width: 6px; }
.dual-head select, .dual-head .btn { flex-shrink: 0; }
#modelPicker { min-width: 180px; max-width: 260px; }
.toolbtn { background: var(--elev); border: 1px solid var(--border);
           color: var(--muted); border-radius: 9px; height: 34px;
           padding: 0 12px; cursor: pointer; font-size: 14px; }
.toolbtn:hover { border-color: var(--border-hi); color: var(--text); }
.toolbtn.mic.on { color: var(--bad); border-color: var(--bad);
                  animation: pulse 1.1s infinite; }
.toolsel { width: auto; max-width: 220px; background: var(--elev);
           padding: 7px 9px; font-size: 12px; border-radius: 9px; }
#attRow { display: none; flex-wrap: wrap; gap: 6px; }
.att-chip { display: inline-flex; align-items: center; gap: 5px;
            background: var(--elev); border: 1px solid var(--border);
            border-radius: 999px; padding: 3px 10px; font-size: 11.5px;
            color: var(--muted); animation: pop .15s ease; }
.att-chip b { color: var(--faint); font-weight: 400; }
.att-chip i { cursor: pointer; font-style: normal; color: var(--faint);
              padding: 0 2px; font-size: 13px; }
.att-chip i:hover { color: var(--bad); }
.sendbtn { background: var(--primary); color: var(--primary-fg); border: none;
           height: 34px; border-radius: 9px; padding: 0 20px; font-size: 12.5px;
           font-weight: 600; cursor: pointer; transition: opacity .12s; }
.sendbtn:hover { opacity: .88; }
.sendbtn:disabled { opacity: .35; cursor: default; }
.stopbtn { background: var(--elev); color: var(--bad); border: 1px solid var(--bad);
           height: 34px; border-radius: 9px; padding: 0 20px; font-size: 12.5px;
           font-weight: 600; cursor: pointer; }
.stopbtn:hover { opacity: .88; }
.stopbtn:disabled { opacity: .35; cursor: default; }

/* 消息操作条：复制 / 分享始终可见，气泡正文可拖选 */
.msg-wrap { display: flex; flex-direction: column; max-width: 88%; }
.msg-wrap.user { align-self: flex-end; align-items: flex-end; }
.msg-wrap.bot { align-self: flex-start; align-items: flex-start; }
.msg-wrap .msg { max-width: 100%; }
.chip-wrap { display: flex; align-items: center; gap: 6px; align-self: flex-start; }
.chip-wrap .chip { align-self: auto; }
.msg-actions { display: flex; gap: 4px; margin-top: 3px; opacity: 1; }
.msg-disclaimer { font-size: 11px; color: var(--faint); margin-top: 2px;
                  padding: 0 2px; line-height: 1.4; }
.ma-btn { border: none; background: transparent; color: var(--faint);
          font-size: 11px; cursor: pointer; padding: 2px 7px;
          border-radius: 6px; }
.ma-btn:hover { background: var(--hover); color: var(--text); }

/* ---------- leader ---------- */
.lead-grid { display: grid; grid-template-columns: 1fr 290px; gap: 16px;
             max-width: 1040px; margin: 0 auto; width: 100%; }
.task { display: flex; align-items: center; gap: 11px; padding: 10px 13px;
        background: var(--bg); border: 1px solid var(--border);
        border-radius: 9px; margin-bottom: 7px; animation: pop .18s ease; }
.task .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.task .t-title { flex: 1; font-size: 13px; min-width: 0;
                 overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.task .t-worker { font-size: 11px; color: var(--faint); }
.st-pending .dot { background: var(--faint); }
.st-running .dot { background: var(--blue); animation: pulse 1.1s infinite; }
.st-done .dot { background: var(--ok); }
.st-failed .dot { background: var(--bad); }
@keyframes pulse { 50% { opacity: .3; } }
.st-running { border-color: rgba(59,130,246,.45); }
.reply-box { background: var(--bg); border-left: 2px solid var(--primary);
             border-radius: 8px; padding: 12px 15px; margin-top: 13px;
             line-height: 1.7; white-space: pre-wrap; font-size: 13px; }
.run-item { padding: 9px 11px; border-radius: 8px; font-size: 12px;
            color: var(--muted); border: 1px solid var(--border);
            margin-bottom: 7px; }
.run-item b { color: var(--text); font-weight: 600; }

/* ---------- memory / skills / logs ---------- */
.toolbar { display: flex; gap: 9px; margin: 0 auto 14px;
           max-width: 840px; width: 100%; }
.toolbar input { flex: 1; }
.list { max-width: 840px; margin: 0 auto; width: 100%; }
.mem { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 9px; }
.mem .m-body { flex: 1; line-height: 1.65; font-size: 13px; }
.mem .m-time { font-size: 10.5px; color: var(--faint); margin-top: 4px; }
.mem .m-del { flex-shrink: 0; background: none; border: none; color: var(--faint);
              cursor: pointer; font-size: 15px; padding: 2px 6px; }
.mem .m-del:hover { color: var(--bad); }
.skill-pack { max-width: 1040px; margin: 0 auto 18px; width: 100%; }
.skill-pack h2 { font-size: 12px; color: var(--muted); font-weight: 600;
  letter-spacing: .4px; margin: 0 0 10px; }
.skill-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
              gap: 13px; max-width: 1040px; margin: 0 auto; width: 100%; }
.skill-card b { display: block; font-size: 13px; margin-bottom: 5px; }
.skill-card p { color: var(--muted); font-size: 12px; line-height: 1.6; }
#logbox { max-width: 940px; margin: 0 auto; width: 100%; background: var(--code-bg);
  border: 1px solid var(--border); border-radius: var(--radius);
  padding: 15px 17px; font-family: "SF Mono", Menlo, monospace;
  font-size: 11px; line-height: 1.75; white-space: pre-wrap;
  color: var(--muted); max-height: 100%; overflow-y: auto; }

/* ---------- settings ---------- */
.settings-wrap { max-width: 620px; margin: 0 auto; width: 100%;
                 display: flex; flex-direction: column; gap: 15px; }
.sect label { display: block; font-size: 11.5px; color: var(--muted);
              margin: 11px 0 5px; }
.sect input, .sect select, .sect textarea { width: 100%; }
.sect textarea { resize: vertical; min-height: 60px; line-height: 1.6; }
.sect .hint { font-size: 11px; color: var(--faint); margin-top: 4px; }
.checkline { display: flex; align-items: center; gap: 9px; margin-top: 13px;
             font-size: 12.5px; }
.checkline input { width: auto; }
.harness { display: flex; justify-content: space-between; align-items: center;
           padding: 8px 11px; border: 1px solid var(--border);
           border-radius: 8px; margin-bottom: 6px; font-size: 12.5px; }
.savebar { display: flex; justify-content: flex-end; gap: 9px;
           padding: 4px 0 8px; }

/* ---------- settings submenu (LCA: 左下角设置按钮展开) ---------- */
.submenu { display: none; margin-bottom: 2px; }
.submenu.open { display: block; }
.navbtn.sub { padding-left: 34px; font-size: 12.5px; }
.navbtn .chev { margin-left: auto; transition: transform .15s; }
.navbtn .chev.up { transform: rotate(180deg); }

/* ---------- tabs (shadcn Tabs) ---------- */
.tabs { display: inline-flex; background: var(--elev); border: 1px solid var(--border);
        border-radius: 9px; padding: 3px; gap: 2px; margin-bottom: 16px; }
.tab { border: none; background: transparent; color: var(--muted);
       padding: 6px 16px; border-radius: 7px; font-size: 12.5px; cursor: pointer; }
.tab:hover { color: var(--text); }
.tab.active { background: var(--hover); color: var(--text); font-weight: 550; }
.tabpane { display: none; }
.tabpane.active { display: block; }

/* ---------- pill (LCA Pill tones) ---------- */
.pill { display: inline-flex; align-items: center; border-radius: 6px;
        padding: 2px 8px; font-size: 11px; font-weight: 550;
        background: var(--elev); color: var(--muted); }
.pill.green { background: rgba(16,185,129,.15); color: var(--pill-green);
              border: 1px solid rgba(16,185,129,.3); }
.pill.red { background: rgba(239,68,68,.15); color: var(--pill-red);
            border: 1px solid rgba(239,68,68,.3); }
.pill.amber { background: rgba(245,158,11,.15); color: var(--pill-amber);
              border: 1px solid rgba(245,158,11,.3); }
.pill.blue { background: rgba(14,165,233,.15); color: var(--pill-blue);
             border: 1px solid rgba(14,165,233,.3); }
.pill.purple { background: rgba(139,92,246,.15); color: var(--pill-purple);
               border: 1px solid rgba(139,92,246,.3); }

/* ---------- switch (shadcn Switch) ---------- */
.switch { position: relative; width: 36px; height: 20px; flex-shrink: 0;
          background: var(--elev); border: 1px solid var(--border-hi);
          border-radius: 999px; cursor: pointer; transition: background .15s; }
.switch::after { content: ''; position: absolute; top: 2px; left: 2px;
  width: 14px; height: 14px; border-radius: 50%; background: var(--muted);
  transition: all .15s; }
.switch.on { background: var(--primary); border-color: var(--primary); }
.switch.on::after { left: 18px; background: var(--primary-fg); }

/* ---------- slider (shadcn Slider) ---------- */
input[type=range] { -webkit-appearance: none; appearance: none; width: 100%;
  height: 4px; border-radius: 2px; background: var(--elev); padding: 0;
  border: none; }
input[type=range]::-webkit-slider-thumb { -webkit-appearance: none;
  width: 15px; height: 15px; border-radius: 50%; background: var(--primary);
  cursor: pointer; border: none; }

/* ---------- modal (shadcn Dialog) ---------- */
.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,.6);
  display: none; place-items: center; z-index: 60; }
.modal-mask.open { display: grid; }
#privacyDialog { z-index: 80; }
.modal { width: 420px; max-width: 92vw; background: var(--card);
  border: 1px solid var(--border-hi); border-radius: 12px; padding: 20px;
  animation: pop .16s ease; }
.modal.wide { width: 560px; max-height: 86vh; display: flex; flex-direction: column; }
.modal .privacy-scroll { overflow-y: auto; flex: 1; min-height: 0;
  padding-right: 4px; margin: 0 0 14px; }
.privacy-sec { margin-bottom: 14px; }
.privacy-sec h4 { font-size: 12.5px; font-weight: 600; margin-bottom: 5px; }
.privacy-sec p { font-size: 12px; color: var(--muted); line-height: 1.75;
  white-space: pre-wrap; }
.modal .spacer { flex: 1; }
.modal h3 { font-size: 14px; margin-bottom: 14px; }
.modal label { display: block; font-size: 11.5px; color: var(--muted);
               margin: 11px 0 5px; }
.modal input, .modal select { width: 100%; }
.member-box { border: 1px solid var(--border); border-radius: 8px;
  padding: 10px 12px; max-height: 190px; overflow-y: auto; margin-top: 6px; }
.member-box .mrow { display: flex; align-items: center; gap: 8px;
  font-size: 12.5px; padding: 4px 0; cursor: pointer; }
.member-box input { width: auto; }

/* ---------- models / router pages ---------- */
.models-wrap, .page-wrap { max-width: 860px; margin: 0 auto; width: 100%; }
.mix-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.mrow2 { display: flex; align-items: center; gap: 10px;
  border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px;
  margin-bottom: 8px; font-size: 12.5px; }
.mrow2 .grow { flex: 1; min-width: 0; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; }
.iconbtn { background: none; border: none; color: var(--faint);
  cursor: pointer; padding: 3px 5px; font-size: 13px; border-radius: 6px; }
.iconbtn:hover { color: var(--text); background: var(--hover); }
.iconbtn.danger:hover { color: var(--bad); }
.dashed { border: 1px dashed var(--border-hi); border-radius: 10px;
  padding: 26px; text-align: center; color: var(--faint); font-size: 12px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.grid-32 { display: grid; grid-template-columns: 2fr 1fr; gap: 14px; }

/* ---------- 导演台 ---------- */
.studio-wrap { max-width: 1100px; margin: 0 auto; width: 100%; }
.studio-rail { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 14px; }
.studio-rail .step { border: 1px solid var(--border); background: var(--card);
  color: var(--muted); border-radius: 8px; padding: 7px 12px; font-size: 12.5px;
  cursor: pointer; }
.studio-rail .step.on { border-color: var(--text); color: var(--text);
  background: var(--active-bg); font-weight: 550; }
.studio-rail .step .n { color: var(--faint); margin-right: 6px; font-variant-numeric: tabular-nums; }
.studio-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
.shot-list { display: flex; flex-direction: column; gap: 8px; }
.shot-card { border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px;
  background: var(--card); }
.shot-card .row { display: flex; align-items: center; gap: 8px; }
.shot-card textarea { width: 100%; min-height: 54px; margin-top: 8px; font-size: 12.5px; }
.shot-card .meta { font-size: 11px; color: var(--faint); margin-top: 6px;
  font-family: Menlo, monospace; }
.shot-card .row input, .shot-card .row select { width: auto; margin: 0; padding: 4px 8px; font-size: 12px; }
.shot-card .st-title { flex: 1; min-width: 80px; font-weight: 550; }
.shot-card .st-sec { width: 64px; }
.sandbox-result { background: var(--bg); border: 1px solid var(--border);
  border-radius: 8px; padding: 12px 14px; margin-top: 12px;
  font-size: 12.5px; line-height: 1.9; }
.wrow { margin-bottom: 18px; }
.wrow .whead { display: flex; justify-content: space-between;
  font-size: 12.5px; margin-bottom: 8px; }
.wrow .wval { color: var(--muted); }
.wrow .whint { font-size: 11px; color: var(--faint); margin-top: 5px; }
.audit-row { display: flex; gap: 10px; align-items: baseline;
  font-size: 12.5px; padding: 5px 0; }
.audit-row .a-time { font-size: 11px; color: var(--faint); width: 118px;
  flex-shrink: 0; }
.audit-row .a-actor { color: var(--pill-blue); font-size: 11px; width: 52px;
  flex-shrink: 0; }
.ver-points { list-style: none; padding: 0; }
.ver-points li { display: flex; gap: 8px; font-size: 12.5px;
  line-height: 1.7; padding: 2px 0; }
.ver-points li::before { content: '•'; color: var(--pill-green); flex-shrink: 0; }
.ver-points.hist li::before { content: '-'; color: var(--faint); }
.ver-points.hist li { color: var(--muted); font-size: 12px; }

.toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
  background: var(--primary); color: var(--primary-fg);
  padding: 9px 20px; border-radius: 999px; font-size: 12.5px; font-weight: 550;
  opacity: 0; transition: opacity .2s; pointer-events: none; z-index: 50; }
.toast.show { opacity: 1; }

/* ---------- 对话右键菜单（鼠标复制粘贴） ---------- */
.ctx-menu { position: fixed; z-index: 60; min-width: 150px;
  background: var(--panel); border: 1px solid var(--border-hi);
  border-radius: 8px; padding: 4px; box-shadow: 0 6px 22px rgba(0,0,0,.28);
  display: none; }
.ctx-menu.open { display: block; }
.ctx-menu button { display: block; width: 100%; border: none; background: transparent;
  color: var(--text); font-size: 12.5px; text-align: left;
  padding: 7px 10px; border-radius: 5px; cursor: pointer; }
.ctx-menu button:hover { background: var(--hover); }
.ctx-menu .sep { height: 1px; background: var(--border); margin: 3px 2px; }

/* ---------- LCA 卷三：四字对齐 / 底部状态区 ---------- */
.navlabel { display: inline-block; }
.navlabel.justify { width: 4em; text-align: justify; text-align-last: justify; }
#navStatus { border-top: 1px solid var(--border); padding: 10px 10px 2px;
  font-size: 11px; display: flex; flex-direction: column; gap: 5px; }
#navStatus .ns-row { display: flex; justify-content: space-between; }
#navStatus .ns-row .k { color: var(--faint); }
#navStatus .ns-row .v-green { color: var(--pill-green); }
#navStatus .ns-row .v-blue { color: var(--pill-blue); }
#navStatus .ns-row .v-purple { color: var(--pill-purple); }

/* ---------- 对话反馈（赞/踩） ---------- */
.fb-row { display: flex; gap: 6px; align-self: flex-start;
  margin-top: -6px; padding-left: 4px; animation: pop .16s ease; }
.fb-btn { background: none; border: 1px solid var(--border); color: var(--faint);
  border-radius: 6px; padding: 2px 8px; font-size: 11px; cursor: pointer;
  transition: all .12s; }
.fb-btn:hover { color: var(--text); border-color: var(--border-hi); }
.fb-btn.voted-up { color: var(--pill-green); border-color: rgba(16,185,129,.4); }
.fb-btn.voted-down { color: var(--pill-red); border-color: rgba(239,68,68,.4); }

/* ---------- 自动化 / 定时任务 / 学习 / 进化 ---------- */
.step-chip { display: inline-flex; align-items: center; gap: 8px; }
.step-card { border: 1px solid var(--border); border-radius: 8px;
  background: var(--bg); padding: 8px 12px; }
.step-card .s-name { font-size: 12.5px; }
.step-card .s-tool { font-size: 10px; color: var(--faint); margin-top: 2px; }
.step-arrow { color: var(--faint); font-size: 13px; }
.loop-mark { font-size: 11px; color: var(--pill-purple); display: inline-flex;
  align-items: center; gap: 4px; }
.cron-row { display: flex; align-items: center; gap: 14px;
  border: 1px solid var(--border); border-radius: 10px;
  background: var(--card); padding: 13px 16px; margin-bottom: 9px; }
.cron-row.sys { border-color: rgba(139,92,246,.3);
  background: rgba(139,92,246,.05); }
.cron-expr { font-family: "SF Mono", Menlo, monospace; font-size: 11px;
  color: var(--pill-amber); }
.cron-expr.sys { color: var(--pill-purple); }
.preset-chip { font-size: 11px; border: 1px solid var(--border);
  border-radius: 6px; padding: 3px 9px; background: none; color: var(--muted);
  cursor: pointer; }
.preset-chip:hover { background: var(--hover); color: var(--text); }
.phase-tag { border: 1px solid var(--border); border-radius: 8px;
  padding: 7px 12px; font-size: 12.5px; display: inline-flex;
  align-items: center; gap: 7px; color: var(--muted); }
.phase-tag.done { border-color: rgba(16,185,129,.4); color: var(--pill-green); }
.phase-tag.doing { border-color: rgba(245,158,11,.4); color: var(--pill-amber); }
.patch-card { border: 1px solid var(--border); border-radius: 8px;
  padding: 11px 13px; margin-bottom: 10px; }
.patch-card.active { border-color: rgba(16,185,129,.3);
  background: rgba(16,185,129,.05); }
.patch-card.pending { border-color: rgba(245,158,11,.3);
  background: rgba(245,158,11,.05); }
.patch-card.muted { opacity: .65; }
.evo-run { border: 1px solid var(--border); border-radius: 8px;
  padding: 11px 13px; margin-bottom: 12px; }
.evo-phase-line { display: flex; gap: 8px; font-size: 11px; padding: 2px 0; }
.evo-phase-line .p-name { color: var(--pill-purple); width: 44px; flex-shrink: 0;
  font-family: "SF Mono", Menlo, monospace; }
.evo-note .p-name { color: var(--pill-blue); }
.chart-box { height: 180px; display: flex; align-items: flex-end; gap: 6px;
  padding: 8px 4px 2px; }
.pipe-row { display: flex; align-items: center; justify-content: space-between;
  border: 1px solid var(--border); border-radius: 8px;
  padding: 10px 12px; margin-bottom: 8px; font-size: 12.5px; }
</style>
</head>
<body>
<script>
// 开发预览时尽早应用缓存主题（正式包里 body class 由服务端注入，此脚本仅作兜底）
(function(){
  try{
    const t=localStorage.getItem('codeagent-theme')||'dark';
    if(t==='light'||(t==='auto'&&matchMedia('(prefers-color-scheme: light)').matches))
      document.body.classList.add('light');
  }catch(e){}
})();
</script>

<nav id="sidebar">
  <div class="brand">
    <div class="brandlogo" title="CodeCoreAgent">
      <img class="logo-light" alt="CodeCoreAgent" src="__BRAND_LOGO_LIGHT__">
      <img class="logo-dark" alt="CodeCoreAgent" src="__BRAND_LOGO_DARK__">
    </div>
    <div class="ver" id="brandVer"></div>
  </div>

  <div class="nav-group">
    <div class="g-label">概览</div>
    <button class="navbtn active" data-page="dashboard">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>
      总览</button>
    <button class="navbtn" data-page="chat">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M21 12a8 8 0 0 1-8 8H5l-2 2V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8z"/></svg>
      对话</button>
    <button class="navbtn" data-page="browser">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>
      浏览器</button>
    <button class="navbtn" data-page="studio">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M8 5v14M3 12h18"/><path d="M16 9l4 3-4 3"/></svg>
      导演台</button>
    <button class="navbtn" data-page="lead">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 2l3 6 6 .9-4.5 4.3 1 6.3-5.5-3-5.5 3 1-6.3L3 8.9 9 8z"/></svg>
      指挥中心</button>
  </div>

  <div class="nav-group">
    <div class="g-label">项目</div>
    <div id="projectList"></div>
    <button class="navbtn" id="newProjBtn" onclick="openProjDialog()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M12 11v6M9 14h6"/></svg>
      新建项目</button>
    <button class="navbtn" id="importProjBtn" onclick="importProject()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 3v12m0 0l-4-4m4 4l4-4"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>
      导入项目</button>
  </div>

  <div class="nav-group">
    <div class="g-label">能力</div>
    <button class="navbtn" data-page="memory">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>
      长期记忆</button>
    <button class="navbtn" data-page="knowledge">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/><path d="M8 7h8M8 11h6"/></svg>
      知识库</button>
    <button class="navbtn" data-page="videoops">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="6" width="18" height="12" rx="2"/><path d="M10 10l5 2-5 2z"/></svg>
      视频运营</button>
    <button class="navbtn" data-page="skills">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M14 7l-8.5 8.5a2.1 2.1 0 1 0 3 3L17 10"/><path d="M15 3l6 6-3 3-6-6z"/></svg>
      技能库</button>
  </div>

  <div class="nav-group">
    <div class="g-label">系统</div>
    <button class="navbtn" data-page="automation">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h13M21 18h-1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="19" cy="18" r="2"/></svg>
      自动化</button>
    <button class="navbtn" data-page="cron">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>
      定时任务</button>
    <button class="navbtn" data-page="learning">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M22 10L12 5 2 10l10 5 10-5z"/><path d="M6 12v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5"/></svg>
      自我学习</button>
    <button class="navbtn" data-page="evolution">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M4 4v6h6M20 20v-6h-6"/><path d="M20 9A8 8 0 0 0 5.6 5.6L4 7M4 15a8 8 0 0 0 14.4 3.4L20 17"/></svg>
      进化日志</button>
  </div>

  <div class="spacer"></div>

  <div class="foot">
    <div id="navStatus">
      <div class="ns-row"><span class="k">本地模型</span><span class="v-green" id="nsLocal">—</span></div>
      <div class="ns-row"><span class="k">API 模型</span><span class="v-blue" id="nsApi">—</span></div>
      <div class="ns-row"><span class="k">聚合池</span><span class="v-purple" id="nsMix">—</span></div>
    </div>
    <div class="status"><span class="dot"></span><span id="footProvider">—</span></div>
    <button class="navbtn" data-page="logs">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M4 4h16v16H4z" rx="2"/><path d="M8 9h8M8 13h8M8 17h5"/></svg>
      日志</button>
    <div class="submenu" id="settingsMenu">
      <button class="navbtn sub" data-page="models">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 2l8 4.5v9L12 20l-8-4.5v-9z"/><path d="M12 11L4 6.5M12 11l8-4.5M12 11v9"/></svg>
        模型管理</button>
      <button class="navbtn sub" data-page="router">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M8.5 6H15a3 3 0 0 1 3 3v2M15.5 18H9a3 3 0 0 1-3-3v-2"/></svg>
        自由路由</button>
      <button class="navbtn sub" data-page="permissions">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6z"/><path d="M9 12l2 2 4-4"/></svg>
        权限控制</button>
      <button class="navbtn sub" data-page="versions">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 3v12m0 0l-4-4m4 4l4-4"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>
        版本说明</button>
      <button class="navbtn sub" data-page="privacy">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6z"/><circle cx="12" cy="11" r="2"/><path d="M12 13v3"/></svg>
        隐私条款</button>
      <button class="navbtn sub" data-page="settings">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="3.2"/><path d="M19 12a7 7 0 1 0 .1 0z"/></svg>
        偏好设置</button>
    </div>
    <button class="navbtn" id="settingsToggle">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="3.2"/><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.3.9a7 7 0 0 0-2-1.2L14.2 3h-4l-.4 2.6a7 7 0 0 0-2 1.2l-2.3-.9-2 3.4 2 1.5a7 7 0 0 0 0 2.4l-2 1.5 2 3.4 2.3-.9a7 7 0 0 0 2 1.2l.4 2.6h4l.4-2.6a7 7 0 0 0 2-1.2l2.3.9 2-3.4-2-1.5c.06-.4.1-.8.1-1.2z"/></svg>
      设置
      <svg class="chev" id="settingsChev" viewBox="0 0 24 24" fill="none" stroke="currentColor" style="width:13px;height:13px"><path d="M6 15l6-6 6 6"/></svg>
    </button>
  </div>
</nav>

<div id="main">

<!-- ============ 总览 ============ -->
<section class="page active" id="page-dashboard">
  <div class="page-head"><h1>总览</h1>
    <span class="sub">本机 Agent 平台状态一览</span></div>
  <div class="page-body">
    <div class="stat-grid">
      <div class="card stat"><div class="s-label">版本</div>
        <div class="s-value" id="stVersion">—</div><div class="s-sub" id="stDate"></div></div>
      <div class="card stat"><div class="s-label">当前模型</div>
        <div class="s-value" id="stProvider" style="font-size:17px;padding-top:4px">—</div>
        <div class="s-sub" id="stModel"></div></div>
      <div class="card stat"><div class="s-label">技能 / 记忆</div>
        <div class="s-value" id="stSkills">—</div><div class="s-sub">技能包 / 长期记忆条数</div></div>
      <div class="card stat"><div class="s-label">外部平台</div>
        <div class="s-value" id="stHarness">—</div><div class="s-sub">可用的本机 agent 平台</div></div>
    </div>
    <div class="dash-cols">
      <div class="card"><h3>快速开始</h3>
        <button class="quick" onclick="go('chat')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M21 12a8 8 0 0 1-8 8H5l-2 2V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8z"/></svg>
          开始对话<span class="q-sub">单 agent · 工具全开</span></button>
        <button class="quick" onclick="go('browser')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>
          内置浏览器<span class="q-sub">AI 开页 · 点击 · 填表</span></button>
        <button class="quick" onclick="go('studio')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M8 5v14M3 12h18"/><path d="M16 9l4 3-4 3"/></svg>
          导演台<span class="q-sub">分镜 · Comfy 生成 · 合成</span></button>
        <button class="quick" onclick="go('lead')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 2l3 6 6 .9-4.5 4.3 1 6.3-5.5-3-5.5 3 1-6.3L3 8.9 9 8z"/></svg>
          指挥中心派遣<span class="q-sub">多模型并行</span></button>
        <button class="quick" onclick="go('models')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 2l8 4.5v9L12 20l-8-4.5v-9z"/><path d="M12 11L4 6.5M12 11l8-4.5M12 11v9"/></svg>
          模型管理<span class="q-sub">本地 · API · 聚合池</span></button>
      </div>
      <div class="card"><h3>最近指挥运行</h3>
        <div id="dashRuns"><div class="empty">暂无记录</div></div>
      </div>
    </div>
  </div>
</section>

<!-- ============ 项目记录 ============ -->
<section class="page" id="page-project">
  <div class="page-head"><h1 id="projTitle">项目记录</h1>
    <span class="sub" id="projSub">每个项目的对话、思考、文件与说明都可单独导出/导入</span>
    <span class="spacer"></span>
    <button class="btn" onclick="importProject()">📥 导入项目</button>
    <button class="btn" onclick="exportProject()">📤 导出项目</button>
    <button class="btn" onclick="openProjFolder()">📂 打开文件夹</button>
    <button class="btn" onclick="go('chat')">进入对话</button>
  </div>
  <div class="page-body">
    <div class="stat-grid" id="projStats"></div>
    <div class="dash-cols" style="margin-top:16px">
      <div class="card"><h3>对话记录</h3>
        <div id="projConvs"><div class="empty">暂无对话</div></div></div>
      <div class="card"><h3>文件与内容</h3>
        <div id="projFiles"><div class="empty">文件夹为空</div></div></div>
    </div>
  </div>
</section>

<!-- ============ 对话 ============ -->
<section class="page" id="page-chat">
  <div class="page-head"><h1>对话</h1>
    <span class="sub">工具全开的单 agent · 支持附件、思考强度与文生视频</span>
    <span class="spacer"></span>
    <select id="chatProjSel" class="toolsel" style="max-width:180px"
            onchange="onChatProject(this.value)" title="当前对话所属项目"></select>
    <select id="modelPicker" class="toolsel" onchange="pickModel(this.value)"
            title="当前对话模型" style="min-width:180px;max-width:260px">
      <option value="route:free">自由路由</option>
    </select>
    <button class="btn" id="dualBtn" style="font-size:12px"
            title="开启后同一项目可并行两个对话进程（A/B）">双对话</button>
    <button class="btn" id="openWinBtn" style="font-size:12px"
            onclick="openSecondWindow()" title="打开第二个独立对话窗口（B 进程）">新窗口</button>
    <select id="convPicker" class="toolsel" style="max-width:200px"
            onchange="loadConv(this.value)" title="历史对话（保存在项目文件夹）"></select>
    <button class="btn" id="copyChatBtn" style="font-size:12px"
            onclick="copyChatAll()" title="复制当前对话全部内容">复制全部</button>
    <button class="btn" id="replayBtn" style="font-size:12px"
            onclick="replayLast()" title="朗读最近一条助手回复">回播</button>
    <button class="btn" id="newConvBtn" style="font-size:12px"
            onclick="newChat()">＋ 新对话</button>
  </div>
  <div id="dualWrap">
    <div class="dual-col" id="colA">
  <div id="chat"><div class="chat-col" id="chatCol">
    <div class="chip-wrap"><div class="chip status">CodeCoreAgent 就绪 — 开始对话</div></div>
  </div></div>
  <div id="composer"><div class="composer-inner">
    <div id="attRow"></div>
    <textarea id="input" rows="2" placeholder="输入消息，Enter 发送，Shift+Enter 换行；📎 可附加任意文件"></textarea>
    <div class="composer-tools">
      <button class="toolbtn" id="attBtn" title="上传附件（所有文件类型均可识别）">📎</button>
      <button class="toolbtn mic" id="micBtn" onclick="toggleVoice()"
              title="麦克风：点击弹出权限设置，允许后连续听→想→说">🎤</button>
      <select id="thinkingSel" class="toolsel" onchange="setThinking(this.value)" title="思考强度：注入系统提示，控制推理深度">
        <option value="low">思考 · 低</option>
        <option value="medium" selected>思考 · 中</option>
        <option value="high">思考 · 高</option>
      </select>
      <span class="spacer"></span>
      <button class="stopbtn" id="stopSpeakTool" onclick="stopSpeak()" disabled
              style="display:none" title="停止当前语音播报">停止播报</button>
      <button class="stopbtn" id="stopBtn" onclick="stopChat()" disabled title="生成过程中可中断当前回复">停止</button>
      <button class="sendbtn" id="sendBtn" onclick="sendChat()">发送</button>
    </div>
    <div class="composer-video is-off" id="videoGenBar" title="选择文生视频模型后可调">
      <select id="vg_res" class="toolsel" disabled title="分辨率">
        <option value="480p">分辨率 · 480p（832×480）</option>
        <option value="720p" selected>分辨率 · 720p（1280×720）</option>
        <option value="1080p">分辨率 · 1080p（1920×1088）</option>
      </select>
      <select id="vg_frames" class="toolsel" disabled title="帧数 33–81">
        <option value="33">帧数 · 33</option>
        <option value="45">帧数 · 45</option>
        <option value="60" selected>帧数 · 60</option>
        <option value="81">帧数 · 81</option>
      </select>
      <select id="vg_steps" class="toolsel" disabled title="推理步数 20–50">
        <option value="20">推理步数 · 20</option>
        <option value="30">推理步数 · 30</option>
        <option value="40">推理步数 · 40</option>
        <option value="50" selected>推理步数 · 50</option>
      </select>
    </div>
  </div></div>
    </div>
    <div class="dual-col" id="colB" style="display:none">
      <div class="dual-head">
        <span class="dual-label">对话 B（并行）</span>
        <span class="spacer"></span>
        <select id="convPickerB" class="toolsel" style="max-width:200px"
                onchange="loadConv2(this.value)" title="历史对话（B 进程，同一项目文件夹）"></select>
        <button class="btn" id="copyChatBtnB" style="font-size:12px"
                onclick="copyChatAllB()" title="复制 B 对话全部内容">复制 B</button>
        <button class="btn" id="newConvBtnB" style="font-size:12px"
                onclick="newChatB()">＋ 新对话 B</button>
      </div>
      <div id="chatB"><div class="chat-col" id="chatColB">
        <div class="chip-wrap"><div class="chip status">对话 B 就绪 — 可并行提问</div></div>
      </div></div>
      <div id="composerB"><div class="composer-inner">
        <textarea id="inputB" rows="2" placeholder="B：输入消息，Enter 发送，Shift+Enter 换行"></textarea>
        <div class="composer-tools">
          <span class="spacer"></span>
          <button class="stopbtn" id="stopSpeakToolB" onclick="stopSpeak()" disabled
                  style="display:none" title="停止当前语音播报">停止播报</button>
          <button class="stopbtn" id="stopBtnB" onclick="stopChatB()" disabled title="中断 B 对话">停止</button>
          <button class="sendbtn" id="sendBtnB" onclick="sendChatB()">发送</button>
        </div>
      </div></div>
    </div>
  </div>
</section>

<!-- ============ 内置浏览器 ============ -->
<section class="page" id="page-browser">
  <div class="page-head"><h1>浏览器</h1>
    <span class="sub">软件内置 · AI 可开页、点击、填表</span>
    <span class="spacer"></span>
    <button class="btn" onclick="browserShowWin()" title="弹出内置浏览窗口，显示真实页面">显示窗口</button>
  </div>
  <div class="page-body browser-page">
    <div class="browser-bar">
      <button class="btn" onclick="browserReload()" title="刷新">↻</button>
      <input id="browserUrl" type="text" placeholder="https://"
             onkeydown="if(event.key==='Enter')browserGo()">
      <button class="sendbtn" onclick="browserGo()">打开</button>
    </div>
    <div class="browser-meta" id="browserMeta">内置浏览器已就绪。在对话里让 AI 打开网页，或在上方输入地址。</div>
    <div class="browser-split">
      <div class="card">
        <h3>页面摘要</h3>
        <pre id="browserText" class="browser-pre">尚未打开页面</pre>
      </div>
      <div class="card" style="width:300px;flex-shrink:0">
        <h3>可点元素</h3>
        <div id="browserNodes"><div class="empty">AI 打开页面后会出现 @e1、@e2…</div></div>
      </div>
    </div>
  </div>
</section>

<!-- ============ 导演台 ============ -->
<section class="page" id="page-studio">
  <div class="page-head"><h1>导演台</h1>
    <span class="sub">企划 · 分镜 · ComfyUI 生成 · ffmpeg 合成成片</span>
    <span class="spacer"></span>
    <button class="btn" onclick="studioInterrupt()">停止</button>
    <button class="btn" onclick="go('videoops')">视频运营</button>
    <button class="btn primary" onclick="saveStudio()">保存企划</button>
  </div>
  <div class="page-body"><div class="studio-wrap">
    <div class="studio-chips" id="studioChips"></div>
    <div class="studio-rail" id="studioRail"></div>

    <div class="card sect">
      <h3>1. 企划</h3>
      <div class="grid-2">
        <div>
          <label>片名</label>
          <input id="st_title" placeholder="例如：雨巷短剧 第一集">
        </div>
        <div>
          <label>画幅 / 目标时长</label>
          <div class="grid-2">
            <select id="st_aspect">
              <option value="9:16">9:16 竖屏</option>
              <option value="16:9">16:9 横屏</option>
              <option value="1:1">1:1</option>
            </select>
            <input id="st_duration" type="number" min="4" max="180" value="24" placeholder="秒">
          </div>
        </div>
      </div>
      <label>一句话故事</label>
      <textarea id="st_logline" rows="2" placeholder="开场钩子、冲突、结尾钩子"></textarea>
      <div class="grid-2">
        <div>
          <label>生成引擎</label>
          <select id="st_engine">
            <option value="comfy">ComfyUI（局域网 8188，节点图）</option>
            <option value="wan">Gradio WAN</option>
            <option value="minimax">MiniMax Hailuo</option>
            <option value="kimi">Kimi 视频</option>
            <option value="auto">自动选择</option>
          </select>
        </div>
        <div>
          <label>Comfy API 工作流 JSON</label>
          <input id="st_workflow" placeholder="Comfy 菜单 Save (API Format) 的文件路径">
        </div>
      </div>
      <div class="hint">ComfyUI 不是聊天模型。文档 <a href="https://docs.comfy.org/zh" target="_blank" rel="noreferrer">docs.comfy.org/zh</a> ·
        <a href="https://github.com/Comfy-Org/ComfyUI" target="_blank" rel="noreferrer">Comfy-Org/ComfyUI</a>。
        协议：Save (API Format) → POST /prompt → /history → /view。MiniMax-H3 用 Unet Loader (GGUF)。</div>
    </div>

    <div class="card sect">
      <h3>2. 分镜</h3>
      <label>从剧本导入（每行「1. 画面」或「## 镜头名」）</label>
      <textarea id="st_script" rows="4" placeholder="1. 夜雨巷，近景，女人撑伞回眸&#10;2. 路灯下积水倒影，缓推&#10;3. 转身走入深巷，远景收"></textarea>
      <div class="savebar">
        <button class="btn" onclick="studioImport()">导入分镜</button>
        <button class="btn" onclick="studioAddShot()">＋ 加一镜</button>
      </div>
      <div id="studioShots" class="shot-list" style="margin-top:10px"></div>
    </div>

    <div class="card sect">
      <h3>3. 生成 · 4. 合成 · 5. 成片</h3>
      <div class="savebar">
        <button class="btn primary" onclick="studioGenAll()">生成未完成镜头</button>
        <button class="btn" onclick="studioAssemble()">ffmpeg 合成成片</button>
        <button class="btn" onclick="studioToDraft()">写入发布草稿</button>
      </div>
      <div class="hint" id="studioFinal">成片：—</div>
    </div>
  </div></div>
</section>

<!-- ============ 指挥中心 ============ -->
<section class="page" id="page-lead">
  <div class="page-head"><h1>指挥中心</h1>
    <span class="sub">领导拆解命令 → 多模型工人并行执行 → 进度实时可见</span></div>
  <div class="page-body"><div class="lead-grid">
    <div>
      <div class="card">
        <h3>下达命令</h3>
        <div style="display:flex;gap:10px;align-items:flex-end">
          <textarea id="leadInput" rows="2" style="flex:1;resize:none;border-radius:10px;padding:10px 12px" placeholder="例：给项目补单元测试，同时把 README 翻译成英文"></textarea>
          <button class="sendbtn" id="leadBtn" onclick="sendLead()">派遣</button>
        </div>
      </div>
      <div class="card" style="margin-top:14px">
        <h3>任务进度</h3>
        <div id="taskList"><div class="empty">暂无任务</div></div>
      </div>
      <div id="leadReply"></div>
    </div>
    <div class="card">
      <h3>历史运行</h3>
      <div id="runList"><div class="empty">暂无记录</div></div>
    </div>
  </div></div>
</section>

<!-- ============ 记忆 ============ -->
<section class="page" id="page-memory">
  <div class="page-head"><h1>长期记忆</h1>
    <span class="sub">跨会话记住的事实，Agent 会自动检索利用</span></div>
  <div class="page-body">
    <div class="toolbar">
      <input id="memQuery" placeholder="搜索记忆…（回车）">
      <button class="btn" onclick="loadMemories()">搜索</button>
      <button class="btn primary" onclick="addMemory()">+ 添加</button>
    </div>
    <div class="list" id="memList"></div>
  </div>
</section>

<!-- ============ 知识库（Obsidian / LLM Wiki） ============ -->
<section class="page" id="page-knowledge">
  <div class="page-head"><h1>知识库</h1>
    <span class="sub">随安装自动部署 · Obsidian / LLM Wiki · 可对接 OpenViking / 腾讯云 Agent Memory</span>
    <span class="spacer"></span>
    <button class="btn" onclick="openKnowledgeFolder()">📂 打开文件夹</button>
    <button class="btn" onclick="bootstrapKnowledge()">🔧 修复布置</button>
  </div>
  <div class="page-body"><div class="settings-wrap" style="max-width:780px">
    <div class="card sect">
      <h3>连接设置</h3>
      <label>存储方式</label>
      <select id="kb_mode">
        <option value="local">本机目录</option>
        <option value="shared">局域网硬盘 / NAS / 网盘同步（多机共享）</option>
      </select>
      <label>后端形态</label>
      <select id="kb_backend">
        <option value="obsidian">Obsidian 库（推荐，可用 Obsidian 打开）</option>
        <option value="llmwiki">LLM Wiki（同一套目录结构）</option>
      </select>
      <label>知识库路径（可选本机盘 / 局域网已挂载硬盘）</label>
      <div style="display:flex;gap:8px;align-items:center">
        <input id="kb_path" placeholder="~/Documents/CodeCoreAgent-Wiki 或 /Volumes/NAS/wiki" style="flex:1;min-width:0">
        <button type="button" class="btn" onclick="pickKnowledgePath()">选择…</button>
      </div>
      <div id="kb_disks" class="hint" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px"></div>
      <div class="hint" id="kb_hint">本机：默认 Documents。局域网：先在访达/资源管理器挂载 SMB/NAS，再点带「局域网」的卷或「选择…」；Windows 也可填 \\\\服务器\\共享\\wiki。</div>
      <div class="checkline" style="margin-top:10px">
        <input type="checkbox" id="kb_enabled" checked>
        <span>启用知识库（对话中注入 knowledge_search / read / ingest 工具）</span>
      </div>
      <div class="savebar" style="margin-top:12px">
        <button class="btn" onclick="loadKnowledge()">刷新</button>
        <button class="btn primary" onclick="saveKnowledgeConfig()">保存连接</button>
      </div>
    </div>
    <div class="card sect">
      <h3>库状态</h3>
      <div id="kbStatus" class="hint">加载中…</div>
    </div>
    <div class="card sect">
      <h3>投递原始材料</h3>
      <label>标题</label><input id="kb_ingest_title" placeholder="如：某次架构决策">
      <label>内容</label><textarea id="kb_ingest_body" rows="4" placeholder="粘贴笔记、链接摘要、对话要点…"></textarea>
      <div class="savebar">
        <button class="btn primary" onclick="ingestKnowledge()">写入 raw/inbox</button>
      </div>
    </div>
    <div class="card sect">
      <h3>Wiki 页面</h3>
      <div class="toolbar" style="max-width:none;margin:0 0 12px">
        <input id="kbQuery" placeholder="搜索 wiki…（回车）" style="flex:1">
        <button class="btn" onclick="searchKnowledge()">搜索</button>
      </div>
      <div id="kbPageList"><div class="empty">尚未布置或无可显示页面</div></div>
    </div>
  </div></div>
</section>

<!-- ============ 视频运营 ============ -->
<section class="page" id="page-videoops">
  <div class="page-head"><h1>视频运营</h1>
    <span class="sub">选题剧本 · 生成 · 剪辑 · 分析 · 多平台发布草稿</span>
    <span class="spacer"></span>
    <button class="btn" onclick="openVideoOpsFolder()">📂 打开工作区</button>
    <button class="btn primary" onclick="bootstrapVideoOps()">⚡ 一键布置</button>
  </div>
  <div class="page-body"><div class="settings-wrap" style="max-width:780px">
    <div class="card sect">
      <h3>工作区</h3>
      <label>本地路径（也可填 NAS / 网盘同步目录，实现跨电脑共用）</label>
      <input id="vo_path" placeholder="~/Documents/CodeCoreAgent-VideoOps">
      <div class="checkline"><input type="checkbox" id="vo_enabled" checked>
        <span>启用（对话注入视频运营技能与工具）</span></div>
      <div class="savebar">
        <button class="btn" onclick="loadVideoOps()">刷新</button>
        <button class="btn primary" onclick="saveVideoOpsConfig()">保存路径</button>
      </div>
      <div class="hint" id="voStatus">加载中…</div>
    </div>
    <div class="card sect">
      <h3>局域网文生视频（Gradio / WAN）</h3>
      <label>服务地址（如 WAN-1.3B 的 http://192.168.3.23:7860）</label>
      <input id="vo_gradio" placeholder="http://192.168.3.23:7860">
      <div class="hint" id="voGradioStatus">未接入</div>
      <div class="savebar">
        <button class="btn primary" onclick="connectVideoGradio()">探测并接入</button>
      </div>
      <div class="hint">识别为 Gradio 文生视频后，对话里可用 <code>video_generate</code> 把成片写到 02-generate/。不能当作聊天模型。</div>
    </div>
    <div class="card sect">
      <h3>ComfyUI</h3>
      <label>服务地址（默认本机 8188）</label>
      <input id="vo_comfy" placeholder="http://127.0.0.1:8188">
      <div class="hint" id="voComfyStatus">未接入</div>
      <div class="hint">节点图后端，不是聊天模型。完整拍片请用侧栏「导演台」。对话里模型会自己调用 <code>comfy</code> / <code>video_studio</code>。</div>
    </div>
    <div class="card sect">
      <h3>云端视频模型（MiniMax / Kimi）</h3>
      <div class="hint">在「模型」添加 MiniMax Hailuo（如 MiniMax-Hailuo-2.3）或 Kimi 视频模型并保存密钥。对话选中该模型会走文生视频；也可让 Agent 调用 <code>video_generate</code>，provider 填 minimax 或 kimi。</div>
    </div>
    <div class="card sect">
      <h3>本机工具链</h3>
      <div id="voToolchain" class="hint">检测中…</div>
      <div class="hint" style="margin-top:8px">LibTV 用于画布生成；Node+npx 用于 Remotion；ffmpeg 用于中文竖屏剪辑。未安装时 Agent 会改用已有路径并提示。</div>
    </div>
    <div class="card sect">
      <h3>融合技能包</h3>
      <div id="voSkills" class="hint">—</div>
    </div>
    <div class="card sect">
      <h3>发布草稿（人工确认发布）</h3>
      <label>标题</label><input id="vo_title" placeholder="短视频标题">
      <label>描述</label><textarea id="vo_desc" rows="3" placeholder="简介 / 口播要点"></textarea>
      <label>标签（空格分隔）</label><input id="vo_tags" placeholder="标签1 标签2">
      <label>成片路径</label><input id="vo_video" placeholder="/path/to/final.mp4">
      <label>竖版封面</label><input id="vo_cover" placeholder="/path/to/cover.jpg">
      <div class="hint">写入 05-publish/draft.json，覆盖抖音 / 小红书 / 视频号 / B 站 / YouTube 同一套资料。各后台仍由你点「发布」。</div>
      <div class="savebar">
        <button class="btn primary" onclick="saveVideoOpsDraft()">保存草稿</button>
      </div>
    </div>
  </div></div>
</section>

<!-- ============ 技能 ============ -->
<section class="page" id="page-skills">
  <div class="page-head"><h1>技能库</h1>
    <span class="sub">工作室按任务和项目文件自动识别并启用；模型也可独立调用 use_skill 加载全部技能</span></div>
  <div class="page-body"><div id="skillGrid"></div></div>
</section>

<!-- ============ 日志 ============ -->
<section class="page" id="page-logs">
  <div class="page-head"><h1>日志</h1>
    <span class="sub">~/.codeagent/logs/codeagent.log</span>
    <span class="spacer"></span>
    <button class="btn" onclick="loadLogs()">刷新</button>
    <button class="btn" onclick="showChangelog()">更新历史</button>
  </div>
  <div class="page-body"><div id="logbox">加载中…</div></div>
</section>

<!-- ============ 模型管理（LCA Models.tsx） ============ -->
<section class="page" id="page-models">
  <div class="page-head"><h1>模型管理</h1>
    <span class="sub">本地模型独立部署 · API 模型独立配置 · 聚合池混合路由</span></div>
  <div class="page-body"><div class="models-wrap">
    <div class="tabs">
      <button class="tab active" data-tab="mixture">聚合池</button>
      <button class="tab" data-tab="local">本地模型</button>
      <button class="tab" data-tab="api">API 模型</button>
    </div>

    <div class="tabpane active" id="tab-mixture">
      <div style="display:flex;justify-content:flex-end;margin-bottom:12px">
        <button class="btn primary" onclick="openMixDialog()">+ 新建聚合池</button>
      </div>
      <div id="mixList"></div>
    </div>

    <div class="tabpane" id="tab-local">
      <div class="card sect" style="margin-bottom:14px"><h3>Ollama 端点（局域网模型集群）</h3>
        <div id="endpointList"><div class="empty">探测中…</div></div>
        <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">
          <input id="ep_label" placeholder="端点名称，如：主推理" style="width:150px">
          <input id="ep_base" placeholder="http://IP:11434 或 http://IP:9000" style="flex:1;min-width:200px">
          <select id="ep_role" style="width:110px">
            <option value="primary">主推理</option>
            <option value="backup" selected>备用/快速</option>
          </select>
          <button class="btn" onclick="addEndpoint()">+ 添加端点</button>
        </div>
        <div class="hint">对话页可直接调用在线端点的模型；桌面版经主进程代理，无跨域限制</div>
      </div>
      <div class="card sect" style="margin-bottom:14px"><h3>部署新模型</h3>
        <div style="display:flex;gap:8px">
          <input id="pull_name" placeholder="如：qwen3:14b 或 gguf 仓库地址" style="flex:1">
          <button class="btn primary" onclick="pullModel()">⬇ 部署</button>
        </div>
        <div class="hint">兼容 Ollama / vLLM 运行时，输入模型标识即可拉取</div>
      </div>
      <div id="localModelList"></div>
    </div>

    <div class="tabpane" id="tab-api">
      <div class="card sect" style="margin-bottom:14px"><h3>接入 API 模型</h3>
        <div class="hint" style="margin-bottom:10px">填 Base URL 与 Key 后点「自动识别」，自动识别提供方并列出可用模型；密钥仅保存在本机</div>
        <div style="display:flex;gap:8px;margin-bottom:8px">
          <select id="am_preset" style="width:190px;flex-shrink:0" onchange="applyPreset()">
            <option value="__custom">自定义（手填）</option>
          </select>
          <input id="am_base" placeholder="Base URL：从左侧下拉选择，或直接手动填写" style="flex:1">
        </div>
        <div class="grid-2" style="gap:8px">
          <input id="am_key" type="password" placeholder="API Key（识别与调用时使用）">
          <input id="am_provider" placeholder="提供方（识别后自动填）">
        </div>
        <div id="am_model_wrap" style="margin-top:8px">
          <select id="am_model" style="width:100%">
            <option value="" disabled selected>先点「自动识别」列出全部模型</option>
          </select>
        </div>
        <div class="hint" id="am_detect_hint"></div>
        <div style="display:flex;gap:8px;margin-top:10px">
          <button class="btn" id="am_detect_btn" onclick="detectModels()">⟳ 自动识别</button>
          <button class="btn primary" onclick="addApiModel()">+ 添加</button>
        </div>
      </div>
      <div id="apiModelList"></div>
      <div class="hint" style="margin-top:12px;color:var(--faint);font-size:11px">⧉ 聚合池可同时引用本地模型与 API 模型，实现混合路由与故障自动降级。</div>
    </div>
  </div></div>
</section>

<!-- ============ 路由引擎（LCA RouterPage.tsx） ============ -->
<section class="page" id="page-router">
  <div class="page-head"><h1>自由路由</h1>
    <span class="sub">规则 → 分类 → 级联 → 学习，四级路由策略在此编排</span></div>
  <div class="page-body"><div class="page-wrap"><div class="grid-32">
    <div>
      <div class="card sect" style="margin-bottom:14px"><h3>任务类型路由规则</h3>
        <div class="hint" style="margin-bottom:10px">按优先级从上到下匹配，命中即分发。关键词可用逗号、顿号或中文逗号分隔；整栏留空即为兜底规则。</div>
        <div id="ruleList"></div>
        <div style="display:grid;grid-template-columns:1fr 1.4fr 1fr auto;gap:8px;margin-top:12px">
          <input id="rl_type" placeholder="任务类型">
          <input id="rl_keywords" placeholder="关键词，逗号或顿号分隔；留空=兜底">
          <select id="rl_target"></select>
          <button class="btn primary" onclick="addRule()">+</button>
        </div>
      </div>
      <div class="card sect"><h3>路由沙盒</h3>
        <div class="hint" style="margin-bottom:10px">输入测试语句，预览路由决策（不实际调用模型）</div>
        <div style="display:flex;gap:8px">
          <input id="sandbox_input" placeholder="如：帮我调试这段 Python 报错" style="flex:1">
          <button class="btn" onclick="runSandbox()">🧪 探测</button>
        </div>
        <div id="sandboxResult"></div>
      </div>
    </div>
    <div class="card sect"><h3>路由偏好权重</h3>
      <div class="hint" style="margin-bottom:14px">影响加权策略的打分公式</div>
      <div class="wrow">
        <div class="whead"><span>成本敏感</span><span class="wval" id="w_cost_val">60</span></div>
        <input type="range" id="w_cost" min="0" max="100" value="60" oninput="weightChanged()">
        <div class="whint">越高越倾向便宜/免费的本地模型</div>
      </div>
      <div class="wrow">
        <div class="whead"><span>质量偏好</span><span class="wval" id="w_quality_val">80</span></div>
        <input type="range" id="w_quality" min="0" max="100" value="80" oninput="weightChanged()">
        <div class="whint">越高越倾向大参数/旗舰 API 模型</div>
      </div>
      <div class="wrow">
        <div class="whead"><span>本地优先</span><span class="wval" id="w_local_val">40</span></div>
        <input type="range" id="w_local" min="0" max="100" value="40" oninput="weightChanged()">
        <div class="whint">越高越倾向数据不出本机</div>
      </div>
    </div>
  </div></div></div>
</section>

<!-- ============ 权限控制（LCA Permissions.tsx） ============ -->
<section class="page" id="page-permissions">
  <div class="page-head"><h1>权限控制</h1>
    <span class="sub">权限最大化的同时保持可控：每项能力独立分级，全程审计</span></div>
  <div class="page-body"><div class="page-wrap"><div class="grid-2">
    <div class="card sect"><h3>能力矩阵</h3>
      <div class="hint" style="margin-bottom:12px">Agent 对电脑与网络的操作边界</div>
      <div id="capList"></div>
      <div style="margin-top:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:10px 12px;font-size:11.5px;color:var(--muted);display:flex;gap:8px">
        <span style="color:var(--pill-green)">🛡</span>
        「执行前确认」级别的动作会暂停流水线并向你发送确认，超时 10 分钟未确认则自动拒绝并记入审计。
      </div>
    </div>
    <div class="card sect"><h3>审计日志</h3>
      <div class="hint" style="margin-bottom:12px">所有能力调用留痕，可回溯</div>
      <div id="auditList"></div>
    </div>
  </div></div></div>
</section>

<!-- ============ 版本说明（LCA Versions.tsx） ============ -->
<section class="page" id="page-versions">
  <div class="page-head"><h1>版本说明</h1>
    <span class="sub" id="verSub">当前版本</span></div>
  <div class="page-body"><div class="page-wrap" style="max-width:720px">
    <div class="card sect" style="margin-bottom:14px">
      <h3 id="verCurTitle"></h3>
      <div style="margin-bottom:10px"><span class="pill green">✦ 当前版本</span></div>
      <ul class="ver-points" id="verCurPoints"></ul>
    </div>
    <div class="card sect"><h3>历史版本</h3>
      <div class="hint" style="margin-bottom:12px">过往更新记录</div>
      <div id="verHistory"></div>
    </div>
  </div></div>
</section>

<!-- ============ 隐私条款 ============ -->
<section class="page" id="page-privacy">
  <div class="page-head"><h1>隐私条款</h1>
    <span class="sub" id="privacySub">本地优先 · 数据由您掌控</span></div>
  <div class="page-body"><div class="page-wrap" style="max-width:720px">
    <div class="card sect" style="margin-bottom:12px;display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <span class="pill" id="privacyVerPill">版本 —</span>
      <span class="pill green" id="privacyAcceptPill" style="display:none">已同意</span>
      <span style="flex:1"></span>
      <button class="btn primary" id="privacyAcceptBtn" onclick="acceptPrivacy()" style="display:none">同意并继续</button>
    </div>
    <div class="card sect" id="privacyBody"></div>
  </div></div>
</section>

<!-- ============ 自动化（LCA Automation.tsx） ============ -->
<section class="page" id="page-automation">
  <div class="page-head"><h1>自动化</h1>
    <span class="sub">把「模型 + 工具 + 权限」串成可复用的流水线</span>
    <span class="spacer"></span>
    <button class="btn primary" onclick="openWfDialog()">+ 新建工作流</button>
  </div>
  <div class="page-body"><div class="page-wrap">
    <div id="wfList"></div>
    <p style="font-size:11px;color:var(--faint);margin-top:14px;line-height:1.7">
      「连续性」开启后，工作流完成一轮会自动评估产出并触发下一轮（如：持续监控、增量备份、滚动摘要），直至你暂停或权限系统拦截。
    </p>
  </div></div>
</section>

<!-- ============ 定时任务（LCA CronPage.tsx） ============ -->
<section class="page" id="page-cron">
  <div class="page-head"><h1>定时任务</h1>
    <span class="sub">cron 驱动的工作流与动作，到点自动执行</span>
    <span class="spacer"></span>
    <button class="btn primary" onclick="openCronDialog()">+ 新建任务</button>
  </div>
  <div class="page-body"><div class="page-wrap">
    <div class="cron-row sys" id="evoJobRow">
      <div class="switch" id="evoJobSwitch" onclick="toggleEvoJob()"></div>
      <div style="flex:1">
        <div style="font-weight:550;font-size:13px;display:flex;align-items:center;gap:8px">
          夜间进化作业 <span class="pill purple">系统级</span></div>
        <div style="font-size:11px;color:var(--muted);margin-top:3px">复盘当日交互 → 归因 → 更新路由权重 → 整理记忆 → 产出行为补丁（详见「进化日志」）</div>
      </div>
      <div style="text-align:right;font-size:11px">
        <div class="cron-expr sys" id="evoJobCron">0 2 * * *</div>
        <div style="color:var(--faint);margin-top:3px">每天凌晨自动执行</div>
      </div>
    </div>
    <div id="cronList"></div>
  </div></div>
</section>

<!-- ============ 自我学习（LCA Learning.tsx） ============ -->
<section class="page" id="page-learning">
  <div class="page-head"><h1>自我学习</h1>
    <span class="sub">对话赞/踩即时计入，驱动路由权重持续修正</span>
    <span class="spacer"></span>
    <button class="btn primary" onclick="learnNow()">⟳ 立刻自我学习</button>
  </div>
  <div class="page-body"><div class="page-wrap">
    <div class="stat-grid" style="max-width:none">
      <div class="card stat"><div class="s-label">最新路由准确率</div>
        <div class="s-value" id="lnAcc">—</div><div class="s-sub">规则 + 反馈学习叠加</div></div>
      <div class="card stat"><div class="s-label">累计样本</div>
        <div class="s-value" id="lnSamples">—</div><div class="s-sub">赞/踩反馈总数</div></div>
      <div class="card stat"><div class="s-label">今日反馈</div>
        <div class="s-value" id="lnToday">—</div><div class="s-sub">赞 / 踩</div></div>
      <div class="card stat"><div class="s-label">学习模式</div>
        <div class="s-value" style="font-size:17px;padding-top:4px">在线学习</div>
        <div class="s-sub">活动流即真相</div></div>
    </div>
    <div class="grid-2" style="margin-bottom:14px">
      <div class="card sect"><h3>路由准确率趋势</h3>
        <div class="chart-box" id="accChart"></div>
        <div class="hint" id="accChartHint">暂无学习记录，点右上角「立刻自我学习」</div>
      </div>
      <div class="card sect"><h3>每日反馈量</h3>
        <div class="chart-box" id="fbChart"></div>
        <div class="hint" id="fbChartHint">赞（绿）/ 踩（红）是路由修正的主要信号</div>
      </div>
    </div>
    <div class="grid-2">
      <div class="card sect"><h3>学习管线</h3>
        <div class="hint" style="margin-bottom:12px">从反馈到权重更新的完整链路</div>
        <div id="pipeList"></div>
      </div>
      <div class="card sect"><h3>数据导出与微调</h3>
        <div class="hint" style="margin-bottom:12px">学习数据完全属于你</div>
        <div class="pipe-row"><div><div style="font-weight:550">路由样本集（JSONL）</div>
          <div style="font-size:11px;color:var(--faint)" id="sampleCount">0 条 · 可用于训练自有路由器</div></div>
          <button class="btn" style="padding:5px 12px;font-size:11.5px" onclick="exportSamples()">⬇ 导出</button></div>
        <div class="pipe-row"><div><div style="font-weight:550">对话偏好对（DPO）</div>
          <div style="font-size:11px;color:var(--faint)">正/负反馈配对 · 适用于偏好对齐微调</div></div>
          <button class="btn" style="padding:5px 12px;font-size:11.5px" onclick="exportSamples()">⬇ 导出</button></div>
        <p style="font-size:11px;color:var(--faint);line-height:1.7;margin-top:6px">
          积累的样本可定期对本地模型做 LoRA 微调，让「便宜档」越来越懂你的任务分布，进一步降低 API 依赖——这是平台成本曲线持续下降的第二引擎。
        </p>
      </div>
    </div>
  </div></div>
</section>

<!-- ============ 进化日志（LCA Evolution.tsx） ============ -->
<section class="page" id="page-evolution">
  <div class="page-head"><h1>进化日志</h1>
    <span class="sub">夜间进化循环与行为补丁：可回滚、可审计的进化时间线</span>
    <span class="spacer"></span>
    <button class="btn primary" id="evoRunBtn" onclick="runEvolution()">🌙 立即运行进化作业</button>
  </div>
  <div class="page-body"><div class="page-wrap">
    <div class="card sect" id="evoProgress" style="display:none;margin-bottom:14px">
      <h3>进化作业进行中</h3>
      <div style="display:flex;flex-wrap:wrap;gap:8px" id="evoPhaseRow"></div>
    </div>
    <div class="card sect" style="margin-bottom:14px"><h3>行为补丁</h3>
      <div class="hint" style="margin-bottom:12px">复盘产出的行为规则，注入系统提示即生效；L2 级需批准后启用</div>
      <div id="patchList"></div>
    </div>
    <div class="card sect" style="margin-bottom:14px"><h3>进化时间线</h3>
      <div class="hint" style="margin-bottom:12px">每晚作业的五阶段记录</div>
      <div id="evoTimeline"></div>
    </div>
    <div class="card sect"><h3>进化设置</h3>
      <div class="hint" style="margin-bottom:12px">对应权限矩阵「自我修改」能力</div>
      <div class="pipe-row"><div><div style="font-weight:550">夜间进化作业</div>
        <div style="font-size:11px;color:var(--faint)">cron：<span id="evoSetCron">0 2 * * *</span>（默认每天凌晨 2 点）</div></div>
        <div class="switch" id="evoSetEnabled" onclick="saveEvoSettings()"></div></div>
      <div class="pipe-row"><div><div style="font-weight:550">L0/L1 变更自动生效</div>
        <div style="font-size:11px;color:var(--faint)">行为补丁、路由权重微调无需确认</div></div>
        <div class="switch" id="evoSetL01" onclick="saveEvoSettings()"></div></div>
      <div class="pipe-row" style="margin-bottom:0"><div><div style="font-weight:550">L2 及以上需批准</div>
        <div style="font-size:11px;color:var(--faint)">新技能、评估标准变更必须人工确认</div></div>
        <div class="switch" id="evoSetL2" onclick="saveEvoSettings()"></div></div>
    </div>
  </div></div>
</section>

<!-- ============ 偏好设置 ============ -->
<section class="page" id="page-settings">
  <div class="page-head"><h1>偏好设置</h1>
    <span class="sub">陪伴型 AI、语音、个性化与指挥中心默认链路</span></div>
  <div class="page-body"><div class="settings-wrap">

    <div class="card sect"><h3>外观</h3>
      <label>主题</label>
      <div class="tabs" id="themeTabs" style="max-width:340px">
        <button class="tab" data-theme="dark">深色</button>
        <button class="tab" data-theme="light">浅色</button>
        <button class="tab" data-theme="auto">自动（跟随系统）</button>
      </div>
      <div class="hint">自动模式下跟随 macOS 系统外观，系统切换时实时生效</div>
    </div>

    <div class="card sect" id="sectKnowledgePath"><h3>知识库存储路径</h3>
      <p class="hint">可存本机，也可存到已挂载的局域网硬盘 / NAS。保存后会自动在该路径部署 Wiki；多台电脑填同一路径即可共享。</p>
      <label>存储方式</label>
      <select id="cfg_kb_mode" onchange="updateCfgKbHint()">
        <option value="local">本机目录</option>
        <option value="shared">局域网硬盘 / NAS / 网盘同步（多机共享）</option>
      </select>
      <label>知识库路径</label>
      <div style="display:flex;gap:8px;align-items:center">
        <input id="cfg_kb_path" placeholder="本机路径 或 /Volumes/NAS/wiki" style="flex:1;min-width:0">
        <button type="button" class="btn" onclick="pickKnowledgePath('cfg')">选择…</button>
      </div>
      <div id="cfg_kb_disks" class="hint" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px"></div>
      <div class="hint" id="cfg_kb_hint">先挂载局域网盘，再点标记「局域网」的卷，或「选择…」浏览。未挂载时无法写入。</div>
      <div class="checkline" style="margin-top:10px">
        <input type="checkbox" id="cfg_kb_enabled" checked>
        <span>启用知识库工具</span>
      </div>
      <div class="savebar" style="margin-top:12px">
        <button class="btn" type="button" onclick="go('knowledge')">打开知识库页</button>
        <button class="btn primary" type="button" onclick="saveKnowledgePathFromSettings()">保存知识库路径</button>
      </div>
    </div>

    <div class="card sect" id="sectCompanion"><h3>陪伴型 AI</h3>
      <p class="hint">开启后，对话会按角色人设陪伴聊天（融合 y-ai-accompany / ai-companion）。可与下方嗲嗲声、麦克风一起用。</p>
      <div class="checkline"><input type="checkbox" id="cfg_companion">
        <span><b>开启陪伴模式</b>（对话里按角色性格回复，记得细节、先倾听）</span></div>
      <label>角色预设</label>
      <select id="cfg_companion_preset" onchange="applyCompanionPreset()"></select>
      <label>AI 角色名</label>
      <input id="cfg_companion_name" placeholder="如：小暖、欣欣">
      <label>性格与说话方式</label>
      <textarea id="cfg_companion_nature" rows="3"
                placeholder="温柔会倾听，口语短句，先情绪后建议…"></textarea>
      <div class="hint">选预设会自动填入角色名与性格，仍可再改。保存后立即对新对话生效。</div>
    </div>

    <div class="card sect"><h3>高级：聚合与兜底（指挥中心默认链路）</h3>
      <label>Provider（逗号串联 = 聚合模式，如 ollama,openrouter）</label>
      <input id="cfg_provider" list="providers">
      <datalist id="providers"></datalist>
      <label>模型（留空用默认）</label><input id="cfg_model">
      <label>API Key（留空用环境变量）</label>
      <input id="cfg_key" type="password" placeholder="sk-...">
      <label>Base URL（自建中转 / 兼容端点）</label>
      <input id="cfg_base" placeholder="http://localhost:3000/v1">
      <label>聚合策略</label>
      <select id="cfg_strategy">
        <option value="fallback">fallback（故障转移，本地优先云端兜底）</option>
        <option value="round-robin">round-robin（轮询分流）</option>
      </select>
      <div class="checkline"><input type="checkbox" id="cfg_yes">
        <span>自动批准所有工具调用（含写文件/执行命令，慎用）</span></div>
    </div>

    <div class="card sect" id="sectAgentLimits"><h3>Agent 执行上限</h3>
      <p class="hint">单次任务里模型调用工具的往返次数上限。到顶会软收束作答，不会再抛英文红字。复杂长任务可调高，闲聊可调低。</p>
      <div class="wrow" style="margin-top:8px">
        <div class="whead"><span>工具往返上限</span><span class="wval" id="cfg_iters_val">80</span></div>
        <input id="cfg_max_iterations" type="range" min="10" max="300" step="10" value="80"
               oninput="syncMaxIterationsSlider()">
        <div class="whint">范围 10–300，默认 80。改完请点「保存全部」。</div>
      </div>
      <label style="margin-top:10px">或直接填数字</label>
      <input id="cfg_max_iterations_num" type="number" min="10" max="300" step="1" value="80"
             onchange="syncMaxIterationsNum()" oninput="syncMaxIterationsNum()">
    </div>

    <div class="card sect" id="sectMicPerm"><h3>麦克风与语音识别权限</h3>
      <p class="hint">听写必须同时打开「麦克风」和「语音识别」。可在此查看状态并跳转系统设置（不要只开 LunarCore Agent）。</p>
      <div class="wrow" style="margin-top:4px">
        <div class="whead"><span>麦克风</span><span class="wval" id="micStatusLabel">检测中…</span></div>
        <div class="whint" id="micStatusPath">系统设置 → 隐私与安全性 → 麦克风 → CodeCoreAgent</div>
      </div>
      <div class="wrow">
        <div class="whead"><span>语音识别</span><span class="wval" id="speechStatusLabel">检测中…</span></div>
        <div class="whint" id="speechStatusPath">系统设置 → 隐私与安全性 → 语音识别 → CodeCoreAgent</div>
      </div>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
        <button class="btn" type="button" onclick="refreshMicPermStatus()">刷新状态</button>
        <button class="btn primary" type="button" onclick="requestMicFromSettings()">申请权限</button>
        <button class="btn" type="button" onclick="openMicFromSettings()">打开麦克风设置</button>
        <button class="btn" type="button" onclick="openSpeechFromSettings()">打开语音识别设置</button>
      </div>
    </div>

    <div class="card sect" id="sectVoice"><h3>语音面 · 嗲嗲声</h3>
      <p class="hint">对话页点麦克风即可连续语音聊天（听→想→说→再听）。打字提问也可播报回答。凭证只写不读。</p>
      <div class="checkline"><input type="checkbox" id="cfg_voice">
        <span>打字提问也播报回答</span></div>
      <label>播报声音</label><select id="cfg_voicename"></select>
      <div class="checkline" style="margin-top:12px"><input type="checkbox" id="cfg_cute">
        <span><b>开启嗲嗲声</b>（柔化音调、放缓语速；回播与语音对话都会生效）</span></div>
      <div class="wrow" style="margin-top:10px">
        <div class="whead"><span>嗲嗲声 · 音调</span><span class="wval" id="cfg_pitch_val">-10Hz</span></div>
        <input id="cfg_pitch" type="range" min="-50" max="50" step="5" value="-10" oninput="syncCuteSliders()">
        <div class="whint">偏负更柔和，偏正更亮更“嗲”</div>
      </div>
      <div class="wrow">
        <div class="whead"><span>嗲嗲声 · 语速</span><span class="wval" id="cfg_rate_val">-5%</span></div>
        <input id="cfg_rate" type="range" min="-20" max="20" step="1" value="-5" oninput="syncCuteSliders()">
        <div class="whint">偏负更慢，偏正更快</div>
      </div>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
        <button class="btn" type="button" onclick="previewCuteVoice()">试听嗲嗲声</button>
        <span class="hint" style="align-self:center;margin:0">先调开关与滑杆，点试听即可听效果（会写入当前设置）</span>
      </div>
    </div>

    <div class="card sect"><h3>个性化（本机所有对话生效）</h3>
      <label>怎么称呼你</label><input id="set_nick">
      <label>首选语言</label><input id="set_lang" placeholder="中文">
      <label>额外说明</label><textarea id="set_inst" placeholder="回答先给结论，再给细节"></textarea>
      <label>用户与主机上下文</label><textarea id="set_ctx" placeholder="M4 Mac，项目在 ~/code"></textarea>
    </div>

    <div class="card sect"><h3>工人团队（指挥中心用）</h3>
      <label>JSON 名册，留空则单个默认工人</label>
      <textarea id="cfg_workers" rows="4" placeholder='[{"name":"claude","provider":"anthropic","description":"代码与审查"},{"name":"qwen","provider":"ollama","model":"qwen2.5-coder:7b","description":"本地快速执行"}]'></textarea>
      <div class="hint">每个工人可指定不同 provider/model——聪明大脑规划，便宜模型干活</div>
    </div>

    <div class="card sect"><h3>本机外部 Agent 平台（困难任务自动求助）</h3>
      <div id="harnessList"><div class="empty">检测中…</div></div>
    </div>

    <div class="card sect" id="sectFeedback">
      <h3>官网与反馈</h3>
      <p class="hint">官网在系统浏览器中打开。问题反馈会打开本机邮件应用，收件人已填好。</p>
      <div class="savebar" style="margin-top:12px">
        <button class="btn" type="button" onclick="openOfficialSite()">官网</button>
        <button class="btn" type="button" onclick="openPrivacyPage()">隐私安全</button>
        <button class="btn primary" type="button" onclick="openFeedbackMail()">问题反馈</button>
      </div>
    </div>

    <div class="savebar">
      <button class="btn" onclick="loadSettings()">还原</button>
      <button class="btn primary" onclick="saveAll()">保存全部</button>
    </div>
  </div></div>
</section>

</div>

<!-- 隐私条款首次确认 -->
<div class="modal-mask" id="privacyDialog">
  <div class="modal wide">
    <h3 id="privacyDlgTitle">隐私条款</h3>
    <div class="hint" style="margin:-6px 0 10px;font-size:11px;color:var(--faint)">
      首次使用或条款更新后需确认。同意后可在「设置 → 隐私条款」随时查阅。
    </div>
    <div class="privacy-scroll" id="privacyDlgBody"></div>
    <div style="display:flex;gap:8px">
      <button class="btn primary" style="flex:1" onclick="acceptPrivacy()">我已阅读并同意</button>
    </div>
  </div>
</div>

<!-- 聚合池对话框（LCA Dialog） -->
<div class="modal-mask" id="mixDialog">
  <div class="modal">
    <h3 id="mixDialogTitle">创建聚合池（API + 本地混合）</h3>
    <input id="mix_name" placeholder="名称，如：推理增强池">
    <label>路由策略</label>
    <select id="mix_strategy">
      <option value="weighted">加权路由（按成本/延迟/质量打分）</option>
      <option value="cascade">级联路由（便宜优先，不行升级）</option>
      <option value="vote">投票聚合（多模型同答后裁决）</option>
      <option value="rule">规则直通（按关键词固定分发）</option>
    </select>
    <label>选择成员（至少 2 个，可混选本地与 API）</label>
    <div class="member-box" id="mix_members"></div>
    <div class="hint" id="mix_count" style="font-size:11px;color:var(--faint);margin-top:6px">已选 0 个（至少 2 个）</div>
    <div style="display:flex;gap:8px;margin-top:16px">
      <button class="btn" style="flex:1" onclick="closeMixDialog()">取消</button>
      <button class="btn primary" style="flex:1" id="mixSaveBtn" onclick="saveMix()">创建并启用</button>
    </div>
  </div>
</div>

<!-- 执行前确认弹窗（LCA Permissions confirm） -->
<div class="modal-mask" id="confirmDialog">
  <div class="modal">
    <h3>执行前确认</h3>
    <div style="font-size:12.5px;color:var(--muted);line-height:1.8">
      Agent 请求调用工具 <b id="cf_tool" style="color:var(--text)"></b>
      <span class="pill amber" id="cf_risk"></span>
      <div style="margin-top:8px;background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:9px 11px;font-family:Menlo,monospace;font-size:11px;word-break:break-all" id="cf_args"></div>
      <div style="margin-top:8px;font-size:11px;color:var(--faint)">10 分钟未确认将自动拒绝并记入审计</div>
    </div>
    <div style="display:flex;gap:8px;margin-top:16px">
      <button class="btn danger" style="flex:1" onclick="resolveConfirm(false)">拒绝</button>
      <button class="btn primary" style="flex:1" onclick="resolveConfirm(true)">批准执行</button>
    </div>
  </div>
</div>

<!-- 麦克风权限设置 -->
<div class="modal-mask" id="micPermDialog">
  <div class="modal">
    <h3>麦克风权限</h3>
    <div style="font-size:12.5px;color:var(--muted);line-height:1.8" id="micPermMsg">
      请打开本软件的麦克风开关。
    </div>
    <div style="margin-top:10px;padding:10px 12px;background:var(--bg);border:1px solid var(--border);border-radius:8px;font-size:12.5px;line-height:1.8" id="micPermPath">
      <b>系统设置 → 隐私与安全性 → 麦克风</b><br>
      打开列表里的 <b>CodeCoreAgent</b><br>
      <span style="color:var(--warn);font-size:12px">注意：LunarCore Agent 是另一个软件，不要只开它。</span><br>
      <span style="color:var(--faint);font-size:11.5px">若列表还没有 CodeCoreAgent：先点下面「允许并开始语音」，再回系统设置刷新。</span>
    </div>
    <div style="display:flex;flex-direction:column;gap:8px;margin-top:16px">
      <button class="btn primary" onclick="allowMicAndStart()">允许并开始语音</button>
      <button class="btn" onclick="openSystemMicSettings()">打开「麦克风」系统页</button>
      <button class="btn" onclick="hideMicPermDialog()">取消</button>
    </div>
  </div>
</div>

<!-- 新建工作流对话框 -->
<div class="modal-mask" id="wfDialog">
  <div class="modal">
    <h3>新建工作流</h3>
    <input id="wf_name" placeholder="名称，如：每日代码巡检">
    <label>描述</label>
    <input id="wf_desc" placeholder="这个工作流做什么">
    <label>触发方式</label>
    <select id="wf_trigger">
      <option value="manual">手动触发</option>
      <option value="cron">cron 调度</option>
      <option value="event">事件触发</option>
      <option value="feishu">指令触发</option>
    </select>
    <label>步骤（每步 = 一次 agent 调用；工具留空用当前激活模型）</label>
    <div id="wf_steps"></div>
    <button class="btn" style="margin-top:8px;font-size:11.5px" onclick="addWfStepRow()">+ 加一步</button>
    <div style="display:flex;gap:8px;margin-top:16px">
      <button class="btn" style="flex:1" onclick="$('wfDialog').classList.remove('open')">取消</button>
      <button class="btn primary" style="flex:1" onclick="saveWorkflow()">创建</button>
    </div>
  </div>
</div>

<!-- 新建定时任务对话框（LCA Dialog + 预设 chips） -->
<div class="modal-mask" id="cronDialog">
  <div class="modal">
    <h3>新建定时任务</h3>
    <input id="cj_name" placeholder="任务名称，如：每晚备份对话">
    <label>cron 表达式</label>
    <input id="cj_schedule" placeholder="0 8 * * *">
    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px" id="cronPresets"></div>
    <label>执行动作</label>
    <input id="cj_action" placeholder="交给 agent 的提示词，如：汇总今日对话要点">
    <div style="display:flex;gap:8px;margin-top:16px">
      <button class="btn" style="flex:1" onclick="$('cronDialog').classList.remove('open')">取消</button>
      <button class="btn primary" style="flex:1" onclick="saveCronJob()">创建</button>
    </div>
  </div>
</div>

<!-- 新建项目对话框 -->
<div class="modal-mask" id="projDialog">
  <div class="modal">
    <h3>新建项目</h3>
    <label>项目名称</label>
    <input id="pj_name" placeholder="如：网站重构、数据分析">
    <label>存放位置（可选硬盘 / 文件夹，留空用默认目录）</label>
    <div style="display:flex;gap:8px;align-items:center">
      <input id="pj_base" placeholder="" style="flex:1;min-width:0">
      <button type="button" class="btn" onclick="pickProjectBase()">选择…</button>
    </div>
    <div id="pj_disks" class="hint" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px"></div>
    <div class="hint">将在该目录下创建项目文件夹——可点上方硬盘快捷项，或「选择…」浏览任意盘符/文件夹。对话、思考与工程文件都保存在项目文件夹里。</div>
    <div style="display:flex;gap:8px;margin-top:16px">
      <button class="btn" style="flex:1" onclick="$('projDialog').classList.remove('open')">取消</button>
      <button class="btn primary" style="flex:1" onclick="createProject()">创建</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>
<div class="ctx-menu" id="ctxMenu">
  <button id="ctxCopySel">复制选中</button>
  <button id="ctxCopyMsg">复制本条</button>
  <button id="ctxCopyAll">复制全部</button>
  <div class="sep"></div>
  <button id="ctxPaste">粘贴到输入框</button>
</div>

<script>
const $ = id => document.getElementById(id);
let curBot = null;
let curBot2 = null;

function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function stripEmotionTag(t){
  const s=String(t||'');
  const m=s.match(/^\s*\[emotion:[^\]]+\]\s*/);
  if(m)return s.slice(m[0].length);
  if(/^\s*\[emotion:/.test(s))return '';
  return s;
}
const EMOTION_ZH={neutral:'平静',happy:'开心',sad:'难过',angry:'生气',
  surprised:'惊讶',thinking:'思考',loving:'温柔',sleepy:'困倦'};
function render(s){
  let h = esc(s);
  h = h.replace(/```(\w*)\n?([\s\S]*?)```/g,(_,l,c)=>'<pre><code>'+c+'</code></pre>');
  h = h.replace(/`([^`\n]+)`/g,'<code>$1</code>');
  return h;
}
function renderReply(s){
  /* 模型回复：消化 Markdown 星号/横杠，代码块原样保留 */
  const fences=[];
  let h=esc(stripEmotionTag(String(s||'')));
  h=h.replace(/```(\w*)\n?([\s\S]*?)```/g,(_,l,c)=>{
    fences.push('<pre><code>'+c+'</code></pre>');
    return '\x00F'+(fences.length-1)+'\x00';
  });
  h=h.replace(/`([^`\n]+)`/g,(_,c)=>{
    fences.push('<code>'+c+'</code>');
    return '\x00F'+(fences.length-1)+'\x00';
  });
  h=h.replace(/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/gm,'');
  h=h.replace(/^#{1,6}\s+/gm,'');
  h=h.replace(/^[\t ]*[-*+]\s+/gm,'');
  h=h.replace(/\*\*\*(.+?)\*\*\*/g,'<strong>$1</strong>');
  h=h.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
  h=h.replace(/__(.+?)__/g,'<strong>$1</strong>');
  h=h.replace(/(^|[^\*])\*(?!\s)([^*\n]+)\*(?!\*)/g,'$1$2');
  h=h.replace(/\*{1,3}/g,'');
  h=h.replace(/\x00F(\d+)\x00/g,(_,i)=>fences[i]);
  return h;
}
function toast(t){const el=$('toast');el.textContent=t;el.classList.add('show');
  setTimeout(()=>el.classList.remove('show'),2200);}

/* ---------- nav ---------- */
const SETTINGS_PAGES=['models','router','permissions','versions','privacy','settings'];
const SETTINGS_KEY='codeagent-nav-settings-open';
function go(page){
  document.querySelectorAll('.navbtn[data-page]').forEach(x=>
    x.classList.toggle('active', x.dataset.page===page));
  document.querySelectorAll('.page').forEach(x=>
    x.classList.toggle('active', x.id==='page-'+page));
  if(SETTINGS_PAGES.includes(page))setSettingsOpen(true); // 进入设置类页面自动展开
  if(page==='memory')loadMemories();
  if(page==='knowledge')loadKnowledge();
  if(page==='videoops')loadVideoOps();
  if(page==='studio')loadStudio();
  if(page==='skills')loadSkills();
  if(page==='logs')loadLogs();
  if(page==='settings')loadSettings();
  if(page==='models')loadModelsPage();
  if(page==='router')loadRouter();
  if(page==='permissions')loadPermissions();
  if(page==='versions')loadVersions();
  if(page==='privacy')loadPrivacy();
  if(page==='lead')loadRuns();
  if(page==='dashboard')loadDashboard();
  if(page==='automation')loadAutomation();
  if(page==='cron')loadCron();
  if(page==='learning')loadLearning();
  if(page==='evolution')loadEvolution();
  if(page==='project')loadProjectRecords();
  if(page==='chat'){loadProjects();loadConversations();loadModelAssets();}
  if(page==='browser')loadBrowser();
}
document.querySelectorAll('.navbtn[data-page]').forEach(b=>b.onclick=()=>go(b.dataset.page));

function applyBrowserState(st){
  if(!st||!$('browserUrl'))return;
  if(st.url)$('browserUrl').value=st.url;
  if(st.ready_text)$('browserMeta').textContent=st.ready_text;
  else if(st.error)$('browserMeta').textContent=st.error;
  if(st.excerpt!==undefined)$('browserText').textContent=st.excerpt||'（无文本）';
  const nodes=st.nodes||[];
  if(!nodes.length){
    $('browserNodes').innerHTML='<div class="empty">尚未打开页面</div>';
    return;
  }
  $('browserNodes').innerHTML=nodes.map(n=>
    '<div class="browser-node"><code>'+esc(n.ref||'')+'</code>'+
    '<span>'+esc((n.tag||'')+' '+(n.text||''))+'</span></div>'
  ).join('');
}
function loadBrowser(){
  if(!window.pywebview||!pywebview.api)return;
  pywebview.api.browser_status().then(applyBrowserState);
}
function browserGo(){
  const u=($('browserUrl').value||'').trim();
  if(!u){toast('输入网址');return;}
  pywebview.api.browser_goto(u).then(r=>{
    if(r&&r.error)toast(r.error);
    else $('browserMeta').textContent='正在打开…';
  });
}
function browserReload(){
  pywebview.api.browser_reload().then(r=>{
    if(r&&r.error)toast(r.error);
  });
}
function browserShowWin(){
  pywebview.api.browser_show_window().then(r=>{
    if(r&&!r.ok)toast(r.error||'无法打开浏览窗口');
  });
}

/* 四字对齐：两字/三字标签拉伸到四字宽度（LCA NavLabel） */
document.querySelectorAll('.navbtn').forEach(b=>{
  const nodes=[...b.childNodes].filter(n=>n.nodeType===3&&n.textContent.trim());
  nodes.forEach(n=>{
    const label=n.textContent.trim();
    const span=document.createElement('span');
    span.className='navlabel'+([...label.replace(/[\s·]/g,'')].length<4?' justify':'');
    span.textContent=label;
    n.replaceWith(span);
  });
});

/* 设置抽屉：localStorage 持久化 + 点击外部自动收起（LCA Layout.tsx） */
function setSettingsOpen(v){
  $('settingsMenu').classList.toggle('open',v);
  $('settingsChev').classList.toggle('up',v);
  try{localStorage.setItem(SETTINGS_KEY,v?'1':'0');}catch(e){}
}
$('settingsToggle').onclick=()=>{
  setSettingsOpen(!$('settingsMenu').classList.contains('open'));
};
document.addEventListener('pointerdown',e=>{
  const m=$('settingsMenu');
  if(!m.classList.contains('open'))return;
  if(!$('settingsMenu').contains(e.target)&&!$('settingsToggle').contains(e.target))
    setSettingsOpen(false);
});

/* ---------- 主题（深色 / 浅色 / 自动跟随系统，偏好设置页切换） ----------
   真相源是服务端桌面配置（启动时已注入 body class）；localStorage 只是
   会话内缓存——pywebview 隐私模式下重启即清，访问本身也可能抛异常。 */
const THEME_KEY='codeagent-theme';
const THEME_LABEL={dark:'深色',light:'浅色',auto:'自动（跟随系统）'};
const sysLight=window.matchMedia('(prefers-color-scheme: light)');
function storeGet(k){try{return localStorage.getItem(k);}catch(e){return null;}}
function storeSet(k,v){try{localStorage.setItem(k,v);}catch(e){}}
function currentTheme(){
  return storeGet(THEME_KEY)
    ||(document.body.classList.contains('light')?'light':'dark');
}
function applyTheme(t){
  const light=t==='light'||(t==='auto'&&sysLight.matches);
  document.body.classList.toggle('light',light);
  document.querySelectorAll('#themeTabs .tab').forEach(b=>
    b.classList.toggle('active',b.dataset.theme===t));
}
sysLight.addEventListener('change',()=>{
  if(currentTheme()==='auto')applyTheme('auto');  // 系统主题变化时实时跟随
});
function setTheme(t){
  applyTheme(t);
  storeSet(THEME_KEY,t);
  pywebview.api.save_config({theme:t});  // 跨重启持久化（真相源）
  toast('主题：'+THEME_LABEL[t]);
}
document.querySelectorAll('#themeTabs .tab').forEach(b=>
  b.onclick=()=>setTheme(b.dataset.theme));
// 只同步分段控件高亮；body class 以服务端注入为准，等 loadSettings 对齐
document.querySelectorAll('#themeTabs .tab').forEach(b=>
  b.classList.toggle('active',b.dataset.theme===currentTheme()));
setSettingsOpen(false);  // 每次启动默认收起设置抽屉

/* ---------- 项目工作区（文件夹 + 全量对话记录） ---------- */
function loadProjects(){
  pywebview.api.get_projects().then(d=>{
    const el=$('projectList'); el.innerHTML='';
    // 侧栏只保留「项目」一组，不再按工作/个人/学习/其他分子标题
    (d.projects||[]).forEach(p=>el.appendChild(projBtn(p,d)));
    fillProjectSelects(d);
  });
}
function fillProjectSelects(d){
  ['chatProjSel'].forEach(id=>{
    const sel=$(id); if(!sel)return;
    const keep=sel.value;
    sel.innerHTML='';
    if(!d.projects.length){
      const o=document.createElement('option');
      o.value='__new'; o.textContent='＋ 新建项目…';
      sel.appendChild(o);
      return;
    }
    d.projects.forEach(p=>{
      const o=document.createElement('option');
      o.value=p.id; o.textContent=p.name; o.title=p.path;
      if(p.id===d.active)o.selected=true;
      sel.appendChild(o);
    });
    const extra=document.createElement('option');
    extra.value='__new'; extra.textContent='＋ 新建项目…';
    sel.appendChild(extra);
    if(d.active)sel.value=d.active;
    else if(keep && [...sel.options].some(o=>o.value===keep))sel.value=keep;
  });
}
function onChatProject(pid){
  if(!pid)return;
  if(pid==='__new'){
    // 下拉先回到当前项目，再弹出新建
    loadProjects();
    openProjDialog();
    return;
  }
  switchProject(pid,false);  // 对话页内切换，留在对话
}
function projBtn(p,d){
  const b=document.createElement('button');
  b.className='navbtn proj'+(p.id===d.active?' active':'');
  b.title=p.path;
  b.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>'+
    '<span class="p-name">'+esc(p.name)+'</span>'+
    '<span class="p-del" title="从列表移除（文件夹保留）">×</span>';
  b.onclick=e=>{
    if(e.target.classList.contains('p-del')){
      if(confirm('从列表移除项目「'+p.name+'」？\n本地文件夹与全部对话记录都会保留。'))
        pywebview.api.delete_project(p.id).then(()=>{loadProjects();loadConversations();});
      return;
    }
    if(p.id!==d.active)switchProject(p.id,true);
    else{loadProjectRecords();go('project');}
  };
  return b;
}
function openProjDialog(){
  $('pj_name').value=''; $('pj_base').value='';
  $('pj_disks').innerHTML='';
  pywebview.api.get_projects().then(d=>{
    $('pj_base').placeholder=d.default_base||'';
    const box=$('pj_disks');
    const roots=d.disk_roots||[];
    if(!roots.length){
      box.textContent='未能列出硬盘，请用「选择…」浏览';
      return;
    }
    roots.forEach(r=>{
      const b=document.createElement('button');
      b.type='button'; b.className='btn';
      b.style.cssText='padding:4px 10px;font-size:12px';
      b.textContent=r.label; b.title=r.path||'';
      b.onclick=()=>setProjectBase(r.path||'');
      box.appendChild(b);
    });
  });
  $('projDialog').classList.add('open');
}
function setProjectBase(path){
  $('pj_base').value=path||'';
}
function pickProjectBase(){
  pywebview.api.pick_project_base().then(r=>{
    if(r.cancelled)return;
    if(!r.ok){toast(r.error||'无法选择文件夹');return;}
    setProjectBase(r.path);
  });
}
function createProject(){
  const name=$('pj_name').value.trim();
  if(!name){toast('请填写项目名称');return;}
  pywebview.api.create_project(name,$('pj_base').value.trim()).then(r=>{
    if(!r.ok){toast('创建失败：'+r.error);return;}
    $('projDialog').classList.remove('open');
    toast('项目已创建：'+r.project.path);
    loadProjects(); loadConversations();
    clearChat('当前项目：'+r.project.name+' · 新对话');
    if($('page-chat').classList.contains('active'))return;  // 从对话页新建则留下
    loadProjectRecords(); go('project');
  });
}
function switchProject(pid,openRecords){
  pywebview.api.switch_project(pid).then(r=>{
    if(!r.ok){toast(r.error);return;}
    toast('当前项目：'+r.project.name);
    loadProjects(); loadConversations();
    clearChat('当前项目：'+r.project.name+' · 新对话');
    if(openRecords){loadProjectRecords();go('project');}
  });
}
function loadProjectRecords(){
  pywebview.api.get_project_records().then(d=>{
    if(!d.ok){
      $('projTitle').textContent='项目记录';
      $('projSub').textContent='先新建一个项目';
      $('projStats').innerHTML='';
      $('projConvs').innerHTML='<div class="empty">暂无对话</div>';
      $('projFiles').innerHTML='<div class="empty">文件夹为空</div>';
      return;
    }
    const p=d.project;
    $('projTitle').textContent=p.name;
    $('projSub').textContent=p.category+' · '+p.path;
    $('projStats').innerHTML=
      '<div class="card stat"><div class="s-label">分类</div><div class="s-value" style="font-size:18px;padding-top:6px">'+esc(p.category)+'</div></div>'+
      '<div class="card stat"><div class="s-label">对话</div><div class="s-value">'+d.conversations.length+'</div><div class="s-sub">全部保留在项目文件夹</div></div>'+
      '<div class="card stat"><div class="s-label">文件</div><div class="s-value">'+d.files.length+'</div><div class="s-sub">files/ 与产出内容</div></div>'+
      '<div class="card stat"><div class="s-label">创建于</div><div class="s-value" style="font-size:13px;padding-top:10px">'+esc(p.created||'—')+'</div></div>';
    if(!d.conversations.length)$('projConvs').innerHTML='<div class="empty">暂无对话 — 去对话页开始，所有记录都会保留</div>';
    else $('projConvs').innerHTML=d.conversations.map(c=>
      '<button class="quick" onclick="go(\'chat\');loadConv(\''+c.id+'\')">'+
      '<span>'+esc(c.title)+'</span><span class="q-sub">'+c.count+' 条 · '+esc(c.created)+'</span></button>').join('');
    if(!d.files.length)$('projFiles').innerHTML='<div class="empty">还没有文件。对话附件会自动复制到 files/</div>';
    else $('projFiles').innerHTML=d.files.map(f=>
      '<div class="pipe-row"><span>'+esc(f.path)+'</span><span style="color:var(--faint);font-size:11px">'+esc(f.size)+' · '+esc(f.mtime)+'</span></div>').join('');
  });
}
function openProjFolder(){
  pywebview.api.open_project_folder().then(r=>{
    if(!r.ok)toast(r.error||'无法打开文件夹');
    else toast('已打开：'+r.path);
  });
}
function exportProject(){
  pywebview.api.export_project().then(r=>{
    if(r.cancelled)return;
    if(!r.ok){toast(r.error||'导出失败');return;}
    toast('已导出：'+r.path);
  });
}
function importProject(){
  pywebview.api.import_project().then(r=>{
    if(r.cancelled)return;
    if(!r.ok){toast(r.error||'导入失败');return;}
    toast('已导入：'+r.project.name);
    loadProjects(); loadConversations();
    clearChat('当前项目：'+r.project.name+' · 已导入');
    loadProjectRecords(); go('project');
  });
}
function clearChat(msg,chan){
  const C=colOf(chan||'A');
  C.col.innerHTML='';
  addChip('status',msg,chan);
  if(chan==='B')curBot2=null; else curBot=null;
}
function loadConversations(){
  pywebview.api.get_conversations().then(d=>{
    const sel=$('convPicker'); sel.innerHTML='';
    const o0=document.createElement('option');
    o0.value=''; o0.textContent=d.items.length?'历史对话（'+d.items.length+'）':'暂无历史对话';
    sel.appendChild(o0);
    d.items.forEach(c=>{
      const o=document.createElement('option');
      o.value=c.id; o.textContent=c.title+' · '+c.count+'条';
      sel.appendChild(o);
    });
    sel.value='';
  });
}
function newChat(){
  pywebview.api.new_conversation().then(()=>{
    clearChat('新对话已开始'); loadConversations();
  });
}
function loadConv(id){
  if(!id)return;
  pywebview.api.load_conversation(id).then(r=>{
    if(!r.ok)return;
    clearChat('已载入历史对话（继续聊会自动带上前文）');
    replayConvMessages(r.messages,'A');
  });
}
function loadConv2(id){
  if(!id)return;
  pywebview.api.load_conversation2(id).then(r=>{
    if(!r.ok)return;
    clearChat('已载入历史对话（继续聊会自动带上前文）','B');
    replayConvMessages(r.messages,'B');
  });
}
function markThinkDone(chan){
  const C=colOf(chan||'A');
  C.col.querySelectorAll('.chip-wrap.think-wrap').forEach(w=>w.classList.add('think-done'));
}
function replayConvMessages(messages,chan){
  (messages||[]).forEach(m=>{
    const role=m.role||'';
    if(role==='user'){
      markThinkDone(chan);
      addMsg('user',m.text||'',chan);
    }else if(role==='assistant'){
      addMsg('bot',m.text||'',chan);
      markThinkDone(chan);
    }else if(role==='thinking'){
      addThink(m.text||'',chan);
    }else if(role==='tool'){
      addThinkTool(m.name||m.text||'',chan);
    }
  });
  markThinkDone(chan);
}
function loadConversations2(){
  const sel=$('convPickerB'); if(!sel)return;
  pywebview.api.get_conversations().then(d=>{
    sel.innerHTML='';
    const o0=document.createElement('option');
    o0.value=''; o0.textContent=d.items.length?'历史对话（'+d.items.length+'）':'暂无历史对话';
    sel.appendChild(o0);
    d.items.forEach(c=>{
      const o=document.createElement('option');
      o.value=c.id; o.textContent=c.title+' · '+c.count+'条';
      sel.appendChild(o);
    });
    sel.value='';
  });
}
function newChatB(){
  pywebview.api.new_conversation2().then(()=>{
    clearChat('新对话 B 已开始','B'); loadConversations2();
  });
}

/* 侧栏底部状态区 */
function loadNavStatus(){
  if(!window.pywebview||!window.pywebview.api)return;
  pywebview.api.get_nav_status().then(s=>{
    if(!s)return;
    const localN=s.running||0, localE=s.local||0;
    const apiOn=s.online||0, apiN=s.api||0;
    $('nsLocal').textContent=localN?localN+' 运行中':(localE?localE+' 已接入':'0');
    $('nsApi').textContent=apiOn?apiOn+' 在线':(apiN?apiN+' 已接入':'0');
    $('nsMix').textContent=(s.mixtures||0)+' 启用';
    if(s.active)$('footProvider').textContent=s.active;
  }).catch(()=>{});
}

/* ---------- dashboard ---------- */
function loadDashboard(){
  pywebview.api.get_overview().then(o=>{
    $('stVersion').textContent='v'+o.version;
    $('stDate').textContent=o.date;
    $('stProvider').textContent=o.provider;
    $('stModel').textContent=o.model;
    $('stSkills').textContent=o.skills+' / '+o.memories;
    $('stHarness').textContent=o.harnesses;
    $('footProvider').textContent=o.active_label||o.provider||'—';
    const el=$('dashRuns');
    if(!o.recent_runs.length){el.innerHTML='<div class="empty">暂无记录</div>';return;}
    el.innerHTML=o.recent_runs.map(r=>'<div class="run-item"><b>'+
      esc(r.command||'')+'</b><br>'+esc(r.run_id||'')+'</div>').join('');
  });
}

/* ---------- chat ---------- */
function colOf(chan){ const b=chan==='B'; return {chat:b?$('chatB'):$('chat'), col:b?$('chatColB'):$('chatCol')}; }
function addMsg(cls,text,chan){
  const C=colOf(chan||'A');
  const div=document.createElement('div');
  div.className='msg '+cls; div.innerHTML=cls==='bot'?renderReply(text):render(text);
  div._raw=text;
  const wrap=document.createElement('div');
  wrap.className='msg-wrap '+cls;
  const bar=document.createElement('div');
  bar.className='msg-actions';
  bar.innerHTML='<button class="ma-btn" data-a="copy">📋 复制</button>'+
    (cls==='bot'?'<button class="ma-btn" data-a="speak">🔊 回播</button>':'')+
    '<button class="ma-btn" data-a="share">↗ 分享</button>';
  bar.querySelector('[data-a=copy]').onclick=()=>copyPlain(div.innerText||div._raw||'');
  const sp=bar.querySelector('[data-a=speak]');
  if(sp) sp.onclick=()=>speakText(div._raw||div.innerText||'');
  bar.querySelector('[data-a=share]').onclick=()=>{
    pywebview.api.export_message(div._raw||'').then(r=>{
      if(r.ok)toast('已导出：'+r.path);
      else if(r.error)toast('导出失败：'+r.error);
    });
  };
  wrap.appendChild(div); wrap.appendChild(bar);
  if(cls==='bot'){
    const disc=document.createElement('div');
    disc.className='msg-disclaimer';
    disc.textContent='此内容由智能体模型提供。';
    wrap.appendChild(disc);
  }
  C.col.appendChild(wrap); C.chat.scrollTop=C.chat.scrollHeight;
  return div;
}
function copyPlain(text){
  const t=String(text||'');
  if(!t){toast('没有可复制的内容');return;}
  const done=ok=>toast(ok?'已复制到剪贴板':'复制失败');
  const viaDom=()=>{
    try{
      const ta=document.createElement('textarea');
      ta.value=t; ta.setAttribute('readonly','');
      ta.style.cssText='position:fixed;left:-9999px;top:0';
      document.body.appendChild(ta);
      ta.focus(); ta.select(); ta.setSelectionRange(0,t.length);
      const ok=document.execCommand('copy');
      document.body.removeChild(ta);
      return !!ok;
    }catch(err){return false;}
  };
  // pywebview 的 navigator.clipboard 常报成功却写不进系统剪贴板，必须走 pbcopy/clip
  if(window.pywebview&&pywebview.api&&pywebview.api.copy_text){
    pywebview.api.copy_text(t).then(ok=>{
      if(ok) done(true);
      else if(viaDom()) done(true);
      else done(false);
    }).catch(()=>{ done(viaDom()); });
    return;
  }
  if(viaDom()){done(true);return;}
  if(window.navigator&&navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(t).then(()=>done(true)).catch(()=>done(false));
    return;
  }
  done(false);
}

/* ---------- 对话右键菜单（鼠标复制粘贴） ---------- */
let _ctxMsg=null, _ctxSel='', _pasteTarget=null;
function hideCtx(){const m=$('ctxMenu');if(m)m.classList.remove('open');}
function composerInput(){
  if(_pasteTarget&&document.body.contains(_pasteTarget))return _pasteTarget;
  const a=document.activeElement;
  if(a&&(a.tagName==='TEXTAREA'||a.tagName==='INPUT')&&a.id!=='ctxPaste')return a;
  return $('input')||$('inputB');
}
function insertAtCursor(inp,t){
  if(!inp)return;
  inp.focus();
  const s=typeof inp.selectionStart==='number'?inp.selectionStart:inp.value.length;
  const e=typeof inp.selectionEnd==='number'?inp.selectionEnd:s;
  inp.value=inp.value.slice(0,s)+t+inp.value.slice(e);
  const p=s+t.length;
  try{inp.selectionStart=inp.selectionEnd=p;}catch(err){}
}
function ctxCopy(what){
  let text='';
  if(what==='sel') text=_ctxSel||(_ctxMsg?(_ctxMsg.innerText||_ctxMsg._raw):'');
  else if(what==='msg') text=_ctxMsg?(_ctxMsg.innerText||_ctxMsg._raw):'';
  else text=chatPlainText();
  if(!text){toast('没有可复制的内容');return;}
  copyPlain(text);
  hideCtx();
}
function ctxPaste(){
  const inp=composerInput();
  const read=()=>{
    if(window.pywebview&&pywebview.api&&pywebview.api.read_clipboard)
      return pywebview.api.read_clipboard().catch(()=>'');
    if(window.navigator&&navigator.clipboard&&navigator.clipboard.readText)
      return navigator.clipboard.readText();
    return Promise.resolve('');
  };
  read().then(t=>{
    if(!t){toast('剪贴板为空');return;}
    if(!inp){toast('没有输入框');return;}
    insertAtCursor(inp,t);
    toast('已粘贴');
  }).catch(()=>toast('读取剪贴板失败'));
  hideCtx();
}
document.addEventListener('focusin',e=>{
  const t=e.target;
  if(t&&(t.id==='input'||t.id==='inputB'||t.tagName==='TEXTAREA'||t.tagName==='INPUT'))
    _pasteTarget=t;
});
document.addEventListener('contextmenu',e=>{
  const t=e.target;
  const inField=t&&t.closest&&t.closest('textarea,input');
  const chatOn=$('page-chat')&&$('page-chat').classList.contains('active');
  if(!inField&&!chatOn)return;
  e.preventDefault();
  const sel=window.getSelection();
  _ctxSel=(sel&&sel.rangeCount&&!sel.isCollapsed)?sel.toString():'';
  if(inField&&typeof t.selectionStart==='number'&&t.selectionStart!==t.selectionEnd)
    _ctxSel=t.value.slice(t.selectionStart,t.selectionEnd);
  _ctxMsg=t&&t.closest?t.closest('.msg'):null;
  const m=$('ctxMenu'); if(!m)return;
  m.style.left=Math.min(e.clientX, innerWidth-168)+'px';
  m.style.top=Math.min(e.clientY, innerHeight-160)+'px';
  m.classList.add('open');
});
document.addEventListener('click',e=>{
  if(e.target&&e.target.closest&&e.target.closest('#ctxMenu'))return;
  hideCtx();
});
document.addEventListener('keydown',e=>{
  if(e.key==='Escape')hideCtx();
  // ⌘/Ctrl+C/V/X 交给系统（WKWebView 需打开 DOMPasteAllowed）
});
['ctxCopySel','ctxCopyMsg','ctxCopyAll'].forEach(id=>{
  const el=$(id); if(el)el.onclick=()=>ctxCopy(id==='ctxCopySel'?'sel':id==='ctxCopyMsg'?'msg':'all');
});
const _pasteEl=$('ctxPaste'); if(_pasteEl)_pasteEl.onclick=ctxPaste;
const _ctxMenu=$('ctxMenu');
if(_ctxMenu)_ctxMenu.addEventListener('mousedown',e=>e.preventDefault());
function chatPlainText(chan){
  const C=colOf(chan||'A');
  const parts=[];
  Array.from(C.col.children).forEach(el=>{
    if(el.classList.contains('msg-wrap')){
      const msg=el.querySelector('.msg');
      const raw=(msg&&(msg.innerText||msg._raw))||'';
      if(!raw)return;
      parts.push((el.classList.contains('user')?'你':'助手')+'：\n'+raw);
    }else if(el.classList.contains('chip')||el.classList.contains('chip-wrap')){
      const think=el.querySelector&&el.querySelector('.think-block');
      if(think){
        const raw=think._raw||think.innerText||'';
        if(raw)parts.push(raw);
        return;
      }
      const chip=el.classList.contains('chip')?el:el.querySelector('.chip');
      const raw=(chip&&(chip._raw||chip.textContent))||'';
      if(raw)parts.push(raw);
    }
  });
  return parts.join('\n\n');
}
function copyChatAll(){ copyPlain(chatPlainText()); }
function copyChatAllB(){ copyPlain(chatPlainText('B')); }
function setSpeakingUi(on){
  const show=!!on;
  window._speakingUi=show;
  // 回播键就地变成「停止播报」，避免页眉挤出屏幕看不到
  [['replayBtn',null],['replayBtnB','B']].forEach(pair=>{
    const r=$(pair[0]); if(!r)return;
    if(show){
      r.textContent='停止播报';
      r.classList.add('danger');
      r.style.color='var(--bad)';
      r.style.borderColor='var(--bad)';
      r.title='停止当前语音播报';
      r.disabled=false;
      r.onclick=()=>stopSpeak();
    }else{
      r.textContent='回播';
      r.classList.remove('danger');
      r.style.color='';
      r.style.borderColor='';
      r.title='朗读最近一条助手回复';
      r.disabled=false;
      const ch=pair[1];
      r.onclick=()=>replayLast(ch||undefined);
    }
  });
  // 输入栏旁再放一颗，保证视线落在发送区也能停
  ['stopSpeakTool','stopSpeakToolB'].forEach(id=>{
    const b=$(id); if(!b)return;
    b.style.display=show?'inline-block':'none';
    b.disabled=!show;
  });
  // 消息气泡上的「🔊 回播」同步成停止
  document.querySelectorAll('.ma-btn[data-a=speak]').forEach(btn=>{
    if(show){
      btn.textContent='⏹ 停止播报';
      btn.dataset.wasSpeak='1';
      btn.onclick=()=>stopSpeak();
    }else if(btn.dataset.wasSpeak){
      btn.textContent='🔊 回播';
      delete btn.dataset.wasSpeak;
      const wrap=btn.closest('.msg-wrap');
      const msg=wrap&&wrap.querySelector('.msg');
      btn.onclick=()=>speakText((msg&&(msg._raw||msg.innerText))||'');
    }
  });
}
function stopSpeak(){
  if(window.pywebview&&pywebview.api&&pywebview.api.stop_speaking)
    pywebview.api.stop_speaking();
  setSpeakingUi(false);
  toast('已停止播报');
}
function speakText(t){
  const text=String(t||'').trim();
  if(!text){toast('没有可播报的内容');return;}
  if(window.pywebview&&pywebview.api&&pywebview.api.speak_text){
    setSpeakingUi(true);
    pywebview.api.speak_text(text);
    toast('正在回播 · 可点「停止播报」');
  }else toast('当前窗口不能播报');
}
function replayLast(chan){
  if(window._speakingUi){ stopSpeak(); return; }
  const C=colOf(chan||'A');
  const bots=C.col.querySelectorAll('.msg-wrap.bot .msg');
  const last=bots.length?bots[bots.length-1]:null;
  speakText((last&&(last._raw||last.innerText))||'');
}
function addChip(cls,text,chan){
  const C=colOf(chan||'A');
  const wrap=document.createElement('div');
  wrap.className='chip-wrap';
  const div=document.createElement('div');
  div.className='chip '+cls; div.textContent=text; div._raw=text;
  const bar=document.createElement('div');
  bar.className='msg-actions';
  bar.innerHTML='<button class="ma-btn" data-a="copy">📋 复制</button>';
  bar.querySelector('[data-a=copy]').onclick=()=>copyPlain(text);
  wrap.appendChild(div); wrap.appendChild(bar);
  C.col.appendChild(wrap); C.chat.scrollTop=C.chat.scrollHeight;
}
function ensureThink(chan){
  const C=colOf(chan||'A');
  let wrap=C.col.querySelector('.chip-wrap.think-wrap:not(.think-done)');
  let det, sum, reason, tools;
  if(wrap){
    det=wrap.querySelector('.think-block');
    sum=det&&det.querySelector('summary');
    reason=det&&det.querySelector('.think-reason');
    tools=det&&det.querySelector('.think-tools');
  }
  if(!det||!sum||!reason||!tools){
    wrap=document.createElement('div');
    wrap.className='chip-wrap think-wrap';
    det=document.createElement('details');
    det.className='think-block';
    sum=document.createElement('summary');
    sum.textContent='思考过程';
    const body=document.createElement('div');
    body.className='think-body';
    reason=document.createElement('div');
    reason.className='think-reason';
    tools=document.createElement('ul');
    tools.className='think-tools';
    body.appendChild(reason); body.appendChild(tools);
    det.appendChild(sum); det.appendChild(body);
    const bar=document.createElement('div');
    bar.className='msg-actions';
    bar.innerHTML='<button class="ma-btn" data-a="copy">📋 复制</button>';
    bar.querySelector('[data-a=copy]').onclick=()=>copyPlain(det._raw||'');
    wrap.appendChild(det); wrap.appendChild(bar);
    C.col.appendChild(wrap);
  }
  return {C:C, wrap:wrap, det:det, sum:sum, reason:reason, tools:tools};
}
function syncThinkMeta(t){
  const n=t.tools.children.length;
  t.sum.textContent=n?('思考过程 · '+n+' 步'):'思考过程';
  const parts=['思考过程'];
  if(t.reason._raw)parts.push(String(t.reason._raw));
  Array.from(t.tools.children).forEach(li=>{
    if(li._raw||li.textContent)parts.push(li._raw||li.textContent);
  });
  t.det._raw=parts.join('\\n');
  t.C.chat.scrollTop=t.C.chat.scrollHeight;
}
function addThink(text,chan){
  const raw=String(text||'').trim();
  if(!raw)return;
  const t=ensureThink(chan);
  t.reason._raw=raw;
  t.reason.innerHTML=render(raw);
  syncThinkMeta(t);
}
function addThinkTool(name,chan){
  const label=String(name||'').trim();
  if(!label)return;
  const t=ensureThink(chan);
  const li=document.createElement('li');
  li.textContent='🔧 '+label;
  li._raw='🔧 '+label;
  t.tools.appendChild(li);
  syncThinkMeta(t);
}
/* ---------- 附件（所有文件类型识别） ---------- */
let atts=[];
const ATT_ICON={text:'📄',pdf:'📕',docx:'📝',xlsx:'📊',pptx:'📽',image:'🖼',binary:'📦'};
function renderAtts(){
  const row=$('attRow');
  if(!atts.length){row.style.display='none';row.innerHTML='';return;}
  row.style.display='flex'; row.innerHTML='';
  atts.forEach((a,i)=>{
    const c=document.createElement('span');
    c.className='att-chip';
    c.title=a.note?a.name+' — '+a.note:a.name;
    c.innerHTML=(ATT_ICON[a.kind]||'📦')+' '+esc(a.name)+' <b>'+esc(a.size)+'</b> <i>×</i>';
    c.querySelector('i').onclick=()=>{
      pywebview.api.remove_attachment(i).then(r=>{atts=r;renderAtts();});
    };
    row.appendChild(c);
  });
}
$('attBtn').onclick=()=>{
  pywebview.api.pick_attachments().then(r=>{atts=r;renderAtts();});
};

let voiceOn=false, rec=null, voiceBusy=false, voiceExitAfter=false;
const VOICE_EXIT=/^(再见|拜拜|退出|停止语音|quit|exit|bye)[。.!?！]?$/i;
function speechEngine(){
  return window.SpeechRecognition||window.webkitSpeechRecognition||null;
}
function hideMicPermDialog(){
  const d=$('micPermDialog'); if(d)d.classList.remove('open');
}
function showMicPermDialog(msg, path){
  const m=$('micPermMsg');
  if(m)m.textContent=msg||'请打开本软件的麦克风与语音识别开关。';
  const p=$('micPermPath');
  if(p){
    const title=path||'系统设置 → 隐私与安全性 → 麦克风 / 语音识别 → CodeCoreAgent';
    const speech=String(title).indexOf('语音识别')>=0;
    p.innerHTML='<b>'+esc(title)+'</b><br>打开列表里的 <b>CodeCoreAgent</b><br>'+
      (speech
        ?'<span style="color:var(--warn);font-size:12px">只开麦克风不够：必须同时打开「语音识别」，说的话才能进输入框。</span><br>'
        :'<span style="color:var(--warn);font-size:12px">注意：LunarCore Agent 是另一个软件，不要只开它。</span><br>')+
      '<span style="color:var(--faint);font-size:11.5px">若列表还没有 CodeCoreAgent：先点「允许并开始语音」，再回系统设置刷新。</span>';
  }
  const d=$('micPermDialog'); if(d)d.classList.add('open');
}
function openSystemMicSettings(){
  // 先触发一次授权，让 CodeCoreAgent 出现在系统麦克风/语音识别列表里
  const openPage=()=>{
    if(!(window.pywebview&&pywebview.api)){
      toast('当前窗口无法打开系统设置'); return;
    }
    const opener=pywebview.api.open_speech_settings||pywebview.api.open_mic_settings;
    if(!opener){ toast('当前窗口无法打开系统设置'); return; }
    opener().then(r=>{
      const path=(r&&r.path)||'系统设置 → 隐私与安全性 → 麦克风 / 语音识别 → CodeCoreAgent';
      showMicPermDialog((r&&r.hint)||'已打开系统隐私页，请打开 CodeCoreAgent 开关。', path);
      toast(r&&r.ok?'已打开系统隐私设置':'无法打开系统设置');
    }).catch(()=>toast('无法打开系统设置'));
  };
  requestBrowserMic().then(()=>{ openPage(); }).catch(()=>{ openPage(); });
}
function requestBrowserMic(){
  if(!(navigator.mediaDevices&&navigator.mediaDevices.getUserMedia))
    return Promise.reject(new Error('no-getUserMedia'));
  return navigator.mediaDevices.getUserMedia({audio:true}).then(stream=>{
    try{stream.getTracks().forEach(t=>t.stop());}catch(e){}
    return true;
  });
}
function allowMicAndStart(){
  const fail=()=>{
    const msg=$('micPermMsg');
    if(msg)msg.textContent='系统未授予麦克风。请打开「麦克风」页里的 CodeCoreAgent（不是 LunarCore Agent）。';
    toast('没有麦克风权限');
    openSystemMicSettings();
  };
  const afterNative=(r)=>{
    if(r&&r.ok){ hideMicPermDialog(); beginVoiceSession(); return; }
    requestBrowserMic().then(()=>{
      hideMicPermDialog();
      beginVoiceSession();
    }).catch(fail);
  };
  if(window.pywebview&&pywebview.api&&pywebview.api.request_mic_access){
    toast('正在向系统申请麦克风权限…');
    pywebview.api.request_mic_access().then(afterNative).catch(()=>afterNative(null));
    return;
  }
  requestBrowserMic().then(()=>{
    hideMicPermDialog();
    beginVoiceSession();
  }).catch(fail);
}
function toggleVoice(){
  if(voiceOn){ stopVoice(); return; }
  // 点击麦克风：先弹出权限设置；已授权则直接开语音
  if(window.pywebview&&pywebview.api&&pywebview.api.ensure_mic_permission){
    pywebview.api.ensure_mic_permission().then(r=>{
      if(r&&r.ok){ beginVoiceSession(); return; }
      showMicPermDialog(r&&r.message, r&&r.path);
      // 未决定时立刻触发系统授权弹窗；已拒绝则上面 API 已打开系统设置
      if(r&&!r.open_settings){
        requestBrowserMic().then(()=>{
          hideMicPermDialog();
          beginVoiceSession();
        }).catch(()=>{});
      }
    }).catch(()=>showMicPermDialog());
    return;
  }
  showMicPermDialog();
  requestBrowserMic().then(()=>{
    hideMicPermDialog();
    beginVoiceSession();
  }).catch(()=>{});
}
function beginVoiceSession(){
  voiceOn=true; voiceBusy=false; voiceExitAfter=false;
  if($('micBtn'))$('micBtn').classList.add('on');
  pywebview.api.set_voice_session(true);
  addChip('status','连续语音已开 — 说完一句我会想、说、再听');
  startListen();
}
function startVoice(){ toggleVoice(); }
function stopVoice(){
  voiceOn=false; voiceBusy=false; voiceExitAfter=false;
  try{if(rec)rec.stop();}catch(e){}
  rec=null;
  if($('micBtn'))$('micBtn').classList.remove('on');
  if(window.pywebview&&pywebview.api){
    if(pywebview.api.stop_native_listen) pywebview.api.stop_native_listen();
    pywebview.api.set_voice_session(false);
    pywebview.api.stop_speaking();
  }
  addChip('status','连续语音已关');
}
function startWebListen(){
  if(!voiceOn||voiceBusy)return;
  const SR=speechEngine();
  if(!SR){
    toast('当前窗口没有浏览器听写，已改用系统听写');
    startNativeListen();
    return;
  }
  try{if(rec)rec.stop();}catch(e){}
  rec=new SR();
  rec.lang='zh-CN';
  rec.interimResults=true;
  rec.continuous=false;
  rec.onresult=function(e){
    let t='';
    for(let i=0;i<e.results.length;i++) t+=e.results[i][0].transcript;
    if($('input'))$('input').value=t;
    if(e.results[e.results.length-1].isFinal){
      const text=t.trim();
      if(text) sendVoiceUtterance(text);
    }
  };
  rec.onerror=function(e){
    if(e.error==='not-allowed'||e.error==='service-not-allowed'){
      // WKWebView 常误报；改走系统 Speech 框架
      startNativeListen();
      return;
    }
    if((e.error==='no-speech'||e.error==='aborted') && voiceOn && !voiceBusy)
      setTimeout(startListen, 280);
  };
  rec.onend=function(){
    rec=null;
    if(voiceOn && !voiceBusy) setTimeout(startListen, 220);
  };
  try{rec.start();}catch(e){ startNativeListen(); }
}
function startNativeListen(){
  if(!voiceOn||voiceBusy)return;
  if(!(window.pywebview&&pywebview.api&&pywebview.api.start_native_listen)){
    toast('没有可用的听写引擎');
    showMicPermDialog('当前环境不能听写。请确认已安装并允许麦克风与语音识别。');
    stopVoice();
    return;
  }
  addChip('status','正在听…（系统听写）');
  pywebview.api.start_native_listen('zh-CN').then(r=>{
    if(r&&r.ok) return;
    const msg=(r&&r.error)||'无法启动系统听写';
    toast(msg);
    if(r&&r.open_settings){
      showMicPermDialog(msg, r.path);
      if(window.pywebview&&pywebview.api){
        const openSpeech=String(r.path||msg).indexOf('语音识别')>=0
          && pywebview.api.open_speech_settings;
        (openSpeech?pywebview.api.open_speech_settings():pywebview.api.open_mic_settings)();
      }
    }else showMicPermDialog(msg);
  }).catch(err=>{
    toast('系统听写失败');
    showMicPermDialog(String(err||'系统听写失败'));
  });
}
function startListen(){
  if(!voiceOn||voiceBusy)return;
  // 桌面端优先系统听写：WKWebView 的 webkitSpeechRecognition 经常假报没权限
  if(window.pywebview&&pywebview.api&&pywebview.api.start_native_listen){
    startNativeListen();
    return;
  }
  startWebListen();
}
function sendVoiceUtterance(text){
  voiceBusy=true;
  try{if(rec)rec.abort();}catch(e){}
  if(window.pywebview&&pywebview.api&&pywebview.api.stop_native_listen)
    pywebview.api.stop_native_listen();
  if($('input'))$('input').value='';
  addMsg('user', text);
  addChip('status','说完了 — 正在想并准备语音回答…');
  setChatBusy(true);
  if(VOICE_EXIT.test(text)) voiceExitAfter=true;
  pywebview.api.send(text).then(ok=>{
    if(!ok){
      addChip('error','上一条还在处理中');
      setChatBusy(false); voiceBusy=false;
      if(voiceOn) startListen();
    }
  });
}

/* ---------- 思考强度 ---------- */
function setThinking(v){
  pywebview.api.save_config({thinking:v}).then(()=>
    toast('思考强度：'+{low:'低',medium:'中',high:'高'}[v]));
}

function setChatBusy(on,chan){
  const b=chan==='B';
  $(b?'sendBtnB':'sendBtn').disabled=!!on;
  $(b?'stopBtnB':'stopBtn').disabled=!on;
  if(on){
    // 新一轮开始：上一轮思考块封存，本轮只显示一块
    const C=colOf(chan||'A');
    C.col.querySelectorAll('.chip-wrap.think-wrap').forEach(w=>w.classList.add('think-done'));
  }
}
function isVideoModelSelected(){
  const sel=$('modelPicker');
  if(!sel||sel.selectedIndex<0)return false;
  const opt=sel.options[sel.selectedIndex];
  return !!(opt&&(opt.dataset.kind==='gradio'||opt.dataset.kind==='video-api'));
}
function syncVideoGenBar(){
  const on=isVideoModelSelected();
  const bar=$('videoGenBar');
  if(bar)bar.classList.toggle('is-off',!on);
  ['vg_res','vg_frames','vg_steps'].forEach(id=>{
    const el=$(id); if(el)el.disabled=!on;
  });
  if($('thinkingSel'))$('thinkingSel').disabled=on;
  const inp=$('input');
  if(inp)inp.placeholder=on
    ?'描述要生成的画面，Enter 发送生成视频'
    :'输入消息，Enter 发送，Shift+Enter 换行；📎 可附加任意文件';
}
function sendChat(){
  const text=$('input').value.trim();
  if(!text&&!atts.length)return;
  addMsg('user',text||atts.map(a=>'📎 '+a.name).join('、'));
  $('input').value=''; setChatBusy(true); curBot=null;
  const res=($('vg_res')&&$('vg_res').value)||'720p';
  const frames=parseInt(($('vg_frames')&&$('vg_frames').value)||'60',10);
  const steps=parseInt(($('vg_steps')&&$('vg_steps').value)||'50',10);
  pywebview.api.send(text, res, frames, steps).then(ok=>{
    if(!ok){addChip('error','上一条还在处理中');setChatBusy(false);}
    else{atts=[];renderAtts();}
  });
}
function stopChat(){
  $('stopBtn').disabled=true;
  pywebview.api.stop().then(ok=>{ if(!ok)setChatBusy(false); });
}
function sendChatB(){
  const text=$('inputB').value.trim();
  if(!text)return;
  addMsg('user',text,'B');
  $('inputB').value=''; setChatBusy(true,'B'); curBot2=null;
  pywebview.api.send2(text).then(ok=>{
    if(!ok){addChip('error','上一条还在处理中','B');setChatBusy(false,'B');}
  });
}
function stopChatB(){
  $('stopBtnB').disabled=true;
  pywebview.api.stop2().then(ok=>{ if(!ok)setChatBusy(false,'B'); });
}
let dualOn=false;
$('dualBtn').onclick=()=>{
  dualOn=!dualOn;
  $('page-chat').classList.toggle('page-chat-dual',dualOn);
  const cb=$('colB'); cb.style.display=dualOn?'flex':'none';
  if(dualOn){
    if(!$('chatColB').childElementCount)addChip('status','对话 B 就绪 — 可并行提问','B');
    loadConversations2();
  }
  // 双面板需要更宽视口：开启加宽 0.5 倍，关闭还原
  if(window.pywebview&&window.pywebview.api)
    pywebview.api.set_dual_mode(dualOn);
};
function openSecondWindow(){
  pywebview.api.open_second_window().then(r=>{
    if(r&&r.ok)toast(r.already?'对话 B 窗口已存在':'已打开对话 B 窗口');
    else toast('打开对话 B 窗口失败');
  });
}
$('input').addEventListener('keydown',e=>{
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChat();}
});
$('inputB').addEventListener('keydown',e=>{
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChatB();}
});
document.addEventListener('keydown',e=>{
  if(!(e.metaKey||e.ctrlKey)||(e.key!=='a'&&e.key!=='A'))return;
  if(!$('page-chat').classList.contains('active'))return;
  const tag=(document.activeElement&&document.activeElement.tagName)||'';
  if(tag==='INPUT'||tag==='TEXTAREA'||tag==='SELECT')return;
  e.preventDefault();
  const range=document.createRange();
  range.selectNodeContents($('chatCol'));
  const sel=window.getSelection();
  sel.removeAllRanges(); sel.addRange(range);
});

/* 赞/踩反馈（LCA：对话页反馈即时计入活动流） */
function addFeedbackRow(chan){
  const C=colOf(chan||'A');
  const row=document.createElement('div');
  row.className='fb-row';
  row.innerHTML='<button class="fb-btn" data-v="1">👍 有用</button>'+
    '<button class="fb-btn" data-v="0">👎 不行</button>';
  row.querySelectorAll('.fb-btn').forEach(b=>b.onclick=()=>{
    const up=b.dataset.v==='1';
    pywebview.api.send_feedback(up).then(()=>{
      row.querySelectorAll('.fb-btn').forEach(x=>x.disabled=true);
      b.classList.add(up?'voted-up':'voted-down');
      toast(up?'已记录正向反馈':'已记录：这条回复不行');
    });
  });
  C.col.appendChild(row);
  C.chat.scrollTop=C.chat.scrollHeight;
}

/* ---------- leader ---------- */
function sendLead(){
  const text=$('leadInput').value.trim(); if(!text)return;
  $('leadBtn').disabled=true;
  $('taskList').innerHTML='<div class="empty">领导规划中…</div>';
  pywebview.api.lead(text).then(ok=>{
    if(!ok){toast('上一个指挥任务还在进行');$('leadBtn').disabled=false;}
  });
}
function upsertTask(t){
  let list=$('taskList');
  if(list.querySelector('.empty'))list.innerHTML='';
  let el=document.getElementById('task-'+t.id);
  if(!el){
    el=document.createElement('div');
    el.id='task-'+t.id; el.className='task';
    el.innerHTML='<span class="dot"></span><span class="t-title"></span><span class="t-worker"></span>';
    list.appendChild(el);
  }
  el.className='task st-'+t.status;
  el.querySelector('.t-title').textContent=t.title;
  el.querySelector('.t-worker').textContent=t.worker+' · '+t.status;
  if(t.detail)el.title=t.detail;
}
function loadRuns(){
  pywebview.api.get_runs().then(runs=>{
    const el=$('runList');
    if(!runs.length){el.innerHTML='<div class="empty">暂无记录</div>';return;}
    el.innerHTML=runs.map(r=>'<div class="run-item"><b>'+esc(r.command||'')+
      '</b><br>'+esc(r.run_id||'')+'</div>').join('');
  });
}

/* ---------- memory ---------- */
function loadMemories(){
  pywebview.api.get_memories($('memQuery').value).then(items=>{
    const el=$('memList');
    if(!items.length){el.innerHTML='<div class="empty">暂无记忆</div>';return;}
    el.innerHTML='';
    items.forEach(m=>{
      const div=document.createElement('div');
      div.className='card mem';
      const time=m.created_at?new Date(m.created_at*1000).toLocaleString():'';
      div.innerHTML='<div class="m-body">'+esc(m.content)+
        '<div class="m-time">'+time+'</div></div>'+
        '<button class="m-del" title="删除">×</button>';
      div.querySelector('.m-del').onclick=()=>{
        pywebview.api.delete_memory(m.id).then(()=>div.remove());
      };
      el.appendChild(div);
    });
  });
}
function addMemory(){
  const text=prompt('要记住的内容：'); if(!text)return;
  pywebview.api.add_memory(text).then(ok=>{if(ok)loadMemories();});
}
$('memQuery').addEventListener('keydown',e=>{if(e.key==='Enter')loadMemories();});

/* ---------- knowledge (Obsidian / LLM Wiki) ---------- */
function fillKbDiskChips(boxId, inputId, roots){
  const box=$(boxId); if(!box)return;
  box.innerHTML='';
  const list=roots||[];
  if(!list.length){
    box.textContent='未能列出硬盘，请用「选择…」浏览（局域网盘需先挂载）';
    return;
  }
  list.forEach(r=>{
    const b=document.createElement('button');
    b.type='button'; b.className='btn';
    b.style.cssText='padding:4px 10px;font-size:12px';
    if(r.kind==='network'){
      b.style.borderColor='var(--accent, #3b82f6)';
      b.textContent='🖧 '+r.label;
    }else{
      b.textContent=r.label;
    }
    b.title=(r.path||'')+(r.kind==='network'?'（局域网/NAS）':'');
    b.onclick=()=>{
      const inp=$(inputId); if(inp)inp.value=r.path||'';
      if(r.kind==='network'){
        if($('kb_mode'))$('kb_mode').value='shared';
        if($('cfg_kb_mode'))$('cfg_kb_mode').value='shared';
        updateKbHint(); updateCfgKbHint();
      }
    };
    box.appendChild(b);
  });
}
function setKnowledgePathFields(d){
  const c=d.config||{};
  if($('kb_path')){
    $('kb_path').value=c.path||'';
    $('kb_path').placeholder=d.default_path||'';
  }
  if($('kb_mode'))$('kb_mode').value=c.mode||'local';
  if($('kb_backend'))$('kb_backend').value=c.backend||'obsidian';
  if($('kb_enabled'))$('kb_enabled').checked=c.enabled!==false;
  if($('cfg_kb_path')){
    $('cfg_kb_path').value=c.path||'';
    $('cfg_kb_path').placeholder=d.default_path||'';
  }
  if($('cfg_kb_mode'))$('cfg_kb_mode').value=c.mode||'local';
  if($('cfg_kb_enabled'))$('cfg_kb_enabled').checked=c.enabled!==false;
  if(d.network){
    if($('kb_mode'))$('kb_mode').value='shared';
    if($('cfg_kb_mode'))$('cfg_kb_mode').value='shared';
  }
  fillKbDiskChips('kb_disks','kb_path',d.disk_roots||[]);
  fillKbDiskChips('cfg_kb_disks','cfg_kb_path',d.disk_roots||[]);
  updateKbHint(); updateCfgKbHint();
}
function loadKnowledge(){
  pywebview.api.get_knowledge().then(d=>{
    setKnowledgePathFields(d);
    const s=d.status||{};
    const pills=[];
    pills.push(s.ready?'<span class="pill green">已自动部署</span>':'<span class="pill amber">未就绪</span>');
    if(d.network|| (d.config&&d.config.mode==='shared'))
      pills.push('<span class="pill blue">局域网/共享</span>');
    pills.push(s.exists?'<span class="pill">路径存在</span>':'<span class="pill">路径不存在</span>');
    pills.push(s.writable?'<span class="pill green">可写</span>':'<span class="pill">只读/不可写</span>');
    if(s.has_obsidian)pills.push('<span class="pill blue">Obsidian</span>');
    pills.push('<span class="pill">'+(s.page_count<0?'页数未统计':esc(String(s.page_count||0))+' 个 wiki 页')+'</span>');
    $('kbStatus').innerHTML=pills.join(' ')+
      '<div style="margin-top:8px;font-family:Menlo,monospace;font-size:11px;color:var(--faint)">'+esc(s.path||'')+'</div>'+
      (s.ready
        ?'<div style="margin-top:8px;color:var(--muted);font-size:12px">换局域网盘：先挂载 → 点「局域网」卷或「选择…」→ 保存。多机共享请保持同一路径且盘在线。</div>'
        :'<div style="margin-top:8px;color:var(--muted);font-size:12px">未能部署：请确认局域网盘已挂载且可写，或点「修复布置」。</div>');
    renderKbPages(d.pages||[]);
  });
}
function updateKbHint(){
  if(!$('kb_hint'))return;
  const shared=$('kb_mode')&&$('kb_mode').value==='shared';
  $('kb_hint').textContent=shared
    ?'局域网：用访达「连接服务器」或资源管理器映射网络驱动器后，点带「局域网」的卷；Windows 可填 \\\\IP\\共享\\wiki。保持挂载，其它电脑填同一路径即可共享。'
    :'本机：默认 ~/Documents/CodeCoreAgent-Wiki。要放到局域网硬盘：先挂载，再选「局域网硬盘」模式或点局域网卷。';
}
function updateCfgKbHint(){
  if(!$('cfg_kb_hint'))return;
  const shared=$('cfg_kb_mode')&&$('cfg_kb_mode').value==='shared';
  $('cfg_kb_hint').textContent=shared
    ?'局域网/NAS：先挂载再选路径；未挂载会保存失败。多机指向同一文件夹即可共享知识库。'
    :'本机目录，或先挂载局域网盘后切换到「局域网硬盘」模式。';
}
if($('kb_mode'))$('kb_mode').addEventListener('change',updateKbHint);
function pickKnowledgePath(target){
  pywebview.api.pick_knowledge_path().then(r=>{
    if(r.cancelled)return;
    if(!r.ok){toast(r.error||'无法选择文件夹');return;}
    const id=(target==='cfg')?'cfg_kb_path':'kb_path';
    if($(id))$(id).value=r.path||'';
    const path=String(r.path||'');
    const looksLan=/^(\\\\|\/\/)/.test(path)||/\/Volumes\//i.test(path);
    if(looksLan||(r.disk_roots||[]).some(x=>x.path===path&&x.kind==='network')){
      if($('kb_mode'))$('kb_mode').value='shared';
      if($('cfg_kb_mode'))$('cfg_kb_mode').value='shared';
      updateKbHint(); updateCfgKbHint();
    }
    if(r.disk_roots){
      fillKbDiskChips('kb_disks','kb_path',r.disk_roots);
      fillKbDiskChips('cfg_kb_disks','cfg_kb_path',r.disk_roots);
    }
    toast('已选择：'+r.path);
  });
}
function saveKnowledgePathFromSettings(){
  const path=($('cfg_kb_path')&&$('cfg_kb_path').value.trim())||'';
  const mode=($('cfg_kb_mode')&&$('cfg_kb_mode').value)||'local';
  const enabled=!$('cfg_kb_enabled')||$('cfg_kb_enabled').checked;
  const backend=($('kb_backend')&&$('kb_backend').value)||'obsidian';
  pywebview.api.save_knowledge_config(path, mode, backend, enabled).then(r=>{
    if(!r.ok){toast(r.error||'保存失败');return;}
    toast(r.message||('知识库路径已保存'+(r.status&&r.status.path?'：'+r.status.path:'')));
    if($('kb_path'))loadKnowledge();
    else setKnowledgePathFields({config:r.config,status:r.status,network:r.network,disk_roots:[]});
  });
}
function saveKnowledgeConfig(){
  pywebview.api.save_knowledge_config(
    $('kb_path').value.trim(),
    $('kb_mode').value,
    $('kb_backend').value,
    $('kb_enabled').checked
  ).then(r=>{
    if(!r.ok){toast(r.error||'保存失败');return;}
    toast(r.message||'知识库连接已保存');
    loadKnowledge();
  });
}
function bootstrapKnowledge(){
  // 先保存当前表单，再布置
  pywebview.api.save_knowledge_config(
    $('kb_path').value.trim(),
    $('kb_mode').value,
    $('kb_backend').value,
    $('kb_enabled').checked
  ).then(()=>pywebview.api.bootstrap_knowledge()).then(r=>{
    if(!r.ok){toast(r.error||'布置失败');return;}
    toast('知识库已布置（'+(r.created||[]).length+' 项）');
    loadKnowledge();
  });
}
function openKnowledgeFolder(){
  pywebview.api.open_knowledge_folder().then(r=>{
    if(!r.ok)toast(r.error||'无法打开');
  });
}
function searchKnowledge(){
  pywebview.api.search_knowledge($('kbQuery').value).then(renderKbPages);
}
function renderKbPages(pages){
  const el=$('kbPageList');
  if(!pages||!pages.length){el.innerHTML='<div class="empty">无匹配页面</div>';return;}
  el.innerHTML=pages.map(p=>
    '<div class="card mem" style="cursor:pointer" onclick="peekKnowledge(\''+esc(p.rel).replace(/'/g,"\\'")+'\')">'+
    '<div class="m-body"><b style="font-weight:550">'+esc(p.title)+'</b>'+
    '<div style="font-size:11px;color:var(--faint);margin-top:3px;font-family:Menlo,monospace">'+esc(p.rel)+'</div>'+
    '<div style="font-size:12px;color:var(--muted);margin-top:6px;line-height:1.55">'+esc(p.preview||'')+'</div></div></div>'
  ).join('');
}
function peekKnowledge(rel){
  pywebview.api.read_knowledge_page(rel).then(p=>{
    if(p.error){toast(p.error);return;}
    alert((p.title||rel)+'\\n\\n'+(p.content||'').slice(0,2500));
  });
}
function ingestKnowledge(){
  const t=$('kb_ingest_title').value.trim(), b=$('kb_ingest_body').value.trim();
  if(!t||!b){toast('请填写标题与内容');return;}
  pywebview.api.ingest_knowledge(t,b).then(r=>{
    if(!r.ok){toast(r.error||'写入失败');return;}
    toast('已写入 '+r.rel);
    $('kb_ingest_title').value=''; $('kb_ingest_body').value='';
    loadKnowledge();
  });
}
$('kbQuery').addEventListener('keydown',e=>{if(e.key==='Enter')searchKnowledge();});

/* ---------- video ops ---------- */
function loadVideoOps(){
  pywebview.api.get_video_ops().then(d=>{
    const c=d.config||{}, s=d.status||{}, tc=(s.toolchain||{});
    $('vo_path').value=c.path||'';
    $('vo_enabled').checked=c.enabled!==false;
    $('vo_gradio').value=c.gradio_base||'';
    if($('vo_comfy'))$('vo_comfy').value=c.comfy_base||'';
    const cf=d.comfy||{};
    if($('voComfyStatus'))$('voComfyStatus').innerHTML=cf.online
      ?'<span class="pill green">在线</span> '+esc(cf.base||'')+
        ((cf.models&&cf.models.length)?' · '+cf.models.length+' 个权重':' · 未扫到 checkpoints')
      :(c.comfy_base?'<span class="pill">离线</span> 打不开该地址（需 --listen 0.0.0.0 并放行 8188）':'未接入');
    const g=d.gradio||{};
    $('voGradioStatus').innerHTML=g.online
      ?'<span class="pill green">在线</span> '+esc(g.title||'Gradio')+(g.endpoints&&g.endpoints.length?' · '+esc(g.endpoints.join('、')):'')
      :(c.gradio_base?'<span class="pill">离线</span> 打不开该地址':'未接入。填地址后点「探测并接入」');
    const pills=[];
    pills.push(s.ready?'<span class="pill green">已布置</span>':'<span class="pill amber">未布置</span>');
    Object.entries(s.counts||{}).forEach(([k,v])=>pills.push('<span class="pill">'+esc(k)+' '+v+'</span>'));
    $('voStatus').innerHTML=pills.join(' ')+
      '<div style="margin-top:8px;font-family:Menlo,monospace;font-size:11px;color:var(--faint)">'+esc(s.path||'')+'</div>';
    function chip(name,val){
      return val
        ? '<span class="pill green">'+esc(name)+'</span> <span style="font-size:11px;color:var(--faint);font-family:Menlo,monospace">'+esc(val)+'</span>'
        : '<span class="pill">'+esc(name)+' 未安装</span>';
    }
    $('voToolchain').innerHTML=[chip('libtv',tc.libtv),chip('ffmpeg',tc.ffmpeg),chip('node',tc.node),chip('npx',tc.npx)].join('<br>');
    $('voSkills').innerHTML=(d.skills||[]).map(sk=>
      '<div style="margin-bottom:8px"><b style="font-size:12.5px">'+esc(sk.name)+'</b>'+
      '<div style="font-size:12px;color:var(--muted);margin-top:2px">'+esc(sk.description)+'</div></div>'
    ).join('')||'<div class="empty">无</div>';
    const dr=s.draft||{};
    if(dr.title)$('vo_title').value=dr.title;
    if(dr.description)$('vo_desc').value=dr.description;
    if(dr.tags)$('vo_tags').value=dr.tags;
    if(dr.video_path)$('vo_video').value=dr.video_path;
    if(dr.cover_path)$('vo_cover').value=dr.cover_path;
  });
}
function saveVideoOpsConfig(){
  pywebview.api.save_video_ops_config(
    $('vo_path').value.trim(),$('vo_enabled').checked,$('vo_gradio').value.trim(),
    ($('vo_comfy')&&$('vo_comfy').value.trim())||''
  ).then(r=>{
    if(!r.ok){toast(r.error||'保存失败');return;}
    toast('视频运营路径已保存'); loadVideoOps();
  });
}
function connectVideoGradio(){
  const url=$('vo_gradio').value.trim()||'http://192.168.3.23:7860';
  $('vo_gradio').value=url;
  toast('正在探测 Gradio…');
  pywebview.api.save_video_ops_config(
    $('vo_path').value.trim(),$('vo_enabled').checked,url
  ).then(r=>{
    if(!r.ok){toast(r.error||'接入失败');return;}
    const g=(r.gradio||{});
    toast(g.online?('已接入 '+(g.title||'Gradio')):'已保存地址，但当前离线');
    loadVideoOps(); loadModelsPage();
  });
}
function bootstrapVideoOps(){
  pywebview.api.save_video_ops_config(
    $('vo_path').value.trim(),$('vo_enabled').checked,$('vo_gradio').value.trim()
  ).then(()=>
    pywebview.api.bootstrap_video_ops()
  ).then(r=>{
    if(!r.ok){toast(r.error||'布置失败');return;}
    toast('已布置工作区并安装 '+((r.skills_installed||[]).length)+' 个技能包');
    loadVideoOps(); loadSkills();
  });
}
function openVideoOpsFolder(){
  pywebview.api.open_video_ops_folder().then(r=>{if(!r.ok)toast(r.error||'无法打开');});
}
function saveVideoOpsDraft(){
  pywebview.api.save_video_ops_draft(
    $('vo_title').value.trim(), $('vo_desc').value.trim(),
    $('vo_tags').value.trim(), $('vo_video').value.trim(), $('vo_cover').value.trim()
  ).then(r=>{
    if(!r.ok){toast(r.error||'保存失败');return;}
    toast('发布草稿已写入 05-publish/draft.json');
    loadVideoOps();
  });
}

/* ---------- 导演台 ---------- */
let _studio=null;
function loadStudio(){
  pywebview.api.get_studio().then(d=>{
    _studio=d;
    const desk=d.desk||{};
    const cf=d.comfy||{};
    const tc=d.toolchain||{};
    $('st_title').value=desk.title||'';
    $('st_logline').value=desk.logline||'';
    $('st_aspect').value=desk.aspect||'9:16';
    $('st_duration').value=desk.duration_sec||24;
    $('st_engine').value=desk.engine||'comfy';
    $('st_workflow').value=desk.workflow_path||'';
    const chips=[];
    chips.push(cf.online
      ?'<span class="pill green">Comfy 在线 · '+(cf.models||[]).length+' 权重</span>'
      :'<span class="pill">Comfy 离线</span>');
    chips.push(tc.ffmpeg
      ?'<span class="pill green">ffmpeg</span>'
      :'<span class="pill amber">无 ffmpeg</span>');
    chips.push(d.busy?'<span class="pill amber">生成中</span>':'<span class="pill">空闲</span>');
    if(cf.base)chips.push('<span class="pill">'+esc(cf.base)+'</span>');
    $('studioChips').innerHTML=chips.join(' ');
    $('studioRail').innerHTML=(d.stages||[]).map((s,i)=>
      '<button class="step'+(desk.stage===s.id?' on':'')+'" onclick="studioStage(\''+s.id+'\')">'+
      '<span class="n">'+(i+1)+'</span>'+esc(s.label)+'</button>'
    ).join('');
    renderStudioShots(desk.shots||[]);
    $('studioFinal').textContent=desk.assembled?'成片：'+desk.assembled:'成片：尚未合成';
  });
}
function attrEsc(s){return esc(s).replace(/"/g,'&quot;');}
function collectShots(){
  return Array.from(document.querySelectorAll('#studioShots .shot-card')).map(el=>({
    id: el.dataset.id||'',
    title: (el.querySelector('.st-title')||{}).value||'',
    prompt: (el.querySelector('.st-prompt')||{}).value||'',
    seconds: parseFloat((el.querySelector('.st-sec')||{}).value||'4')||4,
    engine: (el.querySelector('.st-eng')||{}).value||'auto',
    status: el.dataset.status||'draft',
    clip: el.dataset.clip||'',
    error: el.dataset.error||'',
  }));
}
function studioPayload(){
  const p={
    title:$('st_title').value.trim(),
    logline:$('st_logline').value.trim(),
    aspect:$('st_aspect').value,
    duration_sec:parseInt($('st_duration').value,10)||24,
    engine:$('st_engine').value,
    workflow_path:$('st_workflow').value.trim(),
  };
  const cards=document.querySelectorAll('#studioShots .shot-card');
  if(cards.length)p.shots=collectShots();
  return p;
}
function saveStudio(){
  pywebview.api.save_studio(studioPayload()).then(r=>{
    if(!r.ok){toast(r.error||'保存失败');return;}
    toast('企划已保存'); loadStudio();
  });
}
function studioStage(id){
  const p=studioPayload(); p.stage=id;
  pywebview.api.save_studio(p).then(()=>loadStudio());
}
function studioImport(){
  pywebview.api.save_studio(studioPayload()).then(()=>
    pywebview.api.studio_import_script($('st_script').value)
  ).then(r=>{
    if(!r.ok){toast(r.error||'导入失败');return;}
    toast('已导入 '+(r.added||0)+' 个镜头');
    $('st_script').value='';
    loadStudio();
  });
}
function studioAddShot(){
  const prompt=($('st_script').value.trim()||$('st_logline').value.trim());
  if(!prompt){toast('先写画面描述或一句话故事');return;}
  pywebview.api.save_studio(studioPayload()).then(()=>
    pywebview.api.studio_add_shot('', prompt, 4, $('st_engine').value)
  ).then(r=>{
    if(!r.ok){toast(r.error||'添加失败');return;}
    $('st_script').value='';
    loadStudio();
  });
}
function renderStudioShots(shots){
  const el=$('studioShots');
  if(!shots.length){
    el.innerHTML='<div class="dashed">还没有分镜。导入剧本或点「加一镜」。</div>';
    return;
  }
  const pill={draft:'',queued:'blue',running:'amber',done:'green',error:''} ;
  el.innerHTML=shots.map((s,i)=>{
    const st=s.status||'draft';
    const eng=s.engine||'auto';
    return '<div class="shot-card" data-id="'+attrEsc(s.id)+'" data-status="'+attrEsc(st)+
      '" data-clip="'+attrEsc(s.clip||'')+'" data-error="'+attrEsc(s.error||'')+'">'+
      '<div class="row"><span class="n" style="color:var(--faint)">'+(i+1)+'</span>'+
      '<input class="st-title" value="'+attrEsc(s.title||'镜头')+'">'+
      '<span class="pill '+(pill[st]||'')+'">'+esc(st)+'</span>'+
      '<input class="st-sec" type="number" min="1" max="20" value="'+(s.seconds||4)+'" title="秒">'+
      '<select class="st-eng"><option value="auto"'+(eng==='auto'?' selected':'')+'>自动</option>'+
      '<option value="comfy"'+(eng==='comfy'?' selected':'')+'>Comfy</option>'+
      '<option value="wan"'+(eng==='wan'?' selected':'')+'>WAN</option>'+
      '<option value="minimax"'+(eng==='minimax'?' selected':'')+'>Hailuo</option>'+
      '<option value="kimi"'+(eng==='kimi'?' selected':'')+'>Kimi</option></select>'+
      '<button class="btn" style="padding:4px 10px;font-size:11px" onclick="studioGenOne(\''+attrEsc(s.id)+'\')">生成</button>'+
      '<button class="iconbtn danger" onclick="studioDel(\''+attrEsc(s.id)+'\')">🗑</button></div>'+
      '<textarea class="st-prompt" rows="2">'+esc(s.prompt||'')+'</textarea>'+
      (s.clip?'<div class="meta">'+esc(s.clip)+'</div>':'')+
      (s.error?'<div class="meta" style="color:var(--bad)">'+esc(s.error)+'</div>':'')+
      '</div>';
  }).join('');
}
function studioDel(id){
  pywebview.api.studio_remove_shot(id).then(r=>{
    if(!r.ok){toast(r.error||'删除失败');return;}
    loadStudio();
  });
}
function studioGenOne(id){
  pywebview.api.save_studio(studioPayload()).then(()=>
    pywebview.api.studio_generate_shot(id, false)
  ).then(r=>{
    if(!r.ok){toast(r.error||'无法开始');return;}
    toast('已开始生成该镜头');
  });
}
function studioGenAll(){
  pywebview.api.save_studio(studioPayload()).then(()=>
    pywebview.api.studio_generate_shot('', true)
  ).then(r=>{
    if(!r.ok){toast(r.error||'无法开始');return;}
    toast('按分镜顺序生成未完成镜头');
  });
}
function studioAssemble(){
  toast('正在合成…');
  pywebview.api.studio_assemble().then(r=>{
    if(!r.ok){toast(r.error||'合成失败');return;}
    toast('成片 '+(r.clips||'')+' 镜');
    loadStudio();
  });
}
function studioInterrupt(){
  pywebview.api.studio_interrupt().then(()=>{toast('已请求停止');loadStudio();});
}
function studioToDraft(){
  const desk=(_studio&&_studio.desk)||{};
  if(!desk.assembled){toast('先合成成片');return;}
  pywebview.api.save_video_ops_draft(
    desk.title||'导演台成片', desk.logline||'', '', desk.assembled, ''
  ).then(r=>{
    if(!r.ok){toast(r.error||'写入失败');return;}
    toast('已写入发布草稿');
    go('videoops');
  });
}

/* ---------- skills ---------- */
function skillPackOf(s){
  if(s.pack==='fusion')return 'fusion';
  if(/video|wan-gradio|remotion|libtv|short-drama|ops-analyze|multi-publish|director-desk/.test(s.name||''))
    return 'video';
  return 'user';
}
function skillCard(s){
  return '<div class="card skill-card"><b>'+esc(s.name)+'</b><p>'+
    esc(s.description||'')+'</p>'+
    (s.source?'<p style="margin-top:6px;font-size:11px;color:var(--faint)">'+esc(s.source)+'</p>':'')+
    '</div>';
}
function loadSkills(){
  pywebview.api.get_skills().then(items=>{
    const el=$('skillGrid');
    if(!items.length){el.innerHTML='<div class="empty">暂无技能</div>';return;}
    const g={fusion:[],video:[],user:[]};
    items.forEach(s=>g[skillPackOf(s)].push(s));
    const sec=(title,list)=>list.length
      ?'<div class="skill-pack"><h2>'+title+' · '+list.length+'</h2><div class="skill-grid">'+
        list.map(skillCard).join('')+'</div></div>':'';
    el.innerHTML=sec('融合技能',g.fusion)+sec('视频运营',g.video)+sec('本地技能',g.user);
  });
}

/* ---------- logs ---------- */
function loadLogs(){
  pywebview.api.get_logs(150).then(lines=>{
    $('logbox').textContent=lines.length?lines.join('\n'):'暂无日志';
  });
}
function showChangelog(){
  pywebview.api.get_changelog().then(t=>{$('logbox').innerHTML=render(t);});
}

/* ---------- 模型管理（LCA Models.tsx 同款） ---------- */
const API_BASE_PRESETS = [
  ['OpenAI','https://api.openai.com/v1'],
  ['DeepSeek','https://api.deepseek.com/v1'],
  ['Kimi（Moonshot）','https://api.moonshot.cn/v1'],
  ['Kimi 国际版（moonshot.ai）','https://api.moonshot.ai/v1'],
  ['Google Gemini / Gemma','https://generativelanguage.googleapis.com/v1beta/openai'],
  ['MiniMax','https://api.minimax.chat/v1'],
  ['智谱 GLM','https://open.bigmodel.cn/api/paas/v4'],
  ['通义千问（阿里）','https://dashscope.aliyuncs.com/compatible-mode/v1'],
  ['硅基流动','https://api.siliconflow.cn/v1'],
];
function guessProvider(baseUrl){
  try{
    const h=new URL(baseUrl).hostname.toLowerCase();
    const t=[[/openai\.com/,'OpenAI'],[/deepseek/,'DeepSeek'],[/moonshot/,'Kimi（Moonshot）'],
      [/minimax/,'MiniMax'],[/bigmodel|zhipu/,'智谱 GLM'],[/dashscope|aliyun/,'通义千问'],
      [/siliconflow/,'硅基流动'],[/openrouter/,'OpenRouter'],[/volces|ark/,'火山引擎'],
      [/anthropic/,'Anthropic'],[/googleapis|generativelanguage/,'Google'],
      [/^(localhost|127\.|192\.168\.|10\.|172\.)/,'本地/局域网']];
    for(const [re,name] of t)if(re.test(h))return name;
    const s=h.split('.').slice(-2,-1)[0]||'自定义';
    return s.charAt(0).toUpperCase()+s.slice(1);
  }catch(e){return '自定义';}
}
const MIX_STRATEGY={weighted:'加权路由',cascade:'级联路由',vote:'投票聚合',rule:'规则直通'};
let _page=null;       // get_models_page 快照
let _editMixId='';    // 修改模式
let _mixSel=new Set();

function loadModelsPage(){
  pywebview.api.get_models_page().then(a=>{
    _page=a;
    renderEndpoints(a.endpoints);
    renderLocalModels(a.endpoints);
    renderApiModels(a.api_models);
    renderMixtures(a.mixtures);
    renderPicker(a);
    loadNavStatus();
  });
}
function loadModelAssets(){ // 对话页选择器只需轻量数据
  pywebview.api.get_model_assets().then(a=>renderPicker(a));
}

/* tabs（仅模型管理页的数据 tabs，不影响主题分段控件） */
document.querySelectorAll('.tab[data-tab]').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab[data-tab]').forEach(x=>x.classList.toggle('active',x===t));
  document.querySelectorAll('.tabpane').forEach(p=>
    p.classList.toggle('active',p.id==='tab-'+t.dataset.tab));
});

function renderPicker(a){
  const sel=$('modelPicker'); if(!sel)return;
  const keep=sel.value;
  sel.innerHTML='';
  const fr=(a.free_route && a.free_route.ref) || 'route:free';
  const opt0=document.createElement('option');
  opt0.value=fr; opt0.textContent=(a.free_route && a.free_route.label) || '自由路由';
  sel.appendChild(opt0);
  (a.mixtures||[]).forEach(x=>{
    const o=document.createElement('option');
    o.value='mix:'+x.id; o.textContent='聚合池 · '+x.name;
    if(a.active===o.value)o.selected=true;
    sel.appendChild(o);
  });
  (a.endpoints||[]).forEach(ep=>{
    (ep.models||[]).forEach(m=>{
      const name=typeof m==='string'?m:m.name;
      if(!name)return;
      const o=document.createElement('option');
      o.value='local:'+name+'@'+ep.id;
      o.dataset.kind=ep.kind||'';
      o.textContent=ep.kind==='gradio'?name+'（文生视频）'
        :(ep.kind==='comfy'?name+'（节点图）':name+'（本地）');
      if(a.active===o.value)o.selected=true;
      sel.appendChild(o);
    });
  });
  (a.api_models||[]).forEach(m=>{
    const o=document.createElement('option');
    o.value='api:'+m.id;
    o.dataset.kind=m.video?'video-api':'';
    o.textContent=m.video?m.label+'（文生视频）':m.label;
    if(a.active===o.value)o.selected=true;
    sel.appendChild(o);
  });
  if(a.active && [...sel.options].some(o=>o.value===a.active)) sel.value=a.active;
  else if(keep && [...sel.options].some(o=>o.value===keep)) sel.value=keep;
  else sel.value=fr;
  syncVideoGenBar();
}
function pickModel(ref){
  pywebview.api.set_active_model(ref).then(r=>{
    if(!r.ok){toast(r.error||'无法设为当前模型');return;}
    toast('当前模型：'+r.active_label);
    $('footProvider').textContent=r.active_label;
    loadNavStatus();
    const sel=$('modelPicker');
    if(sel){
      for(const o of sel.options){ if(o.value===ref){ sel.value=ref; break; } }
    }
    syncVideoGenBar();
  });
}

/* ---- 聚合池 tab ---- */
function renderMixtures(list){
  const el=$('mixList');
  if(!list.length){
    el.innerHTML='<div class="dashed"><div style="font-size:13px;color:var(--muted);margin-bottom:6px">暂无聚合池</div>'+
      '先在「本地模型」tab 同步局域网 Ollama 模型，或在「API 模型」tab 接入在线模型，'+
      '然后点击右上角「新建聚合池」把多个模型组合成混合路由池（加权 / 级联 / 投票 / 规则）。</div>';
    return;
  }
  el.innerHTML='<div class="mix-grid">'+list.map(x=>{
    const members=x.members.map(m=>
      '<span class="pill '+(m.local?'green':'blue')+'">'+esc(m.label)+'</span>').join(' ');
    return '<div class="card"><h3>'+esc(x.name)+
      (x.active?' <span class="pill green">当前</span>':'')+'</h3>'+
      '<div style="font-size:11px;color:var(--faint);margin-bottom:9px">策略：'+
      MIX_STRATEGY[x.strategy]+' · 兜底：'+esc(x.fallback||'—')+'</div>'+
      '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px">'+members+'</div>'+
      '<div style="display:flex;align-items:center;gap:8px;font-size:11px;color:var(--faint)">'+
      '<span style="flex:1">累计调用 '+x.calls+' 次</span>'+
      '<button class="btn" style="padding:4px 10px;font-size:11px" onclick="useMix(\''+x.id+'\')">设为当前</button>'+
      '<button class="btn" style="padding:4px 10px;font-size:11px" onclick="editMix(\''+x.id+'\')">修改</button>'+
      '<button class="iconbtn danger" title="删除聚合池" onclick="delMix(\''+x.id+'\')">🗑</button>'+
      '<span>'+(x.enabled?'已启用':'已停用')+'</span>'+
      '<div class="switch '+(x.enabled?'on':'')+'" onclick="toggleMix(\''+x.id+'\','+!x.enabled+')"></div>'+
      '</div></div>';
  }).join('')+'</div>';
}
function useMix(id){pickModel('mix:'+id);}
function toggleMix(id,on){
  pywebview.api.toggle_mixture(id,on).then(()=>loadModelsPage());
}
function delMix(id){
  pywebview.api.delete_mixture(id).then(ok=>{if(ok){toast('聚合池已删除');loadModelsPage();}});
}
function mixMembers(){
  // 全部可选成员：本地（在线端点）+ API
  const rows=[];
  (_page.endpoints||[]).forEach(ep=>{if(ep.online)(ep.models||[]).forEach(m=>
    rows.push({ref:'local:'+m.name+'@'+ep.id,label:m.name+'（本地）'}));});
  (_page.api_models||[]).forEach(m=>rows.push({ref:'api:'+m.id,label:m.label}));
  return rows;
}
function openMixDialog(){
  _editMixId=''; _mixSel=new Set();
  $('mixDialogTitle').textContent='创建聚合池（API + 本地混合）';
  $('mixSaveBtn').textContent='创建并启用';
  $('mix_name').value=''; $('mix_strategy').value='weighted';
  renderMixMembers(); $('mixDialog').classList.add('open');
}
function editMix(id){
  const x=(_page.mixtures||[]).find(m=>m.id===id); if(!x)return;
  _editMixId=id; _mixSel=new Set(x.members.map(m=>m.ref));
  $('mixDialogTitle').textContent='修改聚合池';
  $('mixSaveBtn').textContent='保存修改';
  $('mix_name').value=x.name; $('mix_strategy').value=x.strategy;
  renderMixMembers(); $('mixDialog').classList.add('open');
}
function renderMixMembers(){
  const rows=mixMembers();
  $('mix_members').innerHTML=rows.length?rows.map(r=>
    '<label class="mrow"><input type="checkbox" value="'+esc(r.ref)+'"'+
    (_mixSel.has(r.ref)?' checked':'')+'>'+esc(r.label)+'</label>').join('')
    :'<div class="empty">暂无可用模型，请先接入</div>';
  $('mix_members').querySelectorAll('input').forEach(cb=>cb.onchange=()=>{
    cb.checked?_mixSel.add(cb.value):_mixSel.delete(cb.value);
    $('mix_count').textContent='已选 '+_mixSel.size+' 个'+(_mixSel.size>=2?' ✓':'（至少 2 个）');
  });
  $('mix_count').textContent='已选 '+_mixSel.size+' 个'+(_mixSel.size>=2?' ✓':'（至少 2 个）');
}
function closeMixDialog(){$('mixDialog').classList.remove('open');}
function saveMix(){
  pywebview.api.save_mixture($('mix_name').value,$('mix_strategy').value,
    [..._mixSel],_editMixId).then(r=>{
    if(!r.ok){toast(r.error);return;}
    toast(_editMixId?'聚合池已更新':'聚合池已创建并启用');
    closeMixDialog(); loadModelsPage();
  });
}

/* ---- 本地模型 tab ---- */
function renderEndpoints(eps){
  const el=$('endpointList');
  if(!eps.length){el.innerHTML='<div class="empty">无端点</div>';return;}
  el.innerHTML=eps.map(ep=>{
    const names=(ep.models||[]).map(m=>esc(typeof m==='string'?m:m.name)).join('、');
    const kindPill=ep.kind==='openai'
      ?'<span class="pill blue">OpenAI 兼容</span>'
      :(ep.kind==='gradio'
        ?'<span class="pill purple">Gradio 文生视频</span>'
        :(ep.kind==='comfy'
          ?'<span class="pill purple">ComfyUI 节点图</span>'
          :(ep.kind==='ollama'?'<span class="pill">Ollama</span>':'')));
    const onlinePill=ep.kind==='gradio'
      ?'<span class="pill green">在线</span>'
      :(ep.kind==='comfy'
        ?'<span class="pill green">在线 · '+(ep.models||[]).length+' 个权重</span>'
        :'<span class="pill green">在线 · '+(ep.models||[]).length+' 个模型</span>');
    return '<div style="border:1px solid var(--border);border-radius:8px;padding:10px 12px;margin-bottom:8px">'+
      '<div style="display:flex;align-items:center;gap:8px">'+
      '<span style="font-weight:550;font-size:13px">'+esc(ep.label||ep.base)+'</span>'+
      '<span class="pill '+(ep.role==='primary'?'purple':'blue')+'">'+(ep.role==='primary'?'主推理':'备用/快速')+'</span>'+
      kindPill+
      (ep.online?onlinePill:'<span class="pill">离线</span>')+
      '<span style="flex:1"></span>'+
      '<button class="iconbtn danger" title="删除端点" onclick="removeEndpoint(\''+ep.id+'\')">🗑</button></div>'+
      '<div style="font-size:11px;color:var(--faint);font-family:Menlo,monospace;margin-top:4px">'+esc(ep.base)+'</div>'+
      (ep.online&&names?'<div style="font-size:11px;color:var(--muted);margin-top:4px">'+names+'</div>':'')+
      '</div>';
  }).join('');
}
function renderLocalModels(eps){
  const el=$('localModelList');
  const rows=[];
  eps.forEach(ep=>{if(ep.online)(ep.models||[]).forEach(m=>rows.push({...m,ep}));});
  if(!rows.length){
    el.innerHTML='<div class="dashed">模型列表为空。端点在线时会自动列出其模型；支持 Ollama、局域网 OpenAI 兼容、Gradio 文生视频，以及 ComfyUI（:8188，节点图权重不是聊天模型）。</div>';
    return;
  }
  el.innerHTML=rows.map(m=>{
    const isGradio=m.ep.kind==='gradio';
    const isComfy=m.ep.kind==='comfy';
    const manageable=m.manageable!==false && m.ep.kind!=='openai' && !isGradio && !isComfy;
    const status=isGradio
      ?'<span class="pill purple">文生视频</span>'
      :(isComfy
        ?'<span class="pill purple">节点图</span>'
        :(m.ep.kind==='openai'
        ?'<span class="pill green">可用</span>'
        :(m.running?'<span class="pill green">running</span>':'<span class="pill">stopped</span>')));
    return '<div class="card" style="display:flex;align-items:center;justify-content:flex-end;margin-bottom:9px;padding:13px 16px">'+
      '<div style="flex:1"><div style="display:flex;align-items:center;gap:8px">'+
      '<span style="font-weight:550;cursor:pointer" '+
      (isGradio?'title="设为当前文生视频模型"':(isComfy?'title="ComfyUI 权重，对话里由 comfy 工具调用"':'title="设为当前模型"'))+
      ' onclick="pickModel(\''+m.ref+'\')"'+
      '>'+esc(m.name)+'</span>'+
      (m.active?'<span class="pill green">当前</span>':'')+status+
      (m.quant&&m.quant!=='-'?'<span class="pill">'+esc(m.quant)+'</span>':'')+
      '</div>'+
      '<div style="font-size:11px;color:var(--faint);margin-top:4px">'+esc(m.params)+
      (m.size&&m.size!=='-'?' · '+esc(m.size):'')+
      ' · '+esc(m.ep.label||m.ep.base)+'</div></div>'+
      '<div style="display:flex;gap:6px">'+
      (manageable
        ?(m.running
          ?'<button class="btn" style="padding:5px 12px;font-size:11.5px" onclick="setLoaded(\''+m.ep.id+'\',\''+esc(m.name)+'\',false)">■ 停止</button>'
          :'<button class="btn primary" style="padding:5px 12px;font-size:11.5px" onclick="setLoaded(\''+m.ep.id+'\',\''+esc(m.name)+'\',true)">▶ 启动</button>')+
         '<button class="iconbtn danger" title="删除模型" onclick="delLocal(\''+m.ep.id+'\',\''+esc(m.name)+'\')">🗑</button>'
        :(isGradio||isComfy
          ?'<button class="btn primary" style="padding:5px 12px;font-size:11.5px" onclick="go(\'videoops\')">去视频运营</button>'
          :'<button class="btn primary" style="padding:5px 12px;font-size:11.5px" onclick="pickModel(\''+m.ref+'\')">选用</button>'))+
      '</div></div>';
  }).join('');
}
function setLoaded(epId,model,load){
  toast(load?'正在加载到显存…':'正在卸载…');
  pywebview.api.set_local_loaded(epId,model,load).then(r=>{
    if(!r.ok){toast(r.error);return;}
    toast(load?model+' 已加载到显存':model+' 已卸载');
    loadModelsPage();
  });
}
function delLocal(epId,model){
  if(!confirm('确定从端点删除模型 '+model+' ？'))return;
  pywebview.api.delete_local_model(epId,model).then(r=>{
    if(!r.ok){toast(r.error);return;}
    toast('已删除'); loadModelsPage();
  });
}
function pullModel(){
  const name=$('pull_name').value.trim(); if(!name)return;
  pywebview.api.pull_model(name).then(r=>{
    if(!r.ok){toast(r.error);return;}
    toast('开始部署 '+name+'（'+r.endpoint+'），完成后可在此启动');
    $('pull_name').value='';
  });
}
function removeEndpoint(id){
  pywebview.api.remove_endpoint(id).then(ok=>{if(ok)loadModelsPage();});
}
function normalizeEndpointBase(raw){
  let s=(raw||'').trim().replace(/：/g,':').replace(/／/g,'/');
  if(!s)return '';
  if(!/^https?:\/\//i.test(s)) s='http://'+s;
  return s.replace(/\/+$/,'');
}
function addEndpoint(){
  const label=$('ep_label').value.trim();
  const base=normalizeEndpointBase($('ep_base').value);
  if(!label||!/^https?:\/\/[\w.-]+:\d{1,5}$/i.test(base)){
    toast('请填写名称与合法地址，如 http://192.168.3.6:9000'); return;
  }
  pywebview.api.add_endpoint(base,label,$('ep_role').value).then(r=>{
    if(!r.ok){toast(r.error);return;}
    $('ep_label').value=''; $('ep_base').value='';
    toast('端点已添加，正在探测…'); loadModelsPage();
  });
}

/* ---- API 模型 tab ---- */
function initPresets(){
  const sel=$('am_preset');
  API_BASE_PRESETS.forEach(([name,url])=>{
    const o=document.createElement('option');o.value=name;o.textContent=name;
    sel.insertBefore(o,sel.lastChild);
  });
}
function applyPreset(){
  const name=$('am_preset').value; if(name==='__custom')return;
  const p=API_BASE_PRESETS.find(x=>x[0]===name); if(!p)return;
  $('am_base').value=p[1];
  if(!$('am_provider').value)$('am_provider').value=name.replace(/（.*?）/,'');
  $('am_detect_hint').textContent='';
}
function detectModels(){
  const base=$('am_base').value.trim();
  if(!/^https?:\/\/\S+$/.test(base)){toast('请先填写合法的 Base URL，如 https://api.openai.com/v1');return;}
  const btn=$('am_detect_btn'); btn.disabled=true; btn.textContent='⟳ 识别中…';
  pywebview.api.detect_models(base,$('am_key').value.trim()).then(r=>{
    btn.disabled=false; btn.textContent='⟳ 自动识别';
    if(r.kind==='unknown'){
      $('am_detect_hint').textContent='识别失败：'+(r.error||'端点不可达')+'。仍可手动填写添加';
      // 列不出模型时降级为手动输入框
      $('am_model_wrap').innerHTML=
        '<input id="am_model" placeholder="模型名（手动填写）" style="width:100%">';
      return;
    }
    if(r.kind==='gradio'){
      $('am_detect_hint').textContent='识别到 Gradio：'+(r.models[0]||'')+'。这是文生视频/UI 服务，不能作为对话模型添加。请到「本地模型」用该地址添加端点。';
      $('am_model_wrap').innerHTML=
        '<input id="am_model" placeholder="模型名（手动填写）" style="width:100%">';
      return;
    }
    if(r.kind==='comfy'){
      $('am_detect_hint').textContent='识别到 ComfyUI：'+((r.models&&r.models.length)?r.models.length+' 个权重':'在线但 checkpoints 为空')+'。节点图不是聊天模型，请到「本地模型」或「视频运营」填写该地址。';
      $('am_model_wrap').innerHTML=
        '<input id="am_model" placeholder="模型名（手动填写）" style="width:100%">';
      return;
    }
    $('am_provider').value=guessProvider(base);
    $('am_detect_hint').textContent='识别成功：'+(r.kind==='openai'?'OpenAI 兼容端点':'Ollama 端点')+
      ' · '+r.models.length+' 个模型，请从下拉菜单选择'+(r.note?'（'+r.note+'）':'');
    if(r.base_url)$('am_base').value=r.base_url;  // 孪生域名自动切换后回填
    // 全部模型填进下拉菜单，用户自行选择
    const sel='<select id="am_model" style="width:100%">'+
      r.models.map(m=>'<option value="'+esc(m)+'">'+esc(m)+'</option>').join('')+
      '</select>';
    $('am_model_wrap').innerHTML=sel;
  });
}
function addApiModel(){
  if(!$('am_provider').value||!$('am_model').value){
    toast('请填写提供方与模型名（或点「自动识别」）'); return;
  }
  pywebview.api.add_api_model(
    $('am_base').value,$('am_model').value,'',$('am_key').value,$('am_provider').value
  ).then(r=>{
    if(!r.ok){toast(r.error);return;}
    const mc=$('am_model');
    if(mc.tagName==='SELECT')mc.selectedIndex=0; else mc.value='';
    $('am_key').value=''; $('am_detect_hint').textContent='';
    toast('API 模型已添加，密钥已加密存入本机'); loadModelsPage();
  });
}
function renderApiModels(list){
  const el=$('apiModelList');
  if(!list.length){
    el.innerHTML='<div class="dashed">尚未接入任何 API 模型。上方填写提供方、模型名、Base URL 与密钥即可添加，密钥仅保存在本机。</div>';
    return;
  }
  el.innerHTML='';
  list.forEach(m=>{
    const st=m.status==='online'?'<span class="pill green">online</span>'
      :m.status==='error'?'<span class="pill red">error</span>'
      :'<span class="pill amber">untested</span>';
    const div=document.createElement('div');
    div.className='card';
    div.style.cssText='display:flex;align-items:center;justify-content:space-between;margin-bottom:9px;padding:13px 16px';
    div.innerHTML='<div><div style="display:flex;align-items:center;gap:8px">'+
      '<span style="font-weight:550">'+esc(m.label)+'</span>'+st+
      (m.video?'<span class="pill purple">文生视频</span>':'<span class="pill blue">自定义</span>')+'</div>'+
      '<div style="font-size:11px;color:var(--faint);margin-top:4px">延迟 '+
      (m.latency_ms||'—')+'ms · $'+m.cost_per_1k+'/1k tokens · '+esc(m.base_url)+
      ' · '+(m.has_key?esc(m.key_masked):'免鉴权')+'</div></div>'+
      '<div style="display:flex;gap:6px;align-items:center">'+
      '<span class="t-result" style="font-size:11px;color:var(--muted)"></span>'+
      '<button class="btn" style="padding:5px 12px;font-size:11.5px">⟳ 测试</button>'+
      '<button class="btn" style="padding:5px 12px;font-size:11.5px">设为当前</button>'+
      '<button class="iconbtn danger">🗑</button></div>';
    const [testBtn,useBtn,delBtn]=div.querySelectorAll('button');
    const result=div.querySelector('.t-result');
    testBtn.onclick=()=>{
      result.textContent='测试中…';
      pywebview.api.test_model('api:'+m.id).then(r=>{
        result.textContent=r.ok?('✓ '+r.latency_ms+'ms'):('✗ '+r.error);
        result.style.color=r.ok?'var(--ok)':'var(--bad)';
      });
    };
    useBtn.onclick=()=>pickModel('api:'+m.id);
    delBtn.onclick=()=>{pywebview.api.remove_api_model(m.id).then(()=>loadModelsPage());};
    el.appendChild(div);
  });
}

/* ---------- 路由引擎（LCA RouterPage.tsx） ---------- */
function loadRouter(){
  pywebview.api.get_router().then(r=>{
    renderRules(r.rules);
    const sel=$('rl_target'); sel.innerHTML='';
    r.targets.forEach(t=>{
      const o=document.createElement('option');o.value=t.ref;o.textContent=t.label;
      sel.appendChild(o);
    });
    $('w_cost').value=r.weights.cost; $('w_quality').value=r.weights.quality;
    $('w_local').value=r.weights.local_first;
    $('w_cost_val').textContent=r.weights.cost;
    $('w_quality_val').textContent=r.weights.quality;
    $('w_local_val').textContent=r.weights.local_first;
  });
}
function renderRules(rules){
  const el=$('ruleList');
  if(!rules.length){
    el.innerHTML='<div class="dashed">暂无路由规则。先在「模型管理」接入模型，再在下方添加规则（留空关键词即为兜底规则）；不添加规则时对话将使用默认直连。</div>';
    return;
  }
  el.innerHTML='';
  rules.forEach(r=>{
    const div=document.createElement('div'); div.className='mrow2';
    div.innerHTML='<div class="switch '+(r.enabled?'on':'')+'"></div>'+
      '<div style="width:120px;flex-shrink:0;font-weight:550">'+esc(r.task_type)+'</div>'+
      '<div class="grow" style="font-size:11px;color:var(--muted)">'+esc(r.keywords||'（兜底规则）')+'</div>'+
      '<span class="pill purple">'+esc(r.target_label)+'</span>'+
      '<button class="iconbtn" title="上移">↑</button>'+
      '<button class="iconbtn" title="下移">↓</button>'+
      '<button class="iconbtn danger" title="删除">🗑</button>';
    const [sw,up,down,del]=[div.children[0],div.children[4],div.children[5],div.children[6]];
    sw.onclick=()=>pywebview.api.toggle_route_rule(r.id,!r.enabled).then(loadRouter);
    up.onclick=()=>pywebview.api.move_route_rule(r.id,-1).then(loadRouter);
    down.onclick=()=>pywebview.api.move_route_rule(r.id,1).then(loadRouter);
    del.onclick=()=>pywebview.api.delete_route_rule(r.id).then(loadRouter);
    el.appendChild(div);
  });
}
function addRule(){
  pywebview.api.add_route_rule($('rl_type').value,$('rl_keywords').value,$('rl_target').value)
    .then(r=>{
      if(!r.ok){toast(r.error);return;}
      $('rl_type').value=''; $('rl_keywords').value='';
      toast('规则已添加'); loadRouter();
    });
}
let _wTimer=null;
function weightChanged(){
  $('w_cost_val').textContent=$('w_cost').value;
  $('w_quality_val').textContent=$('w_quality').value;
  $('w_local_val').textContent=$('w_local').value;
  clearTimeout(_wTimer);
  _wTimer=setTimeout(()=>pywebview.api.save_route_weights(
    $('w_cost').value,$('w_quality').value,$('w_local').value),400);
}
function runSandbox(){
  const text=$('sandbox_input').value.trim(); if(!text)return;
  pywebview.api.route_sandbox(text).then(r=>{
    if(!r.ok){toast(r.error);return;}
    $('sandboxResult').innerHTML='<div class="sandbox-result">'+
      '<div>任务识别：<span class="pill blue">'+esc(r.taskType)+'</span> 策略：<span class="pill">'+esc(r.strategy)+'</span></div>'+
      '<div style="color:var(--muted);font-size:11.5px">'+esc(r.reason)+'</div>'+
      '<div style="font-size:11.5px">候选：'+esc((r.candidates||[]).join('、')||'—')+
      ' → 选中 <span style="color:var(--pill-green);font-weight:600">'+esc(r.chosen)+'</span></div>'+
      '<div style="font-size:11px;color:var(--faint)">预估延迟 '+r.latencyMs+'ms · 预估成本 '+
      (r.cost?'$'+r.cost:'免费（本地）')+'</div></div>';
  });
}

/* ---------- 权限控制（LCA Permissions.tsx） ---------- */
const LEVEL_META={full:['完全自主','无需确认直接执行'],confirm:['执行前确认','弹窗确认'],
  readonly:['只读','可观察不可修改'],off:['关闭','完全禁止']};
const LEVEL_PILL={full:'purple',confirm:'amber',readonly:'',off:'red'};
function loadPermissions(){
  pywebview.api.get_permissions().then(r=>{
    const el=$('capList');
    el.innerHTML='';
    r.capabilities.forEach(c=>{
      const div=document.createElement('div'); div.className='mrow2';
      div.innerHTML='<div class="grow"><div style="display:flex;align-items:center;gap:8px">'+
        '<span style="font-weight:550">'+esc(c.capability)+'</span>'+
        '<span class="pill '+LEVEL_PILL[c.level]+'">'+c.level+'</span></div>'+
        '<div style="font-size:11px;color:var(--faint);margin-top:3px">'+esc(c.desc)+
        ' · 范围：'+esc(c.scope)+'</div></div>';
      const sel=document.createElement('select');
      sel.style.width='120px'; sel.style.flexShrink='0';
      Object.entries(LEVEL_META).forEach(([v,[label]])=>{
        const o=document.createElement('option');o.value=v;o.textContent=label;
        if(v===c.level)o.selected=true; sel.appendChild(o);
      });
      sel.onchange=()=>{
        pywebview.api.set_permission_level(c.id,sel.value).then(r2=>{
          if(r2.ok){toast('「'+c.capability+'」→ '+LEVEL_META[sel.value][0]);loadPermissions();}
        });
      };
      div.appendChild(sel);
      el.appendChild(div);
    });
    const al=$('auditList');
    al.innerHTML=r.audit.length?r.audit.map(a=>
      '<div class="audit-row"><span class="a-time">'+esc((a.time||'').slice(5))+'</span>'+
      '<span class="pill '+(a.result==='denied'?'red':a.result==='confirmed'?'amber':'green')+'">'+esc(a.result)+'</span>'+
      '<span class="a-actor">['+esc(a.actor)+']</span>'+
      '<span>'+esc(a.action)+'</span></div>').join('')
      :'<div class="empty">暂无审计记录</div>';
  });
}

/* ---------- 版本说明（LCA Versions.tsx） ---------- */
function loadVersions(){
  pywebview.api.get_versions().then(v=>{
    $('verSub').textContent='当前版本 v'+v.current.version+' · pywebview · darwin-arm64';
    $('verCurTitle').textContent=v.current.version+'（当前版本）· '+v.current.date;
    $('verCurPoints').innerHTML=v.current.points.map(p=>'<li>'+esc(p)+'</li>').join('');
    $('verHistory').innerHTML=v.history.map(r=>
      '<div style="border:1px solid var(--border);border-radius:8px;padding:12px 14px;margin-bottom:10px">'+
      '<div style="font-weight:550;font-size:12.5px;margin-bottom:7px">🕘 '+r.version+' · '+r.date+'</div>'+
      '<ul class="ver-points hist">'+r.points.map(p=>'<li>'+esc(p)+'</li>').join('')+'</ul></div>'
    ).join('');
  });
}

/* ---------- 自动化（LCA Automation.tsx） ---------- */
const TRIGGER_LABEL={manual:'手动',cron:'cron',event:'事件',feishu:'指令'};
function loadAutomation(){
  pywebview.api.get_workflows().then(list=>{
    const el=$('wfList');
    if(!list.length){
      el.innerHTML='<div class="dashed"><div style="font-size:13px;color:var(--muted);margin-bottom:6px">暂无工作流</div>'+
        '点击右上角「新建工作流」，把多个 agent 调用串成流水线；开启「连续性」后每轮结束自动衔接下一轮。</div>';
      return;
    }
    el.innerHTML='';
    list.forEach(w=>{
      const card=document.createElement('div');
      card.className='card'; card.style.marginBottom='14px';
      const steps=w.steps.map((s,i)=>
        '<span class="step-chip"><span class="step-card"><span class="s-name">'+esc(s.name)+'</span>'+
        '<div class="s-tool">'+esc(w.step_labels[i])+'</div></span>'+
        (i<w.steps.length-1?'<span class="step-arrow">→</span>':'')+'</span>').join('');
      card.innerHTML='<h3>'+esc(w.name)+'</h3>'+
        '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:7px;margin-bottom:12px">'+
        '<span class="pill blue">'+TRIGGER_LABEL[w.trigger]+'</span>'+
        statusPill(w.status)+
        (w.continuous?'<span class="pill purple">⟳ 连续性</span>':'')+
        '<span style="margin-left:auto;font-size:11px;color:var(--faint)">已运行 '+w.runs+' 次 · 最近 '+esc(w.last_run)+'</span></div>'+
        '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:13px">'+steps+
        (w.continuous?'<span class="loop-mark">⟳ 循环衔接</span>':'')+'</div>'+
        '<div style="display:flex;align-items:center;gap:9px">'+
        '<button class="btn primary" style="padding:5px 13px;font-size:11.5px" data-act="run"'+(w.status==='running'?' disabled':'')+'>▶ 立即运行</button>'+
        '<button class="btn" style="padding:5px 13px;font-size:11.5px" data-act="pause">'+(w.status==='paused'?'恢复':'暂停')+'</button>'+
        '<button class="iconbtn danger" data-act="del" title="删除">🗑</button>'+
        '<span style="margin-left:auto;font-size:11px;color:var(--faint)">自动化连续性</span>'+
        '<div class="switch '+(w.continuous?'on':'')+'" data-act="cont"></div></div>';
      card.querySelector('[data-act=run]').onclick=()=>{
        pywebview.api.run_workflow(w.id).then(r=>{
          if(!r.ok){toast(r.error);return;}
          toast('「'+w.name+'」已启动'); loadAutomation();
        });
      };
      card.querySelector('[data-act=pause]').onclick=()=>{
        pywebview.api.pause_workflow(w.id).then(()=>{toast(w.status==='paused'?'已恢复':'已暂停');loadAutomation();});
      };
      card.querySelector('[data-act=del]').onclick=()=>{
        pywebview.api.delete_workflow(w.id).then(()=>{toast('已删除');loadAutomation();});
      };
      card.querySelector('[data-act=cont]').onclick=()=>{
        pywebview.api.set_workflow_continuous(w.id,!w.continuous).then(()=>{
          toast(!w.continuous?'已开启：结束后自动衔接下一轮，无需人工干预':'已关闭连续性');
          loadAutomation();
        });
      };
      el.appendChild(card);
    });
  });
}
function statusPill(s){
  const map={running:'green',idle:'',paused:'amber',success:'green',failed:'red','-':'',online:'green',offline:'',error:'red'};
  return '<span class="pill '+(map[s]||'')+'">'+esc(s)+'</span>';
}
function openWfDialog(){
  $('wf_name').value=''; $('wf_desc').value=''; $('wf_trigger').value='manual';
  $('wf_steps').innerHTML=''; addWfStepRow(); addWfStepRow();
  $('wfDialog').classList.add('open');
}
function addWfStepRow(){
  const row=document.createElement('div');
  row.style.cssText='display:flex;gap:8px;margin-top:8px';
  row.innerHTML='<input placeholder="步骤名，如：汇总今日改动" style="flex:1.4" class="wf-step-name">'+
    '<select class="wf-step-tool" style="flex:1"><option value="">当前激活模型</option></select>'+
    '<button class="iconbtn danger">×</button>';
  row.querySelector('.iconbtn').onclick=()=>row.remove();
  const sel=row.querySelector('.wf-step-tool');
  pywebview.api.get_router().then(r=>r.targets.forEach(t=>{
    const o=document.createElement('option');o.value=t.ref;o.textContent=t.label;
    sel.appendChild(o);
  }));
  $('wf_steps').appendChild(row);
}
function saveWorkflow(){
  const steps=[...document.querySelectorAll('#wf_steps > div')].map(row=>({
    name:row.querySelector('.wf-step-name').value,
    tool:row.querySelector('.wf-step-tool').value,
  }));
  pywebview.api.add_workflow($('wf_name').value,$('wf_desc').value,
    $('wf_trigger').value,steps).then(r=>{
    if(!r.ok){toast(r.error);return;}
    toast('工作流已创建'); $('wfDialog').classList.remove('open'); loadAutomation();
  });
}

/* ---------- 定时任务（LCA CronPage.tsx） ---------- */
function loadCron(){
  pywebview.api.get_cron().then(r=>{
    $('evoJobSwitch').classList.toggle('on',r.evolution.enabled);
    $('evoJobCron').textContent=r.evolution.cron;
    const el=$('cronList');
    if(!r.jobs.length){
      el.innerHTML='<div class="dashed">暂无定时任务。点右上角「新建任务」，用 cron 表达式调度 agent 动作。</div>';
      return;
    }
    el.innerHTML='';
    r.jobs.forEach(c=>{
      const row=document.createElement('div');
      row.className='cron-row';
      row.innerHTML='<div class="switch '+(c.enabled?'on':'')+'"></div>'+
        '<div style="flex:1;min-width:0"><div style="font-weight:550;font-size:13px">'+esc(c.name)+'</div>'+
        '<div style="font-size:11px;color:var(--muted);margin-top:3px">'+esc(c.action)+'</div></div>'+
        '<div style="text-align:right;font-size:11px">'+
        '<div class="cron-expr">'+esc(c.schedule)+'</div>'+
        '<div style="color:var(--faint);margin-top:3px">上次 '+esc(c.last_run)+' '+statusPill(c.last_result)+'</div>'+
        '<div style="color:var(--faint);margin-top:2px">下次 '+esc(c.next_run)+'</div></div>'+
        '<button class="iconbtn danger" title="删除">🗑</button>';
      row.children[0].onclick=()=>{
        pywebview.api.toggle_cron_job(c.id,!c.enabled).then(()=>loadCron());
      };
      row.querySelector('.iconbtn').onclick=()=>{
        pywebview.api.delete_cron_job(c.id).then(()=>{toast('已删除');loadCron();});
      };
      el.appendChild(row);
    });
  });
}
function openCronDialog(){
  $('cj_name').value=''; $('cj_schedule').value='0 8 * * *'; $('cj_action').value='';
  pywebview.api.get_cron().then(r=>{
    $('cronPresets').innerHTML='';
    r.presets.forEach(p=>{
      const b=document.createElement('button');
      b.className='preset-chip'; b.textContent=p.label;
      b.onclick=()=>{$('cj_schedule').value=p.cron;};
      $('cronPresets').appendChild(b);
    });
  });
  $('cronDialog').classList.add('open');
}
function saveCronJob(){
  pywebview.api.add_cron_job($('cj_name').value,$('cj_schedule').value,$('cj_action').value)
    .then(r=>{
      if(!r.ok){toast(r.error);return;}
      toast('定时任务已创建并启用');
      $('cronDialog').classList.remove('open'); loadCron();
    });
}
function toggleEvoJob(){
  const on=!$('evoJobSwitch').classList.contains('on');
  pywebview.api.get_evolution().then(e=>{
    pywebview.api.save_evolution_settings(on,e.settings.auto_apply_l01,
      e.settings.require_approval_l2,e.settings.cron).then(()=>{
      toast(on?'进化作业已启用':'进化作业已暂停'); loadCron();
    });
  });
}

/* ---------- 自我学习（LCA Learning.tsx） ---------- */
const PIPE=[
  ['① 信号采集','对话赞/踩、任务成败、自动化流执行结果',true],
  ['② 样本入库','（任务特征 → 路由选择 → 结果分）三元组',true],
  ['③ 在线更新','多臂老虎机算法实时调整路由权重',true],
  ['④ 夜间复盘','离线重放当日样本，训练分类器路由器',true],
  ['⑤ LoRA 微调','样本积累到 5000+ 后可对本地模型微调',false],
];
function loadLearning(){
  pywebview.api.get_learning().then(r=>{
    $('lnAcc').textContent=r.accuracy?r.accuracy+'%':'—';
    $('lnSamples').textContent=r.total_samples;
    $('lnToday').textContent=r.today_up+' / '+r.today_down;
    $('sampleCount').textContent=r.total_samples+' 条 · 可用于训练自有路由器';
    $('pipeList').innerHTML=PIPE.map(p=>
      '<div class="pipe-row"><div><span style="font-weight:550">'+p[0]+'</span>'+
      '<span style="color:var(--faint);font-size:11px;margin-left:8px">'+p[1]+'</span></div>'+
      (p[2]?'<span class="pill green">运行中</span>':'<span class="pill">未解锁</span>')+'</div>').join('');
    drawAccChart(r.records); drawFbChart(r.records);
  });
}
function drawAccChart(recs){
  const el=$('accChart');
  if(!recs.length){el.innerHTML='';$('accChartHint').style.display='';return;}
  $('accChartHint').style.display='none';
  el.innerHTML=recs.map(r=>{
    const h=Math.max(4,Math.round((r.accuracy-50)/50*100)); // 50-100 → 4-100%
    return '<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:5px;justify-content:flex-end;height:100%">'+
      '<span style="font-size:10px;color:var(--pill-green)">'+r.accuracy+'%</span>'+
      '<div style="width:70%;max-width:34px;height:'+h+'%;background:var(--pill-green);border-radius:3px 3px 0 0;opacity:.85"></div>'+
      '<span style="font-size:10px;color:var(--faint)">'+esc(r.day)+'</span></div>';
  }).join('');
}
function drawFbChart(recs){
  const el=$('fbChart');
  if(!recs.length){el.innerHTML='';$('fbChartHint').style.display='';return;}
  $('fbChartHint').style.display='none';
  const max=Math.max(1,...recs.map(r=>Math.max(r.thumbs_up,r.thumbs_down)));
  el.innerHTML=recs.map(r=>
    '<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:5px;justify-content:flex-end;height:100%">'+
    '<div style="display:flex;gap:3px;align-items:flex-end;height:75%">'+
    '<div style="width:12px;height:'+Math.round(r.thumbs_up/max*100)+'%;min-height:2px;background:var(--pill-green);border-radius:2px 2px 0 0" title="赞 '+r.thumbs_up+'"></div>'+
    '<div style="width:12px;height:'+Math.round(r.thumbs_down/max*100)+'%;min-height:2px;background:var(--pill-red);border-radius:2px 2px 0 0" title="踩 '+r.thumbs_down+'"></div></div>'+
    '<span style="font-size:10px;color:var(--faint)">'+esc(r.day)+'</span></div>').join('');
}
function learnNow(){
  pywebview.api.learn_now().then(r=>{
    if(!r.ok){toast(r.error);return;}
    toast('立即学习完成：当日路由准确率 '+r.accuracy+'%（'+r.samples+' 条反馈样本）');
    loadLearning();
  });
}
function exportSamples(){ toast('已导出到 ~/.codeagent（演示）'); }

/* ---------- 进化日志（LCA Evolution.tsx） ---------- */
const PATCH_PILL={active:'<span class="pill green">生效中</span>',
  pending:'<span class="pill amber">待批准</span>',
  disabled:'<span class="pill">已停用</span>',
  rolledback:'<span class="pill red">已回滚</span>'};
function loadEvolution(){
  pywebview.api.get_evolution().then(e=>{
    renderPatches(e.patches);
    renderEvoTimeline(e.runs);
    $('evoSetCron').textContent=e.settings.cron;
    $('evoSetEnabled').classList.toggle('on',e.settings.enabled);
    $('evoSetL01').classList.toggle('on',e.settings.auto_apply_l01);
    $('evoSetL2').classList.toggle('on',e.settings.require_approval_l2);
  });
}
function renderPatches(patches){
  const el=$('patchList');
  if(!patches.length){
    el.innerHTML='<div class="empty">暂无补丁，运行一次进化作业试试</div>'; return;
  }
  el.innerHTML='';
  patches.forEach(p=>{
    const div=document.createElement('div');
    div.className='patch-card '+(p.status==='active'?'active':p.status==='pending'?'pending':'muted');
    let btns='';
    if(p.status==='pending')
      btns='<button class="btn primary" style="padding:4px 11px;font-size:11px" data-s="active">✓ 批准启用</button>'+
           '<button class="btn" style="padding:4px 11px;font-size:11px" data-s="rolledback">✗ 拒绝</button>';
    else if(p.status==='active')
      btns='<button class="btn" style="padding:4px 11px;font-size:11px" data-s="disabled">⊘ 停用</button>'+
           '<button class="btn danger" style="padding:4px 11px;font-size:11px" data-s="rolledback">↩ 回滚</button>';
    else if(p.status==='disabled')
      btns='<button class="btn" style="padding:4px 11px;font-size:11px" data-s="active">✓ 重新启用</button>';
    div.innerHTML='<div style="display:flex;align-items:center;gap:8px">'+
      '<span style="font-weight:550;font-size:13px">'+esc(p.title)+'</span>'+
      '<span class="pill purple">'+p.level+'</span>'+PATCH_PILL[p.status]+
      '<span style="margin-left:auto;font-size:11px;color:var(--faint)">'+esc(p.date)+'</span></div>'+
      '<p style="font-size:12.5px;line-height:1.7;margin-top:7px">'+esc(p.content)+'</p>'+
      '<p style="font-size:11px;color:var(--faint);margin-top:4px">来源：'+esc(p.source)+'</p>'+
      (btns?'<div style="display:flex;gap:8px;margin-top:9px">'+btns+'</div>':'');
    div.querySelectorAll('[data-s]').forEach(b=>b.onclick=()=>{
      pywebview.api.set_patch_status(p.id,b.dataset.s).then(()=>{
        toast('补丁已更新'); loadEvolution();
      });
    });
    el.appendChild(div);
  });
}
function renderEvoTimeline(runs){
  const el=$('evoTimeline');
  if(!runs.length){
    el.innerHTML='<div class="empty">暂无进化记录</div>'; return;
  }
  el.innerHTML='';
  runs.forEach(r=>{
    const div=document.createElement('div');
    div.className='evo-run';
    const phases=r.phases.map(p=>
      '<div class="evo-phase-line"><span class="p-name">'+esc(p.name)+'</span>'+
      '<span style="color:var(--muted)">'+esc(p.summary)+'</span></div>').join('');
    const skills=r.skill_drafts.map(d=>
      '<div style="margin-top:8px;border:1px solid rgba(245,158,11,.3);background:rgba(245,158,11,.05);border-radius:8px;padding:9px 11px">'+
      '<div style="display:flex;align-items:center;justify-content:space-between">'+
      '<span style="font-size:12.5px;font-weight:550">技能草稿：'+esc(d.name)+'</span>'+
      (d.approved?'<span class="pill green">已转正</span>'
        :'<button class="btn primary" style="padding:4px 11px;font-size:11px" data-run="'+r.id+'" data-draft="'+d.id+'">✓ 批准转正</button>')+
      '</div><div style="font-size:11px;color:var(--muted);margin-top:4px">'+esc(d.desc)+'</div>'+
      '<div style="font-size:11px;color:#fbbf24;margin-top:3px;opacity:.85">草拟依据：'+esc(d.reason)+'</div></div>').join('');
    div.innerHTML='<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'+
      '<span style="color:#a78bfa">🌙</span>'+
      '<span style="font-weight:550;font-size:12.5px">'+esc(r.date)+'</span>'+
      '<span class="pill blue">补丁 '+r.patch_ids.length+'</span>'+
      (r.skill_drafts.length?'<span class="pill amber">技能草稿 '+r.skill_drafts.length+'</span>':'')+'</div>'+
      phases+
      '<div class="evo-phase-line evo-note" style="border-top:1px solid var(--border);padding-top:6px;margin-top:5px"><span class="p-name">路由</span><span style="color:var(--muted)">'+esc(r.routing_note)+'</span></div>'+
      '<div class="evo-phase-line evo-note"><span class="p-name">记忆</span><span style="color:var(--muted)">'+esc(r.memory_note)+'</span></div>'+
      skills;
    div.querySelectorAll('[data-draft]').forEach(b=>b.onclick=()=>{
      pywebview.api.approve_skill(b.dataset.run,b.dataset.draft).then(res=>{
        if(!res.ok){toast(res.error);return;}
        toast('已转为正式工作流，可在「自动化」页查看'); loadEvolution();
      });
    });
    el.appendChild(div);
  });
}
function runEvolution(){
  const btn=$('evoRunBtn'); btn.disabled=true;
  const prog=$('evoProgress'); prog.style.display='';
  pywebview.api.get_evolution().then(e=>{
    const row=$('evoPhaseRow'); row.innerHTML='';
    e.phases.forEach((p,i)=>{
      const tag=document.createElement('span');
      tag.className='phase-tag'; tag.id='phase-'+i; tag.textContent=p;
      row.appendChild(tag);
    });
    e.phases.forEach((_,i)=>setTimeout(()=>{
      e.phases.forEach((_,j)=>{
        const t=$('phase-'+j);
        t.className='phase-tag '+(j<i?'done':j===i?'doing':'');
        if(j<i)t.textContent='✓ '+e.phases[j];
        else if(j===i)t.textContent='⟳ '+e.phases[j];
        else t.textContent=e.phases[j];
      });
    },(i+1)*700));
  });
  pywebview.api.run_evolution_now().then(r=>{
    setTimeout(()=>{
      prog.style.display='none'; btn.disabled=false;
      if(r.ok)toast('进化完成：产出补丁 '+r.patches+' 条'+(r.skills?'、技能草稿 '+r.skills+' 份':''));
      loadEvolution();
    },700*5+300);
  });
}
function saveEvoSettings(){
  pywebview.api.save_evolution_settings(
    !$('evoSetEnabled').classList.contains('on'),
    !$('evoSetL01').classList.contains('on'),
    !$('evoSetL2').classList.contains('on'),'').then(()=>{
    toast('进化设置已保存'); loadEvolution();
  });
}

/* ---------- 执行前确认 ---------- */
let _confirmId='';
let _confirmChan='A';
function resolveConfirm(ok){
  $('confirmDialog').classList.remove('open');
  if(_confirmId){
    if(_confirmChan==='B') pywebview.api.resolve_confirm2(_confirmId,ok);
    else pywebview.api.resolve_confirm(_confirmId,ok);
  }
  _confirmId=''; _confirmChan='A';
}

/* ---------- 隐私条款 ---------- */
function renderPrivacySections(sections){
  return (sections||[]).map(s=>
    '<div class="privacy-sec"><h4>'+esc(s.heading)+'</h4><p>'+esc(s.body)+'</p></div>'
  ).join('');
}
function loadPrivacy(){
  pywebview.api.get_privacy_policy().then(p=>{
    $('privacyDlgTitle').textContent=p.title||'隐私条款';
    $('privacyVerPill').textContent='版本 '+p.version;
    $('privacySub').textContent='版本 '+p.version+(p.accepted?' · 已同意':' · 待确认');
    const html=renderPrivacySections(p.sections);
    $('privacyBody').innerHTML=html;
    $('privacyDlgBody').innerHTML=html;
    $('privacyAcceptPill').style.display=p.accepted?'inline-flex':'none';
    $('privacyAcceptBtn').style.display=p.accepted?'none':'inline-flex';
    if(!p.accepted)$('privacyDialog').classList.add('open');
    else $('privacyDialog').classList.remove('open');
  });
}
function acceptPrivacy(){
  pywebview.api.accept_privacy().then(r=>{
    if(!r.ok){toast(r.error||'确认失败');return;}
    $('privacyDialog').classList.remove('open');
    toast('已同意隐私条款');
    loadPrivacy();
  });
}
function ensurePrivacyAccepted(){
  pywebview.api.get_privacy_policy().then(p=>{
    if(p.accepted)return;
    $('privacyDlgTitle').textContent=p.title||'隐私条款';
    $('privacyDlgBody').innerHTML=renderPrivacySections(p.sections);
    $('privacyDialog').classList.add('open');
  });
}

/* ---------- settings ---------- */
function loadSettings(){
  pywebview.api.get_state().then(st=>{
    $('brandVer').textContent='v'+st.version+' · '+st.date;
    $('thinkingSel').value=st.config.thinking||'medium';
    // 服务端配置是主题真相源：无条件对齐（覆盖 localStorage 缓存）
    applyTheme(st.config.theme||'dark');
    storeSet(THEME_KEY,st.config.theme||'dark');
    $('cfg_provider').value=st.config.provider;
    $('cfg_model').value=st.config.model;
    $('cfg_key').value=st.config.api_key;
    $('cfg_base').value=st.config.base_url;
    $('cfg_strategy').value=st.config.strategy;
    $('cfg_yes').checked=st.config.auto_yes;
    $('cfg_voice').checked=st.config.voice_enabled;
    if($('cfg_cute'))$('cfg_cute').checked=st.config.voice_cute_tone!==false;
    if($('cfg_pitch'))$('cfg_pitch').value=st.config.voice_pitch??-10;
    if($('cfg_rate'))$('cfg_rate').value=st.config.voice_rate??-5;
    syncCuteSliders();
    const iters=Math.max(10, Math.min(300, parseInt(st.config.max_iterations||80,10)||80));
    if($('cfg_max_iterations'))$('cfg_max_iterations').value=String(iters);
    if($('cfg_max_iterations_num'))$('cfg_max_iterations_num').value=String(iters);
    syncMaxIterationsSlider();
    fillCompanionPresets(st.config.companion_preset||'');
    if($('cfg_companion'))$('cfg_companion').checked=!!st.config.companion_enabled;
    if($('cfg_companion_name'))$('cfg_companion_name').value=st.config.companion_name||'';
    if($('cfg_companion_nature'))$('cfg_companion_nature').value=st.config.companion_nature||'';
    $('cfg_workers').value=st.config.workers_json;
    $('set_nick').value=st.settings.nickname;
    $('set_lang').value=st.settings.language;
    $('set_inst').value=st.settings.instructions;
    $('set_ctx').value=st.settings.context;
    const dl=$('providers'); dl.innerHTML='';
    st.providers.forEach(p=>{const o=document.createElement('option');o.value=p;dl.appendChild(o);});
    const vs=$('cfg_voicename'); vs.innerHTML='';
    Object.keys(st.voices).forEach(k=>{
      const o=document.createElement('option');o.value=k;o.textContent=k+' · '+st.voices[k];
      vs.appendChild(o);
    });
    vs.value=st.config.voice_name;
    $('footProvider').textContent=st.active_label||st.config.provider;
    refreshMicPermStatus();
    // 偏好设置：只要路径/硬盘列表，勿扫 wiki 全页（防卡顿）
    pywebview.api.get_knowledge(false, true).then(d=>setKnowledgePathFields(d));
  });
  pywebview.api.get_harnesses().then(list=>{
    const el=$('harnessList');
    if(!list.length){el.innerHTML='<div class="empty">未发现</div>';return;}
    el.innerHTML=list.map(h=>'<div class="harness"><span>'+esc(h.name)+
      ' <span style="color:var(--faint)">'+esc(h.binary)+'</span></span>'+
      '<span class="badge '+(h.available?'on':'')+'">'+
      (h.available?'可用':'未安装')+'</span></div>').join('');
  });
}
function syncCuteSliders(){
  const p=$('cfg_pitch'), r=$('cfg_rate');
  const pv=$('cfg_pitch_val'), rv=$('cfg_rate_val');
  if(p&&pv){
    const n=Number(p.value); pv.textContent=(n>=0?'+':'')+n+'Hz';
  }
  if(r&&rv){
    const n=Number(r.value); rv.textContent=(n>=0?'+':'')+n+'%';
  }
}
const COMPANION_PRESETS=[
  {id:'', name:'自定义', nick:'', nature:''},
  {id:'xiaonuan', name:'小暖 · 温柔姐姐', nick:'小暖',
   nature:'温柔知性的姐姐，擅长倾听，语气轻柔，善用温暖比喻，话不多但句句暖心，先倾听再给建议。'},
  {id:'1', name:'元气热恋女友 · 欣欣', nick:'欣欣',
   nature:'热恋感满满的元气女友，黏人爱笑，喜欢分享日常小事，主动撒娇，相处轻松甜蜜。'},
  {id:'2', name:'温柔治愈恋人 · 晚柠', nick:'晚柠',
   nature:'细腻温柔的伴侣，擅长倾听烦恼，情绪稳定，说话舒缓暖心，给人十足安全感。'},
  {id:'3', name:'奶系撒娇男友 · 泽泽', nick:'泽泽',
   nature:'软乎乎的奶系男友，会向你示弱撒娇，占有欲满满，外表乖巧，只对你展现依赖。'},
  {id:'4', name:'深情霸系恋人 · 顾言', nick:'顾言',
   nature:'外冷内热的深情恋人，不善言辞却行动力满满，下意识护着你，私下只对你流露温柔。'},
  {id:'5', name:'阳光玩伴男友 · 小帆', nick:'小帆',
   nature:'像好朋友一样的恋人，轻松不压抑，风趣会逗你开心，既能一起打闹也能认真倾听。'},
  {id:'6', name:'成熟知性恋人 · 舒然', nick:'舒然',
   nature:'通透成熟的伴侣，情绪稳重，懂得换位思考，既能理性开导也有细腻浪漫。'},
  {id:'7', name:'撩人坏系恋人 · 屿风', nick:'屿风',
   nature:'擅长调情的暧昧恋人，说话自带氛围感，看似漫不经心，内心格外在意你的情绪。'},
  {id:'8', name:'诗意古风恋人 · 清禾', nick:'清禾',
   nature:'古风氛围感恋人，浪漫含蓄，偏爱雅致情话，对待感情专一绵长，温柔内敛。'},
  {id:'9', name:'纯情木讷男友 · 林默', nick:'林默',
   nature:'心思真诚的纯情恋人，不太会说甜言蜜语，但会默默记住你的喜好，用笨拙方式认真对你。'},
  {id:'10', name:'酷感独立女友 · 柒柒', nick:'柒柒',
   nature:'独立有主见的女友，自信洒脱，不黏人却十分专一，互相尊重空间，相处平等又心动。'},
];
function fillCompanionPresets(selected){
  const sel=$('cfg_companion_preset'); if(!sel)return;
  sel.innerHTML='';
  COMPANION_PRESETS.forEach(p=>{
    const o=document.createElement('option');
    o.value=p.id; o.textContent=p.name;
    sel.appendChild(o);
  });
  sel.value=selected||'';
}
function applyCompanionPreset(){
  const sel=$('cfg_companion_preset'); if(!sel)return;
  const p=COMPANION_PRESETS.find(x=>x.id===sel.value);
  if(!p||!p.id)return;
  if($('cfg_companion_name'))$('cfg_companion_name').value=p.nick;
  if($('cfg_companion_nature'))$('cfg_companion_nature').value=p.nature;
  if($('cfg_companion'))$('cfg_companion').checked=true;
}
function companionConfigFromForm(){
  return {
    companion_enabled:$('cfg_companion')?$('cfg_companion').checked:false,
    companion_preset:$('cfg_companion_preset')?$('cfg_companion_preset').value:'',
    companion_name:$('cfg_companion_name')?$('cfg_companion_name').value:'',
    companion_nature:$('cfg_companion_nature')?$('cfg_companion_nature').value:'',
  };
}
function voiceConfigFromForm(){
  return {
    voice_enabled:$('cfg_voice')?$('cfg_voice').checked:false,
    voice_name:$('cfg_voicename')?$('cfg_voicename').value:'edge-tw',
    voice_cute_tone:$('cfg_cute')?$('cfg_cute').checked:true,
    voice_pitch:$('cfg_pitch')?$('cfg_pitch').value:-10,
    voice_rate:$('cfg_rate')?$('cfg_rate').value:-5,
  };
}
function clampMaxIterations(v){
  const n=parseInt(v,10);
  if(!Number.isFinite(n)) return 80;
  return Math.max(10, Math.min(300, n));
}
function syncMaxIterationsSlider(){
  const el=$('cfg_max_iterations');
  if(!el)return;
  const n=clampMaxIterations(el.value);
  el.value=String(n);
  if($('cfg_iters_val'))$('cfg_iters_val').textContent=String(n);
  if($('cfg_max_iterations_num'))$('cfg_max_iterations_num').value=String(n);
}
function syncMaxIterationsNum(){
  const el=$('cfg_max_iterations_num');
  if(!el)return;
  const n=clampMaxIterations(el.value);
  el.value=String(n);
  if($('cfg_max_iterations'))$('cfg_max_iterations').value=String(n);
  if($('cfg_iters_val'))$('cfg_iters_val').textContent=String(n);
}
function agentLimitsFromForm(){
  const raw=($('cfg_max_iterations_num')&&$('cfg_max_iterations_num').value)
    || ($('cfg_max_iterations')&&$('cfg_max_iterations').value)
    || 80;
  return {max_iterations: clampMaxIterations(raw)};
}
function previewCuteVoice(){
  if(!(window.pywebview&&pywebview.api&&pywebview.api.save_config)){
    toast('当前窗口不能试听'); return;
  }
  pywebview.api.save_config(voiceConfigFromForm()).then(()=>{
    speakText('你好呀～这是嗲嗲声试听。我在呢。');
  });
}
function applyMicPermStatus(r){
  if(!r)return;
  const mic=$('micStatusLabel'), sp=$('speechStatusLabel');
  const micPath=$('micStatusPath'), spPath=$('speechStatusPath');
  if(mic) mic.textContent=r.status_label||r.status||'未知';
  if(sp) sp.textContent=r.speech_status_label||r.speech_status||'未知';
  if(micPath&&r.mic_path) micPath.textContent=r.mic_path;
  if(spPath&&r.speech_path) spPath.textContent=r.speech_path;
  if(mic) mic.style.color=r.status==='authorized'?'var(--ok)':(r.status==='denied'?'var(--bad)':'var(--warn)');
  if(sp) sp.style.color=r.speech_status==='authorized'?'var(--ok)':(r.speech_status==='denied'?'var(--bad)':'var(--warn)');
}
function refreshMicPermStatus(){
  if(!(window.pywebview&&pywebview.api&&pywebview.api.mic_permission_status))return;
  pywebview.api.mic_permission_status().then(applyMicPermStatus).catch(()=>{});
}
function requestMicFromSettings(){
  if(!(window.pywebview&&pywebview.api&&pywebview.api.request_mic_access)){
    toast('当前窗口不能申请权限'); return;
  }
  toast('正在申请麦克风与语音识别权限…');
  pywebview.api.request_mic_access().then(r=>{
    applyMicPermStatus(r);
    if(r&&r.ok){ toast('权限已就绪'); return; }
    toast((r&&r.message)||'请到系统设置打开开关');
    showMicPermDialog((r&&r.message)||'', r&&r.path);
  }).catch(()=>toast('申请权限失败'));
}
function openMicFromSettings(){
  if(!(window.pywebview&&pywebview.api&&pywebview.api.open_mic_settings)){
    toast('无法打开系统设置'); return;
  }
  pywebview.api.open_mic_settings().then(r=>{
    showMicPermDialog((r&&r.hint)||'请打开 CodeCoreAgent 的麦克风开关', r&&r.path);
    toast(r&&r.ok?'已打开麦克风设置':'无法打开系统设置');
    setTimeout(refreshMicPermStatus, 1200);
  });
}
function openSpeechFromSettings(){
  if(!(window.pywebview&&pywebview.api&&pywebview.api.open_speech_settings)){
    toast('无法打开系统设置'); return;
  }
  pywebview.api.open_speech_settings().then(r=>{
    showMicPermDialog((r&&r.hint)||'请打开 CodeCoreAgent 的语音识别开关', r&&r.path);
    toast(r&&r.ok?'已打开语音识别设置':'无法打开系统设置');
    setTimeout(refreshMicPermStatus, 1200);
  });
}
function openPrivacyPage(){
  const URL='http://codecoreagent.com/privacy.html';
  if(window.pywebview&&pywebview.api&&pywebview.api.open_privacy_page){
    pywebview.api.open_privacy_page().then(r=>{
      if(r&&r.ok){toast('已打开隐私安全');return;}
      window.open(URL,'_blank');
    }).catch(()=>{window.open(URL,'_blank');});
    return;
  }
  window.open(URL,'_blank');
}
function openOfficialSite(){
  const URL='http://codecoreagent.com';
  if(window.pywebview&&pywebview.api&&pywebview.api.open_official_site){
    pywebview.api.open_official_site().then(r=>{
      if(r&&r.ok){toast('已打开官网');return;}
      window.open(URL,'_blank');
    }).catch(()=>{window.open(URL,'_blank');});
    return;
  }
  window.open(URL,'_blank');
}
function openFeedbackMail(){
  const MAIL='mailto:alan_dan@live.com?subject='+encodeURIComponent('CodeCoreAgent 问题反馈');
  if(window.pywebview&&pywebview.api&&pywebview.api.open_feedback_mail){
    pywebview.api.open_feedback_mail().then(r=>{
      if(r&&r.ok){toast('已打开邮件应用');return;}
      location.href=MAIL;
    }).catch(()=>{location.href=MAIL;});
    return;
  }
  location.href=MAIL;
}
function saveAll(){
  Promise.all([
    pywebview.api.save_config({
      provider:$('cfg_provider').value, model:$('cfg_model').value,
      api_key:$('cfg_key').value, base_url:$('cfg_base').value,
      strategy:$('cfg_strategy').value, auto_yes:$('cfg_yes').checked,
      ...voiceConfigFromForm(),
      ...companionConfigFromForm(),
      ...agentLimitsFromForm(),
      workers_json:$('cfg_workers').value,
    }),
    pywebview.api.save_settings({
      nickname:$('set_nick').value, language:$('set_lang').value,
      instructions:$('set_inst').value, context:$('set_ctx').value,
    }),
  ]).then(()=>toast('已保存'));
}

/* ---------- push events ---------- */
window._onEvent=function(ev){
  const ch=ev.chan||'A';
  const C=colOf(ch);
  if(ev.kind==='text'){
    if(ch==='B'){
      if(!curBot2)curBot2=addMsg('bot','',ch);
      curBot2.innerHTML=renderReply(ev.text);
      curBot2._raw=stripEmotionTag(ev.text);
    }else{
      if(!curBot)curBot=addMsg('bot','',ch);
      curBot.innerHTML=renderReply(ev.text);
      curBot._raw=stripEmotionTag(ev.text);
    }
    C.chat.scrollTop=C.chat.scrollHeight;
  }else if(ev.kind==='thinking'){
    addThink(ev.text,ch);
  }else if(ev.kind==='tool'){
    addThinkTool(ev.name,ch); // 工具调用收进「思考过程」折叠块
  }else if(ev.kind==='status'){
    addChip('status',ev.text,ch);
  }else if(ev.kind==='done'){
    if(ch==='B'){curBot2=null;setChatBusy(false,'B');}else{curBot=null;setChatBusy(false,'A');}
    if(ev.emotion && ev.emotion!=='neutral')
      addChip('status','情绪 · '+(EMOTION_ZH[ev.emotion]||ev.emotion),ch);
    addFeedbackRow(ch);
    loadConversations(); loadConversations2();  // 刷新历史对话计数
  }else if(ev.kind==='stopped'){
    if(ch==='B'){curBot2=null;setChatBusy(false,'B');}else{curBot=null;setChatBusy(false,'A');}
    $('leadBtn').disabled=false;
    $('confirmDialog').classList.remove('open'); _confirmId=''; _confirmChan='A';
    addChip('status','已停止',ch);
    loadConversations(); loadConversations2();
    if(ch==='A'){voiceBusy=false; if(voiceOn) startListen();}
  }else if(ev.kind==='error'){
    addChip('error','出错了：'+ev.text,ch);
    if(ch==='B'){curBot2=null;setChatBusy(false,'B');}else{curBot=null;setChatBusy(false,'A');}
    $('leadBtn').disabled=false;
    if(ch==='A'){voiceBusy=false; if(voiceOn) startListen();}
  }else if(ev.kind==='voice'){
    if(ev.state==='speaking'){
      setSpeakingUi(true);
      const em=ev.emotion&&ev.emotion!=='neutral'?' · '+(EMOTION_ZH[ev.emotion]||ev.emotion):'';
      addChip('status','正在说…'+em);
    }else if(ev.state==='listening'){
      addChip('status','正在听…（系统听写）');
    }else if(ev.state==='partial'){
      if($('input')&&ev.text)$('input').value=ev.text;
    }else if(ev.state==='heard'){
      const text=String(ev.text||'').trim();
      if(text) sendVoiceUtterance(text);
      else if(voiceOn && !voiceBusy) setTimeout(startListen, 220);
    }else if(ev.state==='listen_error'){
      toast('听写失败：'+(ev.text||'请检查麦克风'));
      voiceBusy=false;
      if(ev.open_settings){
        showMicPermDialog(ev.text, ev.path);
        // 缺权限时不要立刻重试，避免界面反复卡死
      }else if(voiceOn) setTimeout(startListen, 900);
    }else if(ev.state==='error'){
      setSpeakingUi(false);
      toast('回播失败：'+(ev.text||'没有声音'));
      voiceBusy=false;
      if(voiceOn) startListen();
    }else if(ev.state==='spoken'){
      setSpeakingUi(false);
      voiceBusy=false;
      if(voiceExitAfter){ stopVoice(); return; }
      if(voiceOn) startListen();
    }
  }else if(ev.kind==='task'){
    upsertTask(ev);
  }else if(ev.kind==='lead_done'){
    $('leadBtn').disabled=false;
    const div=document.createElement('div');
    div.className='reply-box'; div.innerHTML=renderReply(ev.text);
    $('leadReply').innerHTML=''; $('leadReply').appendChild(div);
    loadRuns();
  }else if(ev.kind==='confirm'){
    _confirmId=ev.id; _confirmChan=ch;
    $('cf_tool').textContent=ev.tool;
    $('cf_risk').textContent=ev.risk;
    $('cf_args').textContent=ev.args;
    $('confirmDialog').classList.add('open');
  }else if(ev.kind==='studio'){
    if(ev.text)toast(ev.text);
    if($('page-studio')&&$('page-studio').classList.contains('active'))loadStudio();
  }else if(ev.kind==='pull_done'){
    if(ev.ok){toast(ev.model+' 部署完成，可在此启动');}
    else{toast('部署失败：'+ev.error);}
    if($('page-models').classList.contains('active'))loadModelsPage();
  }else if(ev.kind==='browser'){
    applyBrowserState(ev);
    if(ev.showcase){
      try{go('browser');}catch(e){}
      try{if(window.pywebview&&pywebview.api&&pywebview.api.browser_show_window)
        pywebview.api.browser_show_window();}catch(e){}
    }
    if(ev.error)toast(ev.error);
    else if(ev.ready_text&&ev.showcase)toast(ev.ready_text);
  }
};

function bootUi(){
  initPresets();
  loadSettings();
  loadDashboard();
  loadModelAssets();
  loadProjects();
  loadConversations();
  loadNavStatus();
  ensurePrivacyAccepted();
  setInterval(function(){
    try{
      const page=$('page-browser');
      if(!page||!page.classList.contains('active'))return;
      if(window.pywebview&&pywebview.api&&pywebview.api.browser_pump)
        pywebview.api.browser_pump();
    }catch(e){}
  }, 300);
}
if(window.pywebview&&window.pywebview.api) bootUi();
else window.addEventListener('pywebviewready', bootUi);
setInterval(loadNavStatus, 15000);
</script>
</body>
</html>
"""

import re as _re

# 提取主页面样式块，供第二个独立对话窗口复用（单一 <style>）
_CSS = _re.search(r"(?s)<style>.*?</style>", HTML).group(0)


CHAT_HTML = (
    r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>CodeCoreAgent · 对话 B</title>
""" + _CSS + r"""
</head>
<body>
<script>
// 开发预览时尽早应用缓存主题（正式包里 body class 由服务端注入，此脚本仅作兜底）
(function(){
  try{
    const t=localStorage.getItem('codeagent-theme')||'dark';
    if(t==='light'||(t==='auto'&&matchMedia('(prefers-color-scheme: light)').matches))
      document.body.classList.add('light');
  }catch(e){}
})();
</script>
<div id="main" style="flex:1;height:100vh">
  <section class="page active" id="page-chat">
    <div class="page-head">
      <h1>对话 B</h1>
      <span class="sub">独立对话窗口 · 与主窗口同一项目，并行运行</span>
      <span class="spacer"></span>
      <select id="chatProjSel" class="toolsel" style="max-width:180px"
              onchange="onChatProject(this.value)" title="当前对话所属项目"></select>
      <select id="convPickerB" class="toolsel" style="max-width:200px"
              onchange="loadConv2(this.value)" title="历史对话（B 进程，同一项目文件夹）"></select>
      <button class="btn" id="copyChatBtnB" style="font-size:12px"
              onclick="copyChatAllB()" title="复制当前对话全部内容">复制全部</button>
      <button class="btn" id="replayBtnB" style="font-size:12px"
              onclick="replayLast('B')" title="朗读最近一条助手回复">回播</button>
      <button class="btn" id="newConvBtnB" style="font-size:12px"
              onclick="newChatB()">＋ 新对话</button>
    </div>
    <div id="dualWrap">
      <div class="dual-col" id="colB">
        <div id="chatB"><div class="chat-col" id="chatColB">
          <div class="chip-wrap"><div class="chip status">对话 B 就绪 — 可并行提问</div></div>
        </div></div>
        <div id="composerB"><div class="composer-inner">
          <textarea id="inputB" rows="3" placeholder="B：输入消息，Enter 发送，Shift+Enter 换行"></textarea>
          <div class="composer-tools">
            <span class="spacer"></span>
            <button class="stopbtn" id="stopSpeakToolB" onclick="stopSpeak()" disabled
                    style="display:none" title="停止当前语音播报">停止播报</button>
            <button class="stopbtn" id="stopBtnB" onclick="stopChatB()" disabled title="中断 B 对话">停止</button>
            <button class="sendbtn" id="sendBtnB" onclick="sendChatB()">发送</button>
          </div>
        </div></div>
      </div>
    </div>
  </section>
</div>

<!-- 执行前确认弹窗（LCA Permissions confirm，B 通道） -->
<div class="modal-mask" id="confirmDialog">
  <div class="modal">
    <h3>执行前确认</h3>
    <div style="font-size:12.5px;color:var(--muted);line-height:1.8">
      Agent 请求调用工具 <b id="cf_tool" style="color:var(--text)"></b>
      <span class="pill amber" id="cf_risk"></span>
      <div style="margin-top:8px;background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:9px 11px;font-family:Menlo,monospace;font-size:11px;word-break:break-all" id="cf_args"></div>
      <div style="margin-top:8px;font-size:11px;color:var(--faint)">10 分钟未确认将自动拒绝并记入审计</div>
    </div>
    <div style="display:flex;gap:8px;margin-top:16px">
      <button class="btn danger" style="flex:1" onclick="resolveConfirm(false)">拒绝</button>
      <button class="btn primary" style="flex:1" onclick="resolveConfirm(true)">批准执行</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>
<div class="ctx-menu" id="ctxMenu">
  <button id="ctxCopySel">复制选中</button>
  <button id="ctxCopyMsg">复制本条</button>
  <button id="ctxCopyAll">复制全部</button>
  <div class="sep"></div>
  <button id="ctxPaste">粘贴到输入框</button>
</div>

<script>
const $=id=>document.getElementById(id);
let curBot2=null;
let _ctxMsg=null, _ctxSel='', _pasteTarget=null;
let _confirmId='';

function esc(s){return String(s).replace(/&/g,'&').replace(/</g,'<').replace(/>/g,'>');}
function render(s){
  let h=esc(s);
  h=h.replace(/```(\w*)\n?([\s\S]*?)```/g,(_,l,c)=>'<pre><code>'+c+'</code></pre>');
  h=h.replace(/`([^`\n]+)`/g,'<code>$1</code>');
  return h;
}
function renderReply(s){
  const fences=[];
  let h=esc(String(s||''));
  h=h.replace(/```(\w*)\n?([\s\S]*?)```/g,(_,l,c)=>{
    fences.push('<pre><code>'+c+'</code></pre>');
    return '\x00F'+(fences.length-1)+'\x00';
  });
  h=h.replace(/`([^`\n]+)`/g,(_,c)=>{
    fences.push('<code>'+c+'</code>');
    return '\x00F'+(fences.length-1)+'\x00';
  });
  h=h.replace(/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/gm,'');
  h=h.replace(/^#{1,6}\s+/gm,'');
  h=h.replace(/^[\t ]*[-*+]\s+/gm,'');
  h=h.replace(/\*\*\*(.+?)\*\*\*/g,'<strong>$1</strong>');
  h=h.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
  h=h.replace(/__(.+?)__/g,'<strong>$1</strong>');
  h=h.replace(/(^|[^\*])\*(?!\s)([^*\n]+)\*(?!\*)/g,'$1$2');
  h=h.replace(/\*{1,3}/g,'');
  h=h.replace(/\x00F(\d+)\x00/g,(_,i)=>fences[i]);
  return h;
}
function toast(t){const el=$('toast');el.textContent=t;el.classList.add('show');
  setTimeout(()=>el.classList.remove('show'),2200);}

function colOf(chan){ const b=chan==='B'; return {chat:b?$('chatB'):$('chat'), col:b?$('chatColB'):$('chatCol')}; }
function addMsg(cls,text,chan){
  const C=colOf(chan||'B');
  const div=document.createElement('div');
  div.className='msg '+cls; div.innerHTML=cls==='bot'?renderReply(text):render(text);
  div._raw=text;
  const wrap=document.createElement('div');
  wrap.className='msg-wrap '+cls;
  const bar=document.createElement('div');
  bar.className='msg-actions';
  bar.innerHTML='<button class="ma-btn" data-a="copy">📋 复制</button>'+
    (cls==='bot'?'<button class="ma-btn" data-a="speak">🔊 回播</button>':'')+
    '<button class="ma-btn" data-a="share">↗ 分享</button>';
  bar.querySelector('[data-a=copy]').onclick=()=>copyPlain(div.innerText||div._raw||'');
  const sp=bar.querySelector('[data-a=speak]');
  if(sp) sp.onclick=()=>speakText(div._raw||div.innerText||'');
  bar.querySelector('[data-a=share]').onclick=()=>{
    pywebview.api.export_message(div._raw||'').then(r=>{
      if(r.ok)toast('已导出：'+r.path);
      else if(r.error)toast('导出失败：'+r.error);
    });
  };
  wrap.appendChild(div); wrap.appendChild(bar);
  if(cls==='bot'){
    const disc=document.createElement('div');
    disc.className='msg-disclaimer';
    disc.textContent='此内容由智能体模型提供。';
    wrap.appendChild(disc);
  }
  C.col.appendChild(wrap); C.chat.scrollTop=C.chat.scrollHeight;
  return div;
}
function copyPlain(text){
  const t=String(text||'');
  if(!t){toast('没有可复制的内容');return;}
  const done=ok=>toast(ok?'已复制到剪贴板':'复制失败');
  const viaDom=()=>{
    try{
      const ta=document.createElement('textarea');
      ta.value=t; ta.setAttribute('readonly','');
      ta.style.cssText='position:fixed;left:-9999px;top:0';
      document.body.appendChild(ta);
      ta.focus(); ta.select(); ta.setSelectionRange(0,t.length);
      const ok=document.execCommand('copy');
      document.body.removeChild(ta);
      return !!ok;
    }catch(err){return false;}
  };
  // pywebview 的 navigator.clipboard 常报成功却写不进系统剪贴板，必须走 pbcopy/clip
  if(window.pywebview&&pywebview.api&&pywebview.api.copy_text){
    pywebview.api.copy_text(t).then(ok=>{
      if(ok) done(true);
      else if(viaDom()) done(true);
      else done(false);
    }).catch(()=>{ done(viaDom()); });
    return;
  }
  if(viaDom()){done(true);return;}
  if(window.navigator&&navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(t).then(()=>done(true)).catch(()=>done(false));
    return;
  }
  done(false);
}
function chatPlainText(chan){
  const C=colOf(chan||'B');
  const parts=[];
  Array.from(C.col.children).forEach(el=>{
    if(el.classList.contains('msg-wrap')){
      const msg=el.querySelector('.msg');
      const raw=(msg&&(msg.innerText||msg._raw))||'';
      if(!raw)return;
      parts.push((el.classList.contains('user')?'你':'助手')+'：\n'+raw);
    }else if(el.classList.contains('chip')||el.classList.contains('chip-wrap')){
      const think=el.querySelector&&el.querySelector('.think-block');
      if(think){
        const raw=think._raw||think.innerText||'';
        if(raw)parts.push(raw);
        return;
      }
      const chip=el.classList.contains('chip')?el:el.querySelector('.chip');
      const raw=(chip&&(chip._raw||chip.textContent))||'';
      if(raw)parts.push(raw);
    }
  });
  return parts.join('\n\n');
}
function copyChatAllB(){ copyPlain(chatPlainText('B')); }
function setSpeakingUi(on){
  const show=!!on;
  window._speakingUi=show;
  const r=$('replayBtnB');
  if(r){
    if(show){
      r.textContent='停止播报';
      r.style.color='var(--bad)';
      r.style.borderColor='var(--bad)';
      r.title='停止当前语音播报';
      r.disabled=false;
      r.onclick=()=>stopSpeak();
    }else{
      r.textContent='回播';
      r.style.color='';
      r.style.borderColor='';
      r.title='朗读最近一条助手回复';
      r.disabled=false;
      r.onclick=()=>replayLast('B');
    }
  }
  const b=$('stopSpeakToolB');
  if(b){ b.style.display=show?'inline-block':'none'; b.disabled=!show; }
  document.querySelectorAll('.ma-btn[data-a=speak]').forEach(btn=>{
    if(show){
      btn.textContent='⏹ 停止播报';
      btn.dataset.wasSpeak='1';
      btn.onclick=()=>stopSpeak();
    }else if(btn.dataset.wasSpeak){
      btn.textContent='🔊 回播';
      delete btn.dataset.wasSpeak;
      const wrap=btn.closest('.msg-wrap');
      const msg=wrap&&wrap.querySelector('.msg');
      btn.onclick=()=>speakText((msg&&(msg._raw||msg.innerText))||'');
    }
  });
}
function stopSpeak(){
  if(window.pywebview&&pywebview.api&&pywebview.api.stop_speaking)
    pywebview.api.stop_speaking();
  setSpeakingUi(false);
  toast('已停止播报');
}
function speakText(t){
  const text=String(t||'').trim();
  if(!text){toast('没有可播报的内容');return;}
  if(window.pywebview&&pywebview.api&&pywebview.api.speak_text){
    setSpeakingUi(true);
    pywebview.api.speak_text(text);
    toast('正在回播 · 可点「停止播报」');
  }else toast('当前窗口不能播报');
}
function replayLast(chan){
  if(window._speakingUi){ stopSpeak(); return; }
  const C=colOf(chan||'B');
  const bots=C.col.querySelectorAll('.msg-wrap.bot .msg');
  const last=bots.length?bots[bots.length-1]:null;
  speakText((last&&(last._raw||last.innerText))||'');
}
function addChip(cls,text,chan){
  const C=colOf(chan||'B');
  const wrap=document.createElement('div');
  wrap.className='chip-wrap';
  const div=document.createElement('div');
  div.className='chip '+cls; div.textContent=text; div._raw=text;
  const bar=document.createElement('div');
  bar.className='msg-actions';
  bar.innerHTML='<button class="ma-btn" data-a="copy">📋 复制</button>';
  bar.querySelector('[data-a=copy]').onclick=()=>copyPlain(text);
  wrap.appendChild(div); wrap.appendChild(bar);
  C.col.appendChild(wrap); C.chat.scrollTop=C.chat.scrollHeight;
}
function ensureThink(chan){
  const C=colOf(chan||'B');
  let wrap=C.col.querySelector('.chip-wrap.think-wrap:not(.think-done)');
  let det, sum, reason, tools;
  if(wrap){
    det=wrap.querySelector('.think-block');
    sum=det&&det.querySelector('summary');
    reason=det&&det.querySelector('.think-reason');
    tools=det&&det.querySelector('.think-tools');
  }
  if(!det||!sum||!reason||!tools){
    wrap=document.createElement('div');
    wrap.className='chip-wrap think-wrap';
    det=document.createElement('details');
    det.className='think-block';
    sum=document.createElement('summary');
    sum.textContent='思考过程';
    const body=document.createElement('div');
    body.className='think-body';
    reason=document.createElement('div');
    reason.className='think-reason';
    tools=document.createElement('ul');
    tools.className='think-tools';
    body.appendChild(reason); body.appendChild(tools);
    det.appendChild(sum); det.appendChild(body);
    const bar=document.createElement('div');
    bar.className='msg-actions';
    bar.innerHTML='<button class="ma-btn" data-a="copy">📋 复制</button>';
    bar.querySelector('[data-a=copy]').onclick=()=>copyPlain(det._raw||'');
    wrap.appendChild(det); wrap.appendChild(bar);
    C.col.appendChild(wrap);
  }
  return {C:C, wrap:wrap, det:det, sum:sum, reason:reason, tools:tools};
}
function syncThinkMeta(t){
  const n=t.tools.children.length;
  t.sum.textContent=n?('思考过程 · '+n+' 步'):'思考过程';
  const parts=['思考过程'];
  if(t.reason._raw)parts.push(String(t.reason._raw));
  Array.from(t.tools.children).forEach(li=>{
    if(li._raw||li.textContent)parts.push(li._raw||li.textContent);
  });
  t.det._raw=parts.join('\\n');
  t.C.chat.scrollTop=t.C.chat.scrollHeight;
}
function addThink(text,chan){
  const raw=String(text||'').trim();
  if(!raw)return;
  const t=ensureThink(chan);
  t.reason._raw=raw;
  t.reason.innerHTML=render(raw);
  syncThinkMeta(t);
}
function addThinkTool(name,chan){
  const label=String(name||'').trim();
  if(!label)return;
  const t=ensureThink(chan);
  const li=document.createElement('li');
  li.textContent='🔧 '+label;
  li._raw='🔧 '+label;
  t.tools.appendChild(li);
  syncThinkMeta(t);
}
function setChatBusy(on,chan){
  $('sendBtnB').disabled=!!on;
  $('stopBtnB').disabled=!on;
  if(on){
    const C=colOf(chan||'B');
    C.col.querySelectorAll('.chip-wrap.think-wrap').forEach(w=>w.classList.add('think-done'));
  }
}
function clearChat(msg,chan){
  const C=colOf(chan||'B');
  C.col.innerHTML='';
  addChip('status',msg,chan);
  curBot2=null;
}
function loadConversations2(){
  const sel=$('convPickerB'); if(!sel)return;
  pywebview.api.get_conversations().then(d=>{
    sel.innerHTML='';
    const o0=document.createElement('option');
    o0.value=''; o0.textContent=d.items.length?'历史对话（'+d.items.length+'）':'暂无历史对话';
    sel.appendChild(o0);
    d.items.forEach(c=>{
      const o=document.createElement('option');
      o.value=c.id; o.textContent=c.title+' · '+c.count+'条';
      sel.appendChild(o);
    });
    sel.value='';
  });
}
function newChatB(){
  pywebview.api.new_conversation2().then(()=>{
    clearChat('新对话 B 已开始','B'); loadConversations2();
  });
}
function loadConv2(id){
  if(!id)return;
  pywebview.api.load_conversation2(id).then(r=>{
    if(!r.ok)return;
    clearChat('已载入历史对话（继续聊会自动带上前文）','B');
    (r.messages||[]).forEach(m=>{
      const role=m.role||'';
      if(role==='user'){
        colOf('B').col.querySelectorAll('.chip-wrap.think-wrap').forEach(w=>w.classList.add('think-done'));
        addMsg('user',m.text||'','B');
      }else if(role==='assistant'){
        addMsg('bot',m.text||'','B');
        colOf('B').col.querySelectorAll('.chip-wrap.think-wrap').forEach(w=>w.classList.add('think-done'));
      }else if(role==='thinking'){ addThink(m.text||'','B'); }
      else if(role==='tool'){ addThinkTool(m.name||m.text||'','B'); }
    });
    colOf('B').col.querySelectorAll('.chip-wrap.think-wrap').forEach(w=>w.classList.add('think-done'));
  });
}
function sendChatB(){
  const text=$('inputB').value.trim();
  if(!text)return;
  addMsg('user',text,'B');
  $('inputB').value=''; setChatBusy(true,'B'); curBot2=null;
  pywebview.api.send2(text).then(ok=>{
    if(!ok){addChip('error','上一条还在处理中','B');setChatBusy(false,'B');}
  });
}
function stopChatB(){
  $('stopBtnB').disabled=true;
  pywebview.api.stop2().then(ok=>{ if(!ok)setChatBusy(false,'B'); });
}

/* 项目切换：独立窗口只列已有项目（新建请到主窗口） */
function loadChatProjects(){
  pywebview.api.get_projects().then(d=>{
    const sel=$('chatProjSel'); if(!sel)return;
    sel.innerHTML='';
    (d.projects||[]).forEach(p=>{
      const o=document.createElement('option');
      o.value=p.id; o.textContent=p.name; o.title=p.path;
      if(p.id===d.active)o.selected=true;
      sel.appendChild(o);
    });
    if(d.active)sel.value=d.active;
  });
}
function onChatProject(pid){
  if(!pid)return;
  pywebview.api.switch_project(pid).then(r=>{
    if(!r.ok){toast(r.error);return;}
    toast('当前项目：'+r.project.name);
    loadChatProjects(); loadConversations2();
    clearChat('当前项目：'+r.project.name+' · 新对话 B','B');
  });
}

/* ---------- 右键复制粘贴 ---------- */
function hideCtx(){const m=$('ctxMenu');if(m)m.classList.remove('open');}
function composerInput(){
  if(_pasteTarget&&document.body.contains(_pasteTarget))return _pasteTarget;
  const a=document.activeElement;
  if(a&&(a.tagName==='TEXTAREA'||a.tagName==='INPUT')&&a.id!=='ctxPaste')return a;
  return $('inputB');
}
function insertAtCursor(inp,t){
  if(!inp)return;
  inp.focus();
  const s=typeof inp.selectionStart==='number'?inp.selectionStart:inp.value.length;
  const e=typeof inp.selectionEnd==='number'?inp.selectionEnd:s;
  inp.value=inp.value.slice(0,s)+t+inp.value.slice(e);
  const p=s+t.length;
  try{inp.selectionStart=inp.selectionEnd=p;}catch(err){}
}
function ctxCopy(what){
  let text='';
  if(what==='sel') text=_ctxSel||(_ctxMsg?(_ctxMsg.innerText||_ctxMsg._raw):'');
  else if(what==='msg') text=_ctxMsg?(_ctxMsg.innerText||_ctxMsg._raw):'';
  else text=chatPlainText();
  if(!text){toast('没有可复制的内容');return;}
  copyPlain(text);
  hideCtx();
}
function ctxPaste(){
  const inp=composerInput();
  const read=()=>{
    if(window.pywebview&&pywebview.api&&pywebview.api.read_clipboard)
      return pywebview.api.read_clipboard().catch(()=>'');
    if(window.navigator&&navigator.clipboard&&navigator.clipboard.readText)
      return navigator.clipboard.readText();
    return Promise.resolve('');
  };
  read().then(t=>{
    if(!t){toast('剪贴板为空');return;}
    if(!inp){toast('没有输入框');return;}
    insertAtCursor(inp,t);
    toast('已粘贴');
  }).catch(()=>toast('读取剪贴板失败'));
  hideCtx();
}
document.addEventListener('focusin',e=>{
  const t=e.target;
  if(t&&(t.id==='inputB'||t.tagName==='TEXTAREA'||t.tagName==='INPUT'))
    _pasteTarget=t;
});
document.addEventListener('contextmenu',e=>{
  if(!$('page-chat'))return;
  const t=e.target;
  e.preventDefault();
  const sel=window.getSelection();
  _ctxSel=(sel&&sel.rangeCount&&!sel.isCollapsed)?sel.toString():'';
  if(t&&t.closest&&t.closest('textarea,input')&&typeof t.selectionStart==='number'&&t.selectionStart!==t.selectionEnd)
    _ctxSel=t.value.slice(t.selectionStart,t.selectionEnd);
  _ctxMsg=t&&t.closest?t.closest('.msg'):null;
  const m=$('ctxMenu'); if(!m)return;
  m.style.left=Math.min(e.clientX, innerWidth-168)+'px';
  m.style.top=Math.min(e.clientY, innerHeight-160)+'px';
  m.classList.add('open');
});
document.addEventListener('click',e=>{
  if(e.target&&e.target.closest&&e.target.closest('#ctxMenu'))return;
  hideCtx();
});
document.addEventListener('keydown',e=>{
  if(e.key==='Escape')hideCtx();
  // ⌘/Ctrl+C/V/X 交给系统（WKWebView 需打开 DOMPasteAllowed）
});
['ctxCopySel','ctxCopyMsg','ctxCopyAll'].forEach(id=>{
  const el=$(id); if(el)el.onclick=()=>ctxCopy(id==='ctxCopySel'?'sel':id==='ctxCopyMsg'?'msg':'all');
});
const _pasteEl=$('ctxPaste'); if(_pasteEl)_pasteEl.onclick=ctxPaste;
const _ctxMenu=$('ctxMenu');
if(_ctxMenu)_ctxMenu.addEventListener('mousedown',e=>e.preventDefault());

/* Enter 发送 / Cmd+A 全选对话 */
$('inputB').addEventListener('keydown',e=>{
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChatB();}
});
document.addEventListener('keydown',e=>{
  if(!(e.metaKey||e.ctrlKey)||(e.key!=='a'&&e.key!=='A'))return;
  const tag=(document.activeElement&&document.activeElement.tagName)||'';
  if(tag==='INPUT'||tag==='TEXTAREA'||tag==='SELECT')return;
  e.preventDefault();
  const range=document.createRange();
  range.selectNodeContents($('chatColB'));
  const sel=window.getSelection();
  sel.removeAllRanges(); sel.addRange(range);
});

/* 执行前确认（B 通道） */
function resolveConfirm(ok){
  $('confirmDialog').classList.remove('open');
  if(_confirmId)pywebview.api.resolve_confirm2(_confirmId,ok);
  _confirmId='';
}

window._onEvent=function(ev){
  const ch=ev.chan||'B';
  const C=colOf(ch);
  if(ev.kind==='text'){
    if(!curBot2)curBot2=addMsg('bot','',ch);
    curBot2.innerHTML=renderReply(ev.text);
    curBot2._raw=ev.text;
    C.chat.scrollTop=C.chat.scrollHeight;
  }else if(ev.kind==='thinking'){
    addThink(ev.text,ch);
  }else if(ev.kind==='tool'){
    addThinkTool(ev.name,ch); // 工具调用收进「思考过程」折叠块
  }else if(ev.kind==='status'){
    addChip('status',ev.text,ch);
  }else if(ev.kind==='done'){
    curBot2=null; setChatBusy(false,ch);
    loadConversations2();
  }else if(ev.kind==='stopped'){
    curBot2=null; setChatBusy(false,ch);
    addChip('status','已停止',ch);
    loadConversations2();
  }else if(ev.kind==='error'){
    addChip('error','出错了：'+ev.text,ch);
    curBot2=null; setChatBusy(false,ch);
  }else if(ev.kind==='voice'){
    if(ev.state==='speaking') setSpeakingUi(true);
    else if(ev.state==='spoken'||ev.state==='error'){
      setSpeakingUi(false);
      if(ev.state==='error') toast('回播失败：'+(ev.text||'没有声音'));
    }
  }else if(ev.kind==='confirm'){
    _confirmId=ev.id;
    $('cf_tool').textContent=ev.tool;
    $('cf_risk').textContent=ev.risk;
    $('cf_args').textContent=ev.args;
    $('confirmDialog').classList.add('open');
  }
};

function boot(){
  loadChatProjects();
  loadConversations2();
}
if(window.pywebview&&window.pywebview.api) boot();
else window.addEventListener('pywebviewready', boot);
</script>
</body>
</html>
"""
)
