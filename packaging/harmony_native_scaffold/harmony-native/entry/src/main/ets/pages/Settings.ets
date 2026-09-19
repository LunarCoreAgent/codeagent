import { common, Want } from '@kit.AbilityKit';
import { BusinessError } from '@kit.BasicServicesKit';
import { promptAction, router } from '@kit.ArkUI';
import { LLMConfig, loadConfig, saveConfig } from '../model/Config';
import { openFeedbackMail as launchFeedbackMail } from '../model/FeedbackMail';

@Entry
@Component
struct Settings {
  @State cfg: LLMConfig = {
    baseUrl: 'https://api.openai.com/v1',
    apiKey: '',
    model: 'gpt-4o',
    temperature: 0.7,
    theme: 'light',
    systemPrompt: '',
    nickname: '',
    companionOn: false,
    companionName: '助手',
    autoYes: false,
    maxIterations: 80,
    language: 'auto',
  };
  ctx: common.UIAbilityContext = getContext(this) as common.UIAbilityContext;

  aboutToAppear() {
    this.cfg = loadConfig(this.ctx);
  }

  save() {
    saveConfig(this.ctx, this.cfg);
    router.back();
  }

  openFeedbackMail() {
    launchFeedbackMail(this.ctx);
  }

  openOfficialSite() {
    const want: Want = {
      action: 'ohos.want.action.viewData',
      entities: ['entity.system.browsable'],
      uri: 'https://lunarcoreagent.com/CodeCoreAgent/index.html',
    };
    this.ctx.startAbility(want).catch((_err: BusinessError) => {
      promptAction.showToast({ message: '无法打开官网' });
    });
  }

  build() {
    Column() {
      Row() {
        Button('←').fontSize(18).width(44).height(44)
          .backgroundColor(Color.Transparent)
          .onClick(() => router.back())
        Text('设置').fontSize(18).fontWeight(FontWeight.Bold).layoutWeight(1)
      }
      .width('100%').height(52).padding({ left: 8 })

      Scroll() {
        Column({ space: 16 }) {
          Column({ space: 6 }) {
            Text('API Base URL').fontSize(14).fontWeight(FontWeight.Medium)
            TextInput({ text: this.cfg.baseUrl, placeholder: 'https://api.openai.com/v1' })
              .fontColor($r('app.color.input_text'))
              .placeholderColor($r('app.color.input_placeholder'))
              .caretColor($r('app.color.input_caret'))
              .backgroundColor($r('app.color.input_bg'))
              .width('100%').height(44)
              .onChange((v) => { this.cfg.baseUrl = v; })
          }.alignItems(HorizontalAlign.Start).width('100%')

          Column({ space: 6 }) {
            Text('API Key（本地 Ollama 可留空）').fontSize(14).fontWeight(FontWeight.Medium)
            TextInput({ text: this.cfg.apiKey, placeholder: 'sk-...' })
              .fontColor($r('app.color.input_text'))
              .placeholderColor($r('app.color.input_placeholder'))
              .caretColor($r('app.color.input_caret'))
              .backgroundColor($r('app.color.input_bg'))
              .width('100%').height(44).type(InputType.Password)
              .onChange((v) => { this.cfg.apiKey = v; })
          }.alignItems(HorizontalAlign.Start).width('100%')

          Column({ space: 6 }) {
            Text('模型名').fontSize(14).fontWeight(FontWeight.Medium)
            TextInput({ text: this.cfg.model, placeholder: 'gpt-4o / qwen2.5-coder:7b' })
              .fontColor($r('app.color.input_text'))
              .placeholderColor($r('app.color.input_placeholder'))
              .caretColor($r('app.color.input_caret'))
              .backgroundColor($r('app.color.input_bg'))
              .width('100%').height(44)
              .onChange((v) => { this.cfg.model = v; })
          }.alignItems(HorizontalAlign.Start).width('100%')

          Column({ space: 6 }) {
            Text(`温度: ${this.cfg.temperature.toFixed(2)}`).fontSize(14).fontWeight(FontWeight.Medium)
            Slider({ value: this.cfg.temperature, min: 0, max: 2, step: 0.05 })
              .width('100%')
              .onChange((v) => { this.cfg.temperature = v; })
          }.alignItems(HorizontalAlign.Start).width('100%')

          Button('保存')
            .width('100%').height(44).margin({ top: 16 })
            .type(ButtonType.Capsule)
            .onClick(() => this.save())

          Text('官网地址')
            .fontSize(16).fontColor('#007AFF')
            .decoration({ type: TextDecorationType.Underline, color: '#007AFF' })
            .onClick(() => this.openOfficialSite())
          Text('https://lunarcoreagent.com/CodeCoreAgent/index.html')
            .fontSize(12).fontColor('#888888')

          Button('问题反馈')
            .width('100%').height(44)
            .type(ButtonType.Capsule)
            .onClick(() => this.openFeedbackMail())
        }
        .width('100%')
        .padding(20)
      }
      .layoutWeight(1).width('100%')
    }
    .width('100%').height('100%')
    .backgroundColor($r('app.color.page_bg'))
  }
}
