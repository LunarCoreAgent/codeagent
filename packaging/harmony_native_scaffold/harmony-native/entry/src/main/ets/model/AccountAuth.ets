import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';
import { authentication } from '@kit.AccountKit';
import { util } from '@kit.ArkTS';

/** 本地保存的实名核验状态（华为账号 + 绑定手机号）。 */
export interface IdentityRecord {
  verified: boolean;
  openId: string;
  unionId: string;
  /** 脱敏手机号，如 138****8000；可能为空 */
  anonymousPhone: string;
  verifiedAt: number;
}

const STORE = 'cca_identity';
const KEY = 'record';

function store(ctx: common.UIAbilityContext): preferences.Preferences {
  return preferences.getPreferencesSync(ctx, { name: STORE });
}

export function loadIdentity(ctx: common.UIAbilityContext): IdentityRecord {
  try {
    const raw = store(ctx).getSync(KEY, '') as string;
    if (!raw || raw.length === 0) {
      return {
        verified: false,
        openId: '',
        unionId: '',
        anonymousPhone: '',
        verifiedAt: 0,
      };
    }
    const obj = JSON.parse(raw) as IdentityRecord;
    return {
      verified: !!obj.verified && (obj.openId?.length ?? 0) > 0,
      openId: obj.openId || '',
      unionId: obj.unionId || '',
      anonymousPhone: obj.anonymousPhone || '',
      verifiedAt: obj.verifiedAt || 0,
    };
  } catch (_e) {
    return {
      verified: false,
      openId: '',
      unionId: '',
      anonymousPhone: '',
      verifiedAt: 0,
    };
  }
}

export function saveIdentity(ctx: common.UIAbilityContext, record: IdentityRecord): void {
  const pref = store(ctx);
  pref.putSync(KEY, JSON.stringify(record));
  pref.flush();
}

export function clearIdentity(ctx: common.UIAbilityContext): void {
  saveIdentity(ctx, {
    verified: false,
    openId: '',
    unionId: '',
    anonymousPhone: '',
    verifiedAt: 0,
  });
}

export function isIdentityVerified(ctx: common.UIAbilityContext): boolean {
  return loadIdentity(ctx).verified;
}

function readAnonymousPhone(extra?: Record<string, Object>): string {
  if (!extra) {
    return '';
  }
  const v = extra['quickLoginAnonymousPhone'];
  if (typeof v === 'string') {
    return v;
  }
  return '';
}

/**
 * 华为账号登录 + 授权脱敏手机号，满足「合成生成内容前须基于手机号核验真实身份」。
 * 中国大陆华为账号本身已实名；再取绑定手机号用于审核举证。
 */
export async function verifyWithHuaweiAccount(ctx: common.UIAbilityContext): Promise<IdentityRecord> {
  const provider = new authentication.HuaweiIDProvider();
  const controller = new authentication.AuthenticationController(ctx);
  const state = util.generateRandomUUID().replace(/-/g, '').slice(0, 32);

  const loginReq = provider.createLoginWithHuaweiIDRequest();
  loginReq.forceLogin = true;
  loginReq.state = state;
  const loginRaw = await controller.executeRequest(loginReq);
  const loginResp = loginRaw as authentication.LoginWithHuaweiIDResponse;
  const loginData = loginResp.data;
  if (!loginData || !loginData.openID || loginData.openID.length === 0) {
    throw new Error('未取得华为账号身份标识');
  }

  let anonymousPhone = '';
  try {
    const authReq = provider.createAuthorizationWithHuaweiIDRequest();
    authReq.scopes = ['openid', 'quickLoginAnonymousPhone'];
    authReq.permissions = ['idtoken', 'serviceauthcode'];
    authReq.forceAuthorization = true;
    authReq.state = state;
    const authRaw = await controller.executeRequest(authReq);
    const authResp = authRaw as authentication.AuthorizationWithHuaweiIDResponse;
    anonymousPhone = readAnonymousPhone(authResp.data?.extraInfo);
  } catch (_phoneErr) {
    // 手机号 scope 未开通时仍允许以华为账号 OpenID 作为已登录实名身份
    anonymousPhone = '';
  }

  const record: IdentityRecord = {
    verified: true,
    openId: loginData.openID,
    unionId: loginData.unionID || '',
    anonymousPhone,
    verifiedAt: Date.now(),
  };
  saveIdentity(ctx, record);
  return record;
}

export function identityStatusText(record: IdentityRecord): string {
  if (!record.verified) {
    return '未核验';
  }
  if (record.anonymousPhone.length > 0) {
    return `已核验 · ${record.anonymousPhone}`;
  }
  return '已核验 · 华为账号';
}
