import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';

export interface ActivityItem {
  id: string;
  kind: string;
  text: string;
  at: number;
}

const PREF_NAME = 'cca_activity';
const MAX = 200;

export function loadActivity(ctx: common.UIAbilityContext): ActivityItem[] {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    const raw = pref.getSync('items', '[]') as string;
    return JSON.parse(raw) as ActivityItem[];
  } catch (_e) {
    return [];
  }
}

export function pushActivity(ctx: common.UIAbilityContext, kind: string, text: string): void {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    const raw = pref.getSync('items', '[]') as string;
    const list = JSON.parse(raw) as ActivityItem[];
    list.unshift({
      id: Date.now().toString(36),
      kind,
      text,
      at: Date.now(),
    });
    while (list.length > MAX) {
      list.pop();
    }
    pref.putSync('items', JSON.stringify(list));
    pref.flush();
  } catch (_e) {
  }
}

export function clearActivity(ctx: common.UIAbilityContext): void {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    pref.putSync('items', '[]');
    pref.flush();
  } catch (_e) {
  }
}
