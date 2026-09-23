import { http } from '@kit.NetworkKit';
import { util } from '@kit.ArkTS';
import { BusinessError } from '@kit.BasicServicesKit';
import { LLMConfig } from './Config';

export interface ChatMessage {
  role: string;
  content: string;
}

interface ChatDelta {
  content?: string;
}

interface ChatChoice {
  delta?: ChatDelta;
  message?: ChatDelta;
}

interface ChatCompletionChunk {
  choices?: ChatChoice[];
}

/** 流式空闲上限（毫秒）。120B 等大模型给 600 秒，普通模型 90 秒。 */
export function idleTimeoutFor(model: string): number {
  const n = model.toLowerCase();
  if (n.indexOf('120b') >= 0 || n.indexOf('70b') >= 0 || n.indexOf('72b') >= 0 || n.indexOf('65b') >= 0) {
    return 600000;
  }
  return 90000;
}

function buildHeader(apiKey: string): Record<string, string> {
  const header: Record<string, string> = { 'Content-Type': 'application/json' };
  if (apiKey.length > 0) {
    header['Authorization'] = `Bearer ${apiKey}`;
  }
  return header;
}

export function withSystemPrompt(cfg: LLMConfig, messages: ChatMessage[]): ChatMessage[] {
  const out: ChatMessage[] = [];
  let sys = cfg.systemPrompt;
  if (cfg.companionOn && cfg.companionName.length > 0) {
    sys = sys + `\n你的角色名是「${cfg.companionName}」。`;
  }
  if (cfg.nickname.length > 0) {
    sys = sys + `\n用户希望你称呼他/她为「${cfg.nickname}」。`;
  }
  if (sys.length > 0) {
    out.push({ role: 'system', content: sys });
  }
  for (let i = 0; i < messages.length; i++) {
    out.push(messages[i]);
  }
  return out;
}

/**
 * 流式调用。返回可调用的 stop()，后续 delta 将被忽略。
 */
export function chatStream(
  cfg: LLMConfig,
  messages: ChatMessage[],
  onDelta: (text: string) => void,
  onDone: () => void,
  onError: (msg: string) => void,
): () => void {
  let stopped = false;
  const url = cfg.baseUrl.replace(/\/+$/, '') + '/chat/completions';
  const payload = withSystemPrompt(cfg, messages);

  try {
    const req = http.createHttp();
    let sseBuf = '';
    const decoder = util.TextDecoder.create('utf-8');

    const handleLine = (line: string): void => {
      if (stopped) {
        return;
      }
      const trimmed = line.trim();
      if (!trimmed.startsWith('data:')) {
        return;
      }
      const data = trimmed.slice(5).trim();
      if (data === '[DONE]') {
        return;
      }
      try {
        const json = JSON.parse(data) as ChatCompletionChunk;
        const delta = json.choices?.[0]?.delta?.content;
        if (delta !== undefined && delta.length > 0) {
          onDelta(delta);
        }
      } catch (_e) {
      }
    };

    let lastByte = Date.now();
    const idleMs = idleTimeoutFor(cfg.model);
    const idleWatch = setInterval((): void => {
      if (stopped) {
        clearInterval(idleWatch);
        return;
      }
      if (Date.now() - lastByte < idleMs) {
        return;
      }
      stopped = true;
      clearInterval(idleWatch);
      try {
        req.destroy();
      } catch (_e) {
      }
      onError(`本地模型 ${cfg.model} 超过 ${Math.floor(idleMs / 1000)} 秒没有输出，视为卡住`);
    }, 2000);

    req.on('dataReceive', (chunk: ArrayBuffer) => {
      if (stopped) {
        return;
      }
      lastByte = Date.now();
      sseBuf += decoder.decodeToString(new Uint8Array(chunk));
      let idx = sseBuf.indexOf('\n');
      while (idx >= 0) {
        const line = sseBuf.slice(0, idx);
        sseBuf = sseBuf.slice(idx + 1);
        handleLine(line);
        idx = sseBuf.indexOf('\n');
      }
    });

    req.on('dataEnd', () => {
      if (stopped) {
        return;
      }
      clearInterval(idleWatch);
      if (sseBuf.trim().length > 0) {
        handleLine(sseBuf);
      }
      onDone();
    });

    const options: http.HttpRequestOptions = {
      method: http.RequestMethod.POST,
      header: buildHeader(cfg.apiKey),
      extraData: JSON.stringify({
        model: cfg.model,
        messages: payload,
        temperature: cfg.temperature,
        stream: true,
      }),
      expectDataType: http.HttpDataType.STRING,
      connectTimeout: 30000,
      readTimeout: idleTimeoutFor(cfg.model),
    };

    req.requestInStream(url, options, (err: BusinessError, _code: number) => {
      if (stopped) {
        return;
      }
      if (err) {
        clearInterval(idleWatch);
        onError(`网络错误: ${err.code} ${err.message}`);
      }
    });

    return () => {
      stopped = true;
      clearInterval(idleWatch);
      try {
        req.destroy();
      } catch (_e) {
      }
    };
  } catch (e) {
    const be = e as BusinessError;
    onError(`请求失败: ${be.code} ${be.message}`);
    return () => {
      stopped = true;
    };
  }
}
