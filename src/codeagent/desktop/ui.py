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
  display: flex; align-items: center; gap: 10px; padding: 4px 8px 16px;
  border-bottom: 1px solid var(--border); margin-bottom: 12px;
}
#sidebar .brand .mark {
  width: 36px; height: 36px; border-radius: 10px; flex-shrink: 0;
  overflow: hidden; background: #1a120c;
  border: 1px solid rgba(255,255,255,.08);
}
body.light #sidebar .brand .mark {
  background: #1a120c;
  border: 1px solid rgba(0,0,0,.12);
}
#sidebar .brand .mark img { width: 100%; height: 100%; object-fit: cover; display: block; }
#sidebar .brand .name { font-weight: 650; font-size: 14px; letter-spacing: .2px; }
#sidebar .brand .ver { font-size: 10.5px; color: var(--faint); }
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

/* ---------- chat ---------- */
#page-chat { padding: 0; }
#page-chat .msg, #page-chat .chip, #page-chat .fb-row {
  -webkit-user-select: text; user-select: text; cursor: text; }
#page-chat .msg-actions, #page-chat .ma-btn, #page-chat .fb-btn {
  -webkit-user-select: none; user-select: none; cursor: pointer; }
#chat { flex: 1; overflow-y: auto; padding: 22px 0; min-height: 0; }
.chat-col { max-width: 720px; margin: 0 auto; display: flex;
            flex-direction: column; gap: 12px; padding: 0 22px; }
.msg { max-width: 85%; padding: 11px 15px; border-radius: 14px;
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
#composer { padding: 13px 22px 16px; border-top: 1px solid var(--border);
            background: var(--sidebar); flex-shrink: 0; }
.composer-inner { max-width: 720px; margin: 0 auto; display: flex;
                  flex-direction: column; gap: 8px; }
#input { width: 100%; resize: none; border-radius: 12px; padding: 11px 13px;
         line-height: 1.55; }
.composer-tools { display: flex; gap: 8px; align-items: center; }
.composer-tools .spacer { flex: 1; }
.composer-video { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.composer-video .toolsel { flex: 1; min-width: 140px; max-width: none; }
.composer-video.is-off { display: none; }
#modelPicker { min-width: 180px; max-width: 260px; }
.toolbtn { background: var(--elev); border: 1px solid var(--border);
           color: var(--muted); border-radius: 9px; height: 34px;
           padding: 0 12px; cursor: pointer; font-size: 14px; }
.toolbtn:hover { border-color: var(--border-hi); color: var(--text); }
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
.msg-wrap { display: flex; flex-direction: column; max-width: 85%; }
.msg-wrap.user { align-self: flex-end; align-items: flex-end; }
.msg-wrap.bot { align-self: flex-start; align-items: flex-start; }
.msg-wrap .msg { max-width: 100%; }
.chip-wrap { display: flex; align-items: center; gap: 6px; align-self: flex-start; }
.chip-wrap .chip { align-self: auto; }
.msg-actions { display: flex; gap: 4px; margin-top: 3px; opacity: 1; }
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
.grid-32 { display: grid; grid-template-columns: 2fr 1fr; gap: 14px;
  align-items: start; }
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
    <div class="mark" title="CodeCoreAgent">
      <img alt="CCA" src="__BRAND_MARK_SRC__">
    </div>
    <div>
      <div class="name">CodeCoreAgent</div>
      <div class="ver" id="brandVer"></div>
    </div>
  </div>

  <div class="nav-group">
    <div class="g-label">概览</div>
    <button class="navbtn active" data-page="dashboard">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>
      总览</button>
    <button class="navbtn" data-page="chat">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M21 12a8 8 0 0 1-8 8H5l-2 2V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8z"/></svg>
      对话</button>
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
    <span class="sub" id="projSub">每个项目的对话、文件与内容都保存在本地文件夹</span>
    <span class="spacer"></span>
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
    <select id="convPicker" class="toolsel" style="max-width:200px"
            onchange="loadConv(this.value)" title="历史对话（保存在项目文件夹）"></select>
    <button class="btn" id="copyChatBtn" style="font-size:12px"
            onclick="copyChatAll()" title="复制当前对话全部内容">复制全部</button>
    <button class="btn" id="newConvBtn" style="font-size:12px"
            onclick="newChat()">＋ 新对话</button>
  </div>
  <div id="chat"><div class="chat-col" id="chatCol">
    <div class="chip-wrap"><div class="chip status">CodeCoreAgent 就绪 — 开始对话</div></div>
  </div></div>
  <div id="composer"><div class="composer-inner">
    <div id="attRow"></div>
    <textarea id="input" rows="2" placeholder="输入消息，Enter 发送，Shift+Enter 换行；📎 可附加任意文件"></textarea>
    <div class="composer-tools">
      <button class="toolbtn" id="attBtn" title="上传附件（所有文件类型均可识别）">📎</button>
      <select id="thinkingSel" class="toolsel" onchange="setThinking(this.value)" title="思考强度：注入系统提示，控制推理深度">
        <option value="low">思考 · 低</option>
        <option value="medium" selected>思考 · 中</option>
        <option value="high">思考 · 高</option>
      </select>
      <span class="spacer"></span>
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
    <span class="sub">Obsidian / LLM Wiki 结构 · 本地或跨电脑共享目录</span>
    <span class="spacer"></span>
    <button class="btn" onclick="openKnowledgeFolder()">📂 打开文件夹</button>
    <button class="btn primary" onclick="bootstrapKnowledge()">⚡ 一键布置</button>
  </div>
  <div class="page-body"><div class="settings-wrap" style="max-width:780px">
    <div class="card sect">
      <h3>连接设置</h3>
      <label>存储方式</label>
      <select id="kb_mode">
        <option value="local">本机目录</option>
        <option value="shared">跨电脑共享（NAS / 网盘同步 / 网络盘）</option>
      </select>
      <label>后端形态</label>
      <select id="kb_backend">
        <option value="obsidian">Obsidian 库（推荐，可用 Obsidian 打开）</option>
        <option value="llmwiki">LLM Wiki（同一套目录结构）</option>
      </select>
      <label>知识库路径</label>
      <input id="kb_path" placeholder="~/Documents/CodeCoreAgent-Wiki 或 /Volumes/NAS/wiki">
      <div class="hint" id="kb_hint">本机：默认 Documents 下独立库。跨电脑：把库放在 Syncthing / iCloud / NAS 挂载点，各机填写同一路径。</div>
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
      <div class="hint">节点图后端，不是聊天模型。工具 <code>video_generate</code> 的 provider=comfy，并提供 API 格式工作流 JSON。说明见融合技能 comfyui。</div>
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
    <span class="sub">语音、个性化与指挥中心默认链路</span></div>
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

    <div class="card sect"><h3>语音回复</h3>
      <div class="checkline"><input type="checkbox" id="cfg_voice">
        <span>朗读回复（edge-tts 免费语音包）</span></div>
      <label>音色</label><select id="cfg_voicename"></select>
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
    <label>存放位置（留空用默认目录）</label>
    <input id="pj_base" placeholder="">
    <div class="hint">将在该目录下创建项目文件夹——agent 产生的所有文件、内容与全部对话记录都保存在项目文件夹里</div>
    <div style="display:flex;gap:8px;margin-top:16px">
      <button class="btn" style="flex:1" onclick="$('projDialog').classList.remove('open')">取消</button>
      <button class="btn primary" style="flex:1" onclick="createProject()">创建</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const $ = id => document.getElementById(id);
let curBot = null;

function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function render(s){
  let h = esc(s);
  h = h.replace(/```(\w*)\n?([\s\S]*?)```/g,(_,l,c)=>'<pre><code>'+c+'</code></pre>');
  h = h.replace(/`([^`\n]+)`/g,'<code>$1</code>');
  return h;
}
function renderReply(s){
  /* 模型回复：消化 Markdown 星号/横杠，代码块原样保留 */
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
}
document.querySelectorAll('.navbtn[data-page]').forEach(b=>b.onclick=()=>go(b.dataset.page));

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
  pywebview.api.get_projects().then(d=>{$('pj_base').placeholder=d.default_base;});
  $('pj_name').value=''; $('pj_base').value='';
  $('projDialog').classList.add('open');
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
function clearChat(msg){
  $('chatCol').innerHTML='';
  addChip('status',msg);
  curBot=null;
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
    r.messages.forEach(m=>addMsg(m.role==='user'?'user':'bot',m.text));
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
function addMsg(cls,text){
  const div=document.createElement('div');
  div.className='msg '+cls; div.innerHTML=cls==='bot'?renderReply(text):render(text);
  div._raw=text;
  const wrap=document.createElement('div');
  wrap.className='msg-wrap '+cls;
  const bar=document.createElement('div');
  bar.className='msg-actions';
  bar.innerHTML='<button class="ma-btn" data-a="copy">📋 复制</button>'+
    '<button class="ma-btn" data-a="share">↗ 分享</button>';
  bar.querySelector('[data-a=copy]').onclick=()=>copyPlain(div.innerText||div._raw||'');
  bar.querySelector('[data-a=share]').onclick=()=>{
    pywebview.api.export_message(div._raw||'').then(r=>{
      if(r.ok)toast('已导出：'+r.path);
      else if(r.error)toast('导出失败：'+r.error);
    });
  };
  wrap.appendChild(div); wrap.appendChild(bar);
  $('chatCol').appendChild(wrap); $('chat').scrollTop=$('chat').scrollHeight;
  return div;
}
function copyPlain(text){
  const t=String(text||'');
  if(!t){toast('没有可复制的内容');return;}
  pywebview.api.copy_text(t).then(ok=>toast(ok?'已复制到剪贴板':'复制失败'));
}
function chatPlainText(){
  const parts=[];
  Array.from($('chatCol').children).forEach(el=>{
    if(el.classList.contains('msg-wrap')){
      const msg=el.querySelector('.msg');
      const raw=(msg&&(msg.innerText||msg._raw))||'';
      if(!raw)return;
      parts.push((el.classList.contains('user')?'你':'助手')+'：\n'+raw);
    }else if(el.classList.contains('chip')||el.classList.contains('chip-wrap')){
      const chip=el.classList.contains('chip')?el:el.querySelector('.chip');
      const raw=(chip&&(chip._raw||chip.textContent))||'';
      if(raw)parts.push(raw);
    }
  });
  return parts.join('\n\n');
}
function copyChatAll(){ copyPlain(chatPlainText()); }
function addChip(cls,text){
  const wrap=document.createElement('div');
  wrap.className='chip-wrap';
  const div=document.createElement('div');
  div.className='chip '+cls; div.textContent=text; div._raw=text;
  const bar=document.createElement('div');
  bar.className='msg-actions';
  bar.innerHTML='<button class="ma-btn" data-a="copy">📋 复制</button>';
  bar.querySelector('[data-a=copy]').onclick=()=>copyPlain(text);
  wrap.appendChild(div); wrap.appendChild(bar);
  $('chatCol').appendChild(wrap); $('chat').scrollTop=$('chat').scrollHeight;
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

/* ---------- 思考强度 ---------- */
function setThinking(v){
  pywebview.api.save_config({thinking:v}).then(()=>
    toast('思考强度：'+{low:'低',medium:'中',high:'高'}[v]));
}

function setChatBusy(on){
  $('sendBtn').disabled=!!on;
  $('stopBtn').disabled=!on;
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
$('input').addEventListener('keydown',e=>{
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChat();}
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
function addFeedbackRow(){
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
  $('chatCol').appendChild(row);
  $('chat').scrollTop=$('chat').scrollHeight;
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
function loadKnowledge(){
  pywebview.api.get_knowledge().then(d=>{
    const c=d.config||{}, s=d.status||{};
    $('kb_mode').value=c.mode||'local';
    $('kb_backend').value=c.backend||'obsidian';
    $('kb_path').value=c.path||'';
    $('kb_enabled').checked=c.enabled!==false;
    updateKbHint();
    const pills=[];
    pills.push(s.ready?'<span class="pill green">已布置</span>':'<span class="pill amber">未布置</span>');
    pills.push(s.exists?'<span class="pill">路径存在</span>':'<span class="pill">路径不存在</span>');
    pills.push(s.writable?'<span class="pill green">可写</span>':'<span class="pill">只读/不可写</span>');
    if(s.has_obsidian)pills.push('<span class="pill blue">Obsidian</span>');
    pills.push('<span class="pill">'+esc(String(s.page_count||0))+' 个 wiki 页</span>');
    $('kbStatus').innerHTML=pills.join(' ')+
      '<div style="margin-top:8px;font-family:Menlo,monospace;font-size:11px;color:var(--faint)">'+esc(s.path||'')+'</div>'+
      (s.ready?'':'<div style="margin-top:8px;color:var(--muted);font-size:12px">点击右上角「一键布置」按 CodeCoreAgent 结构创建 raw/ + wiki/ + AGENTS.md</div>');
    renderKbPages(d.pages||[]);
  });
}
function updateKbHint(){
  const shared=$('kb_mode').value==='shared';
  $('kb_hint').textContent=shared
    ?'跨电脑：填写 NAS 挂载点、SMB 映射盘或 Syncthing/iCloud/Dropbox 同步文件夹中的库路径，多机保持一致即可共享。'
    :'本机：默认 ~/Documents/CodeCoreAgent-Wiki。可用 Obsidian「打开文件夹作为库」浏览图谱。';
}
$('kb_mode').addEventListener('change',updateKbHint);
function saveKnowledgeConfig(){
  pywebview.api.save_knowledge_config(
    $('kb_path').value.trim(),
    $('kb_mode').value,
    $('kb_backend').value,
    $('kb_enabled').checked
  ).then(r=>{
    if(!r.ok){toast(r.error||'保存失败');return;}
    toast('知识库连接已保存');
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
      ?'<span class="pill green">在线</span> '+esc(cf.base||'')
      :(c.comfy_base?'<span class="pill">离线</span> 打不开该地址':'未接入');
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

/* ---------- skills ---------- */
function skillPackOf(s){
  if(s.pack==='fusion')return 'fusion';
  if(/video|wan-gradio|remotion|libtv|short-drama|ops-analyze|multi-publish/.test(s.name||''))
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
      o.textContent=ep.kind==='gradio'?name+'（文生视频）':name+'（本地）';
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
        :(ep.kind==='ollama'?'<span class="pill">Ollama</span>':''));
    const onlinePill=ep.kind==='gradio'
      ?'<span class="pill green">在线</span>'
      :'<span class="pill green">在线 · '+(ep.models||[]).length+' 个模型</span>';
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
    el.innerHTML='<div class="dashed">模型列表为空。端点在线时会自动列出其模型；支持 Ollama、局域网 OpenAI 兼容服务，以及 Gradio 文生视频（如 WAN）。</div>';
    return;
  }
  el.innerHTML=rows.map(m=>{
    const isGradio=m.ep.kind==='gradio';
    const manageable=m.manageable!==false && m.ep.kind!=='openai' && !isGradio;
    const status=isGradio
      ?'<span class="pill purple">文生视频</span>'
      :(m.ep.kind==='openai'
        ?'<span class="pill green">可用</span>'
        :(m.running?'<span class="pill green">running</span>':'<span class="pill">stopped</span>'));
    return '<div class="card" style="display:flex;align-items:center;justify-content:flex-end;margin-bottom:9px;padding:13px 16px">'+
      '<div style="flex:1"><div style="display:flex;align-items:center;gap:8px">'+
      '<span style="font-weight:550;cursor:pointer" '+
      (isGradio?'title="设为当前文生视频模型"':'title="设为当前模型"')+
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
        :(isGradio
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
function resolveConfirm(ok){
  $('confirmDialog').classList.remove('open');
  if(_confirmId)pywebview.api.resolve_confirm(_confirmId,ok);
  _confirmId='';
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
function saveAll(){
  Promise.all([
    pywebview.api.save_config({
      provider:$('cfg_provider').value, model:$('cfg_model').value,
      api_key:$('cfg_key').value, base_url:$('cfg_base').value,
      strategy:$('cfg_strategy').value, auto_yes:$('cfg_yes').checked,
      voice_enabled:$('cfg_voice').checked, voice_name:$('cfg_voicename').value,
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
  if(ev.kind==='text'){
    if(!curBot)curBot=addMsg('bot','');
    curBot.innerHTML=renderReply(ev.text);
    curBot._raw=ev.text;
    $('chat').scrollTop=$('chat').scrollHeight;
  }else if(ev.kind==='tool'){
    addChip('','🔧 '+ev.name);
  }else if(ev.kind==='status'){
    addChip('status',ev.text);
  }else if(ev.kind==='done'){
    curBot=null; setChatBusy(false);
    addFeedbackRow();
    loadConversations();  // 刷新历史对话计数
  }else if(ev.kind==='stopped'){
    curBot=null; setChatBusy(false); $('leadBtn').disabled=false;
    $('confirmDialog').classList.remove('open'); _confirmId='';
    addChip('status','已停止');
    loadConversations();
  }else if(ev.kind==='error'){
    addChip('error','出错了：'+ev.text);
    curBot=null; setChatBusy(false); $('leadBtn').disabled=false;
  }else if(ev.kind==='task'){
    upsertTask(ev);
  }else if(ev.kind==='lead_done'){
    $('leadBtn').disabled=false;
    const div=document.createElement('div');
    div.className='reply-box'; div.innerHTML=renderReply(ev.text);
    $('leadReply').innerHTML=''; $('leadReply').appendChild(div);
    loadRuns();
  }else if(ev.kind==='confirm'){
    _confirmId=ev.id;
    $('cf_tool').textContent=ev.tool;
    $('cf_risk').textContent=ev.risk;
    $('cf_args').textContent=ev.args;
    $('confirmDialog').classList.add('open');
  }else if(ev.kind==='pull_done'){
    if(ev.ok){toast(ev.model+' 部署完成，可在此启动');}
    else{toast('部署失败：'+ev.error);}
    if($('page-models').classList.contains('active'))loadModelsPage();
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
}
if(window.pywebview&&window.pywebview.api) bootUi();
else window.addEventListener('pywebviewready', bootUi);
setInterval(loadNavStatus, 15000);
</script>
</body>
</html>
"""
