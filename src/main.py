"""
诺艾尔 Telegram Bot — 主入口

用法：
    python -m src                          # 默认 both 模式
    python -m src --mode bot               # 仅 Telegram Bot
    python -m src --mode web               # 仅 FastAPI Web
    python -m src --mode both              # 同时运行 Bot + Web
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import logging.handlers
import os
import sys
from pathlib import Path

from .bot import NoelleBot
from .bot.handlers import set_chat_service
from .chat.service import ChatService
from .config import get_config
from .llm.client import LLMClient
from .db.session import init_db, close_db, create_tables, create_vector_index

# 日志目录（当前工作目录下 logs/）
LOG_DIR = Path(os.getcwd()) / "logs"
# 日志保留天数
LOG_RETENTION_DAYS = 30


def setup_logging(level: int = logging.INFO) -> None:
    """
    配置全局日志（类 Java logback 风格）

    输出目标：
    - Console: 所有级别（stdout）
    - logs/info.log: INFO 及以上（每日轮转，保留 LOG_RETENTION_DAYS 天）
    - logs/error.log: ERROR 及以上（每日轮转，保留 LOG_RETENTION_DAYS 天）
    """
    # 强制 stdout/stderr 使用 UTF-8（解决 Windows cp950 中文乱码）
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    # 统一格式
    fmt = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    # --- 根日志器 ---
    root = logging.getLogger()
    root.setLevel(level)
    # 清除已有 handlers（避免重复添加）
    root.handlers.clear()

    # 1. Console Handler（输出到终端）
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    if hasattr(console.stream, "reconfigure"):
        console.stream.reconfigure(encoding="utf-8", errors="replace")
    root.addHandler(console)

    # 2. 文件 Handlers（需要创建日志目录）
    LOG_DIR.mkdir(exist_ok=True)

    # info.log — INFO 及以上，每日轮转
    info_handler = logging.handlers.TimedRotatingFileHandler(
        filename=LOG_DIR / "info.log",
        when="midnight",
        backupCount=LOG_RETENTION_DAYS,
        encoding="utf-8",
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    root.addHandler(info_handler)

    # error.log — ERROR 及以上，每日轮转
    error_handler = logging.handlers.TimedRotatingFileHandler(
        filename=LOG_DIR / "error.log",
        when="midnight",
        backupCount=LOG_RETENTION_DAYS,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root.addHandler(error_handler)

    # 降低第三方库日志级别
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)

    logging.info("日志系统初始化完成: 目录=%s, 保留%d天", LOG_DIR, LOG_RETENTION_DAYS)


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="诺艾尔 Telegram Bot")
    parser.add_argument(
        "--mode",
        choices=["bot", "web", "both"],
        default="both",
        help="运行模式: bot=仅Telegram, web=仅FastAPI, both=同时运行",
    )
    return parser.parse_args()


def create_services(config=None) -> tuple[LLMClient, ChatService]:
    """
    创建核心服务实例。

    Returns:
        (llm_client, chat_service)
    """
    if config is None:
        config = get_config()

    llm_client = LLMClient(config.llm)
    chat_service = ChatService(llm_client, config)
    return llm_client, chat_service


async def run_bot(chat_service: ChatService, config=None) -> None:
    """运行 Telegram Bot"""
    if config is None:
        config = get_config()

    # 注入 ChatService 到 handlers
    set_chat_service(chat_service)

    bot = NoelleBot(config)
    try:
        await bot.start(skip_updates=True)
    finally:
        await bot.stop()


async def run_web(chat_service: ChatService, config=None) -> None:
    """运行 FastAPI Web 服务"""
    import uvicorn

    if config is None:
        config = get_config()

    from .web import create_app

    app = create_app(chat_service)
    port = getattr(config.memory, "port", 8000) if not hasattr(config, "web") else getattr(config.web, "port", 8000)
    host = "127.0.0.1"

    # 尝试从配置读取 web 段
    if hasattr(config, "web"):
        host = getattr(config.web, "host", host)
        port = getattr(config.web, "port", port)

    uvicorn_config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(uvicorn_config)
    logging.info("FastAPI 启动: http://%s:%d", host, port)
    await server.serve()


async def main() -> None:
    """主异步入口"""
    setup_logging()
    logger = logging.getLogger("main")

    args = parse_args()
    logger.info("运行模式: %s", args.mode)

    try:
        config = get_config()
    except FileNotFoundError as e:
        logger.error("配置加载失败: %s", e)
        sys.exit(1)

    # 初始化数据库
    init_db(config.memory.db.url)
    await create_tables()
    await create_vector_index("conversation_summary", "embedding", config.memory.embedding.dimension)
    logger.info("数据库初始化完成: %s", config.memory.db.database)

    # 创建核心服务（传入已初始化的 DB）
    llm_client, chat_service = create_services(config)
    logger.info("服务初始化完成: LLMClient + ChatService")

    try:
        if args.mode == "bot":
            await run_bot(chat_service, config)

        elif args.mode == "web":
            await run_web(chat_service, config)

        elif args.mode == "both":
            logger.info("同时启动 Bot + Web...")
            # 同时运行 Bot 和 Web
            bot_task = asyncio.create_task(run_bot(chat_service, config))
            web_task = asyncio.create_task(run_web(chat_service, config))

            # 等待任一任务完成（或出错）
            done, pending = await asyncio.wait(
                [bot_task, web_task],
                return_when=asyncio.FIRST_EXCEPTION,
            )

            # 取消未完成的任务
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # 检查是否有异常
            for task in done:
                if task.exception():
                    raise task.exception()

    except KeyboardInterrupt:
        logger.info("收到中断信号")
    finally:
        await llm_client.close()
        # 关闭数据库连接
        try:
            await close_db()
        except Exception:
            pass
        logger.info("服务已停止")


if __name__ == "__main__":
    asyncio.run(main())
