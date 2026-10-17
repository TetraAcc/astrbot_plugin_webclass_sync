import asyncio
import json
import os
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.message.components import Plain
from astrbot.core.message.message_event_result import MessageChain

JST = timezone(timedelta(hours=9))
BASE_DIR = Path("/home/deck/.local/share/webclass-sync")
VENV_PYTHON = BASE_DIR / "venv" / "bin" / "python"
MAIN_RUNNER = BASE_DIR / "main_runner.py"
STATE_FILE = BASE_DIR / "state" / "webclass-sync-state.json"
PREVIEW_FILE = BASE_DIR / "state" / "WebClass_最新巡检简报_本地预览.md"


class WebClassSyncPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._scheduled_task = None
        self._running_lock = asyncio.Lock()

    async def initialize(self):
        logger.info("[WebClassSync] Plugin initialized.")
        if self.config.get("enable_scheduled_inspection", False):
            self._scheduled_task = asyncio.create_task(self._schedule_loop())
            logger.info("[WebClassSync] Scheduled inspection loop started.")

    async def terminate(self):
        if self._scheduled_task and not self._scheduled_task.done():
            self._scheduled_task.cancel()
        logger.info("[WebClassSync] Plugin terminated.")

    async def _run_script(self, live: bool = False) -> str:
        async with self._running_lock:
            mode_arg = "--live" if live else "--dry-run"
            cmd = [str(VENV_PYTHON), str(MAIN_RUNNER), mode_arg]
            
            env = os.environ.copy()
            env["LANG"] = "en_US.UTF-8"
            env["LC_ALL"] = "en_US.UTF-8"

            def _execute():
                return subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=120
                )

            res = await asyncio.to_thread(_execute)
            if res.returncode != 0:
                logger.error(f"[WebClassSync] Execution failed: {res.stderr}")
                return f"❌ 巡检执行遇到错误 (Code: {res.returncode}):\n{res.stderr[:300]}"

            # 优先从最新生成的报告中提取内容
            if PREVIEW_FILE.exists():
                with open(PREVIEW_FILE, "r", encoding="utf-8") as f:
                    return f.read().strip()
            return "✅ 巡检执行完成，但未找到生成的简报文件。"

    @filter.command("webclass")
    async def handle_webclass(self, event: AstrMessageEvent):
        """WebClass 交互指令：
        /webclass 巡检  - 执行全量巡检并同步至 Google Drive
        /webclass 预览  - 只读受控试跑 (Dry-Run)，不写云端
        /webclass 状态  - 查看上次巡检时间与近期重点事项
        /webclass 帮助  - 显示帮助菜单
        """
        msg = event.message_str.strip()
        parts = msg.split()
        subcmd = parts[1] if len(parts) > 1 else ""

        if subcmd in ["", "巡检", "sync", "run"]:
            yield event.plain_result("⏳ 正在唤起无头浏览器执行 WebClass 全量巡检并同步，请稍候约 25 秒...")
            report = await self._run_script(live=True)
            yield event.plain_result(report)

        elif subcmd in ["预览", "dry-run", "dry", "check"]:
            yield event.plain_result("🔍 正在执行 WebClass 只读受控试跑 (Dry-Run)，不写入云端...")
            report = await self._run_script(live=False)
            yield event.plain_result(report)

        elif subcmd in ["状态", "status", "info"]:
            if not STATE_FILE.exists():
                yield event.plain_result("⚠️ 尚未检测到本地巡检状态记录文件。")
                return

            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)

            last_checked = state.get("last_checked_at", "未知")
            materials_count = len(state.get("materials", []))
            
            status_text = (
                f"📊 **WebClass 自动化巡检就绪状态**\n"
                f"- 上次巡检时间：{last_checked}\n"
                f"- 已归档核验材料：{materials_count} 份\n"
                f"- 自动调度状态：{'已开启' if self.config.get('enable_scheduled_inspection') else '已关闭'}\n"
                f"💡 详细任务与最新截止事项请查看最新巡检简报。"
            )
            yield event.plain_result(status_text)

        else:
            yield event.plain_result(
                "💡 **WebClass 指令说明**：\n"
                "- `/webclass 巡检`：执行完整巡检并同步至 Google Drive\n"
                "- `/webclass 预览`：只读受控测试 (Dry-Run)\n"
                "- `/webclass 状态`：查看当前就绪状态与近期首要日程"
            )

    async def _schedule_loop(self):
        """按配置的每日时间定期执行（默认 19:00 JST）"""
        while True:
            try:
                # 获取配置时间
                sched_time = self.config.get("schedule_time_jst", "19:00")
                target_hour, target_min = [int(x) for x in sched_time.split(":")[:2]]

                now_jst = datetime.now(JST)
                target_dt = now_jst.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
                if now_jst >= target_dt:
                    target_dt += timedelta(days=1)

                wait_seconds = (target_dt - now_jst).total_seconds()
                logger.info(f"[WebClassSync] Next scheduled inspection at {target_dt} (in {wait_seconds:.0f}s).")
                await asyncio.sleep(wait_seconds)

                # 到了预定时间，执行巡检
                logger.info("[WebClassSync] Triggering scheduled inspection...")
                report = await self._run_script(live=True)

                # 推送简报给目标会话
                notify_session = self.config.get("notify_session")
                if notify_session:
                    chain = MessageChain([Plain(text=report)])
                    await self.context.send_message(notify_session, chain)
                    logger.info(f"[WebClassSync] Pushed scheduled report to {notify_session}.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[WebClassSync] Error in scheduler loop: {e}")
                await asyncio.sleep(60)
