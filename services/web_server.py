import asyncio
from aiohttp import web
from core.file_manager import FileManager
from utils.logger import setup_logger

logger = setup_logger(__name__)

class WebServer:
    """HTTP server for serving hosted files."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.file_manager = FileManager()
        self._runner = None
    
    async def handle_file_request(self, request: web.Request):
        """Serve hosted files."""
        try:
            filename = request.match_info["filename"]
            
            # Security check
            if ".." in filename or filename.startswith("/"):
                logger.warning(f"Blocked suspicious request: {filename}")
                raise web.HTTPForbidden()
            
            file_path = self.file_manager.get_file_path(filename)
            if not file_path:
                logger.warning(f"File not found: {filename}")
                raise web.HTTPNotFound()
            
            logger.info(f"Serving file: {filename}")
            return web.FileResponse(file_path)
            
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
            site = web.TCPSite(self._runner, self.host, self.port)
            await site.start()
            
            logger.info(f"✅ Web server started on {self.host}:{self.port}")
            
            # Keep running until cancelled
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                pass
            
        except Exception as e:
            logger.error(f"Failed to start web server: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the web server."""
        if self._runner:
            await self._runner.cleanup()
            logger.info("Web server stopped")
