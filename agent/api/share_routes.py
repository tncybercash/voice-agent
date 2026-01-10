"""
API routes for share links management.
Provides endpoints for creating, managing, and using shareable links.
"""
from aiohttp import web
import json
import logging
from datetime import datetime
from typing import Optional

from database.connection import get_db_pool
from database.repository import ShareLinkRepository, AgentInstructionRepository

logger = logging.getLogger("api.share_links")


class ShareLinkAPI:
    """API handler for share links"""
    
    def __init__(self):
        self.share_repo: Optional[ShareLinkRepository] = None
        self.instruction_repo: Optional[AgentInstructionRepository] = None
    
    async def init(self):
        """Initialize repositories"""
        pool = await get_db_pool()
        self.share_repo = ShareLinkRepository(pool)
        self.instruction_repo = AgentInstructionRepository(pool)
    
    def _json_response(self, data: dict, status: int = 200) -> web.Response:
        """Create JSON response with proper headers"""
        return web.json_response(
            data,
            status=status,
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            }
        )
    
    def _serialize_share_link(self, link) -> dict:
        """Serialize ShareLink to JSON-safe dict"""
        return {
            'id': link.id,
            'code': link.code,
            'agent_instruction_id': link.agent_instruction_id,
            'name': link.name,
            'description': link.description,
            'custom_greeting': link.custom_greeting,
            'custom_context': link.custom_context,
            'branding': link.branding.to_dict(),
            'is_active': link.is_active,
            'expires_at': link.expires_at.isoformat() if link.expires_at else None,
            'max_sessions': link.max_sessions,
            'allowed_domains': link.allowed_domains,
            'require_auth': link.require_auth,
            'total_sessions': link.total_sessions,
            'total_messages': link.total_messages,
            'last_used_at': link.last_used_at.isoformat() if link.last_used_at else None,
            'created_by': link.created_by,
            'created_at': link.created_at.isoformat(),
            'updated_at': link.updated_at.isoformat(),
            'url': f"/s/{link.code}"
        }
    
    async def handle_options(self, request: web.Request) -> web.Response:
        """Handle CORS preflight requests"""
        return web.Response(
            status=204,
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            }
        )
    
    # ==========================================
    # CRUD ENDPOINTS
    # ==========================================
    
    async def list_share_links(self, request: web.Request) -> web.Response:
        """GET /api/share-links - List all share links"""
        try:
            include_inactive = request.query.get('include_inactive', 'false').lower() == 'true'
            links = await self.share_repo.get_all(include_inactive=include_inactive)
            return self._json_response({
                'success': True,
                'data': [self._serialize_share_link(link) for link in links],
                'count': len(links)
            })
        except Exception as e:
            logger.error(f"Error listing share links: {e}")
            return self._json_response({'success': False, 'error': str(e)}, status=500)
    
    async def create_share_link(self, request: web.Request) -> web.Response:
        """POST /api/share-links - Create a new share link"""
        try:
            data = await request.json()
            
            # Validate required fields
            if not data.get('name'):
                return self._json_response(
                    {'success': False, 'error': 'Name is required'},
                    status=400
                )
            
            # Get agent instruction ID (use active if not specified)
            agent_instruction_id = data.get('agent_instruction_id')
            if not agent_instruction_id:
                instruction = await self.instruction_repo.get_active_instruction(is_local_mode=False)
                if instruction:
                    agent_instruction_id = instruction.id
                else:
                    return self._json_response(
                        {'success': False, 'error': 'No active agent instruction found'},
                        status=400
                    )
            
            # Parse expires_at if provided
            expires_at = None
            if data.get('expires_at'):
                expires_at = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
            
            link = await self.share_repo.create(
                name=data['name'],
                agent_instruction_id=agent_instruction_id,
                description=data.get('description'),
                custom_greeting=data.get('custom_greeting'),
                custom_context=data.get('custom_context'),
                branding=data.get('branding'),
                expires_at=expires_at,
                max_sessions=data.get('max_sessions'),
                allowed_domains=data.get('allowed_domains'),
                require_auth=data.get('require_auth', False),
                created_by=data.get('created_by')
            )
            
            logger.info(f"Created share link: {link.code}")
            return self._json_response({
                'success': True,
                'data': self._serialize_share_link(link)
            }, status=201)
            
        except Exception as e:
            logger.error(f"Error creating share link: {e}")
            return self._json_response({'success': False, 'error': str(e)}, status=500)
    
    async def get_share_link(self, request: web.Request) -> web.Response:
        """GET /api/share-links/{id} - Get a specific share link"""
        try:
            link_id = request.match_info['id']
            link = await self.share_repo.get_by_id(link_id)
            
            if not link:
                return self._json_response(
                    {'success': False, 'error': 'Share link not found'},
                    status=404
                )
            
            return self._json_response({
                'success': True,
                'data': self._serialize_share_link(link)
            })
            
        except Exception as e:
            logger.error(f"Error getting share link: {e}")
            return self._json_response({'success': False, 'error': str(e)}, status=500)
    
    async def update_share_link(self, request: web.Request) -> web.Response:
        """PUT /api/share-links/{id} - Update a share link"""
        try:
            link_id = request.match_info['id']
            data = await request.json()
            
            # Parse expires_at if provided
            expires_at = None
            if 'expires_at' in data and data['expires_at']:
                expires_at = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
            elif 'expires_at' in data:
                # Explicitly set to None
                expires_at = data['expires_at']
            
            link = await self.share_repo.update(
                link_id=link_id,
                name=data.get('name'),
                description=data.get('description'),
                custom_greeting=data.get('custom_greeting'),
                custom_context=data.get('custom_context'),
                branding=data.get('branding'),
                is_active=data.get('is_active'),
                expires_at=expires_at,
                max_sessions=data.get('max_sessions'),
                allowed_domains=data.get('allowed_domains')
            )
            
            if not link:
                return self._json_response(
                    {'success': False, 'error': 'Share link not found'},
                    status=404
                )
            
            logger.info(f"Updated share link: {link.code}")
            return self._json_response({
                'success': True,
                'data': self._serialize_share_link(link)
            })
            
        except Exception as e:
            logger.error(f"Error updating share link: {e}")
            return self._json_response({'success': False, 'error': str(e)}, status=500)
    
    async def delete_share_link(self, request: web.Request) -> web.Response:
        """DELETE /api/share-links/{id} - Delete a share link"""
        try:
            link_id = request.match_info['id']
            deleted = await self.share_repo.delete(link_id)
            
            if not deleted:
                return self._json_response(
                    {'success': False, 'error': 'Share link not found'},
                    status=404
                )
            
            logger.info(f"Deleted share link: {link_id}")
            return self._json_response({'success': True, 'message': 'Share link deleted'})
            
        except Exception as e:
            logger.error(f"Error deleting share link: {e}")
            return self._json_response({'success': False, 'error': str(e)}, status=500)
    
    # ==========================================
    # PUBLIC ENDPOINTS (for share link access)
    # ==========================================
    
    async def get_share_link_by_code(self, request: web.Request) -> web.Response:
        """GET /api/share/{code} - Get share link config by code (public)"""
        try:
            code = request.match_info['code']
            link = await self.share_repo.get_by_code(code)
            
            if not link:
                return self._json_response(
                    {'success': False, 'error': 'Share link not found'},
                    status=404
                )
            
            # Check if link is valid
            if not link.is_valid():
                if not link.is_active:
                    return self._json_response(
                        {'success': False, 'error': 'This share link has been deactivated'},
                        status=403
                    )
                if link.expires_at and datetime.utcnow() > link.expires_at:
                    return self._json_response(
                        {'success': False, 'error': 'This share link has expired'},
                        status=403
                    )
                if link.max_sessions and link.total_sessions >= link.max_sessions:
                    return self._json_response(
                        {'success': False, 'error': 'This share link has reached its session limit'},
                        status=403
                    )
            
            # Check domain if restricted
            origin = request.headers.get('Origin', '')
            if link.allowed_domains and origin:
                from urllib.parse import urlparse
                domain = urlparse(origin).netloc
                if domain and domain not in link.allowed_domains:
                    # Check wildcard patterns
                    allowed = False
                    for pattern in link.allowed_domains:
                        if pattern.startswith('*.'):
                            if domain.endswith(pattern[1:]):
                                allowed = True
                                break
                    if not allowed:
                        return self._json_response(
                            {'success': False, 'error': 'Domain not allowed'},
                            status=403
                        )
            
            # Get instruction for greeting
            instruction = await self.instruction_repo.get_by_id(link.agent_instruction_id)
            greeting = link.custom_greeting or (instruction.initial_greeting if instruction else None)
            
            # Return public config (don't expose internal IDs)
            return self._json_response({
                'success': True,
                'data': {
                    'code': link.code,
                    'name': link.name,
                    'greeting': greeting,
                    'branding': link.branding.to_dict(),
                    'require_auth': link.require_auth
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting share link by code: {e}")
            return self._json_response({'success': False, 'error': str(e)}, status=500)
    
    # ==========================================
    # ANALYTICS ENDPOINTS
    # ==========================================
    
    async def get_share_link_analytics(self, request: web.Request) -> web.Response:
        """GET /api/share-links/{id}/analytics - Get analytics for a share link"""
        try:
            link_id = request.match_info['id']
            limit = int(request.query.get('limit', '100'))
            event_type = request.query.get('event_type')
            
            analytics = await self.share_repo.get_analytics(
                share_link_id=link_id,
                limit=limit,
                event_type=event_type
            )
            
            return self._json_response({
                'success': True,
                'data': analytics,
                'count': len(analytics)
            })
            
        except Exception as e:
            logger.error(f"Error getting share link analytics: {e}")
            return self._json_response({'success': False, 'error': str(e)}, status=500)


def setup_share_link_routes(app: web.Application, api: ShareLinkAPI):
    """Setup share link routes on the application"""
    # Management endpoints
    app.router.add_route('OPTIONS', '/api/share-links', api.handle_options)
    app.router.add_route('OPTIONS', '/api/share-links/{id}', api.handle_options)
    app.router.add_route('OPTIONS', '/api/share-links/{id}/analytics', api.handle_options)
    app.router.add_route('OPTIONS', '/api/share/{code}', api.handle_options)
    
    app.router.add_get('/api/share-links', api.list_share_links)
    app.router.add_post('/api/share-links', api.create_share_link)
    app.router.add_get('/api/share-links/{id}', api.get_share_link)
    app.router.add_put('/api/share-links/{id}', api.update_share_link)
    app.router.add_delete('/api/share-links/{id}', api.delete_share_link)
    app.router.add_get('/api/share-links/{id}/analytics', api.get_share_link_analytics)
    
    # Public endpoint
    app.router.add_get('/api/share/{code}', api.get_share_link_by_code)
