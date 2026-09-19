import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';

export interface LLMConfig {
  baseUrl: string;
  apiKey: string;
  model: string;
  temperature: number;
  theme: string;          // light | dark | auto
  systemPrompt: string;
  nickname: string;
  companionOn: boolean;
  companionName: string;
  autoYes: boolean;
  maxIterations: number;
  /** auto | zh-Hans | zh-Hant | en | ja | fr | es | ko */
  language: string;
}

export interface ApiModelItem {
  id: string;
  name: string;
  baseUrl: string;
  apiKey: string;
  model: string;
  enabled: boolean;
}

const DEFAULT: LLMConfig = {
  baseUrl: 'https://api.openai.com/v1',
  apiKey: '',
  model: 'gpt-4o',
  temperature: 0.7,
  theme: 'auto',
  systemPrompt: '你是 CodeCoreAgent，一个专业的编程与任务助手。回答简洁、可执行。',
  nickname: '',
  companionOn: false,
  companionName: '助手',
  autoYes: false,
  maxIterations: 80,
  language: 'auto',
};

const PREF_NAME = 'cca_config';

export function loadConfig(ctx: common.UIAbilityContext): LLMConfig {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
      const chosen = pref.getSync('themeChosen', false) as boolean;
      let theme = pref.getSync('theme', DEFAULT.theme) as string;
      if (!chosen) {
        theme = 'auto';
      }
      return {
      baseUrl: pref.getSync('baseUrl', DEFAULT.baseUrl) as string,
      apiKey: pref.getSync('apiKey', DEFAULT.apiKey) as string,
      model: pref.getSync('model', DEFAULT.model) as string,
      temperature: pref.getSync('temperature', DEFAULT.temperature) as number,
      theme: theme,
      systemPrompt: pref.getSync('systemPrompt', DEFAULT.systemPrompt) as string,
      nickname: pref.getSync('nickname', DEFAULT.nickname) as string,
      companionOn: pref.getSync('companionOn', DEFAULT.companionOn) as boolean,
      companionName: pref.getSync('companionName', DEFAULT.companionName) as string,
      autoYes: pref.getSync('autoYes', DEFAULT.autoYes) as boolean,
      maxIterations: pref.getSync('maxIterations', DEFAULT.maxIterations) as number,
      language: pref.getSync('language', DEFAULT.language) as string,
    };
  } catch (_e) {
    return DEFAULT;
  }
}

export function saveConfig(ctx: common.UIAbilityContext, cfg: LLMConfig): void {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    pref.putSync('baseUrl', cfg.baseUrl);
    pref.putSync('apiKey', cfg.apiKey);
    pref.putSync('model', cfg.model);
    pref.putSync('temperature', cfg.temperature);
    pref.putSync('theme', cfg.theme);
    pref.putSync('systemPrompt', cfg.systemPrompt);
    pref.putSync('nickname', cfg.nickname);
    pref.putSync('companionOn', cfg.companionOn);
    pref.putSync('companionName', cfg.companionName);
    pref.putSync('autoYes', cfg.autoYes);
    pref.putSync('maxIterations', cfg.maxIterations);
    pref.putSync('language', cfg.language);
    pref.flush();
  } catch (_e) {
  }
}

export function markThemeChosen(ctx: common.UIAbilityContext): void {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    pref.putSync('themeChosen', true);
    pref.flush();
  } catch (_e) {
  }
}

export function loadApiModels(ctx: common.UIAbilityContext): ApiModelItem[] {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    const raw = pref.getSync('apiModels', '[]') as string;
    return JSON.parse(raw) as ApiModelItem[];
  } catch (_e) {
    return [];
  }
}

export function saveApiModels(ctx: common.UIAbilityContext, list: ApiModelItem[]): void {
  try {
    const pref = preferences.getPreferencesSync(ctx, { name: PREF_NAME });
    pref.putSync('apiModels', JSON.stringify(list));
    pref.flush();
  } catch (_e) {
  }
}

/** theme=dark 强制深色；light 强制浅色；auto 跟随系统。 */
export function isDarkTheme(cfg: LLMConfig, systemDark: boolean): boolean {
  if (cfg.theme === 'dark') {
    return true;
  }
  if (cfg.theme === 'light') {
    return false;
  }
  return systemDark;
}
