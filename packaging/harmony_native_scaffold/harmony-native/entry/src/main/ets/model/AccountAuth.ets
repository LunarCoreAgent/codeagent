import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';
import { authentication } from '@kit.AccountKit';
import { util } from '@kit.ArkTS';
import { BusinessError } from '@kit.BasicServicesKit';
import { hilog } from '@kit.PerformanceAnalysisKit';

/**
 * 本地保存的实名核验状态。仅鸿蒙上架包使用。
 *
 * 方案：华为账号登录（LoginWithHuaweiID）。不申请一键登录敏感权限。
 * 中国大陆华为账号已由华为侧完成手机号实名，取得 OpenID 即视为核验通过。
 */
export interface IdentityRecord {
  verified: boolean;
  openId: string;
  unionId: string;
  verifiedAt: number;
}

const STORE = 'cca_identity';
const KEY = 'record';
const DOMAIN = 0xCCA0;
const TAG = 'AccountAuth';

function store(ctx: common.UIAbilityContext): preferences.Preferences {
  return preferences.getPreferencesSync(ctx, { name: STORE });
}

function emptyRecord(): IdentityRecord {
  return {
    verified: false,
    openId: '',
    unionId: '',
    verifiedAt: 0,
  };
}

export function isRecordVerified(record: IdentityRecord): boolean {
  return !!record.verified && (record.openId?.length ?? 0) > 0;
}

export function loadIdentity(ctx: common.UIAbilityContext): IdentityRecord {
  try {
    const raw = store(ctx).getSync(KEY, '') as string;
    if (!raw || raw.length === 0) {
      return emptyRecord();
    }
    const obj = JSON.parse(raw) as IdentityRecord;
    const record: IdentityRecord = {
      verified: !!obj.verified,
      openId: obj.openId || '',
      unionId: obj.unionId || '',
      verifiedAt: obj.verifiedAt || 0,
    };
    if (!isRecordVerified(record)) {
      return emptyRecord();
    }
    return record;
  } catch (_e) {
    return emptyRecord();
  }
}

export function saveIdentity(ctx: common.UIAbilityContext, record: IdentityRecord): void {
  const pref = store(ctx);
  pref.putSync(KEY, JSON.stringify(record));
  pref.flush();
}

export function clearIdentity(ctx: common.UIAbilityContext): void {
  saveIdentity(ctx, emptyRecord());
}

export function isIdentityVerified(ctx: common.UIAbilityContext): boolean {
  return isRecordVerified(loadIdentity(ctx));
}

function maskOpenId(openId: string): string {
  if (openId.length <= 8) {
    return openId;
  }
  return `${openId.slice(0, 4)}…${openId.slice(-4)}`;
}

/** 把 Account Kit BusinessError 转成可读说明。 */
export function formatAuthError(e: Object | string | number): string {
  const be = e as BusinessError;
  const code = (be && typeof be.code === 'number') ? be.code : 0;
  const raw = (be && typeof be.message === 'string' && be.message.length > 0)
    ? be.message
    : `${e}`;
  if (code === 1001502001 || raw.indexOf('1001502001') >= 0) {
    return `配置错误(${code || 1001502001})：client_id / 包名 / 签名指纹与 AGC 不一致。请确认 module.json5 的 client_id 为应用级 OAuth Client ID，且调试证书指纹已加到 AGC。`;
  }
  if (code === 1001500001 || raw.indexOf('1001500001') >= 0 || raw.indexOf('fingerprint') >= 0) {
    return `签名指纹校验失败(${code || 1001500001})：请在 AGC 添加当前安装包所用证书的 SHA-256 公钥指纹，并提高 versionCode 后重装。`;
  }
  if (code === 1001502012 || raw.indexOf('cancel') >= 0 || raw.indexOf('Cancel') >= 0) {
    return '已取消登录';
  }
  if (code > 0) {
    return `${raw}（错误码 ${code}）`;
  }
  return raw;
}

/** 华为账号登录核验：forceLogin 拉起系统登录，拿到 OpenID 即通过。 */
export async function verifyWithHuaweiAccount(ctx: common.UIAbilityContext): Promise<IdentityRecord> {
  const provider = new authentication.HuaweiIDProvider();
  const controller = new authentication.AuthenticationController(ctx);
  const state = util.generateRandomUUID().replace(/-/g, '').slice(0, 32);

  const loginReq = provider.createLoginWithHuaweiIDRequest();
  loginReq.forceLogin = true;
  loginReq.state = state;
  hilog.info(DOMAIN, TAG, 'start LoginWithHuaweiID forceLogin=true');
  let loginRaw: Object;
  try {
    loginRaw = await controller.executeRequest(loginReq);
  } catch (err) {
    hilog.error(DOMAIN, TAG, 'LoginWithHuaweiID failed: %{public}s', formatAuthError(err as Object));
    throw new Error(formatAuthError(err as Object));
  }
  const loginResp = loginRaw as authentication.LoginWithHuaweiIDResponse;
  const loginData = loginResp.data;
  if (!loginData || !loginData.openID || loginData.openID.length === 0) {
    throw new Error('未取得华为账号身份标识，请使用已实名的中国大陆华为账号重试');
  }
  hilog.info(DOMAIN, TAG, 'login ok openIdLen=%{public}d', loginData.openID.length);

  const record: IdentityRecord = {
    verified: true,
    openId: loginData.openID,
    unionId: loginData.unionID || '',
    verifiedAt: Date.now(),
  };
  saveIdentity(ctx, record);
  return record;
}

export function identityStatusText(record: IdentityRecord): string {
  if (!isRecordVerified(record)) {
    return '未核验';
  }
  return `已核验 · 华为账号（${maskOpenId(record.openId)}）`;
}
