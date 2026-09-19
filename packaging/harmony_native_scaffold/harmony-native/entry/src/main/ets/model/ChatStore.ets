import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';
import { ChatMessage } from './LLMClient';

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  updated: number;
}

const PREF_NAME = 'cca_convos';

function key(id: string): string {
  return `conv_${id}`;
}

export function newId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

export function loadAllIds(ctx: common.UIAbilityContext): string[] {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    const ids = pref.getSync('ids', '[]') as string;
    return JSON.parse(ids) as string[];
  } catch (_e) {
    return [];
  }
}

export function saveIds(ctx: common.UIAbilityContext, ids: string[]): void {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    pref.putSync('ids', JSON.stringify(ids));
    pref.flush();
  } catch (_e) {
  }
}

export function loadConvo(ctx: common.UIAbilityContext, id: string): Conversation | null {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    const raw = pref.getSync(key(id), '') as string;
    if (!raw) return null;
    return JSON.parse(raw) as Conversation;
  } catch (_e) {
    return null;
  }
}

export function saveConvo(ctx: common.UIAbilityContext, conv: Conversation): void {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    pref.putSync(key(conv.id), JSON.stringify(conv));
    let ids = loadAllIds(ctx);
    if (!ids.includes(conv.id)) {
      ids = [conv.id, ...ids];
      pref.putSync('ids', JSON.stringify(ids));
    }
    pref.flush();
  } catch (_e) {
  }
}

export function deleteConvo(ctx: common.UIAbilityContext, id: string): void {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    pref.deleteSync(key(id));
    let ids = loadAllIds(ctx).filter((x) => x !== id);
    pref.putSync('ids', JSON.stringify(ids));
    pref.flush();
  } catch (_e) {
  }
}
