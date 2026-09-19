import { webview } from '@kit.ArkWeb';
import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';
import { display } from '@kit.ArkUI';

// 改成你跑 CodeCoreAgent 桌面版的地址（本机或局域网）
const DEFAULT_URL = 'http://127.0.0.1:8765';
const PREF_KEY = 'cca_url';
const PC_BREAKPOINT = 1024; // vp，≥ 1024vp 按鸿蒙电脑（2in1）布局，< 1024vp 按平板布局

@Entry
@Component
struct Index {
  @State currentUrl: string = DEFAULT_URL;
  @State inputUrl: string = DEFAULT_URL;
  @State showSettings: boolean = false;
  @State isPC: boolean = false;
  controller: webview.WebviewController = new webview.WebviewController();
  ctx: common.UIAbilityContext = getContext(this) as common.UIAbilityContext;

  aboutToAppear() {
    this.loadSavedUrl();
    this.detectDevice();
  }

  loadSavedUrl() {
    try {
      const pref = preferences.getPreferencesSync(this.ctx, { name: 'cca_prefs' });
      const saved = pref.getSync(PREF_KEY, DEFAULT_URL) as string;
      this.currentUrl = saved;
      this.inputUrl = saved;
    } catch (e) {
      // 用默认值
    }
  }

  saveUrl(url: string) {
    try {
      const pref = preferences.getPreferencesSync(this.ctx, { name: 'cca_prefs' });
      pref.putSync(PREF_KEY, url);
      pref.flush();
    } catch (e) {
      // 忽略写入失败
    }
  }

  detectDevice() {
    // 注意：windowRect 与 windowSizeChange 给出的宽度单位是 px，
    // 而断点按 vp 定义，必须用屏幕密度换算，否则平板（px 远大于 vp）
    // 会被误判为 PC 布局。
    try {
      const win = this.ctx.windowStage.getMainWindowSync();
      const updateLayout = (widthPx: number) => {
        const density = display.getDefaultDisplaySync().densityPixels || 1;
        this.isPC = widthPx / density >= PC_BREAKPOINT;
      };
      updateLayout(win.getWindowProperties().windowRect.width);
      win.on('windowSizeChange', (size) => {
        updateLayout(size.width);
      });
    } catch (e) {
      this.isPC = false;
    }
  }

  applyUrl() {
    const url = this.inputUrl.trim();
    if (!url) {
      return;
    }
    this.currentUrl = url;
    this.saveUrl(url);
    this.showSettings = false;
    try {
      this.controller.loadUrl(url);
    } catch (e) {
      // Web 还没准备好时忽略
    }
  }

  refresh() {
    try {
      this.controller.refresh();
    } catch (e) {
    }
  }

  goBack() {
    try {
      if (this.controller.accessBackward()) {
        this.controller.backward();
      }
    } catch (e) {
    }
  }

  build() {
    Row() {
      if (this.isPC) {
        // PC：左侧窄工具栏
        Column() {
          Image($r('app.media.app_icon'))
            .width(40).height(40).margin({ top: 16, bottom: 8 })

          Button('⟲')
            .fontSize(20).width(44).height(44).margin({ bottom: 8 })
            .backgroundColor(Color.Transparent)
            .onClick(() => this.refresh())

          Button('←')
            .fontSize(20).width(44).height(44).margin({ bottom: 8 })
            .backgroundColor(Color.Transparent)
            .onClick(() => this.goBack())

          Button('⚙')
            .fontSize(20).width(44).height(44).margin({ bottom: 8 })
            .backgroundColor(Color.Transparent)
            .onClick(() => { this.showSettings = !this.showSettings; })

          Blank()

          Text('v0.77.0')
            .fontSize(10).fontColor(Color.Gray)
            .margin({ bottom: 12 })
        }
        .width(56)
        .height('100%')
        .backgroundColor('#f5f5f5')
        .justifyContent(FlexAlign.Center)
      }

      // 右侧 / 全屏：Web 内容区
      Stack({ alignContent: Alignment.TopEnd }) {
        Column() {
          if (this.showSettings) {
            this.SettingsPanel()
          }
          Web({ src: this.currentUrl, controller: this.controller })
            .width('100%')
            .height('100%')
            .domStorageAccess(true)
            .fileAccess(true)
            .imageAccess(true)
            .javaScriptAccess(true)
            .zoomAccess(false)
        }

        if (!this.isPC) {
          // 平板浮动按钮
          Column() {
            Button('⟲').fontSize(18).width(40).height(40)
              .backgroundColor('#80000000').fontColor(Color.White)
              .borderRadius(20).margin({ bottom: 8 })
              .onClick(() => this.refresh())
            Button('⚙').fontSize(18).width(40).height(40)
              .backgroundColor('#80000000').fontColor(Color.White)
              .borderRadius(20).margin({ bottom: 8 })
              .onClick(() => { this.showSettings = !this.showSettings; })
            Button('←').fontSize(18).width(40).height(40)
              .backgroundColor('#80000000').fontColor(Color.White)
              .borderRadius(20)
              .onClick(() => this.goBack())
          }
          .position({ top: 16, right: 16 })
        }
      }
      .layoutWeight(1)
      .height('100%')
    }
    .width('100%')
    .height('100%')
  }

  @Builder
  SettingsPanel() {
    Column() {
      Text('CodeCoreAgent 地址')
        .fontSize(16).fontWeight(FontWeight.Bold).margin({ bottom: 12 })

      TextInput({ text: this.inputUrl, placeholder: 'http://192.168.1.100:8765' })
        .width('80%').height(44)
        .onChange((val) => { this.inputUrl = val; })
        .margin({ bottom: 16 })

      Row() {
        Button('取消')
          .width(80).height(40).margin({ right: 12 })
          .backgroundColor('#ccc')
          .onClick(() => { this.showSettings = false; this.inputUrl = this.currentUrl; })
        Button('应用')
          .width(80).height(40)
          .type(ButtonType.Capsule)
          .onClick(() => this.applyUrl())
      }

      Blank().height(16)

      Text('提示：CodeCoreAgent 桌面版需开启远程访问')
        .fontSize(12).fontColor(Color.Gray)
      Text('在 Mac/Win/Linux 跑：codeagent desktop --host 0.0.0.0 --port 8765')
        .fontSize(11).fontColor(Color.Gray)
    }
    .width('100%')
    .padding(24)
    .backgroundColor(Color.White)
  }
}
