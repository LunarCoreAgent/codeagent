import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';

export interface MemoryItem {
  id: string;
  content: string;
  created: number;
  updated?: number;
  source?: string;
  kind?: string;
  zone?: string;
}

const PREF_NAME = 'cca_memory';
const TOKEN_RE = /[a-z0-9_]+|[\u4e00-\u9fff]/g;

export function loadMemories(ctx: common.UIAbilityContext): MemoryItem[] {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    const raw = pref.getSync('items', '[]') as string;
    const list = JSON.parse(raw) as MemoryItem[];
    list.sort((a, b) => (b.updated || b.created) - (a.updated || a.created));
    return list;
  } catch (_e) {
    return [];
  }
}

export function saveMemories(ctx: common.UIAbilityContext, items: MemoryItem[]): void {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    pref.putSync('items', JSON.stringify(items));
    pref.flush();
  } catch (_e) {
  }
}

export function addMemory(
  ctx: common.UIAbilityContext,
  content: string,
  source: string = 'manual',
  kind: string = 'fact',
  zone: string = '',
): MemoryItem {
  const now = Date.now();
  const item: MemoryItem = {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    content: content.trim(),
    created: now,
    updated: now,
    source: source,
    kind: kind,
    zone: zone,
  };
  const list = loadMemories(ctx);
  list.unshift(item);
  saveMemories(ctx, list);
  return item;
}

export function updateMemory(ctx: common.UIAbilityContext, id: string, content: string): boolean {
  const list = loadMemories(ctx);
  const hit = list.find((x) => x.id === id);
  if (!hit) {
    return false;
  }
  hit.content = content.trim();
  hit.updated = Date.now();
  saveMemories(ctx, list);
  return true;
}

export function deleteMemory(ctx: common.UIAbilityContext, id: string): void {
  const list = loadMemories(ctx).filter((x) => x.id !== id);
  saveMemories(ctx, list);
}

function tokenize(text: string): string[] {
  const out: string[] = [];
  const lower = text.toLowerCase();
  TOKEN_RE.lastIndex = 0;
  let m = TOKEN_RE.exec(lower);
  while (m) {
    out.push(m[0]);
    m = TOKEN_RE.exec(lower);
  }
  TOKEN_RE.lastIndex = 0;
  return out;
}

export function searchMemories(ctx: common.UIAbilityContext, q: string): MemoryItem[] {
  const all = loadMemories(ctx);
  const kw = q.trim();
  if (kw.length === 0) {
    return all;
  }
  const queryTokens = tokenize(kw);
  if (queryTokens.length === 0) {
    return all.filter((m) => m.content.toLowerCase().indexOf(kw.toLowerCase()) >= 0);
  }
  const querySet = new Set(queryTokens);
  const scored: Array<[number, MemoryItem]> = [];
  for (const memory of all) {
    const memSet = new Set(tokenize(memory.content));
    let overlap = 0;
    querySet.forEach((t) => {
      if (memSet.has(t)) {
        overlap += 1;
      }
    });
    if (overlap > 0) {
      const score = overlap / (Math.sqrt(querySet.size) * Math.sqrt(memSet.size || 1));
      scored.push([score, memory]);
    }
  }
  scored.sort((a, b) => b[0] - a[0]);
  return scored.map((pair) => pair[1]);
}

export function recentTurns(ctx: common.UIAbilityContext, zone: string = '', limit: number = 5): MemoryItem[] {
  const all = loadMemories(ctx);
  const hits: MemoryItem[] = [];
  for (const memory of all) {
    const kind = memory.kind || '';
    if (kind !== 'turn' && kind !== 'thinking' && kind !== 'conversation') {
      continue;
    }
    if (zone.length > 0 && (memory.zone || '') !== zone) {
      continue;
    }
    hits.push(memory);
    if (hits.length >= limit) {
      break;
    }
  }
  return hits;
}

export function beginZone(ctx: common.UIAbilityContext, zone: string, title: string): void {
  if (zone.length === 0) {
    return;
  }
  const exists = loadMemories(ctx).some((m) => (m.zone || '') === zone && (m.kind || '') === 'progress');
  if (exists) {
    return;
  }
  addMemory(ctx, `开始记录「${title}」的对话、思考与进度。`, 'auto', 'progress', zone);
}

export function rememberTurn(
  ctx: common.UIAbilityContext,
  zone: string,
  user: string,
  assistant: string,
): MemoryItem {
  const u = user.trim().slice(0, 400);
  const a = assistant.trim().slice(0, 500);
  const item = addMemory(ctx, `用户：${u}\n助手：${a}`, 'auto', 'turn', zone);
  const progress = loadMemories(ctx).find((m) => (m.zone || '') === zone && (m.kind || '') === 'progress');
  const line = `项目进度：最近在处理「${u.slice(0, 80)}」`;
  if (progress) {
    updateMemory(ctx, progress.id, line);
  } else {
    addMemory(ctx, line, 'auto', 'progress', zone);
  }
  return item;
}

export function memoryPromptBlock(
  ctx: common.UIAbilityContext,
  query: string,
  limit: number = 5,
  zone: string = '',
): string {
  const recent = recentTurns(ctx, zone, limit);
  const hits = searchMemories(ctx, query).slice(0, limit);
  const seen = new Set(recent.map((m) => m.id));
  const extra = hits.filter((m) => !seen.has(m.id));
  if (recent.length === 0 && extra.length === 0) {
    return '';
  }
  const parts: string[] = [];
  if (recent.length > 0) {
    parts.push('[最近 5 条对话记忆 — 只使用下列条目，不要编造未列出的细节]');
    parts.push(recent.map((m) => `- ${m.content}`).join('\n'));
  }
  if (extra.length > 0) {
    parts.push('[相关记忆 — 只使用下列条目，不要编造未列出的细节]');
    parts.push(extra.map((m) => `- ${m.content}`).join('\n'));
  }
  return '\n\n' + parts.join('\n');
}
