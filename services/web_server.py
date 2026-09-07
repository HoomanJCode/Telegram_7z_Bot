import asyncio
from aiohttp import web
from core.file_manager import FileManager
from utils.logger import setup_logger

logger = setup_logger(__name__)

class WebServer:
    """HTTP server for serving hosted files."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080, settings=None):
        self.host = host
        self.port = port
        self.file_manager = FileManager()
        self._runner = None
        self._site = None
        # Cache lifetime for CDN-friendly responses; files are deleted from
        # origin after store_time_hours, so caches must not outlive them.
        store_hours = getattr(settings, "store_time_hours", 48) if settings else 48
        self._cache_control = f"public, max-age={int(store_hours) * 3600}"
    
    async def handle_file_request(self, request: web.Request):
        """Serve hosted files."""
        try:
            filename = request.match_info["filename"]
            
            if ".." in filename or filename.startswith("/"):
                logger.warning(f"Blocked suspicious request: {filename}")
                raise web.HTTPForbidden()
            
            file_path = self.file_manager.get_file_path(filename)
            if not file_path:
                logger.warning(f"File not found: {filename}")
                raise web.HTTPNotFound()
            
            logger.info(f"Serving file: {filename}")
            return web.FileResponse(file_path, headers={"Cache-Control": self._cache_control})
            
        except web.HTTPException:
            raise
        except Exception as e:
            logger.error(f"Web server error: {e}")
            raise web.HTTPInternalServerError()
    
    async def health_check(self, request: web.Request):
        """Health check endpoint."""
        return web.Response(text="OK")
    
    async def start(self):
        """Start the web server."""
        try:
            app = web.Application()
            app.router.add_get("/files/{filename}", self.handle_file_request)
            app.router.add_get("/health", self.health_check)
            
            self._runner = web.AppRunner(app)
            await self._runner.setup()
            self._site = web.TCPSite(self._runner, self.host, self.port)
            await self._site.start()
            
            logger.info(f"Web server started on {self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Failed to start web server: {e}")
            raise
    
    async def stop(self):
        """Stop the web server."""
        try:
            if self._runner:
                await self._runner.cleanup()
                logger.info("Web server stopped")
        except Exception as e:
            logger.error(f"Error stopping web server: {e}")