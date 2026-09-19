import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';

export interface MemoryItem {
  id: string;
  content: string;
  created: number;
}

const PREF_NAME = 'cca_memory';

export function loadMemories(ctx: common.UIAbilityContext): MemoryItem[] {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    const raw = pref.getSync('items', '[]') as string;
    const list = JSON.parse(raw) as MemoryItem[];
    list.sort((a, b) => b.created - a.created);
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

export function addMemory(ctx: common.UIAbilityContext, content: string): MemoryItem {
  const item: MemoryItem = {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    content: content.trim(),
    created: Date.now(),
  };
  const list = loadMemories(ctx);
  list.unshift(item);
  saveMemories(ctx, list);
  return item;
}

export function deleteMemory(ctx: common.UIAbilityContext, id: string): void {
  const list = loadMemories(ctx).filter((x) => x.id !== id);
  saveMemories(ctx, list);
}

export function searchMemories(ctx: common.UIAbilityContext, q: string): MemoryItem[] {
  const kw = q.trim().toLowerCase();
  const all = loadMemories(ctx);
  if (kw.length === 0) {
    return all;
  }
  return all.filter((m) => m.content.toLowerCase().indexOf(kw) >= 0);
}
