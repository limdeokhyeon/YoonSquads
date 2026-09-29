"""Instagram은 이미지를 URL로만 가져가므로, 다운로드한 사진을 임시로 공개 서빙한다.

텔레그램 파일 URL에는 봇 토큰이 들어 있어 Meta에 넘기면 안 되기 때문에 직접 호스팅한다.
"""
from pathlib import Path

from aiohttp import web


async def start_media_server(media_dir: Path, port: int) -> web.AppRunner:
    media_dir.mkdir(parents=True, exist_ok=True)
    app = web.Application()
    app.router.add_static("/media/", media_dir, show_index=False)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    return runner
