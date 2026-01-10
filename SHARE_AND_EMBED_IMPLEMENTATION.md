# Shareable Links & Embedding Implementation Plan

## Executive Summary

This document outlines the technical implementation for two key distribution features:
1. **Shareable Links** - Generate unique URLs for sharing AI agent access
2. **Embedding System** - Integrate the AI agent into external websites and Flutter apps

---

## Part 1: Shareable Links System

### 1.1 Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Share Link    │────▶│   API Gateway    │────▶│  LiveKit Room   │
│  /s/{shareId}   │     │  /api/share/...  │     │  Voice Agent    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │   PostgreSQL     │
                        │  share_links     │
                        │  share_analytics │
                        └──────────────────┘
```

### 1.2 Database Schema

```sql
-- New table: share_links
CREATE TABLE share_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    share_code VARCHAR(12) UNIQUE NOT NULL,  -- Short URL code (e.g., "abc123xyz")
    
    -- Configuration
    name VARCHAR(255),                        -- Optional friendly name
    agent_instruction_id INTEGER REFERENCES agent_instructions(id),
    custom_greeting TEXT,                     -- Override default greeting
    custom_config JSONB DEFAULT '{}',         -- Branding, restrictions, etc.
    
    -- Access Control
    created_by UUID,                          -- User who created the link
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMP,                     -- Optional expiration
    max_uses INTEGER,                         -- Optional usage limit
    current_uses INTEGER DEFAULT 0,
    allowed_domains TEXT[],                   -- Domain whitelist for embedding
    
    -- Rate Limiting
    rate_limit_per_minute INTEGER DEFAULT 10,
    rate_limit_per_hour INTEGER DEFAULT 100,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Analytics tracking
CREATE TABLE share_link_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    share_link_id UUID REFERENCES share_links(id) ON DELETE CASCADE,
    
    -- Session info
    session_id UUID,
    
    -- Visitor info
    visitor_ip VARCHAR(45),
    visitor_country VARCHAR(2),
    visitor_city VARCHAR(100),
    user_agent TEXT,
    referer_url TEXT,
    
    -- Timestamps
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_duration_seconds INTEGER,
    
    -- Engagement metrics
    messages_sent INTEGER DEFAULT 0,
    tools_used TEXT[]
);

-- Indexes for performance
CREATE INDEX idx_share_links_code ON share_links(share_code);
CREATE INDEX idx_share_links_active ON share_links(is_active, expires_at);
CREATE INDEX idx_share_analytics_link ON share_link_analytics(share_link_id);
CREATE INDEX idx_share_analytics_time ON share_link_analytics(accessed_at);
```

### 1.3 API Endpoints

#### Backend (Python Agent)

```python
# agent/api/share_routes.py

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
import secrets
import string

router = APIRouter(prefix="/api/share", tags=["share"])

class CreateShareLinkRequest(BaseModel):
    name: Optional[str] = None
    agent_instruction_id: Optional[int] = None
    custom_greeting: Optional[str] = None
    expires_in_days: Optional[int] = None
    max_uses: Optional[int] = None
    allowed_domains: Optional[List[str]] = None
    custom_config: Optional[dict] = {}

class ShareLinkResponse(BaseModel):
    id: str
    share_code: str
    share_url: str
    name: Optional[str]
    is_active: bool
    expires_at: Optional[str]
    max_uses: Optional[int]
    current_uses: int
    created_at: str

def generate_share_code(length: int = 10) -> str:
    """Generate URL-safe share code"""
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

@router.post("/links", response_model=ShareLinkResponse)
async def create_share_link(request: CreateShareLinkRequest):
    """Create a new shareable link"""
    share_code = generate_share_code()
    # Insert into database
    # Return share link details
    pass

@router.get("/links/{share_code}")
async def get_share_link(share_code: str):
    """Get share link configuration (public endpoint)"""
    pass

@router.get("/links/{share_code}/validate")
async def validate_share_link(share_code: str, request: Request):
    """Validate and track share link access"""
    # Check if active, not expired, within usage limits
    # Track analytics
    # Return connection configuration
    pass

@router.delete("/links/{link_id}")
async def deactivate_share_link(link_id: str):
    """Deactivate a share link"""
    pass

@router.get("/links")
async def list_share_links(created_by: Optional[str] = None):
    """List all share links (admin)"""
    pass

@router.get("/analytics/{link_id}")
async def get_link_analytics(link_id: str):
    """Get analytics for a share link"""
    pass
```

#### Frontend API Route (Next.js)

```typescript
// front-end/app/api/share/[code]/route.ts

import { NextRequest, NextResponse } from 'next/server';

export async function GET(
  request: NextRequest,
  { params }: { params: { code: string } }
) {
  const shareCode = params.code;
  
  // Validate share link with backend
  const response = await fetch(
    `${process.env.AGENT_API_URL}/api/share/links/${shareCode}/validate`,
    {
      headers: {
        'X-Forwarded-For': request.headers.get('x-forwarded-for') || '',
        'User-Agent': request.headers.get('user-agent') || '',
        'Referer': request.headers.get('referer') || '',
      },
    }
  );
  
  if (!response.ok) {
    return NextResponse.json(
      { error: 'Invalid or expired share link' },
      { status: 404 }
    );
  }
  
  const config = await response.json();
  return NextResponse.json(config);
}
```

### 1.4 Share Link Page Component

```typescript
// front-end/app/s/[code]/page.tsx

import { notFound } from 'next/navigation';
import { SharedAgentView } from '@/components/shared/shared-agent-view';

interface SharePageProps {
  params: { code: string };
}

async function getShareConfig(code: string) {
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/api/share/${code}`,
    { cache: 'no-store' }
  );
  
  if (!res.ok) return null;
  return res.json();
}

export default async function SharePage({ params }: SharePageProps) {
  const config = await getShareConfig(params.code);
  
  if (!config) {
    notFound();
  }
  
  return (
    <SharedAgentView
      shareCode={params.code}
      config={config}
    />
  );
}

// front-end/components/shared/shared-agent-view.tsx
'use client';

import { useState, useCallback } from 'react';
import { LiveKitRoom, RoomAudioRenderer } from '@livekit/components-react';

interface SharedAgentViewProps {
  shareCode: string;
  config: {
    agentName?: string;
    greeting?: string;
    branding?: {
      logo?: string;
      primaryColor?: string;
      companyName?: string;
    };
  };
}

export function SharedAgentView({ shareCode, config }: SharedAgentViewProps) {
  const [connectionDetails, setConnectionDetails] = useState<any>(null);
  const [isConnecting, setIsConnecting] = useState(false);

  const connect = useCallback(async () => {
    setIsConnecting(true);
    
    const response = await fetch('/api/connection-details', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        share_code: shareCode,
        room_config: {
          agents: [{ agent_name: config.agentName }],
        },
      }),
    });
    
    const details = await response.json();
    setConnectionDetails(details);
    setIsConnecting(false);
  }, [shareCode, config]);

  if (!connectionDetails) {
    return (
      <div className="shared-landing" style={{ 
        '--accent-color': config.branding?.primaryColor 
      } as any}>
        {config.branding?.logo && (
          <img src={config.branding.logo} alt="Logo" />
        )}
        <h1>{config.branding?.companyName || 'AI Assistant'}</h1>
        <p>{config.greeting || 'Click below to start a conversation'}</p>
        <button onClick={connect} disabled={isConnecting}>
          {isConnecting ? 'Connecting...' : 'Start Conversation'}
        </button>
      </div>
    );
  }

  return (
    <LiveKitRoom
      serverUrl={connectionDetails.serverUrl}
      token={connectionDetails.participantToken}
      connect={true}
    >
      <RoomAudioRenderer />
      {/* Agent UI components */}
    </LiveKitRoom>
  );
}
```

### 1.5 Share Link Management UI

```typescript
// front-end/components/admin/share-link-manager.tsx

'use client';

import { useState, useEffect } from 'react';
import { Copy, Trash2, BarChart2, Link } from 'lucide-react';

interface ShareLink {
  id: string;
  share_code: string;
  share_url: string;
  name: string;
  is_active: boolean;
  current_uses: number;
  max_uses: number | null;
  expires_at: string | null;
  created_at: string;
}

export function ShareLinkManager() {
  const [links, setLinks] = useState<ShareLink[]>([]);
  const [isCreating, setIsCreating] = useState(false);
  const [newLinkName, setNewLinkName] = useState('');

  const createLink = async () => {
    setIsCreating(true);
    const response = await fetch('/api/share/links', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newLinkName }),
    });
    const link = await response.json();
    setLinks([link, ...links]);
    setNewLinkName('');
    setIsCreating(false);
  };

  const copyLink = (url: string) => {
    navigator.clipboard.writeText(url);
    // Show toast notification
  };

  const deleteLink = async (id: string) => {
    await fetch(`/api/share/links/${id}`, { method: 'DELETE' });
    setLinks(links.filter(l => l.id !== id));
  };

  return (
    <div className="share-link-manager">
      <h2>Shareable Links</h2>
      
      {/* Create new link */}
      <div className="create-link">
        <input
          type="text"
          placeholder="Link name (optional)"
          value={newLinkName}
          onChange={(e) => setNewLinkName(e.target.value)}
        />
        <button onClick={createLink} disabled={isCreating}>
          <Link size={16} />
          Create Link
        </button>
      </div>

      {/* Links list */}
      <div className="links-list">
        {links.map((link) => (
          <div key={link.id} className="link-item">
            <div className="link-info">
              <span className="link-name">{link.name || 'Unnamed Link'}</span>
              <span className="link-url">{link.share_url}</span>
              <span className="link-stats">
                {link.current_uses} uses
                {link.max_uses && ` / ${link.max_uses} max`}
              </span>
            </div>
            <div className="link-actions">
              <button onClick={() => copyLink(link.share_url)}>
                <Copy size={16} />
              </button>
              <button onClick={() => {/* Show analytics */}}>
                <BarChart2 size={16} />
              </button>
              <button onClick={() => deleteLink(link.id)}>
                <Trash2 size={16} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## Part 2: Embedding System

### 2.1 Architecture Overview

```
┌────────────────────────────────────────────────────────────────┐
│                      Host Application                          │
├────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐│
│  │ Web Embed   │    │ Flutter SDK │    │ React Native SDK    ││
│  │ (iframe/JS) │    │  (Package)  │    │    (Package)        ││
│  └──────┬──────┘    └──────┬──────┘    └──────────┬──────────┘│
│         │                  │                       │           │
│         └──────────────────┼───────────────────────┘           │
│                            ▼                                   │
│                   ┌─────────────────┐                          │
│                   │  Embed API      │                          │
│                   │  /api/embed/*   │                          │
│                   └────────┬────────┘                          │
└────────────────────────────┼───────────────────────────────────┘
                             ▼
                    ┌─────────────────┐
                    │   Agent Server  │
                    │   + LiveKit     │
                    └─────────────────┘
```

### 2.2 Database Schema for Embed Keys

```sql
-- Embed API keys for authentication
CREATE TABLE embed_api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key VARCHAR(64) UNIQUE NOT NULL,
    api_secret VARCHAR(128) NOT NULL,  -- Hashed
    
    -- Owner info
    owner_id UUID,
    owner_email VARCHAR(255),
    organization_name VARCHAR(255),
    
    -- Configuration
    name VARCHAR(255),
    allowed_domains TEXT[],             -- Domain whitelist
    allowed_origins TEXT[],             -- CORS origins
    agent_instruction_id INTEGER REFERENCES agent_instructions(id),
    custom_config JSONB DEFAULT '{}',
    
    -- Limits
    is_active BOOLEAN DEFAULT true,
    rate_limit_per_minute INTEGER DEFAULT 60,
    monthly_session_limit INTEGER,
    current_month_sessions INTEGER DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP
);

-- Track embed sessions for billing/analytics
CREATE TABLE embed_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key_id UUID REFERENCES embed_api_keys(id),
    session_id UUID,
    
    -- Context
    domain VARCHAR(255),
    platform VARCHAR(50),  -- 'web', 'flutter', 'react-native'
    app_version VARCHAR(50),
    
    -- Session data
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    duration_seconds INTEGER,
    message_count INTEGER DEFAULT 0,
    
    -- User context (if provided)
    user_id VARCHAR(255),
    user_metadata JSONB
);

CREATE INDEX idx_embed_keys_key ON embed_api_keys(api_key);
CREATE INDEX idx_embed_sessions_key ON embed_sessions(api_key_id);
```

### 2.3 Web Embedding - JavaScript SDK

#### Embed Widget Script

```typescript
// front-end/public/embed/tncb-agent.js

(function() {
  'use strict';

  const EMBED_VERSION = '1.0.0';
  const DEFAULT_API_URL = 'https://voice.tncybertech.com';

  class TNCBAgent {
    constructor(config) {
      this.config = {
        apiKey: config.apiKey,
        apiUrl: config.apiUrl || DEFAULT_API_URL,
        containerId: config.containerId || 'tncb-agent-container',
        position: config.position || 'bottom-right', // bottom-right, bottom-left, inline
        theme: config.theme || 'light',
        primaryColor: config.primaryColor || '#002cf2',
        greeting: config.greeting,
        userInfo: config.userInfo || {},
        autoOpen: config.autoOpen || false,
        onReady: config.onReady || (() => {}),
        onSessionStart: config.onSessionStart || (() => {}),
        onSessionEnd: config.onSessionEnd || (() => {}),
        onError: config.onError || console.error,
      };

      this.isOpen = false;
      this.iframe = null;
      this.sessionId = null;

      this.init();
    }

    async init() {
      // Validate API key
      try {
        const validation = await this.validateApiKey();
        if (!validation.valid) {
          throw new Error(validation.error || 'Invalid API key');
        }
        
        this.embedConfig = validation.config;
        this.createWidget();
        this.config.onReady();
        
        if (this.config.autoOpen) {
          this.open();
        }
      } catch (error) {
        this.config.onError(error);
      }
    }

    async validateApiKey() {
      const response = await fetch(`${this.config.apiUrl}/api/embed/validate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Embed-Key': this.config.apiKey,
        },
        body: JSON.stringify({
          domain: window.location.hostname,
          origin: window.location.origin,
        }),
      });
      return response.json();
    }

    createWidget() {
      // Create container
      const container = document.getElementById(this.config.containerId) || 
                       this.createFloatingContainer();
      
      // Create iframe
      this.iframe = document.createElement('iframe');
      this.iframe.src = `${this.config.apiUrl}/embed/widget?` + new URLSearchParams({
        apiKey: this.config.apiKey,
        theme: this.config.theme,
        primaryColor: this.config.primaryColor,
        greeting: this.config.greeting || '',
      });
      this.iframe.style.cssText = `
        width: 100%;
        height: 100%;
        border: none;
        border-radius: 16px;
      `;
      
      container.appendChild(this.iframe);

      // Listen for messages from iframe
      window.addEventListener('message', this.handleMessage.bind(this));
    }

    createFloatingContainer() {
      const container = document.createElement('div');
      container.id = this.config.containerId;
      container.className = `tncb-agent-floating tncb-agent-${this.config.position}`;
      container.style.cssText = `
        position: fixed;
        ${this.config.position.includes('bottom') ? 'bottom: 20px;' : 'top: 20px;'}
        ${this.config.position.includes('right') ? 'right: 20px;' : 'left: 20px;'}
        width: 400px;
        height: 600px;
        max-height: 80vh;
        z-index: 999999;
        display: none;
        box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        border-radius: 16px;
        overflow: hidden;
      `;
      
      // Create toggle button
      this.toggleButton = document.createElement('button');
      this.toggleButton.innerHTML = this.getToggleIcon();
      this.toggleButton.style.cssText = `
        position: fixed;
        ${this.config.position.includes('bottom') ? 'bottom: 20px;' : 'top: 20px;'}
        ${this.config.position.includes('right') ? 'right: 20px;' : 'left: 20px;'}
        width: 60px;
        height: 60px;
        border-radius: 50%;
        background: ${this.config.primaryColor};
        border: none;
        cursor: pointer;
        z-index: 999998;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        transition: transform 0.2s;
      `;
      this.toggleButton.onclick = () => this.toggle();
      
      document.body.appendChild(container);
      document.body.appendChild(this.toggleButton);
      
      return container;
    }

    getToggleIcon() {
      return `<svg width="24" height="24" viewBox="0 0 24 24" fill="white">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
      </svg>`;
    }

    handleMessage(event) {
      if (event.origin !== this.config.apiUrl) return;
      
      const { type, data } = event.data;
      
      switch (type) {
        case 'session_start':
          this.sessionId = data.sessionId;
          this.config.onSessionStart(data);
          break;
        case 'session_end':
          this.config.onSessionEnd(data);
          this.sessionId = null;
          break;
        case 'resize':
          // Handle resize requests
          break;
      }
    }

    open() {
      const container = document.getElementById(this.config.containerId);
      if (container) {
        container.style.display = 'block';
        this.toggleButton.style.display = 'none';
        this.isOpen = true;
      }
    }

    close() {
      const container = document.getElementById(this.config.containerId);
      if (container) {
        container.style.display = 'none';
        this.toggleButton.style.display = 'block';
        this.isOpen = false;
      }
    }

    toggle() {
      this.isOpen ? this.close() : this.open();
    }

    // Send user context to agent
    setUserContext(context) {
      this.iframe?.contentWindow?.postMessage({
        type: 'set_user_context',
        data: context,
      }, this.config.apiUrl);
    }

    // End current session
    endSession() {
      this.iframe?.contentWindow?.postMessage({
        type: 'end_session',
      }, this.config.apiUrl);
    }

    // Destroy widget
    destroy() {
      const container = document.getElementById(this.config.containerId);
      container?.remove();
      this.toggleButton?.remove();
      window.removeEventListener('message', this.handleMessage);
    }
  }

  // Expose to global scope
  window.TNCBAgent = TNCBAgent;
})();
```

#### Usage Example (HTML)

```html
<!-- Include the SDK -->
<script src="https://voice.tncybertech.com/embed/tncb-agent.js"></script>

<script>
  // Initialize the agent widget
  const agent = new TNCBAgent({
    apiKey: 'your-api-key-here',
    
    // Positioning
    position: 'bottom-right',  // or 'bottom-left', 'inline'
    containerId: 'my-agent',   // for inline mode
    
    // Customization
    theme: 'light',
    primaryColor: '#0066cc',
    greeting: 'Hi! How can I help you today?',
    
    // User context (optional)
    userInfo: {
      userId: 'user-123',
      name: 'John Doe',
      email: 'john@example.com',
    },
    
    // Behavior
    autoOpen: false,
    
    // Callbacks
    onReady: () => {
      console.log('Agent widget ready');
    },
    onSessionStart: (data) => {
      console.log('Session started:', data.sessionId);
    },
    onSessionEnd: (data) => {
      console.log('Session ended');
    },
    onError: (error) => {
      console.error('Agent error:', error);
    },
  });

  // Programmatic control
  document.getElementById('open-agent').onclick = () => agent.open();
  document.getElementById('close-agent').onclick = () => agent.close();
</script>
```

### 2.4 Embed Widget Page

```typescript
// front-end/app/embed/widget/page.tsx

'use client';

import { useSearchParams } from 'next/navigation';
import { useEffect, useState, useCallback } from 'react';
import { LiveKitRoom, RoomAudioRenderer } from '@livekit/components-react';

export default function EmbedWidget() {
  const searchParams = useSearchParams();
  const apiKey = searchParams.get('apiKey');
  const theme = searchParams.get('theme') || 'light';
  const primaryColor = searchParams.get('primaryColor') || '#002cf2';
  const greeting = searchParams.get('greeting');

  const [connectionDetails, setConnectionDetails] = useState<any>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connect = useCallback(async () => {
    setIsConnecting(true);
    setError(null);

    try {
      const response = await fetch('/api/embed/connect', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Embed-Key': apiKey || '',
        },
        body: JSON.stringify({
          domain: window.location.ancestorOrigins?.[0] || document.referrer,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to connect');
      }

      const details = await response.json();
      setConnectionDetails(details);

      // Notify parent window
      window.parent.postMessage({
        type: 'session_start',
        data: { sessionId: details.sessionId },
      }, '*');

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connection failed');
    } finally {
      setIsConnecting(false);
    }
  }, [apiKey]);

  // Listen for messages from parent
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const { type, data } = event.data;
      
      switch (type) {
        case 'set_user_context':
          // Handle user context
          break;
        case 'end_session':
          // End session
          setConnectionDetails(null);
          break;
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  return (
    <div 
      className="embed-widget"
      style={{ 
        '--primary-color': primaryColor,
        '--theme': theme,
      } as any}
    >
      {!connectionDetails ? (
        <div className="embed-landing">
          <div className="embed-header">
            <h2>AI Assistant</h2>
          </div>
          <div className="embed-body">
            <p>{greeting || 'Click below to start a conversation'}</p>
            <button 
              onClick={connect} 
              disabled={isConnecting}
              style={{ backgroundColor: primaryColor }}
            >
              {isConnecting ? 'Connecting...' : 'Start Voice Chat'}
            </button>
            {error && <p className="error">{error}</p>}
          </div>
        </div>
      ) : (
        <LiveKitRoom
          serverUrl={connectionDetails.serverUrl}
          token={connectionDetails.participantToken}
          connect={true}
        >
          <RoomAudioRenderer />
          <EmbedAgentUI 
            onEnd={() => {
              setConnectionDetails(null);
              window.parent.postMessage({ type: 'session_end' }, '*');
            }}
          />
        </LiveKitRoom>
      )}
    </div>
  );
}
```

### 2.5 Flutter SDK

```dart
// lib/tncb_voice_agent.dart

library tncb_voice_agent;

import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:livekit_client/livekit_client.dart';
import 'package:permission_handler/permission_handler.dart';

/// Configuration for the TNCB Voice Agent
class TNCBAgentConfig {
  final String apiKey;
  final String? apiUrl;
  final String? greeting;
  final Color? primaryColor;
  final ThemeMode themeMode;
  final Map<String, dynamic>? userInfo;
  
  TNCBAgentConfig({
    required this.apiKey,
    this.apiUrl = 'https://voice.tncybertech.com',
    this.greeting,
    this.primaryColor,
    this.themeMode = ThemeMode.system,
    this.userInfo,
  });
}

/// Connection details from the API
class ConnectionDetails {
  final String serverUrl;
  final String token;
  final String roomName;
  final String sessionId;
  
  ConnectionDetails({
    required this.serverUrl,
    required this.token,
    required this.roomName,
    required this.sessionId,
  });
  
  factory ConnectionDetails.fromJson(Map<String, dynamic> json) {
    return ConnectionDetails(
      serverUrl: json['serverUrl'],
      token: json['participantToken'],
      roomName: json['roomName'],
      sessionId: json['sessionId'],
    );
  }
}

/// Event callbacks
typedef OnSessionStart = void Function(String sessionId);
typedef OnSessionEnd = void Function();
typedef OnError = void Function(String error);
typedef OnStateChange = void Function(TNCBAgentState state);

/// Agent state
enum TNCBAgentState {
  idle,
  connecting,
  connected,
  listening,
  speaking,
  error,
  disconnected,
}

/// Main Voice Agent Client
class TNCBVoiceAgent {
  final TNCBAgentConfig config;
  
  Room? _room;
  LocalAudioTrack? _audioTrack;
  ConnectionDetails? _connectionDetails;
  
  TNCBAgentState _state = TNCBAgentState.idle;
  TNCBAgentState get state => _state;
  
  // Callbacks
  OnSessionStart? onSessionStart;
  OnSessionEnd? onSessionEnd;
  OnError? onError;
  OnStateChange? onStateChange;
  
  // Stream controllers
  final _stateController = StreamController<TNCBAgentState>.broadcast();
  Stream<TNCBAgentState> get stateStream => _stateController.stream;
  
  TNCBVoiceAgent({
    required this.config,
    this.onSessionStart,
    this.onSessionEnd,
    this.onError,
    this.onStateChange,
  });
  
  void _setState(TNCBAgentState newState) {
    _state = newState;
    _stateController.add(newState);
    onStateChange?.call(newState);
  }
  
  /// Validate API key and get embed configuration
  Future<bool> validateApiKey() async {
    try {
      final response = await http.post(
        Uri.parse('${config.apiUrl}/api/embed/validate'),
        headers: {
          'Content-Type': 'application/json',
          'X-Embed-Key': config.apiKey,
        },
        body: jsonEncode({
          'platform': 'flutter',
        }),
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['valid'] == true;
      }
      return false;
    } catch (e) {
      onError?.call('Failed to validate API key: $e');
      return false;
    }
  }
  
  /// Request microphone permission
  Future<bool> requestPermissions() async {
    final status = await Permission.microphone.request();
    return status.isGranted;
  }
  
  /// Connect to the voice agent
  Future<void> connect() async {
    if (_state == TNCBAgentState.connected || 
        _state == TNCBAgentState.connecting) {
      return;
    }
    
    _setState(TNCBAgentState.connecting);
    
    try {
      // Check permissions
      if (!await requestPermissions()) {
        throw Exception('Microphone permission denied');
      }
      
      // Get connection details
      final response = await http.post(
        Uri.parse('${config.apiUrl}/api/embed/connect'),
        headers: {
          'Content-Type': 'application/json',
          'X-Embed-Key': config.apiKey,
        },
        body: jsonEncode({
          'platform': 'flutter',
          'userInfo': config.userInfo,
        }),
      );
      
      if (response.statusCode != 200) {
        throw Exception('Failed to get connection details');
      }
      
      _connectionDetails = ConnectionDetails.fromJson(jsonDecode(response.body));
      
      // Create room
      _room = Room();
      
      // Set up event listeners
      _room!.addListener(_onRoomEvent);
      
      // Connect to LiveKit
      await _room!.connect(
        _connectionDetails!.serverUrl,
        _connectionDetails!.token,
        roomOptions: RoomOptions(
          adaptiveStream: true,
          dynacast: true,
        ),
      );
      
      // Publish microphone
      _audioTrack = await LocalAudioTrack.create();
      await _room!.localParticipant?.publishAudioTrack(_audioTrack!);
      
      _setState(TNCBAgentState.connected);
      onSessionStart?.call(_connectionDetails!.sessionId);
      
    } catch (e) {
      _setState(TNCBAgentState.error);
      onError?.call(e.toString());
      rethrow;
    }
  }
  
  void _onRoomEvent(RoomEvent event) {
    if (event is RoomDisconnectedEvent) {
      _setState(TNCBAgentState.disconnected);
      onSessionEnd?.call();
    } else if (event is TrackSubscribedEvent) {
      // Agent audio track subscribed
    }
  }
  
  /// Disconnect from the voice agent
  Future<void> disconnect() async {
    await _audioTrack?.stop();
    await _room?.disconnect();
    _room?.removeListener(_onRoomEvent);
    _room = null;
    _audioTrack = null;
    _connectionDetails = null;
    _setState(TNCBAgentState.idle);
    onSessionEnd?.call();
  }
  
  /// Mute/unmute microphone
  Future<void> setMicrophoneMuted(bool muted) async {
    if (_audioTrack != null) {
      if (muted) {
        await _audioTrack!.mute();
      } else {
        await _audioTrack!.unmute();
      }
    }
  }
  
  /// Dispose resources
  void dispose() {
    disconnect();
    _stateController.close();
  }
}

// ============================================================================
// Flutter Widget Components
// ============================================================================

/// Voice Agent Widget - Full-featured UI component
class TNCBVoiceAgentWidget extends StatefulWidget {
  final TNCBAgentConfig config;
  final Widget? loadingWidget;
  final Widget? errorWidget;
  final bool autoConnect;
  
  const TNCBVoiceAgentWidget({
    Key? key,
    required this.config,
    this.loadingWidget,
    this.errorWidget,
    this.autoConnect = false,
  }) : super(key: key);
  
  @override
  State<TNCBVoiceAgentWidget> createState() => _TNCBVoiceAgentWidgetState();
}

class _TNCBVoiceAgentWidgetState extends State<TNCBVoiceAgentWidget> {
  late TNCBVoiceAgent _agent;
  TNCBAgentState _state = TNCBAgentState.idle;
  String? _error;
  
  @override
  void initState() {
    super.initState();
    _agent = TNCBVoiceAgent(
      config: widget.config,
      onStateChange: (state) => setState(() => _state = state),
      onError: (error) => setState(() => _error = error),
    );
    
    if (widget.autoConnect) {
      _agent.connect();
    }
  }
  
  @override
  void dispose() {
    _agent.dispose();
    super.dispose();
  }
  
  @override
  Widget build(BuildContext context) {
    final primaryColor = widget.config.primaryColor ?? 
                         Theme.of(context).primaryColor;
    
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        children: [
          // Header
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: primaryColor,
              borderRadius: const BorderRadius.vertical(
                top: Radius.circular(16),
              ),
            ),
            child: Row(
              children: [
                const Icon(Icons.support_agent, color: Colors.white),
                const SizedBox(width: 12),
                const Text(
                  'AI Assistant',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const Spacer(),
                if (_state == TNCBAgentState.connected)
                  IconButton(
                    icon: const Icon(Icons.close, color: Colors.white),
                    onPressed: _agent.disconnect,
                  ),
              ],
            ),
          ),
          
          // Body
          Expanded(
            child: _buildBody(primaryColor),
          ),
        ],
      ),
    );
  }
  
  Widget _buildBody(Color primaryColor) {
    switch (_state) {
      case TNCBAgentState.idle:
        return _buildIdleState(primaryColor);
      case TNCBAgentState.connecting:
        return widget.loadingWidget ?? 
               const Center(child: CircularProgressIndicator());
      case TNCBAgentState.connected:
      case TNCBAgentState.listening:
      case TNCBAgentState.speaking:
        return _buildConnectedState(primaryColor);
      case TNCBAgentState.error:
        return widget.errorWidget ?? _buildErrorState();
      case TNCBAgentState.disconnected:
        return _buildIdleState(primaryColor);
    }
  }
  
  Widget _buildIdleState(Color primaryColor) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.mic,
            size: 64,
            color: primaryColor.withOpacity(0.5),
          ),
          const SizedBox(height: 16),
          Text(
            widget.config.greeting ?? 
            'Tap below to start a voice conversation',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyLarge,
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _agent.connect,
            icon: const Icon(Icons.phone),
            label: const Text('Start Conversation'),
            style: ElevatedButton.styleFrom(
              backgroundColor: primaryColor,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(
                horizontal: 32,
                vertical: 16,
              ),
            ),
          ),
        ],
      ),
    );
  }
  
  Widget _buildConnectedState(Color primaryColor) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          // Animated indicator
          Container(
            width: 120,
            height: 120,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: primaryColor.withOpacity(0.1),
            ),
            child: Center(
              child: Icon(
                _state == TNCBAgentState.speaking 
                    ? Icons.volume_up 
                    : Icons.mic,
                size: 48,
                color: primaryColor,
              ),
            ),
          ),
          const SizedBox(height: 24),
          Text(
            _state == TNCBAgentState.speaking 
                ? 'Agent is speaking...' 
                : 'Listening...',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 32),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              IconButton(
                icon: const Icon(Icons.mic_off),
                onPressed: () => _agent.setMicrophoneMuted(true),
                tooltip: 'Mute',
              ),
              const SizedBox(width: 16),
              ElevatedButton(
                onPressed: _agent.disconnect,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.red,
                  foregroundColor: Colors.white,
                ),
                child: const Text('End Call'),
              ),
            ],
          ),
        ],
      ),
    );
  }
  
  Widget _buildErrorState() {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.error_outline,
            size: 64,
            color: Colors.red,
          ),
          const SizedBox(height: 16),
          Text(
            _error ?? 'An error occurred',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: _agent.connect,
            child: const Text('Try Again'),
          ),
        ],
      ),
    );
  }
}

/// Floating Action Button for Voice Agent
class TNCBVoiceAgentFAB extends StatefulWidget {
  final TNCBAgentConfig config;
  
  const TNCBVoiceAgentFAB({
    Key? key,
    required this.config,
  }) : super(key: key);
  
  @override
  State<TNCBVoiceAgentFAB> createState() => _TNCBVoiceAgentFABState();
}

class _TNCBVoiceAgentFABState extends State<TNCBVoiceAgentFAB> {
  bool _isOpen = false;
  
  void _toggleAgent() {
    setState(() => _isOpen = !_isOpen);
  }
  
  @override
  Widget build(BuildContext context) {
    final primaryColor = widget.config.primaryColor ?? 
                         Theme.of(context).primaryColor;
    
    return Stack(
      children: [
        // Agent widget (when open)
        if (_isOpen)
          Positioned(
            right: 16,
            bottom: 80,
            child: SizedBox(
              width: 350,
              height: 500,
              child: TNCBVoiceAgentWidget(config: widget.config),
            ),
          ),
        
        // FAB
        Positioned(
          right: 16,
          bottom: 16,
          child: FloatingActionButton(
            onPressed: _toggleAgent,
            backgroundColor: primaryColor,
            child: Icon(
              _isOpen ? Icons.close : Icons.support_agent,
              color: Colors.white,
            ),
          ),
        ),
      ],
    );
  }
}
```

#### Flutter Usage Example

```dart
// main.dart

import 'package:flutter/material.dart';
import 'package:tncb_voice_agent/tncb_voice_agent.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'My App',
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatelessWidget {
  const HomeScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final agentConfig = TNCBAgentConfig(
      apiKey: 'your-api-key-here',
      primaryColor: Colors.blue,
      greeting: 'Hi! How can I help you with your banking today?',
      userInfo: {
        'userId': 'user-123',
        'name': 'John Doe',
      },
    );

    return Scaffold(
      appBar: AppBar(title: const Text('My Banking App')),
      body: const Center(
        child: Text('Welcome to My App'),
      ),
      // Option 1: Floating button with popup
      floatingActionButton: TNCBVoiceAgentFAB(config: agentConfig),
      
      // Option 2: Full widget embedded in page
      // body: TNCBVoiceAgentWidget(config: agentConfig),
    );
  }
}

// Or use programmatically:
class ProgrammaticExample extends StatefulWidget {
  @override
  State<ProgrammaticExample> createState() => _ProgrammaticExampleState();
}

class _ProgrammaticExampleState extends State<ProgrammaticExample> {
  late TNCBVoiceAgent _agent;
  
  @override
  void initState() {
    super.initState();
    _agent = TNCBVoiceAgent(
      config: TNCBAgentConfig(apiKey: 'your-key'),
      onSessionStart: (sessionId) {
        print('Session started: $sessionId');
      },
      onSessionEnd: () {
        print('Session ended');
      },
      onError: (error) {
        print('Error: $error');
      },
    );
  }
  
  @override
  Widget build(BuildContext context) {
    return StreamBuilder<TNCBAgentState>(
      stream: _agent.stateStream,
      builder: (context, snapshot) {
        final state = snapshot.data ?? TNCBAgentState.idle;
        
        return ElevatedButton(
          onPressed: state == TNCBAgentState.idle 
              ? _agent.connect 
              : _agent.disconnect,
          child: Text(state == TNCBAgentState.idle 
              ? 'Start Call' 
              : 'End Call'),
        );
      },
    );
  }
  
  @override
  void dispose() {
    _agent.dispose();
    super.dispose();
  }
}
```

### 2.6 Embed API Endpoints

```python
# agent/api/embed_routes.py

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
import secrets
import hashlib
import time

router = APIRouter(prefix="/api/embed", tags=["embed"])

class ValidateKeyRequest(BaseModel):
    domain: Optional[str] = None
    origin: Optional[str] = None
    platform: Optional[str] = "web"

class ValidateKeyResponse(BaseModel):
    valid: bool
    config: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class ConnectRequest(BaseModel):
    platform: Optional[str] = "web"
    userInfo: Optional[Dict[str, Any]] = None
    domain: Optional[str] = None

@router.post("/validate", response_model=ValidateKeyResponse)
async def validate_api_key(
    request: ValidateKeyRequest,
    x_embed_key: str = Header(..., alias="X-Embed-Key")
):
    """Validate embed API key and return configuration"""
    # Look up API key
    api_key_record = await get_api_key(x_embed_key)
    
    if not api_key_record:
        return ValidateKeyResponse(valid=False, error="Invalid API key")
    
    if not api_key_record.is_active:
        return ValidateKeyResponse(valid=False, error="API key is inactive")
    
    if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
        return ValidateKeyResponse(valid=False, error="API key has expired")
    
    # Check domain whitelist
    if api_key_record.allowed_domains:
        if request.domain and request.domain not in api_key_record.allowed_domains:
            return ValidateKeyResponse(valid=False, error="Domain not allowed")
    
    # Check rate limits
    # Check monthly session limits
    
    return ValidateKeyResponse(
        valid=True,
        config={
            "greeting": api_key_record.custom_config.get("greeting"),
            "primaryColor": api_key_record.custom_config.get("primaryColor"),
            "agentName": api_key_record.custom_config.get("agentName"),
        }
    )

@router.post("/connect")
async def create_embed_connection(
    request: ConnectRequest,
    http_request: Request,
    x_embed_key: str = Header(..., alias="X-Embed-Key")
):
    """Create a new embed session and return connection details"""
    # Validate API key first
    api_key_record = await get_api_key(x_embed_key)
    
    if not api_key_record or not api_key_record.is_active:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    
    # Check rate limits
    if not await check_rate_limit(x_embed_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # Generate room and participant info
    room_name = f"embed_{secrets.token_hex(8)}"
    participant_identity = f"embed_user_{secrets.token_hex(4)}"
    session_id = str(uuid.uuid4())
    
    # Create participant token
    token = create_participant_token(
        identity=participant_identity,
        room_name=room_name,
        agent_name=api_key_record.custom_config.get("agentName")
    )
    
    # Track session
    await create_embed_session(
        api_key_id=api_key_record.id,
        session_id=session_id,
        domain=request.domain,
        platform=request.platform,
        user_metadata=request.userInfo
    )
    
    # Update usage counters
    await increment_api_key_usage(x_embed_key)
    
    return {
        "serverUrl": LIVEKIT_URL,
        "participantToken": token,
        "roomName": room_name,
        "sessionId": session_id,
    }

@router.post("/keys")
async def create_api_key(
    request: CreateApiKeyRequest,
    # Auth required
):
    """Create a new embed API key (admin only)"""
    api_key = f"tncb_embed_{secrets.token_hex(16)}"
    api_secret = secrets.token_hex(32)
    
    # Hash secret for storage
    secret_hash = hashlib.sha256(api_secret.encode()).hexdigest()
    
    # Store in database
    # Return key and secret (secret shown only once)
    
    return {
        "api_key": api_key,
        "api_secret": api_secret,  # Only shown once
        "warning": "Save your API secret now. It won't be shown again."
    }

@router.get("/keys")
async def list_api_keys():
    """List all API keys (admin only)"""
    pass

@router.delete("/keys/{key_id}")
async def revoke_api_key(key_id: str):
    """Revoke an API key"""
    pass

@router.get("/analytics")
async def get_embed_analytics(
    api_key_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get embed usage analytics"""
    pass
```

---

## Part 3: Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

1. **Database Setup**
   - [ ] Create migration for share_links table
   - [ ] Create migration for embed_api_keys table
   - [ ] Create migration for analytics tables
   - [ ] Set up indexes

2. **Backend API**
   - [ ] Implement share link CRUD endpoints
   - [ ] Implement embed key management endpoints
   - [ ] Add rate limiting middleware
   - [ ] Add domain validation middleware

### Phase 2: Share Links (Week 2-3)

3. **Share Link System**
   - [ ] Create /s/[code] dynamic route
   - [ ] Build SharedAgentView component
   - [ ] Implement analytics tracking
   - [ ] Add share link management UI

4. **Testing**
   - [ ] Unit tests for API endpoints
   - [ ] Integration tests for share flow
   - [ ] Load testing for concurrent links

### Phase 3: Web Embedding (Week 3-4)

5. **JavaScript SDK**
   - [ ] Build tncb-agent.js SDK
   - [ ] Create embed widget page
   - [ ] Implement postMessage communication
   - [ ] Add theming support

6. **Documentation**
   - [ ] SDK documentation
   - [ ] Integration guide
   - [ ] Code examples

### Phase 4: Mobile SDKs (Week 4-6)

7. **Flutter SDK**
   - [ ] Create tncb_voice_agent package
   - [ ] Implement LiveKit integration
   - [ ] Build widget components
   - [ ] Publish to pub.dev

8. **React Native SDK (Optional)**
   - [ ] Create @tncb/voice-agent package
   - [ ] Implement native modules
   - [ ] Build React components

### Phase 5: Polish & Launch (Week 6-7)

9. **Admin Dashboard**
   - [ ] Share link management page
   - [ ] API key management page
   - [ ] Analytics dashboard

10. **Security Review**
    - [ ] Penetration testing
    - [ ] Rate limit tuning
    - [ ] Domain validation audit

---

## Part 4: Security Considerations

### 4.1 Share Links

- **Short-lived tokens**: Participant tokens expire after 15 minutes
- **Usage limits**: Optional max_uses per link
- **Expiration**: Optional expires_at timestamp
- **Domain whitelisting**: Restrict which domains can use a link
- **Rate limiting**: Per-link rate limits to prevent abuse

### 4.2 Embed API

- **API key rotation**: Support for key regeneration
- **Domain validation**: Check Origin/Referer headers
- **CORS configuration**: Strict origin policies
- **Rate limiting**: Per-key and per-IP limits
- **Monthly quotas**: Session limits for billing
- **Audit logging**: Track all API key usage

### 4.3 General

- **Input validation**: Sanitize all user inputs
- **XSS prevention**: Content Security Policy headers
- **HTTPS only**: Enforce TLS for all connections
- **Token encryption**: Encrypt sensitive data at rest

---

## Part 5: Monitoring & Analytics

### 5.1 Metrics to Track

**Share Links:**
- Total links created
- Active vs expired links
- Usage by link
- Geographic distribution
- Conversion rate (views → sessions)

**Embeddings:**
- Active API keys
- Sessions per key
- Platform distribution (web/flutter/react-native)
- Average session duration
- Error rates

### 5.2 Dashboards

```typescript
// Analytics data structure
interface ShareAnalytics {
  totalLinks: number;
  activeLinks: number;
  totalSessions: number;
  sessionsToday: number;
  topLinks: Array<{
    id: string;
    name: string;
    uses: number;
  }>;
  sessionsByDay: Array<{
    date: string;
    count: number;
  }>;
  geographicDistribution: Array<{
    country: string;
    count: number;
  }>;
}

interface EmbedAnalytics {
  totalApiKeys: number;
  activeApiKeys: number;
  totalSessions: number;
  sessionsByPlatform: {
    web: number;
    flutter: number;
    reactNative: number;
  };
  topDomains: Array<{
    domain: string;
    sessions: number;
  }>;
  usageByDay: Array<{
    date: string;
    sessions: number;
  }>;
}
```

---

## Summary

This implementation plan provides:

1. **Shareable Links**: Simple URL-based sharing with tracking, expiration, and usage limits
2. **Web Embedding**: JavaScript SDK for easy website integration
3. **Flutter SDK**: Native Flutter package for mobile apps
4. **API Management**: Secure API key system with rate limiting and analytics
5. **Analytics**: Comprehensive tracking for usage and engagement

The architecture is designed to be:
- **Scalable**: Handles multiple concurrent embedded instances
- **Secure**: API keys, domain validation, rate limiting
- **Customizable**: Theming, branding, custom greetings
- **Observable**: Full analytics and monitoring
