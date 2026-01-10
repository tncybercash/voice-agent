"""
REST API Server for Voice Agent

This server runs alongside the LiveKit agent and provides
REST endpoints for:
- Share link management
- Embed key management
- Agent instructions
- Analytics and monitoring

Run with: python api_server.py
"""
import os
import asyncio
import logging
from aiohttp import web
from aiohttp.web import middleware
from dotenv import load_dotenv

load_dotenv()

# Import database and API modules
from database import get_db_pool
from database.repository import AgentInstructionRepository
from api import ShareLinkAPI, EmbedAPI, setup_share_link_routes, setup_embed_routes

logger = logging.getLogger("api-server")
logging.basicConfig(level=logging.INFO)

# CORS configuration
ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")


@middleware
async def cors_middleware(request: web.Request, handler):
    """Handle CORS preflight and response headers."""
    # Get origin from request
    origin = request.headers.get("Origin", "*")
    
    # Check if origin is allowed
    if "*" in ALLOWED_ORIGINS:
        allowed_origin = origin
    elif origin in ALLOWED_ORIGINS:
        allowed_origin = origin
    else:
        allowed_origin = ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else "*"
    
    # Handle preflight requests
    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex
    
    # Add CORS headers
    response.headers["Access-Control-Allow-Origin"] = allowed_origin
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-API-Key, X-Embed-Session"
    response.headers["Access-Control-Max-Age"] = "3600"
    
    return response


@middleware
async def error_middleware(request: web.Request, handler):
    """Global error handling middleware."""
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unhandled error: {e}")
        return web.json_response(
            {"error": "Internal server error", "message": str(e)},
            status=500
        )


async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({"status": "healthy", "service": "voice-agent-api"})


async def get_agent_instructions(request: web.Request) -> web.Response:
    """Get all agent instructions."""
    try:
        instruction_repo = request.app['instruction_repo']
        instructions = await instruction_repo.get_all()
        
        return web.json_response({
            "success": True,
            "data": [
                {
                    "id": inst.id,
                    "name": inst.name,
                    "is_active": inst.is_active,
                    "is_local_mode": inst.is_local_mode,
                    "language": inst.language,
                    "created_at": inst.created_at.isoformat() if inst.created_at else None,
                    "updated_at": inst.updated_at.isoformat() if inst.updated_at else None,
                }
                for inst in instructions
            ],
            "count": len(instructions)
        })
    except Exception as e:
        logger.exception(f"Error getting agent instructions: {e}")
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500
        )


async def on_startup(app):
    """Initialize services on startup."""
    logger.info("Initializing database connection...")
    pool = await get_db_pool()
    
    # Create repositories
    instruction_repo = AgentInstructionRepository(pool)
    app['instruction_repo'] = instruction_repo
    
    # Create API handlers (they initialize their own repositories)
    share_api = ShareLinkAPI()
    await share_api.init()
    
    embed_api = EmbedAPI()
    await embed_api.init()
    
    # Store in app for cleanup
    app['share_api'] = share_api
    app['embed_api'] = embed_api
    
    # Setup routes
    setup_share_link_routes(app, share_api)
    setup_embed_routes(app, embed_api)
    
    # Add agent instructions route
    app.router.add_get("/api/agent-instructions", get_agent_instructions)
    
    logger.info("API routes registered:")
    for route in app.router.routes():
        if hasattr(route, 'method') and hasattr(route, 'resource'):
            logger.info(f"  {route.method} {route.resource.canonical}")


def create_app() -> web.Application:
    """Create the aiohttp application."""
    app = web.Application(middlewares=[cors_middleware, error_middleware])
    
    # Register startup handler
    app.on_startup.append(on_startup)
    
    # Health check (available immediately)
    app.router.add_get("/health", health_check)
    app.router.add_get("/api/health", health_check)
    
    return app


def run_server():
    """Run the server."""
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    logger.info(f"Starting Voice Agent API Server on {host}:{port}")
    
    app = create_app()
    
    # Use web.run_app which handles signals properly
    web.run_app(app, host=host, port=port, print=lambda x: logger.info(x))


if __name__ == "__main__":
    run_server()
