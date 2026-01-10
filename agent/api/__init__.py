"""
API module for voice agent REST endpoints.
Includes routes for share links and embed keys management.
"""
from .share_routes import ShareLinkAPI, setup_share_link_routes
from .embed_routes import EmbedAPI, setup_embed_routes

__all__ = [
    'ShareLinkAPI',
    'EmbedAPI',
    'setup_share_link_routes',
    'setup_embed_routes'
]
