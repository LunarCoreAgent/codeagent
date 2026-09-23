import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';

export interface LocalEndpoint {
  id: string;
  label: string;
  baseUrl: string;   // 如 http://192.168.1.10:11434 或带 /v1
  role: string;      // primary | backup
  models: string[];
  kind: string;      // ollama | openai | unknown
  updated: number;
}

const PREF_NAME = 'cca_local_eps';

export function loadEndpoints(ctx: common.UIAbilityContext): LocalEndpoint[] {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    const raw = pref.getSync('endpoints', '[]') as string;
    return JSON.parse(raw) as LocalEndpoint[];
  } catch (_e) {
    return [];
  }
}

export function saveEndpoints(ctx: common.UIAbilityContext, list: LocalEndpoint[]): void {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    pref.putSync('endpoints', JSON.stringify(list));
    pref.flush();
  } catch (_e) {
  }
}

/** 规范化本地端点：保留用户输入，检测时再补 /v1 */
export function normalizeLocalBase(raw: string): string {
  let s = raw.trim().replace(/：/g, ':').replace(/／/g, '/');
  if (s.length === 0) {
    return '';
  }
  if (!s.startsWith('http://') && !s.startsWith('https://')) {
    s = 'http://' + s;
  }
  while (s.endsWith('/')) {
    s = s.slice(0, s.length - 1);
  }
  return s;
}

/** 对话用 OpenAI 兼容 base（自动补 /v1） */
export function toChatBase(base: string): string {
  const b = normalizeLocalBase(base);
  if (b.endsWith('/v1')) {
    return b;
  }
  if (b.indexOf('/v1/') >= 0) {
    return b;
  }
  return b + '/v1';
}

export interface StallBackup {
  model: string;
  baseUrl: string;
}

export function modelSizeRank(name: string): number {
  const n = name.toLowerCase();
  if (n.indexOf('120b') >= 0) {
    return 120;
  }
  if (n.indexOf('72b') >= 0) {
    return 72;
  }
  if (n.indexOf('70b') >= 0) {
    return 70;
  }
  if (n.indexOf('32b') >= 0) {
    return 32;
  }
  if (n.indexOf('14b') >= 0) {
    return 14;
  }
  if (n.indexOf('8b') >= 0) {
    return 8;
  }
  if (n.indexOf('7b') >= 0) {
    return 7;
  }
  if (n.indexOf('3b') >= 0) {
    return 3;
  }
  return 40;
}

/** 卡住时优先改走更小的本机模型。 */
export function pickStallBackup(
  list: LocalEndpoint[],
  currentModel: string,
  currentBase: string,
): StallBackup | null {
  const curBase = toChatBase(currentBase);
  const cands: StallBackup[] = [];
  for (let i = 0; i < list.length; i++) {
    const ep = list[i];
    const base = toChatBase(ep.baseUrl);
    for (let j = 0; j < ep.models.length; j++) {
      const mid = ep.models[j];
      if (mid === currentModel && base === curBase) {
        continue;
      }
      cands.push({ model: mid, baseUrl: base });
    }
  }
  if (cands.length === 0) {
    return null;
  }
  cands.sort((a: StallBackup, b: StallBackup): number => {
    return modelSizeRank(a.model) - modelSizeRank(b.model);
  });
  return cands[0];
}
