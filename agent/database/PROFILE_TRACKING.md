# User Profile & Conversation Tracking System

## Overview

Production-ready solution for tracking ALL conversations with both anonymous and authenticated users. Creates unique profiles for every user, saves conversations, and generates AI summaries on call end.

## Features

✅ **Anonymous User Tracking** - Every user gets a unique profile (even without authentication)
✅ **Conversation Saving** - All messages saved to database per profile  
✅ **Auto-Summarization** - AI-generated summary on call end with extracted profile info
✅ **Profile Merging** - Anonymous profiles merge into authenticated accounts seamlessly
✅ **Banking Question Detection** - RAG only triggers for banking queries
✅ **Future Profile Recognition** - Identify returning users from conversation patterns

## Database Schema

### New Tables

1. **`user_profiles`** - Both authenticated and anonymous users
   - `id` (UUID) - Unique profile ID
   - `profile_type` - 'authenticated' or 'anonymous'
   - `anonymous_id` - Device/browser fingerprint
   - `username`, `phone_number`, `email` - For authenticated users
   - `profile_metadata` - Extracted info from conversations (JSONB)
   - `total_sessions`, `total_messages` - Usage stats
   - `merged_into_profile_id` - Links merged anonymous profiles

2. **`conversation_summaries`** - AI-generated conversation summaries
   - `session_id`, `profile_id` - Links to session and profile
   - `summary` - AI-generated summary
   - `extracted_info` - Name, intent, topics (JSONB)
   - `sentiment` - positive/neutral/negative
   - `resolution_status` - resolved/escalated/incomplete
   - `topics` - Array of discussed topics
   - `message_count`, `duration_seconds` - Metrics

### Updated Tables

- **`agent_sessions`** - Added `profile_id` to link sessions to profiles

## How It Works

### 1. User Connects (Anonymous)

```
User joins call
→ System creates/finds anonymous profile using participant_id
→ Session linked to profile_id
→ Conversations start saving to database
```

### 2. User Authenticates

```python
# When user logs in with username/password
await session_manager.authenticate_user(
    session_id=session.session_id,
    username="john_doe",
    phone_number="+263771234567"
)
```

**What happens:**
- Creates/finds authenticated profile
- Merges anonymous profile history into authenticated profile
- All past conversations now linked to authenticated user
- Future sessions will use authenticated profile

### 3. Call Ends

```
User disconnects
→ System generates conversation summary
→ Extracts profile metadata (name, preferences, topics)
→ Updates user profile with learned information
→ Saves to conversation_summaries table
```

## Installation

### 1. Run Migration

```powershell
# From agent directory
psql -U postgres -d voice_agent -f database/migrate_profiles.sql
```

This adds:
- ✓ `user_profiles` table
- ✓ `conversation_summaries` table  
- ✓ `profile_id` column to `agent_sessions`
- ✓ Triggers for auto-updating stats
- ✓ `merge_profiles()` function

### 2. Verify Tables

```sql
-- Check new tables exist
\dt

-- Should show:
-- agent_instructions
-- agent_sessions
-- conversation_messages
-- rag_documents
-- system_config
-- user_profiles ← NEW
-- conversation_summaries ← NEW
```

## Usage Examples

### Query User Profile History

```python
from database.repository import ProfileRepository, ConversationSummaryRepository

profile_repo = ProfileRepository(db_pool)
summary_repo = ConversationSummaryRepository(db_pool)

# Get profile
profile = await profile_repo.get_by_username("john_doe")

# Get all conversations for this user
summaries = await summary_repo.get_by_profile(
    profile_id=profile['id'],
    limit=10
)

for summary in summaries:
    print(f"Session: {summary['session_id']}")
    print(f"Summary: {summary['summary']}")
    print(f"Topics: {summary['topics']}")
    print(f"Sentiment: {summary['sentiment']}")
    print(f"Extracted: {summary['extracted_info']}")
```

### Find Returning Anonymous Users

```python
# User returns with same device
profile = await profile_repo.get_by_anonymous_id("device_abc123")

if profile:
    print(f"Welcome back! You have {profile['total_sessions']} previous sessions")
    # Load conversation history
    summaries = await summary_repo.get_by_profile(profile['id'])
```

### Manual Profile Merge

```sql
-- Merge anonymous profile into authenticated one
SELECT merge_profiles(
    'anonymous-profile-uuid'::uuid,
    'authenticated-profile-uuid'::uuid
);
```

## Conversation Summary Example

```json
{
  "summary": "User inquired about cardless withdrawal. Provided USSD code *236# and instructions. User thanked agent. Query resolved.",
  "extracted_info": {
    "user_name": "Sarah",
    "primary_intent": "cardless_withdrawal",
    "authentication_attempted": false
  },
  "sentiment": "positive",
  "resolution_status": "resolved",
  "topics": [
    "cardless_withdrawal",
    "banking_hours"
  ],
  "message_count": 8,
  "duration_seconds": 142
}
```

## Configuration

No additional `.env` variables needed! Works with existing configuration.

Optional: Enable LLM-based summarization (more detailed summaries):

```python
# In database/conversation_summary.py
# Pass an LLM provider to ConversationSummarizer
summarizer = ConversationSummarizer(llm_provider=your_openai_client)
```

## Benefits

1. **Track Every Conversation** - Never lose user interaction data
2. **Identify Returning Users** - Even anonymous ones
3. **Build User Profiles** - Learn from each conversation
4. **Merge on Authentication** - Seamless transition from anonymous to authenticated
5. **Compliance Ready** - Full audit trail of conversations
6. **Analytics** - Sentiment, topics, resolution rates
7. **Personalization** - Use past conversations to improve future interactions

## API Reference

### SessionManager Methods

```python
# Create session with anonymous profile
session = await session_manager.create_session(
    room_id="room123",
    participant_id="participant456",
    anonymous_id="device_fingerprint_xyz"  # Optional
)

# Authenticate user (merges profiles)
success = await session_manager.authenticate_user(
    session_id=session.session_id,
    username="john_doe",
    phone_number="+263771234567"
)

# End session (auto-generates summary)
await session_manager.end_session(
    session_id=session.session_id,
    generate_summary=True  # Default: True
)
```

### ProfileRepository Methods

```python
profile_repo = ProfileRepository(db_pool)

# Create anonymous profile
profile_id = await profile_repo.create_anonymous_profile(
    anonymous_id="device123",
    metadata={"first_seen": "2025-12-30"}
)

# Create authenticated profile
profile_id = await profile_repo.create_authenticated_profile(
    username="john_doe",
    phone_number="+263771234567",
    email="john@example.com"
)

# Get profile
profile = await profile_repo.get_by_id(profile_id)
profile = await profile_repo.get_by_anonymous_id("device123")
profile = await profile_repo.get_by_username("john_doe")

# Update metadata
await profile_repo.update_metadata(
    profile_id=profile_id,
    metadata={"preferred_language": "en", "name": "John"}
)

# Merge profiles
await profile_repo.merge_anonymous_to_authenticated(
    anonymous_profile_id="uuid1",
    authenticated_profile_id="uuid2"
)
```

### ConversationSummaryRepository Methods

```python
summary_repo = ConversationSummaryRepository(db_pool)

# Get summary for session
summary = await summary_repo.get_by_session(session_id)

# Get all summaries for user
summaries = await summary_repo.get_by_profile(
    profile_id=profile_id,
    limit=10
)
```

## Database Queries

```sql
-- Get all anonymous users who haven't authenticated
SELECT id, anonymous_id, total_sessions, total_messages, last_seen_at
FROM user_profiles
WHERE profile_type = 'anonymous' AND merged_into_profile_id IS NULL
ORDER BY total_sessions DESC;

-- Get conversation summaries with positive sentiment
SELECT s.summary, s.topics, p.username, s.created_at
FROM conversation_summaries s
JOIN user_profiles p ON s.profile_id = p.id
WHERE s.sentiment = 'positive'
ORDER BY s.created_at DESC
LIMIT 10;

-- Get users by topic discussed
SELECT DISTINCT p.id, p.username, p.anonymous_id
FROM conversation_summaries s
JOIN user_profiles p ON s.profile_id = p.id
WHERE 'cardless_withdrawal' = ANY(s.topics);

-- User engagement stats
SELECT 
    profile_type,
    COUNT(*) as total_users,
    AVG(total_sessions) as avg_sessions_per_user,
    AVG(total_messages) as avg_messages_per_user
FROM user_profiles
WHERE merged_into_profile_id IS NULL
GROUP BY profile_type;
```

## Next Steps

1. ✅ Run migration SQL
2. ✅ Test anonymous session creation
3. ✅ Make a test call and verify conversation saving
4. ✅ End call and check conversation summary generated
5. ⬜ Implement authentication flow in your banking tools
6. ⬜ Add device fingerprinting in front-end for better anonymous tracking
7. ⬜ Build analytics dashboard using conversation_summaries data

## Notes

- RAG still only triggers for banking questions (balance, transfers, USSD, etc.)
- General chat conversations are saved but don't search knowledge base
- Summaries are generated using rule-based extraction (fast, no LLM needed)
- Can upgrade to LLM-based summaries for better quality
- All profile operations are async and non-blocking
- Auto-cleanup of stale sessions after 30 minutes (configurable)
