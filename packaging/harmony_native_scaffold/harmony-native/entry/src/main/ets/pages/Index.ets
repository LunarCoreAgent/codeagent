import { common, ConfigurationConstant, Want } from '@kit.AbilityKit';
import { display, window } from '@kit.ArkUI';
import { webview } from '@kit.ArkWeb';
import { deviceInfo, BusinessError } from '@kit.BasicServicesKit';
import { LLMConfig, loadConfig, saveConfig, markThemeChosen, ApiModelItem, loadApiModels, saveApiModels, isDarkTheme } from '../model/Config';
import { ChatMessage, chatStream } from '../model/LLMClient';
import { Conversation, newId, loadAllIds, loadConvo, saveConvo, deleteConvo } from '../model/ChatStore';
import { MemoryItem, loadMemories, addMemory, deleteMemory, searchMemories } from '../model/MemoryStore';
import { KnowledgeDoc, WikiPage, KnowledgeConfig, loadDocs, upsertDoc, deleteDoc, searchDocs,
  loadKnowledgeConfig, saveKnowledgeConfig, loadPages, searchPages, bootstrapVault,
  ingestText, vaultStatus, buildKnowledgeContext, deletePage } from '../model/KnowledgeStore';
import { ActivityItem, loadActivity, pushActivity, clearActivity } from '../model/ActivityStore';
import { detectModels, pullOllamaModel } from '../model/ModelDetect';
import { API_BASE_PRESETS, ApiPreset, guessProvider, presetProviderLabel } from '../model/ApiPresets';
import { LocalEndpoint, loadEndpoints, saveEndpoints, normalizeLocalBase, toChatBase } from '../model/LocalStore';
import { openFeedbackMail as launchFeedbackMail } from '../model/FeedbackMail';
import {
  IdentityRecord,
  loadIdentity,
  clearIdentity,
  verifyWithHuaweiAccount,
  identityStatusText,
} from '../model/AccountAuth';
import { i18n } from '@kit.LocalizationKit';
import { translate, resolveLanguage, replyLanguageName } from '../model/I18n';

const PC_BREAKPOINT = 1024;
const APP_VERSION = '0.77.0';

interface NavItem {
  id: string;
  label: string;
  group: string;
  /** 依赖 Mac/Win/Linux 桌面版宿主（bash/文件/Comfy/调度等），平板仅提示 */
  desktopOnly: boolean;
}

const NAV: NavItem[] = [
  { id: 'dashboard', label: '总览', group: '概览', desktopOnly: false },
  { id: 'chat', label: '对话', group: '概览', desktopOnly: false },
  { id: 'browser', label: '浏览器', group: '概览', desktopOnly: false },
  { id: 'studio', label: '导演台', group: '概览', desktopOnly: true },
  { id: 'lead', label: '指挥中心', group: '概览', desktopOnly: true },
  { id: 'memory', label: '长期记忆', group: '能力', desktopOnly: false },
  { id: 'knowledge', label: '知识库', group: '能力', desktopOnly: false },
  { id: 'skills', label: '技能库', group: '能力', desktopOnly: true },
  { id: 'models', label: '模型管理', group: '系统', desktopOnly: false },
  { id: 'automation', label: '自动化', group: '系统', desktopOnly: true },
  { id: 'logs', label: '日志', group: '系统', desktopOnly: false },
  { id: 'versions', label: '版本说明', group: '系统', desktopOnly: false },
  { id: 'privacy', label: '隐私条款', group: '系统', desktopOnly: false },
  { id: 'settings', label: '偏好设置', group: '系统', desktopOnly: false },
];

interface SkillCard {
  name: string;
  desc: string;
  desktopOnly: boolean;
}

const SKILLS: SkillCard[] = [
  { name: '代码阅读', desc: '分析项目结构与关键实现', desktopOnly: true },
  { name: '文件编辑', desc: '按任务修改源码与配置', desktopOnly: true },
  { name: '终端执行', desc: '在桌面宿主侧运行命令', desktopOnly: true },
  { name: '网页抓取', desc: '抓取公开页面摘要', desktopOnly: true },
  { name: '知识检索', desc: '在本地知识库中搜索', desktopOnly: false },
  { name: '视频运营', desc: '脚本/分镜/发布草稿协作', desktopOnly: true },
  { name: '自我学习', desc: '根据反馈优化回答风格', desktopOnly: true },
  { name: '定时任务', desc: '规划周期性作业', desktopOnly: true },
];

function isDesktopOnlyPage(pageId: string): boolean {
  for (let i = 0; i < NAV.length; i++) {
    if (NAV[i].id === pageId) {
      return NAV[i].desktopOnly;
    }
  }
  return false;
}

@Component
struct DashCard {
  @Prop title: string = '';
  @Prop desc: string = '';
  @Prop target: string = '';
  @Prop showBadge: boolean = false;
  @Prop dark: boolean = false;
  @StorageLink('uiLang') uiLang: string = 'zh-Hans';

  build() {
    Column({ space: 6 }) {
      Row() {
        Text(this.title)
          .fontSize(15)
          .fontWeight(FontWeight.Medium)
          .fontColor(this.dark ? '#F2F2F3' : '#1A1A1A')
          .layoutWeight(1)
        Text(translate(this.uiLang, '桌面版'))
          .fontSize(10)
          .fontColor('#8A5A00')
          .padding({ left: 6, right: 6, top: 2, bottom: 2 })
          .backgroundColor('#FFE8B0')
          .borderRadius(4)
          .visibility(this.showBadge ? Visibility.Visible : Visibility.None)
      }
      .width('100%')
      Text(this.desc)
        .fontSize(12)
        .fontColor(this.dark ? '#9A9AA0' : '#666666')
    }
    .width('100%')
    .padding(14)
    .alignItems(HorizontalAlign.Start)
    .backgroundColor(this.dark ? '#242429' : '#FFFFFF')
    .borderRadius(12)
    .border({ width: 1, color: this.dark ? '#2E2E33' : '#E8E8EA' })
    .onClick(() => {
      AppStorage.setOrCreate('pendingNav', this.target);
    })
  }
}

@Entry
@Component
struct Index {
  @State page: string = 'dashboard';
  @State messages: ChatMessage[] = [];
  @State input: string = '';
  @State sending: boolean = false;
  @State cfg: LLMConfig = {
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
  @State convId: string = '';
  @State convList: Conversation[] = [];
  /** 宽屏布局（侧栏常驻），按窗口宽度 */
  @State isPC: boolean = false;
  /** 形态是否为平板/手机（非 2in1）：用于「请在桌面版使用」提示 */
  @State isTabletDevice: boolean = true;
  /** 手机折叠态（未展开）：需提示展开至三折 */
  @State isPhoneFolded: boolean = false;
  @State deviceTypeRaw: string = '';
  @State showNav: boolean = true;
  @State dark: boolean = false;
  @StorageLink('systemDark') @Watch('onSystemTheme') systemDark: boolean = false;
  @StorageLink('systemLang') @Watch('onSystemLang') systemLang: string = 'zh-Hans';
  @State uiLang: string = 'zh-Hans';
  @StorageLink('pendingNav') @Watch('consumeNav') pendingNav: string = '';
  @State topInset: number = 0;
  @State bottomInset: number = 0;
  insetBound: boolean = false;
  sizeBound: boolean = false;

  @State memList: MemoryItem[] = [];
  @State memInput: string = '';
  @State memQuery: string = '';

  @State docs: KnowledgeDoc[] = [];
  @State wikiPages: WikiPage[] = [];
  @State kbCfg: KnowledgeConfig = {
    enabled: true,
    mode: 'local',
    backend: 'obsidian',
    path: '本机沙箱 / CodeCoreAgent-Wiki',
    bootstrapped: false,
  };
  @State kbStatusText: string = '';
  @State ingestTitle: string = '';
  @State ingestBody: string = '';
  @State peekPageId: string = '';
  @State docTitle: string = '';
  @State docBody: string = '';
  @State docQuery: string = '';
  @State editingDocId: string = '';

  @State apiModels: ApiModelItem[] = [];
  @State newModelName: string = '';
  @State newModelId: string = '';
  @State newModelUrl: string = '';
  @State newModelKey: string = '';
  @State newModelProvider: string = '';
  @State presetSelected: string = '自定义';
  @State detectedModels: string[] = [];
  @State detecting: boolean = false;
  @State detectKind: string = '';
  @State detectHint: string = '';
  @State showChatModelMenu: boolean = false;
  @State chatChoices: string[] = [];
  @State showPresetList: boolean = false;
  @State modelsTab: string = 'local';   // api | local
  @State localEndpoints: LocalEndpoint[] = [];
  @State epLabel: string = '';
  @State epBase: string = 'http://127.0.0.1:11434';
  @State epRole: string = 'backup';
  @State pullName: string = '';
  @State pullTargetId: string = '';
  @State localBusy: boolean = false;

  @State browserUrl: string = 'https://www.huawei.com';
  @State browserInput: string = 'https://www.huawei.com';
  browserCtrl: webview.WebviewController = new webview.WebviewController();

  @State studioBrief: string = '';
  @State studioStory: string = '';
  @State studioDraft: string = '';

  @State leadCmd: string = '';
  @State leadTasks: string[] = [];

  @State autoJobs: string[] = [];
  @State autoInput: string = '';

  @State activity: ActivityItem[] = [];
  @State toast: string = '';
  @State identity: IdentityRecord = {
    verified: false,
    openId: '',
    unionId: '',
    anonymousPhone: '',
    verifiedAt: 0,
  };
  @State authBusy: boolean = false;

  stopFn: (() => void) | null = null;
  ctx: common.UIAbilityContext = getContext(this) as common.UIAbilityContext;

  aboutToAppear() {
    this.refreshSystemDark();
    this.refreshSystemLang();
    this.reloadAll();
    this.identity = loadIdentity(this.ctx);
    this.detectDevice();
    this.bindInsets();
    this.paintSystemBars();
    this.showNav = true;
  }

  onPageShow(): void {
    this.refreshSystemDark();
    this.refreshSystemLang();
    this.applyTheme();
    this.applyLanguage();
    this.bindInsets();
    this.paintSystemBars();
  }

  onSystemTheme(): void {
    this.applyTheme();
    this.paintSystemBars();
  }

  onSystemLang(): void {
    this.applyLanguage();
  }

  tx(source: string): string {
    return translate(this.uiLang, source);
  }

  consumeNav(): void {
    const id = this.pendingNav;
    if (id.length === 0) {
      return;
    }
    this.pendingNav = '';
    this.go(id);
  }

  refreshSystemDark(): void {
    try {
      const dark = this.ctx.config.colorMode === ConfigurationConstant.ColorMode.COLOR_MODE_DARK;
      AppStorage.setOrCreate('systemDark', dark);
    } catch (_e) {
    }
  }

  refreshSystemLang(): void {
    let lang = '';
    try {
      lang = i18n.System.getSystemLanguage();
    } catch (_e) {
    }
    if (lang.length === 0) {
      try {
        lang = this.ctx.config.language || '';
      } catch (_e2) {
      }
    }
    if (lang.length > 0) {
      AppStorage.setOrCreate('systemLang', lang);
    }
  }

  applyLanguage(): void {
    const pref = this.cfg.language.length > 0 ? this.cfg.language : 'auto';
    this.uiLang = resolveLanguage(pref, this.systemLang);
    AppStorage.setOrCreate('uiLang', this.uiLang);
  }

  setLanguage(language: string): void {
    const next: LLMConfig = {
      baseUrl: this.cfg.baseUrl,
      apiKey: this.cfg.apiKey,
      model: this.cfg.model,
      temperature: this.cfg.temperature,
      theme: this.cfg.theme,
      systemPrompt: this.cfg.systemPrompt,
      nickname: this.cfg.nickname,
      companionOn: this.cfg.companionOn,
      companionName: this.cfg.companionName,
      autoYes: this.cfg.autoYes,
      maxIterations: this.cfg.maxIterations,
      language: language,
    };
    this.cfg = next;
    this.applyLanguage();
    saveConfig(this.ctx, this.cfg);
  }

  applyTheme(): void {
    this.dark = isDarkTheme(this.cfg, this.systemDark);
  }

  setTheme(theme: string): void {
    const next: LLMConfig = {
      baseUrl: this.cfg.baseUrl,
      apiKey: this.cfg.apiKey,
      model: this.cfg.model,
      temperature: this.cfg.temperature,
      theme: theme,
      systemPrompt: this.cfg.systemPrompt,
      nickname: this.cfg.nickname,
      companionOn: this.cfg.companionOn,
      companionName: this.cfg.companionName,
      autoYes: this.cfg.autoYes,
      maxIterations: this.cfg.maxIterations,
      language: this.cfg.language,
    };
    this.cfg = next;
    this.applyTheme();
    saveConfig(this.ctx, this.cfg);
    markThemeChosen(this.ctx);
    this.paintSystemBars();
  }

  fieldBg(): string {
    return this.dark ? '#2A2A30' : '#F4F4F6';
  }

  bindInsets(): void {
    if (this.insetBound) {
      this.readInsets();
      return;
    }
    try {
      const win = this.ctx.windowStage.getMainWindowSync();
      this.readInsets();
      win.on('avoidAreaChange', () => {
        this.readInsets();
      });
      this.insetBound = true;
    } catch (_e) {
    }
  }

  readInsets(): void {
    try {
      const win = this.ctx.windowStage.getMainWindowSync();
      const sys = win.getWindowAvoidArea(window.AvoidAreaType.TYPE_SYSTEM);
      const cut = win.getWindowAvoidArea(window.AvoidAreaType.TYPE_CUTOUT);
      let bottomPx = sys.bottomRect.height;
      try {
        const nav = win.getWindowAvoidArea(window.AvoidAreaType.TYPE_NAVIGATION_INDICATOR);
        if (nav.bottomRect.height > bottomPx) {
          bottomPx = nav.bottomRect.height;
        }
      } catch (_nav) {
      }
      let density = 1;
      try {
        const d = display.getDefaultDisplaySync().densityPixels;
        if (d > 0) {
          density = d;
        }
      } catch (_d) {
      }
      const topPx = sys.topRect.height > cut.topRect.height ? sys.topRect.height : cut.topRect.height;
      this.topInset = topPx / density;
      this.bottomInset = bottomPx / density;
    } catch (_e) {
    }
  }

  paintSystemBars(): void {
    try {
      const win = this.ctx.windowStage.getMainWindowSync();
      const content = this.dark ? '#F2F2F3' : '#1A1A1A';
      const props: window.SystemBarProperties = {
        statusBarColor: '#00000000',
        statusBarContentColor: content,
        navigationBarColor: '#00000000',
        navigationBarContentColor: content,
      };
      win.setWindowSystemBarProperties(props, (err) => {
        if (err && err.code) {
          return;
        }
      });
    } catch (_e) {
    }
  }

  reloadAll() {
    this.cfg = loadConfig(this.ctx);
    this.applyTheme();
    this.applyLanguage();
    this.refreshList();
    this.memList = loadMemories(this.ctx);
    this.docs = loadDocs(this.ctx);
    this.wikiPages = loadPages(this.ctx);
    this.kbCfg = loadKnowledgeConfig(this.ctx);
    this.refreshKbStatus();
    this.apiModels = loadApiModels(this.ctx);
    this.localEndpoints = loadEndpoints(this.ctx);
    this.activity = loadActivity(this.ctx);
    if (this.convList.length > 0) {
      this.openConvo(this.convList[0].id);
    } else {
      this.newChat();
    }
  }

  detectDevice() {
    try {
      const dtype = deviceInfo.deviceType;
      this.deviceTypeRaw = dtype;
      // 仅鸿蒙电脑（2in1）不算平板形态；平板/手机都显示桌面版提示
      this.isTabletDevice = dtype !== '2in1';
    } catch (_e) {
      this.isTabletDevice = true;
      this.deviceTypeRaw = 'tablet';
    }
    try {
      const win = this.ctx.windowStage.getMainWindowSync();
      const updateLayout = (widthPx: number) => {
        const density = display.getDefaultDisplaySync().densityPixels || 1;
        const widthVp = widthPx / density;
        this.isPC = widthVp >= PC_BREAKPOINT;
        // 系统识别为手机，且窗口仍为窄屏 → 折叠/单屏手机态
        this.isPhoneFolded = this.deviceTypeRaw === 'phone' && widthVp < PC_BREAKPOINT;
        if (this.isPC) {
          this.showNav = true;
        }
      };
      updateLayout(win.getWindowProperties().windowRect.width);
      if (!this.sizeBound) {
        win.on('windowSizeChange', (s) => {
          try {
            updateLayout(s.width);
          } catch (_err) {
          }
        });
        this.sizeBound = true;
      }
    } catch (_e) {
      this.isPC = false;
      this.isPhoneFolded = this.deviceTypeRaw === 'phone';
    }
  }

  bg(): string { return this.dark ? '#0f0f12' : '#FFFFFF'; }
  panel(): string { return this.dark ? '#1a1a1f' : '#F7F7F8'; }
  card(): string { return this.dark ? '#242429' : '#FFFFFF'; }
  ink(): string { return this.dark ? '#F2F2F3' : '#1a1a1a'; }
  muted(): string { return this.dark ? '#9a9aa0' : '#666666'; }
  line(): string { return this.dark ? '#2e2e33' : '#E8E8EA'; }
  accent(): string { return '#007AFF'; }

  /** 平板/手机形态：依赖桌面宿主的功能只提示，不删入口 */
  showDesktopHint(): boolean {
    return this.isTabletDevice && isDesktopOnlyPage(this.page);
  }

  /** 手机未展开至三折宽屏时拦截使用 */
  showPhoneFoldGate(): boolean {
    return this.isPhoneFolded;
  }

  deviceLabel(): string {
    if (this.deviceTypeRaw === '2in1') {
      return this.tx("鸿蒙电脑");
    }
    if (this.deviceTypeRaw === 'phone' && this.isPhoneFolded) {
      return this.tx("鸿蒙手机");
    }
    if (this.deviceTypeRaw === 'phone') {
      return this.tx("鸿蒙三折");
    }
    return this.tx("鸿蒙平板");
  }

  go(page: string) {
    this.page = page;
    if (!this.isPC) {
      this.showNav = false;
    }
    if (page === 'memory') {
      this.memList = loadMemories(this.ctx);
    } else if (page === 'knowledge') {
      this.kbCfg = loadKnowledgeConfig(this.ctx);
      this.wikiPages = searchPages(this.ctx, this.docQuery);
      this.docs = loadDocs(this.ctx);
      this.refreshKbStatus();
      if (!this.kbCfg.bootstrapped) {
        bootstrapVault(this.ctx);
        this.kbCfg = loadKnowledgeConfig(this.ctx);
        this.wikiPages = loadPages(this.ctx);
        this.refreshKbStatus();
      }
    } else if (page === 'logs') {
      this.activity = loadActivity(this.ctx);
    } else if (page === 'models') {
      this.apiModels = loadApiModels(this.ctx);
      this.localEndpoints = loadEndpoints(this.ctx);
    } else if (page === 'settings') {
      this.cfg = loadConfig(this.ctx);
      this.applyTheme();
      this.applyLanguage();
    }
  }

  refreshList() {
    const ids = loadAllIds(this.ctx);
    const convos: Conversation[] = [];
    for (let i = 0; i < ids.length; i++) {
      const c = loadConvo(this.ctx, ids[i]);
      if (c !== null) {
        convos.push(c);
      }
    }
    convos.sort((a, b) => b.updated - a.updated);
    this.convList = convos;
  }

  newChat() {
    this.convId = newId();
    this.messages = [];
    this.saveCurrent();
    this.refreshList();
    this.go('chat');
  }

  openConvo(id: string) {
    const conv = loadConvo(this.ctx, id);
    if (conv) {
      this.convId = id;
      this.messages = conv.messages;
    }
    this.go('chat');
  }

  removeConvo(id: string) {
    deleteConvo(this.ctx, id);
    this.refreshList();
    if (this.convId === id) {
      this.newChat();
    }
  }

  saveCurrent() {
    if (this.convId.length === 0) {
      return;
    }
    const title = this.messages.find((m) => m.role === 'user')?.content.slice(0, 24) || this.tx("新对话");
    saveConvo(this.ctx, {
      id: this.convId,
      title,
      messages: this.messages,
      updated: Date.now(),
    });
    this.refreshList();
  }

  stopSend() {
    if (this.stopFn) {
      this.stopFn();
      this.stopFn = null;
    }
    this.sending = false;
  }

  async ensureIdentity(): Promise<boolean> {
    if (this.identity.verified) {
      return true;
    }
    this.toast = this.tx("使用合成生成内容前，请先用华为账号完成实名核验");
    return false;
  }

  async startIdentityVerify() {
    if (this.authBusy) {
      return;
    }
    this.authBusy = true;
    try {
      this.identity = await verifyWithHuaweiAccount(this.ctx);
      this.toast = this.tx("实名核验已完成，可以开始对话");
      pushActivity(this.ctx, 'settings', this.tx("完成实名核验"));
      this.activity = loadActivity(this.ctx);
    } catch (e) {
      const be = e as BusinessError;
      const msg = (be.message && be.message.length > 0) ? be.message : `${be.code || e}`;
      this.toast = `${this.tx("实名核验未完成")}：${msg}`;
    }
    this.authBusy = false;
  }

  clearIdentityLocal() {
    clearIdentity(this.ctx);
    this.identity = loadIdentity(this.ctx);
    this.toast = this.tx("已退出账号核验");
  }

  async send() {
    const text = this.input.trim();
    if (!text || this.sending) {
      return;
    }
    if (!(await this.ensureIdentity())) {
      return;
    }
    if (!this.cfg.baseUrl) {
      this.go('settings');
      this.toast = this.tx("请先配置 API Base URL");
      return;
    }
    this.input = '';
    this.messages = [...this.messages, { role: 'user', content: text }];
    this.sending = true;
    const assistantIdx = this.messages.length;
    this.messages = [...this.messages, { role: 'assistant', content: '' }];
    pushActivity(this.ctx, 'chat', `用户: ${text.slice(0, 40)}`);

    // 启用知识库时注入相关 wiki 上下文（对齐桌面 knowledge_search）
    const kbExtra = buildKnowledgeContext(this.ctx, text);
    const streamCfg: LLMConfig = {
      baseUrl: this.cfg.baseUrl,
      apiKey: this.cfg.apiKey,
      model: this.cfg.model,
      temperature: this.cfg.temperature,
      theme: this.cfg.theme,
      systemPrompt: this.cfg.systemPrompt + '\nReply to the user in ' + replyLanguageName(this.uiLang) + '.' + kbExtra,
      nickname: this.cfg.nickname,
      companionOn: this.cfg.companionOn,
      companionName: this.cfg.companionName,
      autoYes: this.cfg.autoYes,
      maxIterations: this.cfg.maxIterations,
      language: this.cfg.language,
    };

    this.stopFn = chatStream(
      streamCfg,
      this.messages.slice(0, assistantIdx),
      (delta) => {
        const updated = [...this.messages];
        updated[assistantIdx] = {
          role: 'assistant',
          content: updated[assistantIdx].content + delta,
        };
        this.messages = updated;
      },
      () => {
        this.sending = false;
        this.stopFn = null;
        this.saveCurrent();
        pushActivity(this.ctx, 'chat', this.tx("助手回复完成"));
        this.activity = loadActivity(this.ctx);
      },
      (err) => {
        const updated = [...this.messages];
        updated[assistantIdx] = { role: 'assistant', content: `(错误) ${err}` };
        this.messages = updated;
        this.sending = false;
        this.stopFn = null;
        this.saveCurrent();
      },
    );
  }

  saveSettings() {
    saveConfig(this.ctx, this.cfg);
    this.applyTheme();
    this.toast = this.tx("偏好已保存");
    pushActivity(this.ctx, 'settings', this.tx("更新偏好设置"));
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
      this.toast = '无法打开官网';
    });
  }

  applyModel(item: ApiModelItem) {
    this.cfg.baseUrl = item.baseUrl;
    this.cfg.apiKey = item.apiKey;
    this.cfg.model = item.model;
    saveConfig(this.ctx, this.cfg);
    this.toast = `已切换到 ${item.name}`;
    this.showChatModelMenu = false;
  }

  /** 对话栏切换：先匹配 API，再匹配本地端点 */
  selectChatModel(modelId: string) {
    const found = this.apiModels.find((m) => m.model === modelId);
    if (found) {
      this.applyModel(found);
      return;
    }
    for (let i = 0; i < this.localEndpoints.length; i++) {
      const ep = this.localEndpoints[i];
      if (ep.models.indexOf(modelId) >= 0) {
        this.useLocalModel(ep, modelId);
        return;
      }
    }
    this.cfg.model = modelId;
    saveConfig(this.ctx, this.cfg);
    this.toast = `已切换模型 ${modelId}`;
    this.showChatModelMenu = false;
  }

  chatModelChoices(): string[] {
    const out: string[] = [];
    const pushUnique = (s: string) => {
      if (s.length > 0 && out.indexOf(s) < 0) {
        out.push(s);
      }
    };
    pushUnique(this.cfg.model);
    for (let i = 0; i < this.apiModels.length; i++) {
      pushUnique(this.apiModels[i].model);
    }
    for (let i = 0; i < this.localEndpoints.length; i++) {
      const ms = this.localEndpoints[i].models;
      for (let j = 0; j < ms.length; j++) {
        pushUnique(ms[j]);
      }
    }
    for (let i = 0; i < this.detectedModels.length; i++) {
      pushUnique(this.detectedModels[i]);
    }
    return out;
  }

  useLocalModel(ep: LocalEndpoint, modelId: string) {
    this.cfg.baseUrl = toChatBase(ep.baseUrl);
    this.cfg.apiKey = '';
    this.cfg.model = modelId;
    saveConfig(this.ctx, this.cfg);
    this.toast = `已切换本地模型 ${modelId} @ ${ep.label}`;
    this.showChatModelMenu = false;
  }

  addLocalEndpoint() {
    const base = normalizeLocalBase(this.epBase);
    if (base.length === 0) {
      this.toast = this.tx("请填写端点地址，如 http://192.168.1.10:11434");
      return;
    }
    const label = this.epLabel.trim().length > 0 ? this.epLabel.trim() : this.tx("本地端点");
    const ep: LocalEndpoint = {
      id: newId(),
      label: label,
      baseUrl: base,
      role: this.epRole,
      models: [],
      kind: 'unknown',
      updated: Date.now(),
    };
    const list = [ep, ...this.localEndpoints];
    this.localEndpoints = list;
    saveEndpoints(this.ctx, list);
    this.epLabel = '';
    this.toast = this.tx("端点已添加，正在同步模型…");
    this.syncLocalEndpoint(ep.id);
  }

  async syncLocalEndpoint(id: string) {
    const idx = this.localEndpoints.findIndex((e) => e.id === id);
    if (idx < 0) {
      return;
    }
    const ep = this.localEndpoints[idx];
    this.localBusy = true;
    this.toast = `正在同步 ${ep.label}…`;
    try {
      const result = await detectModels(toChatBase(ep.baseUrl), '');
      this.localBusy = false;
      if (!result.ok) {
        this.toast = `${ep.label}：${result.error}`;
        return;
      }
      const updated: LocalEndpoint = {
        id: ep.id,
        label: ep.label,
        baseUrl: ep.baseUrl,
        role: ep.role,
        models: result.models,
        kind: result.kind,
        updated: Date.now(),
      };
      const list = [...this.localEndpoints];
      list[idx] = updated;
      this.localEndpoints = list;
      saveEndpoints(this.ctx, list);
      this.toast = result.models.length > 0
        ? `${ep.label}：同步到 ${result.models.length} 个模型`
        : `${ep.label}：在线但暂无模型`;
      if (result.models.length > 0 && (this.cfg.model.length === 0 || this.cfg.baseUrl.indexOf('openai.com') >= 0)) {
        // 不强制覆盖已有配置，仅在空模型时启用
      }
    } catch (_e) {
      this.localBusy = false;
      this.toast = this.tx("同步失败");
    }
  }

  removeLocalEndpoint(id: string) {
    const list = this.localEndpoints.filter((e) => e.id !== id);
    this.localEndpoints = list;
    saveEndpoints(this.ctx, list);
  }

  async pullToEndpoint() {
    const name = this.pullName.trim();
    if (name.length === 0) {
      this.toast = this.tx("请填写要部署的模型名，如 qwen2.5-coder:7b");
      return;
    }
    let ep: LocalEndpoint | undefined = undefined;
    if (this.pullTargetId.length > 0) {
      ep = this.localEndpoints.find((e) => e.id === this.pullTargetId);
    }
    if (!ep && this.localEndpoints.length > 0) {
      ep = this.localEndpoints[0];
    }
    if (!ep) {
      this.toast = this.tx("请先添加本地端点");
      return;
    }
    const target = ep;
    this.localBusy = true;
    this.toast = `正在向 ${target.label} 部署 ${name}…（可能较久）`;
    try {
      await pullOllamaModel(target.baseUrl, name);
      this.localBusy = false;
      this.toast = `部署完成：${name}`;
      this.pullName = '';
      await this.syncLocalEndpoint(target.id);
    } catch (e) {
      this.localBusy = false;
      const err = e as Error;
      this.toast = `部署失败：${err.message}`;
    }
  }

  applyPreset(p: ApiPreset) {
    this.presetSelected = p.name;
    this.newModelUrl = p.baseUrl;
    this.newModelProvider = presetProviderLabel(p.name);
    this.newModelName = this.newModelProvider;
    this.detectedModels = [];
    this.newModelId = '';
    this.detectHint = '';
    this.showPresetList = false;
    this.toast = `已选 ${p.name}`;
  }

  applyCustomPreset() {
    this.presetSelected = '自定义 / 本地';
    this.showPresetList = false;
    this.detectHint = this.tx("请填写本机或局域网 Base URL，例如 http://192.168.1.10:11434/v1");
  }

  async runDetect(forAddForm: boolean) {
    const url = forAddForm
      ? (this.newModelUrl.trim().length > 0 ? this.newModelUrl : this.cfg.baseUrl)
      : this.cfg.baseUrl;
    const key = forAddForm
      ? (this.newModelKey.length > 0 ? this.newModelKey : this.cfg.apiKey)
      : this.cfg.apiKey;
    if (url.trim().length === 0) {
      this.toast = this.tx("请先选择提供方或填写 Base URL");
      this.detectHint = this.tx("请先从上方选择 API 提供方，或手动填写本地/自定义地址");
      return;
    }
    this.detecting = true;
    this.detectHint = this.tx("正在识别模型…");
    this.toast = this.tx("正在识别模型…");
    try {
      const result = await detectModels(url, key);
      this.detecting = false;
      if (!result.ok) {
        this.detectedModels = [];
        this.detectKind = '';
        this.detectHint = `识别失败：${result.error}。仍可手动填写模型名后添加。`;
        this.toast = result.error;
        return;
      }
      this.detectedModels = result.models;
      this.detectKind = result.kind;
      if (forAddForm) {
        this.newModelUrl = result.baseUrl;
        this.newModelProvider = guessProvider(result.baseUrl);
        if (this.newModelName.trim().length === 0) {
          this.newModelName = this.newModelProvider;
        }
        if (result.models.length > 0) {
          this.newModelId = result.models[0];
        }
      } else {
        this.cfg.baseUrl = result.baseUrl;
        if (result.models.length > 0) {
          this.cfg.model = result.models[0];
          this.chatChoices = this.chatModelChoices();
        }
        saveConfig(this.ctx, this.cfg);
      }
      const kindLabel = result.kind === 'ollama' ? this.tx("Ollama 端点") : this.tx("OpenAI 兼容端点");
      this.detectHint = result.models.length > 0
        ? `识别成功：${kindLabel}，共 ${result.models.length} 个模型，请在下方选择后添加`
        : `已识别为 ${kindLabel}，但模型列表为空，请手动填写模型名`;
      this.toast = result.models.length > 0
        ? `识别到 ${result.models.length} 个模型`
        : `已识别为 ${result.kind}，列表为空`;
      pushActivity(this.ctx, 'models', `自动识别 ${result.kind}: ${result.models.length} 个`);
    } catch (_e) {
      this.detecting = false;
      this.detectHint = this.tx("识别失败：网络或端点异常");
      this.toast = this.tx("识别失败");
    }
  }

  addDetectedAsModels() {
    if (this.detectedModels.length === 0) {
      this.toast = this.tx("请先自动识别");
      return;
    }
    const base = this.newModelUrl.trim().length > 0 ? this.newModelUrl.trim() : this.cfg.baseUrl;
    const key = this.newModelKey.length > 0 ? this.newModelKey : this.cfg.apiKey;
    const prefix = this.newModelProvider.length > 0
      ? this.newModelProvider
      : (this.newModelName.trim().length > 0 ? this.newModelName.trim() : this.tx("模型"));
    const list = [...this.apiModels];
    let added = 0;
    for (let i = 0; i < this.detectedModels.length; i++) {
      const mid = this.detectedModels[i];
      const exists = list.find((x) => x.model === mid && x.baseUrl === base);
      if (exists) {
        continue;
      }
      list.push({
        id: newId(),
        name: `${prefix} · ${mid}`,
        baseUrl: base,
        apiKey: key,
        model: mid,
        enabled: true,
      });
      added += 1;
    }
    this.apiModels = list;
    saveApiModels(this.ctx, list);
    if (added > 0) {
      this.cfg.model = this.detectedModels[0];
      this.cfg.baseUrl = base;
      this.cfg.apiKey = key;
      saveConfig(this.ctx, this.cfg);
    }
    this.toast = `已添加 ${added} 个模型`;
  }

  pickDetectedForForm(modelId: string) {
    this.newModelId = modelId;
    const provider = this.newModelProvider.length > 0 ? this.newModelProvider : this.tx("模型");
    this.newModelName = `${provider} · ${modelId}`;
  }

  addApiModel() {
    if (this.newModelUrl.trim().length === 0) {
      this.toast = this.tx("请填写 Base URL");
      return;
    }
    if (this.newModelId.trim().length === 0) {
      this.toast = this.tx("请先自动识别并选择模型，或手动填写模型名");
      return;
    }
    const provider = this.newModelProvider.length > 0
      ? this.newModelProvider
      : guessProvider(this.newModelUrl);
    const name = this.newModelName.trim().length > 0
      ? this.newModelName.trim()
      : `${provider} · ${this.newModelId.trim()}`;
    const item: ApiModelItem = {
      id: newId(),
      name: name,
      baseUrl: this.newModelUrl.trim(),
      apiKey: this.newModelKey,
      model: this.newModelId.trim(),
      enabled: true,
    };
    const list = [...this.apiModels, item];
    this.apiModels = list;
    saveApiModels(this.ctx, list);
    this.applyModel(item);
    this.toast = this.tx("模型已添加并启用");
  }

  removeApiModel(id: string) {
    const list = this.apiModels.filter((x) => x.id !== id);
    this.apiModels = list;
    saveApiModels(this.ctx, list);
  }

  addMem() {
    if (this.memInput.trim().length === 0) {
      return;
    }
    addMemory(this.ctx, this.memInput);
    this.memInput = '';
    this.memList = searchMemories(this.ctx, this.memQuery);
    pushActivity(this.ctx, 'memory', this.tx("新增记忆"));
  }

  refreshKbStatus() {
    const st = vaultStatus(this.ctx);
    const pills: string[] = [];
    pills.push(st.ready ? this.tx("已自动部署") : this.tx("未就绪"));
    if (st.shared) {
      pills.push(this.tx("局域网/共享"));
    }
    pills.push(this.tx("路径可写"));
    if (this.kbCfg.backend === 'obsidian') {
      pills.push('Obsidian');
    } else {
      pills.push('LLM Wiki');
    }
    pills.push(`${st.page_count} 个页面（wiki ${st.wiki_count} / raw ${st.raw_count}）`);
    pills.push(st.enabled ? this.tx("工具已启用") : this.tx("工具未启用"));
    this.kbStatusText = pills.join(' · ');
  }

  saveKbConnection() {
    saveKnowledgeConfig(this.ctx, this.kbCfg);
    if (this.kbCfg.enabled && !this.kbCfg.bootstrapped) {
      const n = bootstrapVault(this.ctx);
      this.kbCfg = loadKnowledgeConfig(this.ctx);
      this.wikiPages = loadPages(this.ctx);
      this.toast = `连接已保存，已布置 ${n} 项`;
    } else {
      this.toast = this.tx("知识库连接已保存");
    }
    this.refreshKbStatus();
    pushActivity(this.ctx, 'knowledge', this.tx("保存知识库连接"));
  }

  repairKb() {
    const n = bootstrapVault(this.ctx);
    this.kbCfg = loadKnowledgeConfig(this.ctx);
    this.wikiPages = searchPages(this.ctx, this.docQuery);
    this.refreshKbStatus();
    this.toast = `知识库已布置（${n} 项新建）`;
  }

  doIngest() {
    if (this.ingestBody.trim().length === 0) {
      this.toast = this.tx("请填写内容");
      return;
    }
    if (!this.kbCfg.bootstrapped) {
      bootstrapVault(this.ctx);
    }
    ingestText(this.ctx, this.ingestTitle, this.ingestBody);
    this.ingestTitle = '';
    this.ingestBody = '';
    this.wikiPages = searchPages(this.ctx, this.docQuery);
    this.refreshKbStatus();
    this.toast = this.tx("已写入 raw/inbox");
    pushActivity(this.ctx, 'knowledge', this.tx("投递原始材料"));
  }

  saveDoc() {
    if (this.docTitle.trim().length === 0) {
      this.toast = this.tx("请填写标题");
      return;
    }
    const id = this.editingDocId.length > 0 ? this.editingDocId : newId();
    upsertDoc(this.ctx, {
      id,
      title: this.docTitle.trim(),
      body: this.docBody,
      updated: Date.now(),
    });
    this.editingDocId = '';
    this.docTitle = '';
    this.docBody = '';
    this.docs = searchDocs(this.ctx, this.docQuery);
    this.wikiPages = searchPages(this.ctx, this.docQuery);
    this.refreshKbStatus();
    pushActivity(this.ctx, 'knowledge', this.tx("保存知识文档"));
  }

  editDoc(doc: KnowledgeDoc) {
    this.editingDocId = doc.id;
    this.docTitle = doc.title;
    this.docBody = doc.body;
  }

  editWikiPage(p: WikiPage) {
    this.editingDocId = p.id;
    this.docTitle = p.title;
    this.docBody = p.body;
    this.peekPageId = p.id;
  }

  addLeadTask() {
    if (this.leadCmd.trim().length === 0) {
      return;
    }
    this.leadTasks = [`进行中 · ${this.leadCmd.trim()}`, ...this.leadTasks];
    pushActivity(this.ctx, 'lead', `派遣: ${this.leadCmd.trim()}`);
    this.leadCmd = '';
    this.activity = loadActivity(this.ctx);
  }

  addAutoJob() {
    if (this.autoInput.trim().length === 0) {
      return;
    }
    this.autoJobs = [this.autoInput.trim(), ...this.autoJobs];
    this.autoInput = '';
    pushActivity(this.ctx, 'automation', this.tx("新增自动化任务"));
  }

  saveStudio() {
    pushActivity(this.ctx, 'studio', this.tx("保存导演台草稿"));
    this.toast = this.tx("导演台草稿已保存到本机会话");
    this.activity = loadActivity(this.ctx);
  }

  build() {
    Stack() {
      Row() {
        if (this.showNav) {
          this.NavPane()
        }

        Column() {
          this.TopBar()
          if (this.toast.length > 0) {
            Text(this.toast)
              .fontSize(12).fontColor(Color.White)
              .padding({ left: 12, right: 12, top: 6, bottom: 6 })
              .backgroundColor('#333333')
              .borderRadius(8)
              .margin({ top: 8 })
              .onClick(() => { this.toast = ''; })
          }
          if (this.page === 'dashboard') {
            this.DashboardPane()
          } else if (this.page === 'chat') {
            this.ChatPane()
          } else if (this.page === 'browser') {
            this.BrowserPane()
          } else if (this.page === 'studio') {
            this.StudioPane()
          } else if (this.page === 'lead') {
            this.LeadPane()
          } else if (this.page === 'memory') {
            this.MemoryPane()
          } else if (this.page === 'knowledge') {
            this.KnowledgePane()
          } else if (this.page === 'skills') {
            this.SkillsPane()
          } else if (this.page === 'models') {
            this.ModelsPane()
          } else if (this.page === 'automation') {
            this.AutoPane()
          } else if (this.page === 'logs') {
            this.LogsPane()
          } else if (this.page === 'versions') {
            this.VersionsPane()
          } else if (this.page === 'privacy') {
            this.PrivacyPane()
          } else {
            this.SettingsPane()
          }
        }
        .layoutWeight(1)
        .height('100%')
        .backgroundColor(this.bg())
      }
      .width('100%').height('100%')
      .backgroundColor(this.bg())
      .padding({ top: this.topInset, bottom: this.bottomInset })

      if (this.showPhoneFoldGate()) {
        this.PhoneFoldGate()
      }
    }
    .width('100%').height('100%')
  }

  @Builder
  PhoneFoldGate() {
    Column() {
      Column({ space: 16 }) {
        Image($r('app.media.brand_logo'))
          .width('56%').objectFit(ImageFit.Contain)
        Text(this.tx("请展开至三折模式下使用"))
          .fontSize(20).fontWeight(FontWeight.Medium).fontColor(Color.White)
          .textAlign(TextAlign.Center)
        Text(this.tx("当前为手机折叠/单屏模式。请将设备完全展开至三折宽屏后继续使用本应用。"))
          .fontSize(14).fontColor('#D0D0D0')
          .textAlign(TextAlign.Center)
        Text(this.tx("展开后本提示会自动消失。"))
          .fontSize(12).fontColor('#A0A0A0')
          .textAlign(TextAlign.Center)
      }
      .padding(28)
      .width('86%')
      .alignItems(HorizontalAlign.Center)
      .backgroundColor('#CC111118')
      .borderRadius(16)
    }
    .width('100%').height('100%')
    .justifyContent(FlexAlign.Center)
    .alignItems(HorizontalAlign.Center)
    .backgroundColor('#E6000000')
  }

  @Builder
  TopBar() {
    Row() {
      if (!this.isPC) {
        Button(this.showNav ? '✕' : '☰').fontSize(18).width(44).height(44)
          .backgroundColor(Color.Transparent).fontColor(this.ink())
          .onClick(() => { this.showNav = !this.showNav; })
      }
      Image($r('app.media.brand_logo'))
        .height(28).objectFit(ImageFit.Contain)
        .margin({ left: 8 })
        .layoutWeight(1)
      Text(this.deviceLabel()).fontSize(11).fontColor(this.muted()).margin({ right: 8 })
      Text(`v${APP_VERSION}`).fontSize(11).fontColor(this.muted()).margin({ right: 8 })
      Button('＋').fontSize(20).width(44).height(44)
        .backgroundColor(Color.Transparent).fontColor(this.ink())
        .onClick(() => this.newChat())
    }
    .width('100%').height(52).padding({ left: 8, right: 8 })
    .backgroundColor(this.panel())
    .border({ width: { bottom: 1 }, color: this.line() })
  }

  @Builder
  NavPane() {
    Column() {
      Image($r('app.media.brand_logo'))
        .width('78%').objectFit(ImageFit.Contain)
        .margin({ left: 16, right: 16, top: 14, bottom: 8 })
        .alignSelf(ItemAlign.Start)

      Scroll() {
        Column() {
          ForEach(NAV, (item: NavItem) => {
            if (item.id === 'dashboard' || item.id === 'memory' || item.id === 'models') {
              Text(this.tx(item.group)).fontSize(11).fontColor(this.muted())
                .padding({ left: 16, top: 12, bottom: 4 }).width('100%')
            }
            Text((this.isTabletDevice && item.desktopOnly) ? `${this.tx(item.label)} · ${this.tx("桌面")}` : this.tx(item.label))
              .fontSize(14)
              .fontColor(this.page === item.id ? this.accent() : this.ink())
              .fontWeight(this.page === item.id ? FontWeight.Medium : FontWeight.Normal)
              .width('100%')
              .padding({ left: 16, right: 16, top: 10, bottom: 10 })
              .backgroundColor(this.page === item.id ? (this.dark ? '#1e2a3a' : '#E8F2FF') : Color.Transparent)
              .onClick(() => this.go(item.id))
          }, (item: NavItem) => item.id)

          if (this.page === 'chat' || this.isPC) {
            Text(this.tx("对话记录")).fontSize(11).fontColor(this.muted())
              .padding({ left: 16, top: 16, bottom: 4 }).width('100%')
            ForEach(this.convList, (conv: Conversation) => {
              Row() {
                Text(conv.title).fontSize(13).layoutWeight(1).maxLines(1)
                  .fontColor(this.ink())
                  .textOverflow({ overflow: TextOverflow.Ellipsis })
                Text('✕').fontSize(12).fontColor(Color.Red)
                  .onClick(() => this.removeConvo(conv.id))
              }
              .width('100%').padding({ left: 16, right: 12, top: 8, bottom: 8 })
              .backgroundColor(this.convId === conv.id ? (this.dark ? '#1e2a3a' : '#E5F3FF') : Color.Transparent)
              .onClick(() => this.openConvo(conv.id))
            }, (c: Conversation) => c.id)
          }
        }
      }
      .layoutWeight(1).width('100%')

      Text(this.cfg.model.length > 0 ? this.cfg.model : this.tx("未配置模型"))
        .fontSize(11).fontColor(this.muted())
        .padding(12).width('100%')
    }
    .width(this.isPC ? 220 : '78%')
    .height('100%')
    .backgroundColor(this.panel())
    .border({ width: { right: 1 }, color: this.line() })
  }

  @Builder
  DesktopHintBanner() {
    if (this.showDesktopHint()) {
      Column({ space: 6 }) {
        Text(this.tx("请在桌面版使用"))
          .fontSize(15).fontWeight(FontWeight.Bold).fontColor('#8A5A00')
        Text(this.tx("当前为鸿蒙平板布局。导演台 / 指挥中心 / 技能库 / 自动化等依赖 Mac、Windows 或 Linux 上的 CodeCoreAgent 桌面版（本机工具链与 Agent 宿主）。平板与鸿蒙电脑共用同一套入口；完整执行请打开桌面版。"))
          .fontSize(12).fontColor('#6B4E00')
        Text(this.tx("下方仍保留轻量草稿与对照，方便你在平板上查看与记录。"))
          .fontSize(12).fontColor('#6B4E00')
      }
      .width('100%')
      .padding(14)
      .margin({ left: 16, right: 16, top: 10, bottom: 4 })
      .alignItems(HorizontalAlign.Start)
      .backgroundColor('#FFF6E0')
      .borderRadius(12)
      .border({ width: 1, color: '#F0D9A0' })
    }
  }

  @Builder
  DashboardPane() {
    Scroll() {
      Column({ space: 16 }) {
        Column({ space: 6 }) {
          Text(this.tx("欢迎使用 CodeCoreAgent")).fontSize(22).fontWeight(FontWeight.Bold).fontColor(this.ink())
          Text(`${this.tx("当前设备")}：${this.deviceLabel()}`)
            .fontSize(14).fontColor(this.muted())
        }
        .width('100%').alignItems(HorizontalAlign.Start)

        if (this.isTabletDevice) {
          Column({ space: 6 }) {
            Text(this.tx("平板提示")).fontSize(14).fontWeight(FontWeight.Medium).fontColor('#8A5A00')
            Text(this.tx("对话、模型、记忆、知识库、浏览器、偏好等可直接在平板使用。导演台、指挥中心、技能库、自动化请到桌面版 CodeCoreAgent 使用完整能力。"))
              .fontSize(12).fontColor('#6B4E00')
          }
          .width('100%').padding(14).backgroundColor('#FFF6E0').borderRadius(12)
          .alignItems(HorizontalAlign.Start)
        }

        Flex({ wrap: FlexWrap.Wrap }) {
          DashCard({ title: this.tx("开始对话"), desc: this.tx("与智能体流式聊天"), target: 'chat', showBadge: false, dark: this.dark })
            .width('46%').margin({ right: '2%', bottom: 12 })
          DashCard({ title: this.tx("模型管理"), desc: this.tx("配置 API / 本地端点"), target: 'models', showBadge: false, dark: this.dark })
            .width('46%').margin({ right: '2%', bottom: 12 })
          DashCard({ title: this.tx("长期记忆"), desc: this.tx("保存可检索事实"), target: 'memory', showBadge: false, dark: this.dark })
            .width('46%').margin({ right: '2%', bottom: 12 })
          DashCard({ title: this.tx("知识库"), desc: this.tx("Obsidian / Wiki · 投递与检索"), target: 'knowledge', showBadge: false, dark: this.dark })
            .width('46%').margin({ right: '2%', bottom: 12 })
          DashCard({ title: this.tx("内置浏览器"), desc: this.tx("浏览网页并配合对话"), target: 'browser', showBadge: false, dark: this.dark })
            .width('46%').margin({ right: '2%', bottom: 12 })
          DashCard({ title: this.tx("导演台"), desc: this.tx("企划 / 分镜 · 完整能力在桌面版"), target: 'studio', showBadge: this.isTabletDevice, dark: this.dark })
            .width('46%').margin({ right: '2%', bottom: 12 })
          DashCard({ title: this.tx("指挥中心"), desc: this.tx("任务派遣 · 完整能力在桌面版"), target: 'lead', showBadge: this.isTabletDevice, dark: this.dark })
            .width('46%').margin({ right: '2%', bottom: 12 })
          DashCard({ title: this.tx("偏好设置"), desc: this.tx("主题、人格、API"), target: 'settings', showBadge: false, dark: this.dark })
            .width('46%').margin({ right: '2%', bottom: 12 })
        }
        .width('100%')

        Column({ space: 8 }) {
          Text(this.tx("当前状态")).fontSize(16).fontWeight(FontWeight.Medium).fontColor(this.ink())
          Text(`模型：${this.cfg.model || this.tx("未设置")} · Base：${this.cfg.baseUrl || this.tx("未设置")}`)
            .fontSize(13).fontColor(this.muted())
          Text(`对话 ${this.convList.length} · 记忆 ${this.memList.length} · 知识 ${this.docs.length}`)
            .fontSize(13).fontColor(this.muted())
        }
        .width('100%').padding(16).backgroundColor(this.card())
        .borderRadius(12).border({ width: 1, color: this.line() })
        .alignItems(HorizontalAlign.Start)
      }
      .width('100%').padding(20)
    }
    .layoutWeight(1).width('100%')
  }

  @Builder
  ChatPane() {
    Column() {
      if (!this.identity.verified) {
        Column({ space: 14 }) {
          Text(this.tx("实名核验")).fontSize(22).fontWeight(FontWeight.Bold).fontColor(this.ink())
          Text(this.tx("本应用提供合成生成内容服务。按相关法规要求，使用对话等生成能力前，须通过华为账号（绑定手机号）完成真实身份核验。"))
            .fontSize(14).fontColor(this.muted())
          Text(this.tx("核验仅在本机保存登录状态，不会把对话内容上传到 CodeCore 自有服务器。"))
            .fontSize(13).fontColor(this.muted())
          Button(this.authBusy ? this.tx("核验中…") : this.tx("华为账号登录核验"))
            .width('100%').height(48)
            .enabled(!this.authBusy)
            .onClick(() => this.startIdentityVerify())
          Button(this.tx("查看隐私条款"))
            .width('100%').height(44)
            .backgroundColor(this.fieldBg()).fontColor(this.ink())
            .onClick(() => this.go('privacy'))
        }
        .layoutWeight(1).width('100%')
        .justifyContent(FlexAlign.Center)
        .padding(28)
        .alignItems(HorizontalAlign.Start)
      } else {
      // 对话顶部：模型选择
      Row() {
        Text(this.tx("模型")).fontSize(12).fontColor(this.muted()).margin({ right: 8 })
        Button(this.cfg.model.length > 0 ? this.cfg.model : this.tx("选择模型"))
          .fontSize(13).height(32)
          .backgroundColor(this.dark ? '#2a2a30' : '#EEF3FF')
          .fontColor(this.accent())
          .layoutWeight(1)
          .onClick(() => {
            this.apiModels = loadApiModels(this.ctx);
            this.chatChoices = this.chatModelChoices();
            this.showChatModelMenu = !this.showChatModelMenu;
          })
        Button(this.tx("识别")).fontSize(12).height(32).margin({ left: 8 })
          .backgroundColor('#E8E8EA').fontColor('#333')
          .enabled(!this.detecting)
          .onClick(() => this.runDetect(false))
        Button(this.tx("管理")).fontSize(12).height(32).margin({ left: 6 })
          .backgroundColor('#E8E8EA').fontColor('#333')
          .onClick(() => this.go('models'))
      }
      .width('100%').padding({ left: 12, right: 12, top: 8, bottom: 4 })

      if (this.showChatModelMenu) {
        Column() {
          Scroll() {
            Column() {
              ForEach(this.chatChoices, (mid: string) => {
                Text(mid)
                  .fontSize(14)
                  .fontColor(mid === this.cfg.model ? this.accent() : this.ink())
                  .fontWeight(mid === this.cfg.model ? FontWeight.Medium : FontWeight.Normal)
                  .width('100%')
                  .padding(12)
                  .backgroundColor(mid === this.cfg.model ? (this.dark ? '#1e2a3a' : '#E8F2FF') : Color.Transparent)
                  .onClick(() => this.selectChatModel(mid))
              }, (mid: string, idx: number) => `${idx}_${mid}`)
              if (this.chatChoices.length === 0) {
                Text(this.tx("暂无模型，请先到「模型管理」添加或识别"))
                  .fontSize(12).fontColor(this.muted()).padding(12)
              }
            }.width('100%')
          }
          .constraintSize({ maxHeight: 220 })
          .width('100%')
        }
        .width('100%')
        .margin({ left: 12, right: 12, bottom: 4 })
        .backgroundColor(this.card())
        .borderRadius(10)
        .border({ width: 1, color: this.line() })
      }

      if (this.messages.length === 0) {
        Column({ space: 12 }) {
          Text(this.tx("CodeCoreAgent 就绪")).fontSize(20).fontWeight(FontWeight.Bold).fontColor(this.ink())
          Text(this.tx("开始对话，或从左侧进入总览体验完整功能。"))
            .fontSize(14).fontColor(this.muted())
          Text(identityStatusText(this.identity)).fontSize(12).fontColor(this.muted())
          Row({ space: 8 }) {
            Button(this.tx("去配置模型")).onClick(() => this.go('models'))
            Button(this.tx("打开知识库")).backgroundColor('#E8E8EA').fontColor('#333')
              .onClick(() => this.go('knowledge'))
          }
        }
        .layoutWeight(1).width('100%')
        .justifyContent(FlexAlign.Center)
        .padding(24)
      } else {
        List({ space: 10 }) {
          ForEach(this.messages, (msg: ChatMessage, idx: number) => {
            ListItem() {
              Column({ space: 4 }) {
                Row() {
                  if (msg.role === 'user') {
                    Blank()
                    Text(msg.content).fontSize(15).fontColor(Color.White)
                      .padding(12).backgroundColor(this.accent()).borderRadius(12)
                      .constraintSize({ maxWidth: '75%' })
                  } else {
                    Text(msg.content.length > 0 ? msg.content : '…').fontSize(15)
                      .fontColor(this.ink())
                      .padding(12)
                      .backgroundColor(this.dark ? '#2a2a30' : '#F0F0F0')
                      .borderRadius(12)
                      .constraintSize({ maxWidth: '85%' })
                    Blank()
                  }
                }
                .width('100%')
                if (msg.role === 'assistant' && msg.content.length > 0) {
                  Text(this.tx("此内容由智能体模型提供。"))
                    .fontSize(11).fontColor(this.muted())
                    .margin({ left: 4 })
                }
              }
              .width('100%').alignItems(HorizontalAlign.Start)
            }
          }, (msg: ChatMessage, idx: number) => `${idx}_${msg.role}_${msg.content.length}`)
        }
        .layoutWeight(1).width('100%').padding(12)
      }

      Row() {
        TextInput({ text: this.input, placeholder: this.tx("输入消息…") })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .layoutWeight(1).height(42)
          .backgroundColor(this.dark ? '#2a2a30' : '#F5F5F5')
          .onChange((v) => { this.input = v; })
          .onSubmit(() => this.send())
        if (this.sending) {
          Button(this.tx("停止")).width(64).height(42).margin({ left: 8 })
            .backgroundColor('#FF3B30')
            .onClick(() => this.stopSend())
        } else {
          Button(this.tx("发送")).width(64).height(42).margin({ left: 8 })
            .type(ButtonType.Capsule)
            .onClick(() => this.send())
        }
      }
      .width('100%').padding(12)
      .backgroundColor(this.bg())
      .border({ width: { top: 1 }, color: this.line() })
      } // end verified
    }
    .layoutWeight(1).width('100%')
  }

  @Builder
  BrowserPane() {
    Column() {
      Row({ space: 8 }) {
        TextInput({ text: this.browserInput, placeholder: 'https://…' })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .layoutWeight(1).height(40)
          .onChange((v) => { this.browserInput = v; })
          .onSubmit(() => {
            this.browserUrl = this.browserInput.trim();
            try { this.browserCtrl.loadUrl(this.browserUrl); } catch (_e) {}
          })
        Button(this.tx("前往")).height(40).onClick(() => {
          this.browserUrl = this.browserInput.trim();
          try { this.browserCtrl.loadUrl(this.browserUrl); } catch (_e) {}
        })
        Button(this.tx("刷新")).height(40).backgroundColor('#E8E8EA').fontColor('#333')
          .onClick(() => { try { this.browserCtrl.refresh(); } catch (_e) {} })
      }
      .width('100%').padding(12)
      Web({ src: this.browserUrl, controller: this.browserCtrl })
        .layoutWeight(1).width('100%')
        .javaScriptAccess(true).domStorageAccess(true).fileAccess(true)
    }
    .layoutWeight(1).width('100%')
  }

  @Builder
  StudioPane() {
    Column() {
      this.DesktopHintBanner()
      Scroll() {
        Column({ space: 14 }) {
          Text(this.tx("导演台")).fontSize(20).fontWeight(FontWeight.Bold).fontColor(this.ink())
          Text(this.isPC
            ? this.tx("企划 / 分镜 / 发布草稿。完整合成与 Comfy 管线请配合桌面版。")
            : this.tx("平板可记草稿；完整导演台能力请在桌面版使用。"))
            .fontSize(13).fontColor(this.muted())
          Text(this.tx("企划")).fontSize(14).fontWeight(FontWeight.Medium).fontColor(this.ink())
          TextArea({ text: this.studioBrief, placeholder: this.tx("主题、受众、时长…") })
            .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
            .backgroundColor(this.fieldBg())
            .height(100).width('100%')
            .onChange((v) => { this.studioBrief = v; })
          Text(this.tx("分镜")).fontSize(14).fontWeight(FontWeight.Medium).fontColor(this.ink())
          TextArea({ text: this.studioStory, placeholder: this.tx("镜头 1 / 2 / 3…") })
            .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
            .backgroundColor(this.fieldBg())
            .height(140).width('100%')
            .onChange((v) => { this.studioStory = v; })
          Text(this.tx("发布草稿")).fontSize(14).fontWeight(FontWeight.Medium).fontColor(this.ink())
          TextArea({ text: this.studioDraft, placeholder: this.tx("标题、简介、标签…") })
            .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
            .backgroundColor(this.fieldBg())
            .height(100).width('100%')
            .onChange((v) => { this.studioDraft = v; })
          Button(this.tx("保存草稿")).width('100%').height(44).onClick(() => this.saveStudio())
          Button(this.tx("用对话润色企划")).width('100%').height(44)
            .backgroundColor('#E8E8EA').fontColor('#333')
            .onClick(() => {
              this.input = `请根据以下企划润色成可拍摄脚本：\n${this.studioBrief}`;
              this.go('chat');
            })
        }
        .width('100%').padding(20).alignItems(HorizontalAlign.Start)
      }
      .layoutWeight(1).width('100%')
    }
    .layoutWeight(1).width('100%')
  }

  @Builder
  LeadPane() {
    Column({ space: 12 }) {
      this.DesktopHintBanner()
      Text(this.tx("指挥中心")).fontSize(20).fontWeight(FontWeight.Bold).fontColor(this.ink())
        .width('100%').padding({ left: 20, top: 8 })
      Text(this.isPC
        ? this.tx("可记录派遣；多 Agent 编排请在桌面版指挥中心执行。")
        : this.tx("平板可记录任务清单；完整派遣请在桌面版使用。"))
        .fontSize(12).fontColor(this.muted()).padding({ left: 20, right: 20 })
      Row({ space: 8 }) {
        TextInput({ text: this.leadCmd, placeholder: this.tx("下达命令，例如：整理本周任务清单") })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .layoutWeight(1).height(42)
          .onChange((v) => { this.leadCmd = v; })
        Button(this.tx("派遣")).height(42).onClick(() => this.addLeadTask())
      }
      .width('100%').padding({ left: 20, right: 20 })
      List({ space: 8 }) {
        ForEach(this.leadTasks, (t: string, i: number) => {
          ListItem() {
            Text(t).fontSize(14).fontColor(this.ink()).padding(14)
              .width('100%').backgroundColor(this.card()).borderRadius(10)
          }
        }, (t: string, i: number) => `${i}_${t}`)
      }
      .layoutWeight(1).width('100%').padding({ left: 20, right: 20, bottom: 20 })
      if (this.leadTasks.length === 0) {
        Text(this.tx("暂无任务。"))
          .fontSize(13).fontColor(this.muted()).padding(20)
      }
    }
    .layoutWeight(1).width('100%').alignItems(HorizontalAlign.Start)
  }

  @Builder
  MemoryPane() {
    Column({ space: 10 }) {
      Text(this.tx("长期记忆")).fontSize(20).fontWeight(FontWeight.Bold).fontColor(this.ink())
        .padding({ left: 20, top: 16 }).width('100%')
      Row({ space: 8 }) {
        TextInput({ text: this.memQuery, placeholder: this.tx("搜索记忆…") })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .layoutWeight(1).height(40)
          .onChange((v) => {
            this.memQuery = v;
            this.memList = searchMemories(this.ctx, v);
          })
      }.width('100%').padding({ left: 20, right: 20 })
      Row({ space: 8 }) {
        TextInput({ text: this.memInput, placeholder: this.tx("添加一条记忆…") })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .layoutWeight(1).height(40)
          .onChange((v) => { this.memInput = v; })
        Button(this.tx("添加")).height(40).onClick(() => this.addMem())
      }.width('100%').padding({ left: 20, right: 20 })
      List({ space: 8 }) {
        ForEach(this.memList, (m: MemoryItem) => {
          ListItem() {
            Row() {
              Text(m.content).fontSize(14).fontColor(this.ink()).layoutWeight(1)
              Text(this.tx("删除")).fontSize(12).fontColor(Color.Red)
                .onClick(() => {
                  deleteMemory(this.ctx, m.id);
                  this.memList = searchMemories(this.ctx, this.memQuery);
                })
            }
            .width('100%').padding(14).backgroundColor(this.card()).borderRadius(10)
          }
        }, (m: MemoryItem) => m.id)
      }
      .layoutWeight(1).width('100%').padding({ left: 20, right: 20, bottom: 16 })
    }
    .layoutWeight(1).width('100%')
  }

  @Builder
  KnowledgePane() {
    Scroll() {
      Column({ space: 14 }) {
        Row() {
          Column({ space: 4 }) {
            Text(this.tx("知识库")).fontSize(20).fontWeight(FontWeight.Bold).fontColor(this.ink())
            Text(this.tx("随安装自动部署 · Obsidian / LLM Wiki"))
              .fontSize(12).fontColor(this.muted())
          }.layoutWeight(1).alignItems(HorizontalAlign.Start)
          Button(this.tx("🔧 修复布置")).height(36).fontSize(12)
            .backgroundColor('#E8E8EA').fontColor('#333')
            .onClick(() => this.repairKb())
        }.width('100%')

        // 连接设置
        Column({ space: 10 }) {
          Text(this.tx("连接设置")).fontSize(15).fontWeight(FontWeight.Medium).fontColor(this.ink())
          Text(this.tx("存储方式")).fontSize(12).fontColor(this.muted())
          Row({ space: 8 }) {
            Button(this.kbCfg.mode === 'local' ? this.tx("● 本机目录") : this.tx("本机目录"))
              .layoutWeight(1).height(34).fontSize(12)
              .backgroundColor(this.kbCfg.mode === 'local' ? this.accent() : '#E8E8EA')
              .fontColor(this.kbCfg.mode === 'local' ? Color.White : '#333')
              .onClick(() => { this.kbCfg.mode = 'local'; })
            Button(this.kbCfg.mode === 'shared' ? this.tx("● 局域网/NAS") : this.tx("局域网/NAS"))
              .layoutWeight(1).height(34).fontSize(12)
              .backgroundColor(this.kbCfg.mode === 'shared' ? this.accent() : '#E8E8EA')
              .fontColor(this.kbCfg.mode === 'shared' ? Color.White : '#333')
              .onClick(() => { this.kbCfg.mode = 'shared'; })
          }.width('100%')
          if (this.isTabletDevice && this.kbCfg.mode === 'shared') {
            Text(this.tx("平板提示：NAS / 共享盘路径选择与多机挂载请在桌面版完成；本机沙箱知识库可在平板直接使用。"))
              .fontSize(11).fontColor('#8A5A00')
              .padding(8).backgroundColor('#FFF6E0').borderRadius(8).width('100%')
          }
          Text(this.tx("后端形态")).fontSize(12).fontColor(this.muted())
          Row({ space: 8 }) {
            Button(this.kbCfg.backend === 'obsidian' ? this.tx("● Obsidian 库") : this.tx("Obsidian 库"))
              .layoutWeight(1).height(34).fontSize(12)
              .backgroundColor(this.kbCfg.backend === 'obsidian' ? this.accent() : '#E8E8EA')
              .fontColor(this.kbCfg.backend === 'obsidian' ? Color.White : '#333')
              .onClick(() => { this.kbCfg.backend = 'obsidian'; })
            Button(this.kbCfg.backend === 'llmwiki' ? '● LLM Wiki' : 'LLM Wiki')
              .layoutWeight(1).height(34).fontSize(12)
              .backgroundColor(this.kbCfg.backend === 'llmwiki' ? this.accent() : '#E8E8EA')
              .fontColor(this.kbCfg.backend === 'llmwiki' ? Color.White : '#333')
              .onClick(() => { this.kbCfg.backend = 'llmwiki'; })
          }.width('100%')
          Text(this.tx("知识库路径")).fontSize(12).fontColor(this.muted())
          TextInput({ text: this.kbCfg.path, placeholder: this.tx("本机沙箱路径或桌面版同步路径说明") })
            .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
            .backgroundColor(this.fieldBg())
            .width('100%').height(40)
            .onChange((v) => { this.kbCfg.path = v; })
          if (this.isTabletDevice) {
            Text(this.tx("「选择文件夹 / 打开文件夹」为桌面版能力；鸿蒙端使用应用沙箱 Wiki。"))
              .fontSize(11).fontColor(this.muted())
          }
          Row() {
            Text(this.tx("启用知识库（对话中注入检索上下文）")).fontSize(13).fontColor(this.ink()).layoutWeight(1)
            Toggle({ type: ToggleType.Switch, isOn: this.kbCfg.enabled })
              .onChange((v) => { this.kbCfg.enabled = v; })
          }.width('100%')
          Row({ space: 8 }) {
            Button(this.tx("刷新")).layoutWeight(1).height(40)
              .backgroundColor('#E8E8EA').fontColor('#333')
              .onClick(() => {
                this.kbCfg = loadKnowledgeConfig(this.ctx);
                this.wikiPages = searchPages(this.ctx, this.docQuery);
                this.refreshKbStatus();
              })
            Button(this.tx("保存连接")).layoutWeight(1).height(40)
              .onClick(() => this.saveKbConnection())
          }.width('100%')
        }
        .width('100%').padding(14)
        .backgroundColor(this.card()).borderRadius(12)
        .border({ width: 1, color: this.line() })
        .alignItems(HorizontalAlign.Start)

        // 库状态
        Column({ space: 6 }) {
          Text(this.tx("库状态")).fontSize(15).fontWeight(FontWeight.Medium).fontColor(this.ink())
          Text(this.kbStatusText.length > 0 ? this.kbStatusText : this.tx("加载中…"))
            .fontSize(12).fontColor(this.muted())
        }
        .width('100%').padding(14)
        .backgroundColor(this.card()).borderRadius(12)
        .border({ width: 1, color: this.line() })
        .alignItems(HorizontalAlign.Start)

        // 投递原始材料
        Column({ space: 8 }) {
          Text(this.tx("投递原始材料")).fontSize(15).fontWeight(FontWeight.Medium).fontColor(this.ink())
          TextInput({ text: this.ingestTitle, placeholder: this.tx("标题，如：某次架构决策") })
            .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
            .backgroundColor(this.fieldBg())
            .width('100%').height(40).onChange((v) => { this.ingestTitle = v; })
          TextArea({ text: this.ingestBody, placeholder: this.tx("粘贴笔记、链接摘要、对话要点…") })
            .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
            .backgroundColor(this.fieldBg())
            .width('100%').height(100).onChange((v) => { this.ingestBody = v; })
          Button(this.tx("写入 raw/inbox")).width('100%').height(42)
            .onClick(() => this.doIngest())
        }
        .width('100%').padding(14)
        .backgroundColor(this.card()).borderRadius(12)
        .border({ width: 1, color: this.line() })
        .alignItems(HorizontalAlign.Start)

        // Wiki 页面
        Column({ space: 8 }) {
          Text(this.tx("Wiki 页面")).fontSize(15).fontWeight(FontWeight.Medium).fontColor(this.ink())
          Row({ space: 8 }) {
            TextInput({ text: this.docQuery, placeholder: this.tx("搜索 wiki…（回车）") })
              .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
              .backgroundColor(this.fieldBg())
              .layoutWeight(1).height(40)
              .onChange((v) => { this.docQuery = v; })
              .onSubmit(() => { this.wikiPages = searchPages(this.ctx, this.docQuery); })
            Button(this.tx("搜索")).height(40).onClick(() => {
              this.wikiPages = searchPages(this.ctx, this.docQuery);
            })
          }.width('100%')

          if (this.wikiPages.length === 0) {
            Text(this.tx("尚未布置或无可显示页面")).fontSize(12).fontColor(this.muted())
          }
          ForEach(this.wikiPages, (p: WikiPage) => {
            Column({ space: 6 }) {
              Row() {
                Text(p.title).fontSize(14).fontWeight(FontWeight.Medium).fontColor(this.ink()).layoutWeight(1)
                Text(p.kind === 'raw' ? 'raw' : 'wiki').fontSize(10).fontColor(this.muted())
                  .padding({ left: 6, right: 6, top: 2, bottom: 2 })
                  .backgroundColor(this.dark ? '#2a2a30' : '#EEE').borderRadius(4)
              }.width('100%')
              Text(p.rel).fontSize(11).fontColor(this.muted())
              Text(p.body).fontSize(12).fontColor(this.muted()).maxLines(this.peekPageId === p.id ? 40 : 3)
              Row({ space: 12 }) {
                Text(this.peekPageId === p.id ? this.tx("收起") : this.tx("查看")).fontSize(12).fontColor(this.accent())
                  .onClick(() => { this.peekPageId = this.peekPageId === p.id ? '' : p.id; })
                Text(this.tx("编辑")).fontSize(12).fontColor(this.accent())
                  .onClick(() => this.editWikiPage(p))
                Text(this.tx("删除")).fontSize(12).fontColor(Color.Red)
                  .onClick(() => {
                    deletePage(this.ctx, p.id);
                    this.wikiPages = searchPages(this.ctx, this.docQuery);
                    this.refreshKbStatus();
                  })
                Text(this.tx("带入对话")).fontSize(12).fontColor(this.accent())
                  .onClick(() => {
                    this.input = `请基于以下知识回答：\n标题：${p.title}\n路径：${p.rel}\n${p.body}`;
                    this.go('chat');
                  })
              }
            }
            .width('100%').padding(12)
            .backgroundColor(this.dark ? '#1a1a1f' : '#F7F7F8')
            .borderRadius(10)
            .alignItems(HorizontalAlign.Start)
          }, (p: WikiPage) => p.id)
        }
        .width('100%').padding(14)
        .backgroundColor(this.card()).borderRadius(12)
        .border({ width: 1, color: this.line() })
        .alignItems(HorizontalAlign.Start)

        // 编辑 wiki 页
        if (this.editingDocId.length > 0) {
          Column({ space: 8 }) {
            Text(this.tx("编辑页面")).fontSize(15).fontWeight(FontWeight.Medium).fontColor(this.ink())
            TextInput({ text: this.docTitle, placeholder: this.tx("标题") })
              .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
              .backgroundColor(this.fieldBg())
              .width('100%').height(40).onChange((v) => { this.docTitle = v; })
            TextArea({ text: this.docBody, placeholder: this.tx("正文（Markdown）") })
              .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
              .backgroundColor(this.fieldBg())
              .width('100%').height(140).onChange((v) => { this.docBody = v; })
            Row({ space: 8 }) {
              Button(this.tx("保存")).layoutWeight(1).height(42).onClick(() => this.saveDoc())
              Button(this.tx("取消")).layoutWeight(1).height(42)
                .backgroundColor('#E8E8EA').fontColor('#333')
                .onClick(() => {
                  this.editingDocId = '';
                  this.docTitle = '';
                  this.docBody = '';
                })
            }.width('100%')
          }
          .width('100%').padding(14)
          .backgroundColor(this.card()).borderRadius(12)
          .border({ width: 1, color: this.line() })
          .alignItems(HorizontalAlign.Start)
        }
      }
      .width('100%').padding(20).alignItems(HorizontalAlign.Start)
    }
    .layoutWeight(1).width('100%')
  }

  @Builder
  SkillsPane() {
    Column() {
      this.DesktopHintBanner()
      Scroll() {
        Column({ space: 12 }) {
          Text(this.tx("技能库")).fontSize(20).fontWeight(FontWeight.Bold).fontColor(this.ink())
          Text(this.isPC
            ? this.tx("技能目录与桌面版对齐；需本机文件/终端的技能请在桌面版执行。")
            : this.tx("平板可浏览技能目录；标「桌面版」的技能请在桌面版使用。"))
            .fontSize(13).fontColor(this.muted())
          Flex({ wrap: FlexWrap.Wrap }) {
            ForEach(SKILLS, (s: SkillCard) => {
              Column({ space: 6 }) {
                Row() {
                  Text(this.tx(s.name)).fontSize(15).fontWeight(FontWeight.Medium).fontColor(this.ink()).layoutWeight(1)
                  if (this.isTabletDevice && s.desktopOnly) {
                    Text(this.tx("桌面版")).fontSize(10).fontColor('#8A5A00')
                      .padding({ left: 6, right: 6, top: 2, bottom: 2 })
                      .backgroundColor('#FFE8B0').borderRadius(4)
                  }
                }.width('100%')
                Text(this.tx(s.desc)).fontSize(12).fontColor(this.muted())
              }
              .width('46%').padding(14).margin({ right: '2%', bottom: 12 })
              .backgroundColor(this.card()).borderRadius(12)
              .border({ width: 1, color: this.line() })
              .alignItems(HorizontalAlign.Start)
            }, (s: SkillCard) => s.name)
          }.width('100%')
        }
        .width('100%').padding(20).alignItems(HorizontalAlign.Start)
      }
      .layoutWeight(1).width('100%')
    }
    .layoutWeight(1).width('100%')
  }

  @Builder
  ModelsPane() {
    Column() {
      Column({ space: 6 }) {
        Text(this.tx("模型管理")).fontSize(20).fontWeight(FontWeight.Bold).fontColor(this.ink())
          .padding({ left: 20, top: 16, right: 20 }).width('100%')
        Text(`当前生效：${this.cfg.model} @ ${this.cfg.baseUrl}`)
          .fontSize(12).fontColor(this.muted())
          .padding({ left: 20, right: 20 }).width('100%')
        Row({ space: 8 }) {
          Button(this.tx("本地模型"))
            .layoutWeight(1).height(36)
            .backgroundColor(this.modelsTab === 'local' ? this.accent() : (this.dark ? '#2a2a30' : '#E8E8EA'))
            .fontColor(this.modelsTab === 'local' ? Color.White : this.ink())
            .onClick(() => { this.modelsTab = 'local'; this.localEndpoints = loadEndpoints(this.ctx); })
          Button(this.tx("API 模型"))
            .layoutWeight(1).height(36)
            .backgroundColor(this.modelsTab === 'api' ? this.accent() : (this.dark ? '#2a2a30' : '#E8E8EA'))
            .fontColor(this.modelsTab === 'api' ? Color.White : this.ink())
            .onClick(() => { this.modelsTab = 'api'; })
        }
        .width('100%').padding({ left: 20, right: 20, top: 8, bottom: 8 })
      }
      .width('100%')

      if (this.modelsTab === 'local') {
        this.LocalModelsPane()
      } else {
        this.ApiModelsPane()
      }
    }
    .layoutWeight(1).width('100%')
  }

  @Builder
  LocalModelsPane() {
    Scroll() {
      Column({ space: 12 }) {
        Text(this.tx("Ollama / 本地端点（局域网模型集群）")).fontSize(15).fontWeight(FontWeight.Medium).fontColor(this.ink())
        Text(this.tx("填写本机或局域网地址（如 http://192.168.1.10:11434），添加后同步模型列表，再点选启用。"))
          .fontSize(12).fontColor(this.muted())

        TextInput({ text: this.epLabel, placeholder: this.tx("端点名称，如：主推理") })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .width('100%').height(40).onChange((v) => { this.epLabel = v; })
        TextInput({ text: this.epBase, placeholder: this.tx("http://IP:11434 或 http://IP:9000") })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .width('100%').height(40).onChange((v) => { this.epBase = v; })
        Row({ space: 8 }) {
          Button(this.epRole === 'primary' ? this.tx("● 主推理") : this.tx("主推理"))
            .layoutWeight(1).height(36)
            .backgroundColor(this.epRole === 'primary' ? this.accent() : '#E8E8EA')
            .fontColor(this.epRole === 'primary' ? Color.White : '#333')
            .onClick(() => { this.epRole = 'primary'; })
          Button(this.epRole === 'backup' ? this.tx("● 备用/快速") : this.tx("备用/快速"))
            .layoutWeight(1).height(36)
            .backgroundColor(this.epRole === 'backup' ? this.accent() : '#E8E8EA')
            .fontColor(this.epRole === 'backup' ? Color.White : '#333')
            .onClick(() => { this.epRole = 'backup'; })
        }.width('100%')
        Button(this.localBusy ? this.tx("处理中…") : this.tx("+ 添加端点并同步"))
          .width('100%').height(44)
          .enabled(!this.localBusy)
          .onClick(() => this.addLocalEndpoint())

        Text(this.tx("部署新模型")).fontSize(15).fontWeight(FontWeight.Medium).fontColor(this.ink()).margin({ top: 8 })
        Text(this.tx("兼容 Ollama 运行时，输入模型标识即可拉取到已添加的端点。"))
          .fontSize(12).fontColor(this.muted())
        TextInput({ text: this.pullName, placeholder: this.tx("如：qwen2.5-coder:7b 或 qwen3:14b") })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .width('100%').height(40).onChange((v) => { this.pullName = v; })
        Button(this.localBusy ? this.tx("部署中…") : this.tx("⬇ 部署到端点"))
          .width('100%').height(42)
          .enabled(!this.localBusy)
          .onClick(() => this.pullToEndpoint())

        Text(this.tx("已添加端点")).fontSize(15).fontWeight(FontWeight.Medium).fontColor(this.ink()).margin({ top: 8 })
        if (this.localEndpoints.length === 0) {
          Text(this.tx("尚未添加本地端点。可填 127.0.0.1 或局域网 IP。"))
            .fontSize(12).fontColor(this.muted())
        }
        ForEach(this.localEndpoints, (ep: LocalEndpoint) => {
          Column({ space: 8 }) {
            Row() {
              Column({ space: 2 }) {
                Text(`${ep.label} · ${ep.role === 'primary' ? this.tx("主推理") : this.tx("备用")}`)
                  .fontSize(14).fontWeight(FontWeight.Medium).fontColor(this.ink())
                Text(`${ep.baseUrl} · ${ep.kind || this.tx("未探测")}`)
                  .fontSize(11).fontColor(this.muted())
              }.layoutWeight(1).alignItems(HorizontalAlign.Start)
              Button(this.tx("同步")).height(30).fontSize(12)
                .enabled(!this.localBusy)
                .onClick(() => this.syncLocalEndpoint(ep.id))
              Button(this.tx("删")).height(30).fontSize(12).margin({ left: 6 })
                .backgroundColor('#FF3B30')
                .onClick(() => this.removeLocalEndpoint(ep.id))
            }.width('100%')
            if (ep.models.length === 0) {
              Text(this.tx("暂无模型，点「同步」拉取列表")).fontSize(12).fontColor(this.muted())
            } else {
              Text(`模型（${ep.models.length}）· 点选启用`).fontSize(12).fontColor(this.muted())
              ForEach(ep.models, (mid: string) => {
                Row() {
                  Text(mid).fontSize(13).fontColor(this.ink()).layoutWeight(1)
                  if (mid === this.cfg.model && toChatBase(ep.baseUrl) === this.cfg.baseUrl) {
                    Text(this.tx("使用中")).fontSize(11).fontColor(this.accent())
                  } else {
                    Text(this.tx("启用")).fontSize(11).fontColor(this.accent())
                  }
                }
                .width('100%').padding(10)
                .backgroundColor(mid === this.cfg.model && toChatBase(ep.baseUrl) === this.cfg.baseUrl
                  ? (this.dark ? '#1e2a3a' : '#E8F2FF') : (this.dark ? '#1a1a1f' : '#F7F7F8'))
                .borderRadius(8)
                .onClick(() => this.useLocalModel(ep, mid))
              }, (mid: string) => `${ep.id}_${mid}`)
            }
          }
          .width('100%').padding(12)
          .backgroundColor(this.card()).borderRadius(12)
          .border({ width: 1, color: this.line() })
          .alignItems(HorizontalAlign.Start)
        }, (ep: LocalEndpoint) => ep.id)

        Button(this.tx("快捷：添加本机 Ollama (127.0.0.1:11434)")).width('100%').height(40)
          .backgroundColor('#E8E8EA').fontColor('#333')
          .onClick(() => {
            this.epLabel = this.tx("本机 Ollama");
            this.epBase = 'http://127.0.0.1:11434';
            this.epRole = 'primary';
            this.addLocalEndpoint();
          })
      }
      .width('100%').padding(20).alignItems(HorizontalAlign.Start)
    }
    .layoutWeight(1).width('100%')
  }

  @Builder
  ApiModelsPane() {
    Scroll() {
      Column({ space: 12 }) {
        Text(this.tx("接入 API 模型")).fontSize(15).fontWeight(FontWeight.Medium).fontColor(this.ink())
        Text(this.tx("与桌面版相同：先选提供方填入 Base URL；填 Key 后点「自动识别」列出模型再选择添加。"))
          .fontSize(12).fontColor(this.muted())

        Text(this.tx("提供方 / Base")).fontSize(13).fontColor(this.muted())
        Button(this.presetSelected.length > 0 ? this.tx(this.presetSelected) : this.tx("选择提供方…"))
          .width('100%').height(40)
          .backgroundColor(this.dark ? '#2a2a30' : '#EEF3FF')
          .fontColor(this.accent())
          .onClick(() => { this.showPresetList = !this.showPresetList; })

        if (this.showPresetList) {
          Column() {
            ForEach(API_BASE_PRESETS, (p: ApiPreset) => {
              Column({ space: 2 }) {
                Text(p.name).fontSize(14).fontColor(this.ink()).fontWeight(FontWeight.Medium)
                Text(p.baseUrl).fontSize(11).fontColor(this.muted())
              }
              .width('100%').padding(10).alignItems(HorizontalAlign.Start)
              .backgroundColor(this.presetSelected === p.name ? (this.dark ? '#1e2a3a' : '#E8F2FF') : Color.Transparent)
              .onClick(() => this.applyPreset(p))
            }, (p: ApiPreset) => p.name)
            Text(this.tx("自定义填写"))
              .fontSize(14).fontColor(this.accent())
              .width('100%').padding(12)
              .onClick(() => this.applyCustomPreset())
          }
          .width('100%')
          .backgroundColor(this.card())
          .borderRadius(10)
          .border({ width: 1, color: this.line() })
        }

        Text(this.tx("全部 Base 快捷选择")).fontSize(13).fontColor(this.muted())
        Flex({ wrap: FlexWrap.Wrap }) {
          ForEach(API_BASE_PRESETS, (p: ApiPreset) => {
            Text(p.name)
              .fontSize(11)
              .fontColor(this.presetSelected === p.name ? Color.White : this.ink())
              .padding({ left: 10, right: 10, top: 6, bottom: 6 })
              .margin({ right: 6, bottom: 6 })
              .borderRadius(14)
              .backgroundColor(this.presetSelected === p.name ? this.accent() : (this.dark ? '#2a2a30' : '#EEE'))
              .onClick(() => this.applyPreset(p))
          }, (p: ApiPreset) => `chip_${p.name}`)
        }.width('100%')

        TextInput({ text: this.newModelUrl, placeholder: this.tx("Base URL：从上方选择，或手动填写") })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .width('100%').height(40)
          .onChange((v) => {
            this.newModelUrl = v;
            this.presetSelected = '自定义';
            this.newModelProvider = guessProvider(v);
          })
        TextInput({ text: this.newModelKey, placeholder: this.tx("API Key（识别与调用时使用）") })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .width('100%').height(40).type(InputType.Password)
          .onChange((v) => { this.newModelKey = v; })
        TextInput({ text: this.newModelProvider, placeholder: this.tx("提供方（识别后自动填）") })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .width('100%').height(40)
          .onChange((v) => { this.newModelProvider = v; })

        Text(this.tx("模型")).fontSize(13).fontColor(this.muted())
        if (this.detectedModels.length > 0) {
          Text(`请选择识别到的模型（${this.detectKind} · ${this.detectedModels.length}）`)
            .fontSize(12).fontColor(this.muted())
          Scroll() {
            Column() {
              ForEach(this.detectedModels, (mid: string) => {
                Row() {
                  Text(mid).fontSize(14).fontColor(this.ink()).layoutWeight(1)
                  if (mid === this.newModelId) {
                    Text('✓').fontSize(14).fontColor(this.accent())
                  }
                }
                .width('100%').padding(12)
                .backgroundColor(mid === this.newModelId ? (this.dark ? '#1e2a3a' : '#E8F2FF') : Color.Transparent)
                .onClick(() => this.pickDetectedForForm(mid))
              }, (mid: string, idx: number) => `${idx}_${mid}`)
            }.width('100%')
          }
          .width('100%').height(220)
          .backgroundColor(this.card())
          .borderRadius(10)
          .border({ width: 1, color: this.line() })
        }
        TextInput({ text: this.newModelId, placeholder: this.tx("模型名（识别后点选，或手动填写）") })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .width('100%').height(40)
          .onChange((v) => { this.newModelId = v; })

        if (this.detectHint.length > 0) {
          Text(this.detectHint).fontSize(12).fontColor(this.muted())
        }

        Row({ space: 8 }) {
          Button(this.detecting ? this.tx("识别中…") : this.tx("⟳ 自动识别"))
            .layoutWeight(1).height(44)
            .enabled(!this.detecting)
            .onClick(() => this.runDetect(true))
          Button(this.tx("＋ 添加模型"))
            .layoutWeight(1).height(44)
            .onClick(() => this.addApiModel())
        }.width('100%')

        if (this.detectedModels.length > 1) {
          Button(this.tx("将识别到的全部加入列表")).width('100%').height(40)
            .backgroundColor('#E8E8EA').fontColor('#333')
            .onClick(() => this.addDetectedAsModels())
        }

        Text(this.tx("已保存 API 模型")).fontSize(15).fontWeight(FontWeight.Medium).fontColor(this.ink()).margin({ top: 8 })
        if (this.apiModels.length === 0) {
          Text(this.tx("尚未接入任何 API 模型。密钥仅保存在本机。"))
            .fontSize(12).fontColor(this.muted())
        }
        ForEach(this.apiModels, (m: ApiModelItem) => {
          Row() {
            Column({ space: 4 }) {
              Text(m.name).fontSize(14).fontWeight(FontWeight.Medium).fontColor(this.ink())
              Text(`${m.model} · ${m.baseUrl}`).fontSize(11).fontColor(this.muted())
            }.layoutWeight(1).alignItems(HorizontalAlign.Start)
            Button(m.model === this.cfg.model && m.baseUrl === this.cfg.baseUrl ? this.tx("使用中") : this.tx("启用"))
              .height(32).fontSize(12)
              .onClick(() => this.applyModel(m))
            Button(this.tx("删")).height(32).fontSize(12).margin({ left: 6 })
              .backgroundColor('#FF3B30').onClick(() => this.removeApiModel(m.id))
          }
          .width('100%').padding(12).backgroundColor(this.card()).borderRadius(10)
        }, (m: ApiModelItem) => m.id)
      }
      .width('100%').padding(20).alignItems(HorizontalAlign.Start)
    }
    .layoutWeight(1).width('100%')
  }

  @Builder
  AutoPane() {
    Column({ space: 12 }) {
      this.DesktopHintBanner()
      Text(this.tx("自动化")).fontSize(20).fontWeight(FontWeight.Bold).fontColor(this.ink())
        .padding({ left: 20, top: 8 }).width('100%')
      Text(this.isPC
        ? this.tx("可规划任务清单；定时调度与工作流执行请在桌面版完成。")
        : this.tx("平板可记计划；定时任务与工作流请在桌面版使用。"))
        .fontSize(12).fontColor(this.muted()).padding({ left: 20, right: 20 })
      Row({ space: 8 }) {
        TextInput({ text: this.autoInput, placeholder: this.tx("例如：每天 9:00 汇总待办") })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .layoutWeight(1).height(40).onChange((v) => { this.autoInput = v; })
        Button(this.tx("添加")).height(40).onClick(() => this.addAutoJob())
      }.width('100%').padding({ left: 20, right: 20 })
      List({ space: 8 }) {
        ForEach(this.autoJobs, (j: string, i: number) => {
          ListItem() {
            Text(j).fontSize(14).fontColor(this.ink()).padding(14)
              .width('100%').backgroundColor(this.card()).borderRadius(10)
          }
        }, (j: string, i: number) => `${i}_${j}`)
      }.layoutWeight(1).padding({ left: 20, right: 20, bottom: 16 })
    }
    .layoutWeight(1).width('100%')
  }

  @Builder
  LogsPane() {
    Column({ space: 10 }) {
      Row() {
        Text(this.tx("活动日志")).fontSize(20).fontWeight(FontWeight.Bold).fontColor(this.ink()).layoutWeight(1)
        Button(this.tx("清空")).height(32).fontSize(12).backgroundColor('#E8E8EA').fontColor('#333')
          .onClick(() => {
            clearActivity(this.ctx);
            this.activity = [];
          })
      }.width('100%').padding({ left: 20, right: 20, top: 16 })
      List({ space: 6 }) {
        ForEach(this.activity, (a: ActivityItem) => {
          ListItem() {
            Column({ space: 2 }) {
              Text(`[${a.kind}] ${a.text}`).fontSize(13).fontColor(this.ink())
              Text(new Date(a.at).toLocaleString()).fontSize(11).fontColor(this.muted())
            }
            .width('100%').padding(12).backgroundColor(this.card()).borderRadius(8)
            .alignItems(HorizontalAlign.Start)
          }
        }, (a: ActivityItem) => a.id)
      }.layoutWeight(1).padding({ left: 20, right: 20, bottom: 16 })
    }
    .layoutWeight(1).width('100%')
  }

  @Builder
  VersionsPane() {
    Scroll() {
      Column({ space: 10 }) {
        Text(this.tx("版本说明")).fontSize(20).fontWeight(FontWeight.Bold).fontColor(this.ink())
        Text(`当前版本 v${APP_VERSION}`).fontSize(14).fontColor(this.muted())
        Text(this.tx("· 一套 HAP 通用鸿蒙平板与鸿蒙电脑（2in1），按窗口宽度自适应")).fontSize(13).fontColor(this.ink())
        Text(this.tx("· 平板：对话/模型/记忆/知识库/浏览器可直接用；导演台等标「桌面」功能提示改用桌面版")).fontSize(13).fontColor(this.ink())
        Text(this.tx("· 鸿蒙电脑：同一功能面完整展示，宿主级工具仍建议配合桌面版")).fontSize(13).fontColor(this.ink())
        Text(this.tx("· 流式对话、多会话、深浅主题、智能体免责声明")).fontSize(13).fontColor(this.ink())
        Text(this.tx("· 0.77.0：系统颜色可自动跟随；语言支持简体、繁体、英文、日语、法语、西班牙语、韩语")).fontSize(13).fontColor(this.ink())
        Text(this.tx("· 0.77.0：深色模式下输入文字可读，适配挖孔安全区，并修复启动时立即退回桌面")).fontSize(13).fontColor(this.ink())
        Text(this.tx("· 合成生成内容前须华为账号实名核验（绑定手机号）")).fontSize(13).fontColor(this.ink())
      }.width('100%').padding(20).alignItems(HorizontalAlign.Start)
    }.layoutWeight(1).width('100%')
  }

  @Builder
  PrivacyPane() {
    Scroll() {
      Column({ space: 10 }) {
        Text(this.tx("隐私条款")).fontSize(20).fontWeight(FontWeight.Bold).fontColor(this.ink())
        Text(this.tx("CodeCoreAgent 鸿蒙版在本机处理对话与配置。API Key、聊天记录、记忆与知识文档默认仅保存在设备 Preferences，不会上传到 CodeCore 自有服务器。"))
          .fontSize(14).fontColor(this.ink())
        Text(this.tx("当你配置第三方 LLM 端点时，消息内容会按该服务商的隐私政策传输。请自行确认服务商条款。"))
          .fontSize(14).fontColor(this.ink())
        Text(this.tx("使用合成生成内容（对话等）前，须通过华为账号完成真实身份核验。核验依据账号绑定的移动电话号码；登录状态仅保存在本机。"))
          .fontSize(14).fontColor(this.ink())
        Text(this.tx("开发调试安装包仅用于授权设备；发布版需通过华为应用市场签名分发。"))
          .fontSize(14).fontColor(this.ink())
      }.width('100%').padding(20).alignItems(HorizontalAlign.Start)
    }.layoutWeight(1).width('100%')
  }

  @Builder
  SettingsPane() {
    Scroll() {
      Column({ space: 14 }) {
        Text(this.tx("偏好设置")).fontSize(20).fontWeight(FontWeight.Bold).fontColor(this.ink())

        Text(this.tx("实名核验")).fontSize(14).fontWeight(FontWeight.Medium).fontColor(this.ink())
        Text(this.tx("合成生成内容服务须先完成真实身份核验（华为账号绑定手机号）。"))
          .fontSize(12).fontColor(this.muted())
        Text(identityStatusText(this.identity)).fontSize(13).fontColor(this.ink())
        if (this.identity.verified) {
          Button(this.tx("退出账号核验")).width('100%').height(40)
            .backgroundColor(this.fieldBg()).fontColor(this.ink())
            .onClick(() => this.clearIdentityLocal())
        } else {
          Button(this.authBusy ? this.tx("核验中…") : this.tx("华为账号登录核验"))
            .width('100%').height(44)
            .enabled(!this.authBusy)
            .onClick(() => this.startIdentityVerify())
        }

        Text(this.tx("系统颜色")).fontSize(14).fontWeight(FontWeight.Medium).fontColor(this.ink())
        Text(this.tx("自动跟随设备的深色或浅色。"))
          .fontSize(12).fontColor(this.muted())
        Flex({ wrap: FlexWrap.Wrap }) {
          Button(this.tx("自动")).backgroundColor(this.cfg.theme === 'auto' ? this.accent() : this.fieldBg())
            .fontColor(this.cfg.theme === 'auto' ? Color.White : this.ink())
            .margin({ right: 8, bottom: 8 })
            .onClick(() => this.setTheme('auto'))
          Button(this.tx("浅色")).backgroundColor(this.cfg.theme === 'light' ? this.accent() : this.fieldBg())
            .fontColor(this.cfg.theme === 'light' ? Color.White : this.ink())
            .margin({ right: 8, bottom: 8 })
            .onClick(() => this.setTheme('light'))
          Button(this.tx("深色")).backgroundColor(this.cfg.theme === 'dark' ? this.accent() : this.fieldBg())
            .fontColor(this.cfg.theme === 'dark' ? Color.White : this.ink())
            .margin({ right: 8, bottom: 8 })
            .onClick(() => this.setTheme('dark'))
        }.width('100%')

        Text(this.tx("语言")).fontSize(14).fontWeight(FontWeight.Medium).fontColor(this.ink())
        Text(this.tx("自动会识别系统语言。界面和对话都使用该语言。"))
          .fontSize(12).fontColor(this.muted())
        Flex({ wrap: FlexWrap.Wrap }) {
          Button(this.tx("自动")).backgroundColor(this.cfg.language === 'auto' ? this.accent() : this.fieldBg())
            .fontColor(this.cfg.language === 'auto' ? Color.White : this.ink())
            .margin({ right: 8, bottom: 8 })
            .onClick(() => this.setLanguage('auto'))
          Button('简体中文').backgroundColor(this.cfg.language === 'zh-Hans' ? this.accent() : this.fieldBg())
            .fontColor(this.cfg.language === 'zh-Hans' ? Color.White : this.ink())
            .margin({ right: 8, bottom: 8 })
            .onClick(() => this.setLanguage('zh-Hans'))
          Button('繁體中文').backgroundColor(this.cfg.language === 'zh-Hant' ? this.accent() : this.fieldBg())
            .fontColor(this.cfg.language === 'zh-Hant' ? Color.White : this.ink())
            .margin({ right: 8, bottom: 8 })
            .onClick(() => this.setLanguage('zh-Hant'))
          Button('English').backgroundColor(this.cfg.language === 'en' ? this.accent() : this.fieldBg())
            .fontColor(this.cfg.language === 'en' ? Color.White : this.ink())
            .margin({ right: 8, bottom: 8 })
            .onClick(() => this.setLanguage('en'))
          Button('日本語').backgroundColor(this.cfg.language === 'ja' ? this.accent() : this.fieldBg())
            .fontColor(this.cfg.language === 'ja' ? Color.White : this.ink())
            .margin({ right: 8, bottom: 8 })
            .onClick(() => this.setLanguage('ja'))
          Button('Français').backgroundColor(this.cfg.language === 'fr' ? this.accent() : this.fieldBg())
            .fontColor(this.cfg.language === 'fr' ? Color.White : this.ink())
            .margin({ right: 8, bottom: 8 })
            .onClick(() => this.setLanguage('fr'))
          Button('Español').backgroundColor(this.cfg.language === 'es' ? this.accent() : this.fieldBg())
            .fontColor(this.cfg.language === 'es' ? Color.White : this.ink())
            .margin({ right: 8, bottom: 8 })
            .onClick(() => this.setLanguage('es'))
          Button('한국어').backgroundColor(this.cfg.language === 'ko' ? this.accent() : this.fieldBg())
            .fontColor(this.cfg.language === 'ko' ? Color.White : this.ink())
            .margin({ right: 8, bottom: 8 })
            .onClick(() => this.setLanguage('ko'))
        }.width('100%')

        Text('API Base URL').fontSize(14).fontWeight(FontWeight.Medium).fontColor(this.ink())
        TextInput({ text: this.cfg.baseUrl, placeholder: 'https://api.openai.com/v1' })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .width('100%').height(42).onChange((v) => { this.cfg.baseUrl = v; })

        Text('API Key').fontSize(14).fontWeight(FontWeight.Medium).fontColor(this.ink())
        TextInput({ text: this.cfg.apiKey, placeholder: this.tx("sk-…（Ollama 可留空）") })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .width('100%').height(42).type(InputType.Password)
          .onChange((v) => { this.cfg.apiKey = v; })

        Text(this.tx("模型名")).fontSize(14).fontWeight(FontWeight.Medium).fontColor(this.ink())
        TextInput({ text: this.cfg.model, placeholder: 'gpt-4o' })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .width('100%').height(42).onChange((v) => { this.cfg.model = v; })

        Text(`${this.tx("温度")} ${this.cfg.temperature.toFixed(2)}`).fontSize(14).fontWeight(FontWeight.Medium).fontColor(this.ink())
        Slider({ value: this.cfg.temperature, min: 0, max: 2, step: 0.05 })
          .width('100%').onChange((v) => { this.cfg.temperature = v; })

        Text(this.tx("系统提示词")).fontSize(14).fontWeight(FontWeight.Medium).fontColor(this.ink())
        TextArea({ text: this.cfg.systemPrompt, placeholder: this.tx("系统人格与约束…") })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .width('100%').height(100).onChange((v) => { this.cfg.systemPrompt = v; })

        Text(this.tx("称呼")).fontSize(14).fontWeight(FontWeight.Medium).fontColor(this.ink())
        TextInput({ text: this.cfg.nickname, placeholder: this.tx("希望 AI 怎么称呼你") })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .width('100%').height(42).onChange((v) => { this.cfg.nickname = v; })

        Text(this.tx("陪伴角色名")).fontSize(14).fontWeight(FontWeight.Medium).fontColor(this.ink())
        TextInput({ text: this.cfg.companionName, placeholder: this.tx("助手") })
          .fontColor(this.ink()).placeholderColor(this.muted()).caretColor(this.accent())
          .backgroundColor(this.fieldBg())
          .width('100%').height(42).onChange((v) => { this.cfg.companionName = v; })
        Row() {
          Text(this.tx("开启陪伴型人格")).fontSize(14).fontColor(this.ink()).layoutWeight(1)
          Toggle({ type: ToggleType.Switch, isOn: this.cfg.companionOn })
            .onChange((v) => { this.cfg.companionOn = v; })
        }.width('100%')

        Text(`Agent 执行上限：${this.cfg.maxIterations}`).fontSize(14).fontWeight(FontWeight.Medium).fontColor(this.ink())
        Slider({ value: this.cfg.maxIterations, min: 10, max: 300, step: 10 })
          .width('100%').onChange((v) => { this.cfg.maxIterations = Math.floor(v); })

        Button(this.tx("保存偏好")).width('100%').height(44).margin({ top: 8 })
          .onClick(() => this.saveSettings())

        Text(this.tx("官网地址"))
          .fontSize(16).fontColor(this.accent())
          .decoration({ type: TextDecorationType.Underline, color: this.accent() })
          .padding({ top: 8, bottom: 4 })
          .onClick(() => this.openOfficialSite())
        Text('https://lunarcoreagent.com/CodeCoreAgent/index.html')
          .fontSize(12).fontColor(this.muted())

        Button(this.tx("问题反馈")).width('100%').height(44)
          .onClick(() => this.openFeedbackMail())
      }
      .width('100%').padding(20).alignItems(HorizontalAlign.Start)
    }
    .layoutWeight(1).width('100%')
  }
}
