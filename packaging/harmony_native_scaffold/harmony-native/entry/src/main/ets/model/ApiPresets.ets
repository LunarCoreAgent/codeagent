/** 与桌面版 API_BASE_PRESETS 对齐的提供方 Base URL 列表 */

export interface ApiPreset {
  name: string;
  baseUrl: string;
}

export const API_BASE_PRESETS: ApiPreset[] = [
  { name: 'OpenAI', baseUrl: 'https://api.openai.com/v1' },
  { name: 'DeepSeek', baseUrl: 'https://api.deepseek.com/v1' },
  { name: 'Kimi（Moonshot）', baseUrl: 'https://api.moonshot.cn/v1' },
  { name: 'Kimi 国际版（moonshot.ai）', baseUrl: 'https://api.moonshot.ai/v1' },
  { name: 'Google Gemini / Gemma', baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai' },
  { name: 'MiniMax', baseUrl: 'https://api.minimax.chat/v1' },
  { name: '智谱 GLM', baseUrl: 'https://open.bigmodel.cn/api/paas/v4' },
  { name: '通义千问（阿里）', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  { name: '硅基流动', baseUrl: 'https://api.siliconflow.cn/v1' },
  { name: 'OpenRouter', baseUrl: 'https://openrouter.ai/api/v1' },
  { name: 'Ollama 本机', baseUrl: 'http://127.0.0.1:11434/v1' },
];

export function presetProviderLabel(name: string): string {
  // 去掉括号备注，如「Kimi（Moonshot）」→「Kimi」
  const idx = name.indexOf('（');
  if (idx > 0) {
    return name.slice(0, idx);
  }
  return name;
}

export function guessProvider(baseUrl: string): string {
  const h = baseUrl.toLowerCase();
  if (h.indexOf('openai.com') >= 0) return 'OpenAI';
  if (h.indexOf('deepseek') >= 0) return 'DeepSeek';
  if (h.indexOf('moonshot') >= 0) return 'Kimi（Moonshot）';
  if (h.indexOf('minimax') >= 0) return 'MiniMax';
  if (h.indexOf('bigmodel') >= 0 || h.indexOf('zhipu') >= 0) return '智谱 GLM';
  if (h.indexOf('dashscope') >= 0 || h.indexOf('aliyun') >= 0) return '通义千问';
  if (h.indexOf('siliconflow') >= 0) return '硅基流动';
  if (h.indexOf('openrouter') >= 0) return 'OpenRouter';
  if (h.indexOf('googleapis') >= 0 || h.indexOf('generativelanguage') >= 0) return 'Google';
  if (h.indexOf('volces') >= 0 || h.indexOf('ark') >= 0) return '火山引擎';
  if (h.indexOf('anthropic') >= 0) return 'Anthropic';
  if (h.indexOf('11434') >= 0 || h.indexOf('localhost') >= 0 ||
      h.indexOf('127.0.0.1') >= 0 || h.indexOf('192.168.') >= 0 ||
      h.indexOf('10.') >= 0) {
    return '本地/局域网';
  }
  return '自定义';
}
