"""Bot 工厂 — 创建和配置 aiogram Bot / Dispatcher"""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from ..config import AppConfig
from .handlers import router
from .user_filter import UserFilterMiddleware

logger = logging.getLogger(__name__)


def create_bot(config: AppConfig) -> Bot:
    """
    创建 aiogram Bot 实例。

    配置项：
    - bot_token: Telegram Bot Token
    - proxy: SOCKS5 代理地址（可选，国内服务器需要）
    - parse_mode: 默认 Markdown 解析
    """
    if not config.telegram.bot_token or config.telegram.bot_token == "YOUR_TELEGRAM_BOT_TOKEN":
        raise ValueError(
            "Telegram Bot Token 未配置！\n"
            "请在 config/config.yaml 中设置 telegram.bot_token"
        )

    default_props = DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)

    bot = Bot(
        token=config.telegram.bot_token,
        default=default_props,
    )

    # 设置代理（如果需要）
    if config.telegram.proxy:
        # aiogram 3.x 通过 session 设置代理
        from aiogram.client.session.aiohttp import AiohttpSession
        session = AiohttpSession(proxy=config.telegram.proxy)
        bot.session = session
        logger.info("Telegram Bot 使用代理: %s", config.telegram.proxy)
    else:
        logger.info("Telegram Bot 直连（无代理）")

    return bot


def create_dispatcher(config: AppConfig) -> Dispatcher:
    """
    创建 Dispatcher 并注册中间件和处理器。

    中间件栈：
    1. UserFilterMiddleware — 仅允许配置的用户交互
    """
    dp = Dispatcher()

    # 注册用户过滤中间件
    if config.telegram.allowed_user_id:
        dp.message.middleware(
            UserFilterMiddleware(config.telegram.allowed_user_id)
        )
        logger.info("用户过滤已启用: allowed_user_id=%d", config.telegram.allowed_user_id)

    # 注册路由器
    dp.include_router(router)

    return dp


class NoelleBot:
    """
    Bot 封装类 — 组合 Bot + Dispatcher，提供启停接口。

    用法：
        config = load_config()
        bot = NoelleBot(config)
        await bot.start()  # 阻塞运行
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.bot = create_bot(config)
        self.dp = create_dispatcher(config)
        self._logger = logging.getLogger(self.__class__.__name__)

    async def start(self, skip_updates: bool = True) -> None:
        """
        启动 Bot（阻塞）。

        Args:
            skip_updates: 启动时跳过积压的消息（默认 True）
        """
        self._logger.info("=== 诺艾尔 Bot 启动中 ===")
        self._logger.info("配置: proxy=%s, allowed_user_id=%d, model=%s",
                         self.config.telegram.proxy,
                         self.config.telegram.allowed_user_id,
                         self.config.llm.model)

        # 验证 Bot 连接
        try:
            me = await self.bot.get_me()
            self._logger.info(
                "✓ Telegram 连接成功: @%s (id=%d, name=%s)",
                me.username,
                me.id,
                me.first_name,
            )
        except Exception as e:
            self._logger.error("✗ Telegram 连接失败: %s", e)
            raise

        self._logger.info("开始轮询消息... (Ctrl+C 停止)")
        await self.dp.start_polling(self.bot, skip_updates=skip_updates)

    async def stop(self) -> None:
        """停止 Bot 并清理资源"""
        self._logger.info("诺艾尔 Bot 停止中...")
        await self.bot.session.close()
        self._logger.info("诺elle Bot 已停止")
