# 桌面桥 DesktopAPI 注解

`src/codeagent/desktop/api.py` 的 `DesktopAPI` 暴露给 JS：`pywebview.api.方法名(...)`。
前端在 `desktop/ui.py` 里直接调用。Python 用 `window._onEvent` 回推流式文本、工具、停止。

| 方法 | 行 | 功能说明 |
|---|---|---|
| `get_state` | 212 | 桌面启动时拉取总状态：版本、主题、个性化、当前项目、隐私是否已同意。 |
| `get_privacy_policy` | 238 | 返回隐私条款正文及本机是否已接受当前版本。 |
| `accept_privacy` | 246 | 记录用户同意当前隐私条款版本与时间。 |
| `get_changelog` | 272 | 返回 releases.py 渲染的完整更新历史。 |
| `get_nav_status` | 275 | 侧栏底部计数：本地在跑模型、API 在线、聚合池、当前激活标签。 |
| `get_overview` | 295 | 总览仪表盘：技能/记忆/运行/外部平台数量与最近运行。 |
| `save_config` | 319 | 保存桌面配置（模型、主题、思考强度、语音、自动同意）。 |
| `save_settings` | 347 | 保存主机级个性化（称呼、语言、额外说明、机器上下文）。 |
| `get_model_assets` | 360 | 模型管理三 tab 所需的端点、API、聚合池列表。 |
| `add_endpoint` | 471 | 登记本机或局域网推理端点。 |
| `remove_endpoint` | 491 | 从资产里去掉一条本地/局域网端点。 |
| `detect_models` | 501 | 对 Base URL 做双协议探测（/v1/models 与 /api/tags），带 key 识别需鉴权的服务。 |
| `add_api_model` | 509 | 登记云端或兼容 API 模型（密钥写 secrets.json）。 |
| `remove_api_model` | 525 | 删除一条 API 模型登记（不删远端账号）。 |
| `set_active_model` | 537 | 把当前对话模型设为自由路由或某个本地/API/聚合池。 |
| `test_model` | 552 | 走与真实对话同一条 Provider 链路做连通性测试，记录延迟。 |
| `get_models_page` | 578 | 本地模型页：端点标签、是否在跑、量化/体积等元数据。 |
| `set_local_loaded` | 653 | 让 Ollama 把指定模型载入或卸出显存。 |
| `delete_local_model` | 665 | 从本机 Ollama 删除一个模型权重。 |
| `pull_model` | 681 | 后台线程向主推理端点拉取新模型。 |
| `save_mixture` | 704 | 保存聚合池策略与成员。 |
| `delete_mixture` | 727 | 删除一个聚合池。 |
| `toggle_mixture` | 738 | 启用或停用某个聚合池。 |
| `get_router` | 786 | 读取全部路由规则、权重与兜底设置。 |
| `add_route_rule` | 802 | 新增或更新自由路由关键词规则。 |
| `delete_route_rule` | 826 | 删除一条自由路由规则。 |
| `toggle_route_rule` | 834 | 打开或关闭某条路由规则。 |
| `move_route_rule` | 842 | 调整规则优先级（上移/下移）。 |
| `save_route_weights` | 857 | 保存成本/质量/本地三权重滑杆。 |
| `route_sandbox` | 864 | 不真正调用模型，只预览这条文本会分到哪。 |
| `get_permissions` | 876 | 读取五能力矩阵当前等级与最近审计。 |
| `set_permission_level` | 887 | 改某一能力的自主/确认/只读/关闭等级。 |
| `resolve_confirm` | 897 | 前端确认弹窗的批准/拒绝回写。 |
| `get_versions` | 904 | 版本页数据：当前版 + 全部 Release 列表。 |
| `get_activity` | 922 | 读取自我学习活动流。 |
| `send_feedback` | 925 | 对话赞/踩写入活动流，供学习管线统计准确率。 |
| `get_learning` | 930 | 学习页：当日准确率、趋势、权重回流状态。 |
| `learn_now` | 946 | 立刻跑一轮学习管线，把反馈折算进路由权重。 |
| `get_workflows` | 960 | 列出自动化步骤链。 |
| `add_workflow` | 972 | 新建一条工作流（步骤串行）。 |
| `delete_workflow` | 991 | 删除一条工作流定义。 |
| `run_workflow` | 1000 | 立刻执行该工作流。 |
| `pause_workflow` | 1007 | 暂停正在跑的工作流。 |
| `set_workflow_continuous` | 1010 | 开关「完成后自动衔下一轮」。 |
| `get_cron` | 1038 | 列出定时任务与下次触发提示。 |
| `add_cron_job` | 1048 | 新增五字段 cron 作业。 |
| `delete_cron_job` | 1064 | 删除用户 cron（系统夜间进化作业不可删）。 |
| `toggle_cron_job` | 1072 | 暂停或恢复一条 cron。 |
| `get_evolution` | 1093 | 进化页：补丁、技能草稿、五角色作业状态。 |
| `run_evolution_now` | 1122 | 立刻跑一轮进化作业。 |
| `set_patch_status` | 1125 | 批准/回滚/拒绝行为补丁。 |
| `approve_skill` | 1135 | 把技能草稿转正为可 cron 触发的工作流。 |
| `save_evolution_settings` | 1155 | 保存进化总开关与 cron 表达式。 |
| `pick_attachments` | 1351 | 系统文件框选文件，拷入项目 files/。 |
| `remove_attachment` | 1388 | 从当前待发送附件列表去掉一项。 |
| `copy_text` | 1393 | 系统剪贴板写入（pbcopy / clip / xclip）。 |
| `export_message` | 1410 | 分享：把消息导出为 Markdown 文件（系统保存对话框）。 |
| `get_projects` | 1434 | 项目列表与当前激活项。 |
| `create_project` | 1444 | 新建项目文件夹并写入索引。 |
| `get_project_records` | 1454 | 当前项目的对话 + 文件夹内文件。 |
| `open_project_folder` | 1466 | 用系统文件管理器打开项目目录。 |
| `switch_project` | 1486 | 切换激活项目，后续对话与工具根目录跟着走。 |
| `delete_project` | 1494 | 只从索引移除；磁盘文件夹与对话保留。 |
| `get_conversations` | 1516 | 当前项目的会话列表。 |
| `new_conversation` | 1523 | 开一个空会话并设为当前。 |
| `load_conversation` | 1528 | 把某条历史会话载入对话页。 |
| `send` | 1537 | 发送一条对话：选模型或自由路由，驱动 Agent；Gradio 时走文生视频。 |
| `stop` | 1583 | 设置取消标志，中断当前生成并推 stopped 事件。 |
| `reset` | 1783 | 清空当前对话上下文并开新会话。 |
| `lead` | 1856 | 指挥中心：把老板命令交给 Leader 拆任务、分派工人。 |
| `get_runs` | 1922 | 指挥中心历史运行存档。 |
| `get_memories` | 1939 | 长期记忆列表（可带搜索）。 |
| `add_memory` | 1953 | 手工新增一条长期记忆。 |
| `delete_memory` | 1963 | 删除一条长期记忆。 |
| `get_knowledge` | 1973 | 知识库状态、路径、页面列表。 |
| `save_knowledge_config` | 1994 | 保存知识库根路径等配置。 |
| `bootstrap_knowledge` | 2018 | 一键布置 Obsidian / LLM Wiki 目录结构。 |
| `search_knowledge` | 2039 | 在知识库里按关键词检索页面。 |
| `read_knowledge_page` | 2054 | 读取某一 wiki 页正文。 |
| `ingest_knowledge` | 2061 | 把一段文本写入 inbox。 |
| `open_knowledge_folder` | 2077 | 打开知识库文件夹。 |
| `get_video_ops` | 2101 | 视频运营页状态、选题、草稿、工具链是否就绪。 |
| `save_video_ops_config` | 2156 | 保存 Gradio/Comfy 地址与运营根目录。 |
| `bootstrap_video_ops` | 2250 | 一键创建选题/生成/剪辑/分析/发布目录。 |
| `save_video_ops_draft` | 2277 | 保存多平台发布草稿（仍须人工点发布）。 |
| `get_studio` | 2299 | 导演台：企划、分镜列表、成片路径。 |
| `save_studio` | 2337 | 保存导演台企划与分镜字段。 |
| `studio_import_script` | 2347 | 从「1. 画面」或 Markdown 标题导入分镜。 |
| `studio_add_shot` | 2362 | 手工加一镜。 |
| `studio_remove_shot` | 2386 | 删除一镜。 |
| `studio_generate_shot` | 2398 | 按该镜引擎调用 Comfy/WAN/Hailuo/Kimi 出片。 |
| `studio_assemble` | 2455 | ffmpeg 按分镜顺序合成成片。 |
| `studio_interrupt` | 2464 | 停止生成（含 Comfy /interrupt）。 |
| `open_video_ops_folder` | 2474 | 打开视频运营工作区。 |
| `get_skills` | 2498 | 技能库：融合 / 视频 / 本分页列表。 |
| `get_harnesses` | 2512 | 本机已发现的外部 Agent 平台。 |
| `get_logs` | 2520 | 读取最近运行日志行。 |

内部 `_push` / `_on_event` / `_provider_for_message` 不对外，但决定流式与自由路由是否改道。
