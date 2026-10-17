# astrbot_plugin_webclass_sync

山形大学 WebClass 自动化巡检与归档插件，基于 [AstrBot](https://github.com/Soulter/AstrBot) 开发。

## 功能特性

- **课程全覆盖巡检**：自动巡检山形大学 WebClass 平台 各门专业课程及通用信息栏目。
- **课件与通知归档**：将最新课件材料自动归档并同步至 Google Drive 网盘对应目录。
- **中文日报生成**：自动汇总提取近期作业 Deadline、测验与紧急通知，格式化输出排版工整的中文简报。
- **定时调度与推送**：支持每日固定时间静默调度并主动推送至指定 QQ 私聊或群聊会话。
- **交互指令支持**：支持随时随地通过聊天指令手动触发巡检与状态查询。

## 交互指令

| 指令 | 说明 |
| :--- | :--- |
| `/webclass 巡检` | 唤起无头浏览器执行全量巡检并同步至 Google Drive |
| `/webclass 预览` | 执行只读受控测试 (Dry-Run)，不写入云端 |
| `/webclass 状态` | 查看上次巡检时间、已归档材料数及近期首要日程 |
| `/webclass 帮助` | 显示指令说明菜单 |

## 配置项

- `enable`：是否启用插件。
- `enable_scheduled_inspection`：是否开启每日定时自动巡检推送。
- `schedule_time_jst`：每日定时巡检时间（JST 日本标准时间，默认 `19:00`）。
- `notify_session`：巡检报告推送的目标会话 Session ID。

## License

MIT
