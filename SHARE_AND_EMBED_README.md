# Share Links & Embedding System

This document describes the complete implementation of shareable links and embedding functionality for the TNCB Voice Agent.

## Overview

The system provides two ways to share the voice agent:

1. **Share Links** - Generate unique URLs (e.g., `https://yourdomain.com/s/abc123`) that can be shared directly
2. **Embedding** - Embed the voice agent on external websites and mobile apps using SDKs

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                      │
├──────────────────┬──────────────────┬───────────────────────┤
│  /s/[code]       │  /embed/widget   │  /admin               │
│  Share Pages     │  Widget Page     │  Management UI        │
└────────┬─────────┴────────┬─────────┴───────────┬───────────┘
         │                  │                     │
         ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   API Routes (Next.js)                       │
│  /api/connection-details (supports share/embed auth)         │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent API (Python)                        │
├──────────────────────────────┬──────────────────────────────┤
│  /api/share-links            │  /api/embed-keys             │
│  /api/share/{code}           │  /api/embed/config           │
│                              │  /api/embed/session          │
└──────────────────────────────┴──────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL Database                       │
│  share_links, share_link_analytics                          │
│  embed_api_keys, embed_sessions                             │
└─────────────────────────────────────────────────────────────┘
```

## Database Schema

### Tables

1. **share_links** - Store share link configurations
   - `code` - Unique 8-character alphanumeric code
   - `name`, `description` - Administrative metadata
   - `custom_greeting` - Optional custom greeting for shared sessions
   - `branding` - JSON object with logo_url, primary_color, company_name
   - `expires_at` - Optional expiration date
   - `max_sessions` - Optional session limit
   - `is_active` - Enable/disable toggle

2. **share_link_analytics** - Track share link usage
   - `share_link_id` - Foreign key to share_links
   - `user_agent`, `ip_address`, `referrer` - Request metadata
   - `session_started`, `session_duration`, `messages_count` - Usage metrics

3. **embed_api_keys** - Store embed API keys
   - `key_hash` - SHA-256 hash of the API key
   - `key_prefix` - First 8 characters for identification
   - `name`, `description` - Administrative metadata
   - `allowed_domains` - Array of allowed domains (CORS)
   - `widget_config` - JSON object with position, theme, size, etc.
   - `rate_limit_per_hour`, `rate_limit_per_day` - Rate limiting

4. **embed_sessions** - Track embed sessions
   - `embed_key_id` - Foreign key to embed_api_keys
   - `session_token` - Unique session identifier
   - `origin` - Domain where widget is embedded
   - `status` - active, completed, error
   - Session metrics (duration, messages)

### Migration

Run the migration:

```bash
psql -d your_database -f agent/database/share_and_embed.sql
```

## API Endpoints

### Share Links Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/share-links` | List all share links |
| POST | `/api/share-links` | Create new share link |
| GET | `/api/share-links/{id}` | Get share link by ID |
| PUT | `/api/share-links/{id}` | Update share link |
| DELETE | `/api/share-links/{id}` | Delete share link |
| GET | `/api/share/{code}` | **Public** - Get share link by code |

### Embed Keys Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/embed-keys` | List all embed keys |
| POST | `/api/embed-keys` | Create new embed key |
| GET | `/api/embed-keys/{id}` | Get embed key by ID |
| PUT | `/api/embed-keys/{id}` | Update embed key |
| DELETE | `/api/embed-keys/{id}` | Delete embed key |
| POST | `/api/embed-keys/{id}/regenerate` | Regenerate API key |
| GET | `/api/embed/config` | **Public** - Get widget config (requires API key) |
| POST | `/api/embed/session` | **Public** - Create embed session |

## Usage

### Share Links

1. **Create a share link** in the admin dashboard at `/admin`
2. **Copy the generated URL** (e.g., `https://yourdomain.com/s/abc123`)
3. **Share the URL** - Users can access the voice agent directly

### JavaScript SDK (Web Embedding)

Add to your website:

```html
<script src="https://yourdomain.com/embed/tncb-agent.js"></script>
<script>
  TNCBAgent.init({
    apiKey: 'your-api-key',
    serverUrl: 'https://yourdomain.com',
    position: 'bottom-right',
    theme: 'light'
  });
</script>
```

#### SDK API

```javascript
// Open/close the widget
TNCBAgent.open();
TNCBAgent.close();
TNCBAgent.toggle();

// Show/hide the FAB button
TNCBAgent.show();
TNCBAgent.hide();

// Change position dynamically
TNCBAgent.setPosition('bottom-left');

// Listen to events
TNCBAgent.on('open', () => console.log('Widget opened'));
TNCBAgent.on('close', () => console.log('Widget closed'));
TNCBAgent.on('sessionStart', (sessionId) => console.log('Session started:', sessionId));
TNCBAgent.on('sessionEnd', () => console.log('Session ended'));
TNCBAgent.on('error', (error) => console.error('Error:', error));

// Clean up
TNCBAgent.destroy();
```

### Flutter SDK (Mobile Embedding)

Add to your `pubspec.yaml`:

```yaml
dependencies:
  tncb_voice_agent:
    path: path/to/flutter_sdk/tncb_voice_agent
```

#### Basic Usage

```dart
import 'package:tncb_voice_agent/tncb_voice_agent.dart';

// Initialize the SDK
await TNCBVoiceAgent.instance.init(
  apiKey: 'your-api-key',
  baseUrl: 'https://yourdomain.com',
);

// Use the FAB widget
Stack(
  children: [
    YourContent(),
    TNCBVoiceAgentFAB(
      position: FABPosition.bottomRight,
      onSessionEnd: (duration, messages) {
        print('Session ended: $duration seconds, $messages messages');
      },
    ),
  ],
)
```

#### Full-screen Widget

```dart
TNCBVoiceAgentWidget(
  onStateChange: (state) {
    print('State changed: $state');
  },
  onError: (error) {
    print('Error: $error');
  },
  onSessionEnd: (duration, messages) {
    print('Session ended');
  },
)
```

## Admin Dashboard

Access the admin dashboard at `/admin` to:

- **Share Links Tab**
  - Create, edit, delete share links
  - Configure custom greetings and branding
  - Set expiration dates and session limits
  - View usage statistics
  - Copy shareable URLs

- **Embed Keys Tab**
  - Create, edit, delete API keys
  - Configure allowed domains
  - Set widget appearance (position, theme, size)
  - Configure rate limits
  - Regenerate API keys
  - Copy embed code snippets

## Configuration

### Environment Variables

Add to your `.env.local`:

```bash
# Agent API URL (for share/embed validation)
AGENT_API_URL=http://localhost:8000
```

### Connection Details Route

The `/api/connection-details` route now supports:

1. **Share link access** - Pass `share_code` in the request body
2. **Embed access** - Pass `X-API-Key` and optionally `X-Embed-Session` headers

## Security

### Share Links

- Unique 8-character codes with 62^8 possible combinations
- Optional expiration dates
- Optional session limits
- Can be deactivated without deletion

### Embed Keys

- API keys are hashed (SHA-256) before storage
- Domain whitelisting (CORS)
- Rate limiting (per hour and per day)
- Session tracking and validation

## Analytics

Both share links and embed keys track:

- Access count and unique visitors
- Session count and total duration
- Message count
- Geographic and device information (via user agent)
- Referrer URLs

## Files Created/Modified

### New Files

```
agent/
├── api/
│   ├── __init__.py
│   ├── share_routes.py
│   └── embed_routes.py
├── database/
│   └── share_and_embed.sql

front-end/
├── app/
│   ├── s/[code]/
│   │   ├── page.tsx
│   │   └── layout.tsx
│   ├── embed/widget/
│   │   ├── page.tsx
│   │   └── layout.tsx
│   └── admin/
│       ├── page.tsx
│       └── layout.tsx
├── components/admin/
│   ├── share-link-manager.tsx
│   └── embed-key-manager.tsx
└── public/embed/
    └── tncb-agent.js

flutter_sdk/
└── tncb_voice_agent/
    ├── pubspec.yaml
    └── lib/
        ├── tncb_voice_agent.dart
        └── src/
            ├── tncb_voice_agent.dart
            ├── voice_agent_widget.dart
            ├── voice_agent_fab.dart
            └── models/
                ├── agent_config.dart
                └── session_state.dart
```

### Modified Files

```
agent/database/
├── models.py (added share/embed models)
└── repository.py (added share/embed repositories)

front-end/app/api/connection-details/
└── route.ts (added share/embed authentication)
```

## Next Steps

1. **Register API routes** - Add the share and embed routes to your agent's main application
2. **Run migrations** - Execute the SQL migration to create database tables
3. **Configure CORS** - Ensure your API allows requests from embedded domains
4. **Test share links** - Create a share link and verify access works
5. **Test embedding** - Create an API key and test the JavaScript SDK on a test page
