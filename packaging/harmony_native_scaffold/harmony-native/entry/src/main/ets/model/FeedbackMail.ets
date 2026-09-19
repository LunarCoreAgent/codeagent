import { common, Want } from '@kit.AbilityKit';
import { BusinessError } from '@kit.BasicServicesKit';
import { promptAction } from '@kit.ArkUI';

export const FEEDBACK_MAILTO: string =
  'mailto:alan_dan@live.com?subject=CodeCoreAgent%20问题反馈';

/** 每次点击都拉起系统写信页；按常见邮件应用逐个尝试。 */
export function openFeedbackMail(ctx: common.UIAbilityContext): void {
  const wants: Want[] = [
    { action: 'ohos.want.action.viewData', uri: FEEDBACK_MAILTO },
    { action: 'ohos.want.action.sendToData', uri: FEEDBACK_MAILTO, type: 'text/plain' },
    { action: 'ohos.want.action.sendToData', entities: ['entity.system.email'], uri: FEEDBACK_MAILTO },
    { bundleName: 'com.huawei.hmos.email', action: 'ohos.want.action.viewData', uri: FEEDBACK_MAILTO },
    { bundleName: 'com.huawei.email', action: 'ohos.want.action.viewData', uri: FEEDBACK_MAILTO },
  ];
  launch(ctx, wants, 0);
}

function launch(ctx: common.UIAbilityContext, wants: Want[], index: number): void {
  if (index >= wants.length) {
    promptAction.showToast({ message: '未找到邮件应用，请先安装邮箱' });
    return;
  }
  ctx.startAbility(wants[index]).catch((_err: BusinessError) => {
    launch(ctx, wants, index + 1);
  });
}
