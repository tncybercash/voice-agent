"""
API routes for embed key management.
Provides endpoints for creating, managing, and using embed API keys.
"""
from aiohttp import web
import json
import logging
from datetime import datetime
from typing import Optional

from database.connection import get_db_pool
from database.repository import (
    EmbedApiKeyRepository,
    EmbedSessionRepository,
    AgentInstructionRepository
)

logger = logging.getLogger("api.embed")


class EmbedAPI:
    """API handler for embed keys and sessions"""
    
    def __init__(self):
        self.embed_key_repo: Optional[EmbedApiKeyRepository] = None
        self.embed_session_repo: Optional[EmbedSessionRepository] = None
        self.instruction_repo: Optional[AgentInstructionRepository] = None
    
    async def init(self):
        """Initialize repositories"""
        pool = await get_db_pool()
        self.embed_key_repo = EmbedApiKeyRepository(pool)
        self.embed_session_repo = EmbedSessionRepository(pool)
        self.instruction_repo = AgentInstructionRepository(pool)
    
    def _json_response(self, data: dict, status: int = 200) -> web.Response:
        """Create JSON response with proper headers"""
        return web.json_response(
            data,
            status=status,
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-API-Key'
            }
        )
    
    def _serialize_embed_key(self, key, include_full_key: str = None) -> dict:
        """Serialize EmbedApiKey to JSON-safe dict"""
        data = {
            'id': key.id,
            'key_prefix': key.key_prefix,
            'name': key.name,
            'description': key.description,
            'agent_instruction_id': key.agent_instruction_id,
            'custom_greeting': key.custom_greeting,
            'custom_context': key.custom_context,
            'branding': key.branding.to_dict(),
            'widget_config': key.widget_config.to_dict(),
            'is_active': key.is_active,
            'allowed_domains': key.allowed_domains,
            'rate_limit_rpm': key.rate_limit_rpm,
            'max_concurrent_sessions': key.max_concurrent_sessions,
            'total_sessions': key.total_sessions,
            'total_messages': key.total_messages,
            'last_used_at': key.last_used_at.isoformat() if key.last_used_at else None,
            'created_by': key.created_by,
            'created_at': key.created_at.isoformat(),
            'updated_at': key.updated_at.isoformat()
        }
        
        # Only include full key on creation
        if include_full_key:
            data['api_key'] = include_full_key
        
        return data
    
    async def handle_options(self, request: web.Request) -> web.Response:
        """Handle CORS preflight requests"""
        return web.Response(
            status=204,
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-API-Key'
            }
        )
    
    # ==========================================
    # EMBED KEY CRUD ENDPOINTS
    # ==========================================
    
    async def list_embed_keys(self, request: web.Request) -> web.Response:
        """GET /api/embed-keys - List all embed API keys"""
        try:
            include_inactive = request.query.get('include_inactive', 'false').lower() == 'true'
            keys = await self.embed_key_repo.get_all(include_inactive=include_inactive)
            return self._json_response({
                'success': True,
                'data': [self._serialize_embed_key(key) for key in keys],
                'count': len(keys)
            })
        except Exception as e:
            logger.error(f"Error listing embed keys: {e}")
            return self._json_response({'success': False, 'error': str(e)}, status=500)
    
    async def create_embed_key(self, request: web.Request) -> web.Response:
        """POST /api/embed-keys - Create a new embed API key"""
        try:
            data = await request.json()
            
            # Validate required fields
            if not data.get('name'):
                return self._json_response(
                    {'success': False, 'error': 'Name is required'},
                    status=400
                )
            if not data.get('allowed_domains') or not isinstance(data['allowed_domains'], list):
                return self._json_response(
                    {'success': False, 'error': 'allowed_domains is required and must be a list'},
                    status=400
                )
            
            # Get agent instruction ID (use active if not specified)
            agent_instruction_id = data.get('agent_instruction_id')
            if not agent_instruction_id:
                instruction = await self.instruction_repo.get_active_instruction(is_local_mode=False)
                if instruction:
                    agent_instruction_id = instruction.id
            
            key, full_key = await self.embed_key_repo.create(
                name=data['name'],
                allowed_domains=data['allowed_domains'],
                agent_instruction_id=agent_instruction_id,
                description=data.get('description'),
                custom_greeting=data.get('custom_greeting'),
                custom_context=data.get('custom_context'),
                branding=data.get('branding'),
                widget_config=data.get('widget_config'),
                rate_limit_rpm=data.get('rate_limit_rpm', 60),
                max_concurrent_sessions=data.get('max_concurrent_sessions', 10),
                created_by=data.get('created_by')
            )
            
            logger.info(f"Created embed API key: {key.key_prefix}...")
            return self._json_response({
                'success': True,
                'data': self._serialize_embed_key(key, include_full_key=full_key),
                'message': 'Save this API key now. It will only be shown once!'
            }, status=201)
            
        except Exception as e:
            logger.error(f"Error creating embed key: {e}")
            return self._json_response({'success': False, 'error': str(e)}, status=500)
    
    async def get_embed_key(self, request: web.Request) -> web.Response:
        """GET /api/embed-keys/{id} - Get a specific embed key"""
        try:
            key_id = request.match_info['id']
            key = await self.embed_key_repo.get_by_id(key_id)
            
            if not key:
                return self._json_response(
                    {'success': False, 'error': 'Embed key not found'},
                    status=404
                )
            
            return self._json_response({
                'success': True,
                'data': self._serialize_embed_key(key)
            })
            
        except Exception as e:
            logger.error(f"Error getting embed key: {e}")
            return self._json_response({'success': False, 'error': str(e)}, status=500)
    
    async def update_embed_key(self, request: web.Request) -> web.Response:
        """PUT /api/embed-keys/{id} - Update an embed key"""
        try:
            key_id = request.match_info['id']
            data = await request.json()
            
            key = await self.embed_key_repo.update(
                key_id=key_id,
                name=data.get('name'),
                description=data.get('description'),
                agent_instruction_id=data.get('agent_instruction_id'),
                custom_greeting=data.get('custom_greeting'),
                custom_context=data.get('custom_context'),
                branding=data.get('branding'),
                widget_config=data.get('widget_config'),
                is_active=data.get('is_active'),
                allowed_domains=data.get('allowed_domains'),
                rate_limit_rpm=data.get('rate_limit_rpm'),
                max_concurrent_sessions=data.get('max_concurrent_sessions')
            )
            
            if not key:
                return self._json_response(
                    {'success': False, 'error': 'Embed key not found'},
                    status=404
                )
            
            logger.info(f"Updated embed key: {key.key_prefix}...")
            return self._json_response({
                'success': True,
                'data': self._serialize_embed_key(key)
            })
            
        except Exception as e:
            logger.error(f"Error updating embed key: {e}")
            return self._json_response({'success': False, 'error': str(e)}, status=500)
    
    async def delete_embed_key(self, request: web.Request) -> web.Response:
        """DELETE /api/embed-keys/{id} - Delete an embed key"""
        try:
            key_id = request.match_info['id']
            deleted = await self.embed_key_repo.delete(key_id)
            
            if not deleted:
                return self._json_response(
                    {'success': False, 'error': 'Embed key not found'},
                    status=404
                )
            
            logger.info(f"Deleted embed key: {key_id}")
            return self._json_response({'success': True, 'message': 'Embed key deleted'})
            
        except Exception as e:
            logger.error(f"Error deleting embed key: {e}")
            return self._json_response({'success': False, 'error': str(e)}, status=500)
    
    async def regenerate_embed_key(self, request: web.Request) -> web.Response:
        """POST /api/embed-keys/{id}/regenerate - Regenerate an embed key"""
        try:
            key_id = request.match_info['id']
            result = await self.embed_key_repo.regenerate_key(key_id)
            
            if not result:
                return self._json_response(
                    {'success': False, 'error': 'Embed key not found'},
                    status=404
                )
            
            key, full_key = result
            logger.info(f"Regenerated embed key: {key.key_prefix}...")
            return self._json_response({
                'success': True,
                'data': self._serialize_embed_key(key, include_full_key=full_key),
                'message': 'Save this new API key now. It will only be shown once!'
            })
            
        except Exception as e:
            logger.error(f"Error regenerating embed key: {e}")
            return self._json_response({'success': False, 'error': str(e)}, status=500)
    
    # ==========================================
    # PUBLIC EMBED ENDPOINTS (for SDK)
    # ==========================================
    
    async def get_embed_config(self, request: web.Request) -> web.Response:
        """GET /api/embed/config - Get embed configuration by API key"""
        try:
            # Get API key from header
            api_key = request.headers.get('X-API-Key')
            if not api_key:
                return self._json_response(
                    {'success': False, 'error': 'API key required'},
                    status=401
                )
            
            # Validate API key
            key = await self.embed_key_repo.get_by_key(api_key)
            if not key:
                return self._json_response(
                    {'success': False, 'error': 'Invalid API key'},
                    status=401
                )
            
            if not key.is_active:
                return self._json_response(
                    {'success': False, 'error': 'API key is inactive'},
                    status=403
                )
            
            # Validate origin domain
            origin = request.headers.get('Origin', '')
            if origin:
                from urllib.parse import urlparse
                domain = urlparse(origin).netloc
                if domain and not await self.embed_key_repo.validate_domain(key.id, domain):
                    return self._json_response(
                        {'success': False, 'error': 'Domain not allowed'},
                        status=403
                    )
            
            # Get instruction for greeting
            greeting = key.custom_greeting
            if not greeting and key.agent_instruction_id:
                instruction = await self.instruction_repo.get_by_id(key.agent_instruction_id)
                if instruction:
                    greeting = instruction.initial_greeting
            
            # Return public config
            return self._json_response({
                'success': True,
                'data': {
                    'greeting': greeting,
                    'branding': key.branding.to_dict(),
                    'widget': key.widget_config.to_dict()
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting embed config: {e}")
            return self._json_response({'success': False, 'error': str(e)}, status=500)
    
    async def create_embed_session(self, request: web.Request) -> web.Response:
        """POST /api/embed/session - Create a new embed session"""
        try:
            # Get API key from header
            api_key = request.headers.get('X-API-Key')
            if not api_key:
                return self._json_response(
                    {'success': False, 'error': 'API key required'},
                    status=401
                )
            
            # Validate API key
            key = await self.embed_key_repo.get_by_key(api_key)
            if not key or not key.is_active:
                return self._json_response(
                    {'success': False, 'error': 'Invalid or inactive API key'},
                    status=401
                )
            
            # Get origin domain
            origin = request.headers.get('Origin', '')
            from urllib.parse import urlparse
            domain = urlparse(origin).netloc if origin else 'unknown'
            
            # Validate domain
            if origin and not await self.embed_key_repo.validate_domain(key.id, domain):
                return self._json_response(
                    {'success': False, 'error': 'Domain not allowed'},
                    status=403
                )
            
            # Check concurrent session limit
            active_count = await self.embed_session_repo.get_active_count_for_key(key.id)
            if active_count >= key.max_concurrent_sessions:
                return self._json_response(
                    {'success': False, 'error': 'Maximum concurrent sessions reached'},
                    status=429
                )
            
            data = await request.json()
            
            # Create embed session
            embed_session = await self.embed_session_repo.create(
                embed_key_id=key.id,
                origin_domain=domain,
                visitor_id=data.get('visitor_id'),
                metadata=data.get('metadata')
            )
            
            # Increment stats
            await self.embed_key_repo.increment_stats(key.id)
            
            logger.info(f"Created embed session: {embed_session.id} for key {key.key_prefix}...")
            return self._json_response({
                'success': True,
                'data': {
                    'embed_session_id': embed_session.id,
                    'agent_instruction_id': key.agent_instruction_id
                }
            }, status=201)
            
        except Exception as e:
            logger.error(f"Error creating embed session: {e}")
            return self._json_response({'success': False, 'error': str(e)}, status=500)
    
    async def end_embed_session(self, request: web.Request) -> web.Response:
        """POST /api/embed/session/{id}/end - End an embed session"""
        try:
            embed_session_id = request.match_info['id']
            data = await request.json()
            
            await self.embed_session_repo.end_session(
                embed_session_id=embed_session_id,
                duration_seconds=data.get('duration_seconds')
            )
            
            # Update stats if message count provided
            if data.get('messages_count'):
                await self.embed_session_repo.update_stats(
                    embed_session_id=embed_session_id,
                    messages_count=data['messages_count']
                )
            
            logger.info(f"Ended embed session: {embed_session_id}")
            return self._json_response({'success': True, 'message': 'Session ended'})
            
        except Exception as e:
            logger.error(f"Error ending embed session: {e}")
            return self._json_response({'success': False, 'error': str(e)}, status=500)


def setup_embed_routes(app: web.Application, api: EmbedAPI):
    """Setup embed routes on the application"""
    # Management endpoints
    app.router.add_route('OPTIONS', '/api/embed-keys', api.handle_options)
    app.router.add_route('OPTIONS', '/api/embed-keys/{id}', api.handle_options)
    app.router.add_route('OPTIONS', '/api/embed-keys/{id}/regenerate', api.handle_options)
    app.router.add_route('OPTIONS', '/api/embed/config', api.handle_options)
    app.router.add_route('OPTIONS', '/api/embed/session', api.handle_options)
    app.router.add_route('OPTIONS', '/api/embed/session/{id}/end', api.handle_options)
    
    app.router.add_get('/api/embed-keys', api.list_embed_keys)
    app.router.add_post('/api/embed-keys', api.create_embed_key)
    app.router.add_get('/api/embed-keys/{id}', api.get_embed_key)
    app.router.add_put('/api/embed-keys/{id}', api.update_embed_key)
    app.router.add_delete('/api/embed-keys/{id}', api.delete_embed_key)
    app.router.add_post('/api/embed-keys/{id}/regenerate', api.regenerate_embed_key)
    
    # Public SDK endpoints
    app.router.add_get('/api/embed/config', api.get_embed_config)
    app.router.add_post('/api/embed/session', api.create_embed_session)
    app.router.add_post('/api/embed/session/{id}/end', api.end_embed_session)
