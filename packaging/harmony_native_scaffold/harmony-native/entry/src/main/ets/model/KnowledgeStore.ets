import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';

/** 与桌面版 KnowledgeConfig 对齐 */
export interface KnowledgeConfig {
  enabled: boolean;
  mode: string;      // local | shared
  backend: string;   // obsidian | llmwiki
  path: string;
  bootstrapped: boolean;
}

export interface WikiPage {
  id: string;
  rel: string;
  title: string;
  body: string;
  kind: string;      // wiki | raw
  updated: number;
}

interface SeedPage {
  rel: string;
  title: string;
  body: string;
}

export interface VaultStatusInfo {
  ready: boolean;
  enabled: boolean;
  mode: string;
  backend: string;
  path: string;
  page_count: number;
  wiki_count: number;
  raw_count: number;
  writable: boolean;
  shared: boolean;
}

/** 兼容旧版扁平文档 */
export interface KnowledgeDoc {
  id: string;
  title: string;
  body: string;
  updated: number;
}

const PREF_NAME = 'cca_knowledge';
const DEFAULT_PATH = '本机沙箱 / CodeCoreAgent-Wiki';

const DEFAULT_CFG: KnowledgeConfig = {
  enabled: true,
  mode: 'local',
  backend: 'obsidian',
  path: DEFAULT_PATH,
  bootstrapped: false,
};

function newId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

export function loadKnowledgeConfig(ctx: common.UIAbilityContext): KnowledgeConfig {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    return {
      enabled: pref.getSync('enabled', DEFAULT_CFG.enabled) as boolean,
      mode: pref.getSync('mode', DEFAULT_CFG.mode) as string,
      backend: pref.getSync('backend', DEFAULT_CFG.backend) as string,
      path: pref.getSync('path', DEFAULT_CFG.path) as string,
      bootstrapped: pref.getSync('bootstrapped', DEFAULT_CFG.bootstrapped) as boolean,
    };
  } catch (_e) {
    return DEFAULT_CFG;
  }
}

export function saveKnowledgeConfig(ctx: common.UIAbilityContext, cfg: KnowledgeConfig): void {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    pref.putSync('enabled', cfg.enabled);
    pref.putSync('mode', cfg.mode);
    pref.putSync('backend', cfg.backend);
    pref.putSync('path', cfg.path);
    pref.putSync('bootstrapped', cfg.bootstrapped);
    pref.flush();
  } catch (_e) {
  }
}

export function loadPages(ctx: common.UIAbilityContext): WikiPage[] {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    const raw = pref.getSync('pages', '') as string;
    if (raw.length > 0) {
      const list = JSON.parse(raw) as WikiPage[];
      list.sort((a, b) => b.updated - a.updated);
      return list;
    }
    // 迁移旧 docs
    const old = pref.getSync('docs', '[]') as string;
    const docs = JSON.parse(old) as KnowledgeDoc[];
    const pages: WikiPage[] = [];
    for (let i = 0; i < docs.length; i++) {
      const d = docs[i];
      pages.push({
        id: d.id,
        rel: `wiki/notes/${d.id}.md`,
        title: d.title,
        body: d.body,
        kind: 'wiki',
        updated: d.updated,
      });
    }
    if (pages.length > 0) {
      savePages(ctx, pages);
    }
    return pages;
  } catch (_e) {
    return [];
  }
}

export function savePages(ctx: common.UIAbilityContext, pages: WikiPage[]): void {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    pref.putSync('pages', JSON.stringify(pages));
    pref.flush();
  } catch (_e) {
  }
}

export function upsertPage(ctx: common.UIAbilityContext, page: WikiPage): void {
  const pages = loadPages(ctx);
  const idx = pages.findIndex((p) => p.id === page.id);
  if (idx >= 0) {
    pages[idx] = page;
  } else {
    pages.unshift(page);
  }
  savePages(ctx, pages);
}

export function deletePage(ctx: common.UIAbilityContext, id: string): void {
  savePages(ctx, loadPages(ctx).filter((p) => p.id !== id));
}

export function searchPages(ctx: common.UIAbilityContext, q: string): WikiPage[] {
  const raw = q.trim().toLowerCase();
  const all = loadPages(ctx);
  if (raw.length === 0) {
    return all;
  }
  const tokens = raw.split(' ').filter((t) => t.length > 0);
  return all.filter((p) => {
    const hay = `${p.rel} ${p.title} ${p.body.slice(0, 2000)}`.toLowerCase();
    for (let i = 0; i < tokens.length; i++) {
      if (hay.indexOf(tokens[i]) < 0) {
        return false;
      }
    }
    return true;
  });
}

/** 修复布置：写入种子 wiki 页 */
export function bootstrapVault(ctx: common.UIAbilityContext): number {
  const cfg = loadKnowledgeConfig(ctx);
  const pages = loadPages(ctx);
  const have = new Set<string>();
  for (let i = 0; i < pages.length; i++) {
    have.add(pages[i].rel);
  }
  const seeds: SeedPage[] = [
    {
      rel: 'wiki/index.md',
      title: 'Wiki 索引',
      body: '# CodeCoreAgent Wiki\n\n本库与桌面版 Obsidian / LLM Wiki 结构对齐。\n\n- [[overview|总览]]\n- [[log|日志]]\n- 原始材料见 `raw/inbox`\n',
    } as SeedPage,
    {
      rel: 'wiki/overview.md',
      title: '总览',
      body: '# 总览\n\n在此沉淀项目概念、决策与实体。通过「投递原始材料」写入 inbox，再整理到 wiki。\n',
    } as SeedPage,
    {
      rel: 'wiki/log.md',
      title: '知识日志',
      body: '# 知识日志\n\n| 时间 | 事件 |\n|------|------|\n',
    } as SeedPage,
    {
      rel: 'wiki/concepts/codecore.md',
      title: 'CodeCoreAgent',
      body: '# CodeCoreAgent\n\n跨桌面与鸿蒙的智能体产品。鸿蒙端知识库存于本机沙箱，可与桌面版导出/导入互通。\n',
    } as SeedPage,
  ];
  let created = 0;
  for (let i = 0; i < seeds.length; i++) {
    const s = seeds[i];
    if (have.has(s.rel)) {
      continue;
    }
    const page: WikiPage = {
      id: newId(),
      rel: s.rel,
      title: s.title,
      body: s.body,
      kind: 'wiki',
      updated: Date.now(),
    };
    pages.push(page);
    created += 1;
  }
  savePages(ctx, pages);
  cfg.bootstrapped = true;
  cfg.enabled = true;
  if (cfg.path.trim().length === 0) {
    cfg.path = DEFAULT_PATH;
  }
  saveKnowledgeConfig(ctx, cfg);
  return created;
}

/** 投递到 raw/inbox，并追加 wiki/log */
export function ingestText(ctx: common.UIAbilityContext, title: string, content: string): WikiPage {
  const slug = title.trim().slice(0, 24).split(' ').join('-') || 'note';
  const now = new Date();
  const pad = (n: number): string => (n < 10 ? `0${n}` : `${n}`);
  const stamp =
    `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-` +
    `${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
  const rel = `raw/inbox/${stamp}-${slug}.md`;
  const page: WikiPage = {
    id: newId(),
    rel: rel,
    title: title.trim().length > 0 ? title.trim() : stamp,
    body: `# ${title.trim() || '未命名'}\n\n${content}\n`,
    kind: 'raw',
    updated: Date.now(),
  };
  upsertPage(ctx, page);

  // 追加日志
  const pages = loadPages(ctx);
  const logIdx = pages.findIndex((p) => p.rel === 'wiki/log.md');
  const line = `| ${now.toLocaleString()} | 投递 ${page.title} → \`${rel}\` |\n`;
  if (logIdx >= 0) {
    pages[logIdx].body = pages[logIdx].body + line;
    pages[logIdx].updated = Date.now();
    savePages(ctx, pages);
  }
  return page;
}

export function vaultStatus(ctx: common.UIAbilityContext): VaultStatusInfo {
  const cfg = loadKnowledgeConfig(ctx);
  const pages = loadPages(ctx);
  let wikiCount = 0;
  let rawCount = 0;
  for (let i = 0; i < pages.length; i++) {
    if (pages[i].kind === 'raw') {
      rawCount += 1;
    } else {
      wikiCount += 1;
    }
  }
  const info: VaultStatusInfo = {
    ready: cfg.bootstrapped,
    enabled: cfg.enabled,
    mode: cfg.mode,
    backend: cfg.backend,
    path: cfg.path,
    page_count: pages.length,
    wiki_count: wikiCount,
    raw_count: rawCount,
    writable: true,
    shared: cfg.mode === 'shared',
  };
  return info;
}

/** 对话注入：取与用户问题相关的前几条知识摘要 */
export function buildKnowledgeContext(ctx: common.UIAbilityContext, query: string): string {
  const cfg = loadKnowledgeConfig(ctx);
  if (!cfg.enabled || !cfg.bootstrapped) {
    return '';
  }
  const hits = searchPages(ctx, query);
  const use = hits.length > 0 ? hits : loadPages(ctx);
  const max = Math.min(use.length, 4);
  if (max === 0) {
    return '';
  }
  let out = '\n\n[知识库上下文 — knowledge_search]\n';
  for (let i = 0; i < max; i++) {
    const p = use[i];
    out += `### ${p.title} (${p.rel})\n${p.body.slice(0, 800)}\n\n`;
  }
  return out;
}

// —— 兼容旧 Index 调用 ——
export function loadDocs(ctx: common.UIAbilityContext): KnowledgeDoc[] {
  const pages = loadPages(ctx);
  const docs: KnowledgeDoc[] = [];
  for (let i = 0; i < pages.length; i++) {
    const p = pages[i];
    const d: KnowledgeDoc = { id: p.id, title: p.title, body: p.body, updated: p.updated };
    docs.push(d);
  }
  return docs;
}

export function saveDocs(ctx: common.UIAbilityContext, docs: KnowledgeDoc[]): void {
  const pages: WikiPage[] = [];
  for (let i = 0; i < docs.length; i++) {
    const d = docs[i];
    const page: WikiPage = {
      id: d.id,
      rel: `wiki/notes/${d.id}.md`,
      title: d.title,
      body: d.body,
      kind: 'wiki',
      updated: d.updated,
    };
    pages.push(page);
  }
  savePages(ctx, pages);
}

export function upsertDoc(ctx: common.UIAbilityContext, doc: KnowledgeDoc): void {
  const page: WikiPage = {
    id: doc.id,
    rel: `wiki/notes/${doc.id}.md`,
    title: doc.title,
    body: doc.body,
    kind: 'wiki',
    updated: doc.updated,
  };
  upsertPage(ctx, page);
}

export function deleteDoc(ctx: common.UIAbilityContext, id: string): void {
  deletePage(ctx, id);
}

export function searchDocs(ctx: common.UIAbilityContext, q: string): KnowledgeDoc[] {
  const pages = searchPages(ctx, q);
  const docs: KnowledgeDoc[] = [];
  for (let i = 0; i < pages.length; i++) {
    const p = pages[i];
    const d: KnowledgeDoc = { id: p.id, title: p.title, body: p.body, updated: p.updated };
    docs.push(d);
  }
  return docs;
}
