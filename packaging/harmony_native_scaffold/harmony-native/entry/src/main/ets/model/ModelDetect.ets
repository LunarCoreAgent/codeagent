import { http } from '@kit.NetworkKit';
import { BusinessError } from '@kit.BasicServicesKit';

export interface DetectResult {
  ok: boolean;
  kind: string;      // openai | ollama | unknown
  models: string[];
  error: string;
  baseUrl: string;   // 可能被规范化后的 base
}

function normalizeBase(raw: string): string {
  let s = raw.trim().replace(/：/g, ':').replace(/／/g, '/');
  if (s.length === 0) {
    return '';
  }
  if (!s.startsWith('http://') && !s.startsWith('https://') &&
      !s.startsWith('HTTP://') && !s.startsWith('HTTPS://')) {
    s = 'http://' + s;
  }
  while (s.endsWith('/')) {
    s = s.slice(0, s.length - 1);
  }
  return s;
}

function buildHeader(apiKey: string): Record<string, string> {
  const header: Record<string, string> = { 'Content-Type': 'application/json' };
  if (apiKey.trim().length > 0) {
    header['Authorization'] = `Bearer ${apiKey.trim()}`;
  }
  return header;
}

function httpGet(url: string, apiKey: string): Promise<http.HttpResponse> {
  return new Promise((resolve, reject) => {
    const options: http.HttpRequestOptions = {
      method: http.RequestMethod.GET,
      header: buildHeader(apiKey),
      expectDataType: http.HttpDataType.STRING,
      connectTimeout: 8000,
      readTimeout: 12000,
    };
    http.createHttp().request(url, options, (err: BusinessError, data: http.HttpResponse) => {
      if (err) {
        reject(err);
        return;
      }
      resolve(data);
    });
  });
}

interface OpenAIList {
  data?: Array<Record<string, string>>;
}

interface OllamaTags {
  models?: Array<Record<string, string>>;
}

/**
 * 自动识别：先试 OpenAI 兼容 /models（或 /v1/models），再试 Ollama /api/tags。
 */
export async function detectModels(baseUrl: string, apiKey: string): Promise<DetectResult> {
  const base = normalizeBase(baseUrl);
  if (base.length === 0) {
    return { ok: false, kind: 'unknown', models: [], error: '请先填写 Base URL', baseUrl: '' };
  }

  const candidates: string[] = [];
  candidates.push(base + '/models');
  if (!base.endsWith('/v1')) {
    candidates.push(base + '/v1/models');
  }

  let authError = '';
  let connError = '';

  for (let i = 0; i < candidates.length; i++) {
    const url = candidates[i];
    try {
      const resp = await httpGet(url, apiKey);
      const code = resp.responseCode;
      if (code < 400) {
        try {
          const json = JSON.parse(resp.result as string) as OpenAIList;
          const models: string[] = [];
          const data = json.data;
          if (data) {
            for (let j = 0; j < data.length; j++) {
              const id = data[j]['id'];
              if (id && id.length > 0) {
                models.push(id);
              }
            }
          }
          // 生效 base：若打的是 /v1/models，保留 /v1
          let effective = base;
          if (url.indexOf('/v1/models') >= 0 && !base.endsWith('/v1')) {
            effective = base + '/v1';
          }
          return { ok: true, kind: 'openai', models: models, error: '', baseUrl: effective };
        } catch (_e) {
          connError = '解析 /models 响应失败';
        }
      } else if (code === 401 || code === 403) {
        authError = apiKey.trim().length === 0
          ? '端点要求鉴权，请先填入 API Key 再识别'
          : `鉴权失败（HTTP ${code}），请检查 API Key`;
        break;
      } else {
        connError = `HTTP ${code}`;
      }
    } catch (e) {
      const be = e as BusinessError;
      if (connError.length === 0) {
        connError = `网络错误: ${be.code} ${be.message}`;
      }
    }
  }

  if (authError.length > 0) {
    return { ok: false, kind: 'unknown', models: [], error: authError, baseUrl: base };
  }

  // Ollama：去掉 /v1 后打 /api/tags
  let native = base;
  if (native.endsWith('/v1')) {
    native = native.slice(0, native.length - 3);
  }
  try {
    const resp = await httpGet(native + '/api/tags', '');
    if (resp.responseCode < 400) {
      const json = JSON.parse(resp.result as string) as OllamaTags;
      const models: string[] = [];
      const list = json.models;
      if (list) {
        for (let j = 0; j < list.length; j++) {
          const name = list[j]['name'];
          if (name && name.length > 0) {
            models.push(name);
          }
        }
      }
      return {
        ok: true,
        kind: 'ollama',
        models: models,
        error: '',
        baseUrl: native.endsWith('/v1') ? native : native + '/v1',
      };
    }
  } catch (e) {
    const be = e as BusinessError;
    if (connError.length === 0) {
      connError = `Ollama 探测失败: ${be.code} ${be.message}`;
    }
  }

  return {
    ok: false,
    kind: 'unknown',
    models: [],
    error: connError.length > 0 ? connError : '无法识别该端点',
    baseUrl: base,
  };
}

/** Ollama 拉取模型（stream:false，等待完成） */
export async function pullOllamaModel(baseUrl: string, modelName: string): Promise<string> {
  let native = normalizeBase(baseUrl);
  if (native.endsWith('/v1')) {
    native = native.slice(0, native.length - 3);
  }
  const url = native + '/api/pull';
  return new Promise((resolve, reject) => {
    const options: http.HttpRequestOptions = {
      method: http.RequestMethod.POST,
      header: { 'Content-Type': 'application/json' },
      extraData: JSON.stringify({ name: modelName, stream: false }),
      expectDataType: http.HttpDataType.STRING,
      connectTimeout: 15000,
      readTimeout: 600000,
    };
    http.createHttp().request(url, options, (err: BusinessError, data: http.HttpResponse) => {
      if (err) {
        reject(new Error(`${err.code} ${err.message}`));
        return;
      }
      if (data.responseCode >= 400) {
        reject(new Error(`HTTP ${data.responseCode}: ${(data.result as string).slice(0, 120)}`));
        return;
      }
      resolve('ok');
    });
  });
}

