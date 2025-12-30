# Strict Knowledge Base & Tool Notifications - Implementation Summary

## Overview
This update implements strict knowledge base enforcement, permission-based web search, conversation timing, and tool notification system.

## Changes Made

### 1. Backend - Agent Behavior (agent/agent.py)

#### Modified `_augment_chat_context` method:
- Now returns the RAG context string for validation
- Allows checking if RAG found relevant information

#### Updated `on_user_turn_completed` method:
- Detects when RAG finds no information and asks permission for web search
- Checks for user approval/denial of web search permission
- Tracks permission state in user session

### 2. Backend - Instructions Update (database/update_instructions_strict.sql)

Added strict information policy to agent instructions:
```
# Strict Information Policy
- ONLY use information from knowledge base for banking questions
- If knowledge base has no information, ask: "I don't have that information in my knowledge base. Would you like me to search the internet?"
- ONLY use search_web tool AFTER receiving explicit permission
- For general conversation (greetings, etc.), respond naturally
- Be polite and professional always
```

### 3. Backend - Session Tracking (agent/session_manager.py)

#### Updated `UserSession` class:
- Added `waiting_for_search_permission` flag
- Added `web_search_approved` flag
- Added `pending_search_query` field
- Added `get_duration_seconds()` method to calculate session duration

#### Updated `end_session` method:
- Calculates session duration before ending
- Passes duration to database repository

### 4. Backend - Database Schema (database/add_duration_column.sql)

Added to `agent_sessions` table:
```sql
ALTER TABLE agent_sessions ADD COLUMN duration_seconds INTEGER;
```

### 5. Backend - Repository (database/repository.py)

Updated `SessionRepository.end_session()`:
- Now accepts optional `duration_seconds` parameter
- Saves conversation duration to database

### 6. Backend - Tools (agent/tools.py)

Enhanced `search_web` tool:
- Checks `user_session.web_search_approved` before executing
- Returns error if permission not granted
- Sends notifications to frontend:
  - `tool_started`: When search begins
  - `tool_success`: When search completes successfully
  - `tool_error`: When search fails or permission denied

### 7. Frontend - Conversation Timer (components/app/conversation-timer.tsx)

New component that:
- Displays live conversation duration (MM:SS format)
- Uses red pulsing dot indicator
- Automatically starts/stops with session
- Positioned after theme toggle in header

### 8. Frontend - Tool Notifications (components/app/tool-notification-listener.tsx)

New component that:
- Listens for tool notifications via LiveKit data channel
- Displays toast notifications using Sonner:
  - Info toast for `tool_started`
  - Success toast for `tool_success`
  - Error toast for `tool_error`
- Includes tool name and descriptive messages

### 9. Frontend - Layout Update (app/(app)/layout.tsx)

- Added `ConversationTimer` component after `ThemeToggle`
- Timer appears in top-left header area

### 10. Frontend - App Update (components/app/app.tsx)

- Added `ToolNotificationListener` to AppSetup
- Added `SonnerToaster` component for displaying notifications
- Position: top-right with rich colors

## How It Works

### Permission Flow:
1. User asks a banking question
2. Agent searches knowledge base via RAG
3. If RAG finds information → Agent answers from knowledge base
4. If RAG finds nothing:
   - Agent asks: "I don't have that information in my knowledge base. Would you like me to search the internet?"
   - Sets `user_session.waiting_for_search_permission = True`
5. User responds:
   - "Yes/Okay/Sure" → `web_search_approved = True`, search executes
   - "No/Nope" → `web_search_approved = False`, agent declines politely
6. If web search is called without permission → Returns error, notifies frontend

### Conversation Timer:
- Starts when user connects to voice session
- Updates every second
- Displays in header (top-left after theme toggle)
- Saves duration to database when session ends

### Tool Notifications:
- Backend sends notifications via LiveKit data channel
- Format: `{type: "notification", event: "tool_success|tool_error|tool_started", data: {...}}`
- Frontend listens and displays toasts
- Success = green, Error = red, Info = blue
- Auto-dismiss after 3-5 seconds

## Database Changes

Run migrations:
```bash
psql -U postgres -d voice_agent -f database/update_instructions_strict.sql
psql -U postgres -d voice_agent -f database/add_duration_column.sql
```

## Testing

1. **Test Permission Flow:**
   - Ask: "What is the mobile banking PIN?"
   - Agent should ask permission to search internet
   - Try "yes" and "no" responses

2. **Test Timer:**
   - Connect to voice session
   - Verify timer appears in top-left
   - Check it counts up correctly

3. **Test Notifications:**
   - Grant web search permission
   - Verify toast appears when search starts
   - Verify success toast when complete
   - Try denying permission to see error toast

## Files Modified

### Backend:
- `agent/agent.py`
- `agent/session_manager.py`
- `agent/tools.py`
- `agent/database/repository.py`
- `agent/database/update_instructions_strict.sql` (new)
- `agent/database/add_duration_column.sql` (new)

### Frontend:
- `front-end/components/app/app.tsx`
- `front-end/app/(app)/layout.tsx`
- `front-end/components/app/conversation-timer.tsx` (new)
- `front-end/components/app/tool-notification-listener.tsx` (new)

## Benefits

1. **More Reliable**: Agent only provides verified information from knowledge base
2. **User Control**: Users explicitly approve internet searches
3. **Transparency**: Users see tool activity via notifications
4. **Metrics**: Conversation duration tracked for analytics
5. **Better UX**: Clear visual feedback for timing and tool actions
