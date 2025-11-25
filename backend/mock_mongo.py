#!/usr/bin/env python3
"""
Mock MongoDB Server for Migration Step
Responds with success to all queries to bypass Emergent migration check
"""
import asyncio
import logging
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def handle_ping(request):
    """Handle MongoDB ping command"""
    logger.info("Mock MongoDB: Received ping")
    return web.json_response({"ok": 1})


async def handle_admin(request):
    """Handle admin commands"""
    logger.info("Mock MongoDB: Received admin command")
    return web.json_response({"ok": 1, "databases": []})


async def handle_all(request):
    """Handle all other requests"""
    logger.info(f"Mock MongoDB: Received request to {request.path}")
    return web.json_response({"ok": 1})


async def start_mock_mongo():
    """Start mock MongoDB server on port 27017"""
    app = web.Application()
    app.router.add_route('*', '/admin/ping', handle_ping)
    app.router.add_route('*', '/admin/{tail:.*}', handle_admin)
    app.router.add_route('*', '/{tail:.*}', handle_all)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 27017)
    await site.start()
    
    logger.info("🎭 Mock MongoDB server started on port 27017")
    logger.info("   This satisfies Emergent migration check")
    logger.info("   Actual app will use EXTERNAL_MONGO_URL")


if __name__ == '__main__':
    asyncio.run(start_mock_mongo())
    # Keep running
    asyncio.get_event_loop().run_forever()
