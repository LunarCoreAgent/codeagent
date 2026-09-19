import { AbilityConstant, Configuration, ConfigurationConstant, UIAbility, Want } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { i18n } from '@kit.LocalizationKit';

const TAG = 'EntryAbility';

function readSystemLanguage(fallback: string): string {
  try {
    const lang = i18n.System.getSystemLanguage();
    if (lang.length > 0) {
      return lang;
    }
  } catch (_e) {
  }
  return fallback;
}

function applySystemBars(mainWin: window.Window, dark: boolean): void {
  try {
    const content = dark ? '#F2F2F3' : '#1A1A1A';
    const sysBarProps: window.SystemBarProperties = {
      statusBarColor: '#00000000',
      statusBarContentColor: content,
      navigationBarColor: '#00000000',
      navigationBarContentColor: content,
    };
    mainWin.setWindowSystemBarProperties(sysBarProps, (err) => {
      if (err && err.code) {
        hilog.error(0x0001, TAG, 'setWindowSystemBarProperties failed %{public}s', JSON.stringify(err));
      }
    });
  } catch (_e) {
    // 2in1 上该接口可能不可用，忽略即可
  }
}

export default class EntryAbility extends UIAbility {
  onCreate(_want: Want, _launchParam: AbilityConstant.LaunchParam): void {
    hilog.info(0x0001, TAG, 'onCreate');
    try {
      // 不锁定浅色，跟随系统深色/浅色
      this.context.setColorMode(ConfigurationConstant.ColorMode.COLOR_MODE_NOT_SET);
    } catch (_e) {
    }
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    const dark = this.context.config.colorMode === ConfigurationConstant.ColorMode.COLOR_MODE_DARK;
    AppStorage.setOrCreate('systemDark', dark);
    AppStorage.setOrCreate('systemLang', readSystemLanguage(this.context.config.language || ''));
    try {
      const mainWin = windowStage.getMainWindowSync();
      // 沉浸式，内容区再用避让区 padding，避免顶进挖孔/状态栏
      mainWin.setWindowLayoutFullScreen(true);
      applySystemBars(mainWin, dark);
    } catch (_e) {
      hilog.error(0x0001, TAG, 'window setup failed');
    }

    windowStage.loadContent('pages/Index', (err) => {
      if (err.code) {
        hilog.error(0x0001, TAG, 'load failed %{public}s', JSON.stringify(err));
      }
    });
  }

  onConfigurationUpdate(newConfig: Configuration): void {
    const dark = newConfig.colorMode === ConfigurationConstant.ColorMode.COLOR_MODE_DARK;
    AppStorage.setOrCreate('systemDark', dark);
    if (newConfig.language && newConfig.language.length > 0) {
      AppStorage.setOrCreate('systemLang', newConfig.language);
    }
    try {
      const stage = this.context.windowStage;
      applySystemBars(stage.getMainWindowSync(), dark);
    } catch (_e) {
    }
  }
}
