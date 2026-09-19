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
