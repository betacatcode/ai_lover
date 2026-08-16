"""定时任务调度器 — 情绪自然衰减"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class EmotionDecayScheduler:
    """
    情绪衰减定时任务。

    使用 APScheduler 周期性衰减所有用户的情绪强度。

    用法：
        scheduler = EmotionDecayScheduler(emotion_system, interval_minutes=30)
        scheduler.start()
        ...
        scheduler.shutdown()
    """

    def __init__(
        self,
        emotion_system,  # EmotionSystem
        interval_minutes: int = 30,
    ) -> None:
        self._emotion = emotion_system
        self._interval = interval_minutes
        self._scheduler = AsyncIOScheduler()

    def start(self) -> None:
        """启动衰减调度器"""
        self._scheduler.add_job(
            self._decay_all_users,
            trigger=IntervalTrigger(minutes=self._interval),
            id="emotion_decay",
            name="情绪自然衰减",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("情绪衰减调度器已启动: 间隔 %d 分钟", self._interval)

    def shutdown(self) -> None:
        """停止调度器"""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("情绪衰减调度器已停止")

    async def _decay_all_users(self) -> None:
        """对所有已注册用户应用情绪衰减"""
        # 从存储中获取所有用户 ID
        user_ids = await self._get_all_user_ids()
        if not user_ids:
            return

        decayed_count = 0
        for user_id in user_ids:
            try:
                old_state = await self._emotion.get_state(user_id)
                if old_state.current_intensity > 0:
                    await self._emotion.apply_decay(user_id)
                    decayed_count += 1
            except Exception as e:
                logger.warning("情绪衰减失败: user_id=%d, %s", user_id, e)

        if decayed_count > 0:
            logger.info("情绪衰减完成: %d/%d 用户受影响", decayed_count, len(user_ids))

    async def _get_all_user_ids(self) -> list[int]:
        """获取所有有情绪记录的用户 ID"""
        repo = self._emotion._repo
        if hasattr(repo, "get_all_user_ids"):
            return await repo.get_all_user_ids()
        # 内存存储的 fallback
        if hasattr(repo, "_store"):
            return list(repo._store.keys())
        return []
