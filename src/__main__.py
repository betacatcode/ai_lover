"""允许以 python -m src 方式运行"""
from .main import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
