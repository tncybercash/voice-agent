# Testing Guide for Strict Knowledge Base & Notifications

## Prerequisites
- Agent running with updated code
- Frontend running
- Database migrations applied

## Test 1: Strict Knowledge Base Enforcement

### Scenario A: Question in Knowledge Base
**Ask:** "What is the USSD code for banking?"
**Expected:**
- Agent answers: "*236#" (from knowledge base)
- No web search permission request
- Response is quick and confident

### Scenario B: Question NOT in Knowledge Base  
**Ask:** "What is the weather today?"
**Expected:**
1. Agent responds: "I don't have that information in my knowledge base. Would you like me to search the internet for this information?"
2. Timer should be visible and counting
3. No toast notification yet (waiting for permission)

## Test 2: Permission Flow - Approval

**After agent asks permission:**
**Say:** "Yes, please search"
**Expected:**
1. Blue info toast appears: "Searching the web for: What is the weather today"
2. Brief pause while search executes
3. Green success toast: "Web search completed successfully"
4. Agent provides answer from web search

## Test 3: Permission Flow - Denial

**Ask:** "What are the current loan rates?"
**Expected:** Agent asks permission

**Say:** "No, don't search"
**Expected:**
- Agent responds politely: "I understand. Is there anything else from my knowledge base I can help you with?"
- No search executed
- No tool notifications

## Test 4: Unauthorized Search Attempt

This test checks if the agent incorrectly tries to search without permission.

**Expected Behavior:**
- If agent tries search_web without approval
- Red error toast appears: "Web search attempted without user permission"
- Search is blocked

## Test 5: Conversation Timer

### Part A: Timer Start
1. Connect to agent (click "Start Call")
2. **Expected:** Timer appears in top-left (after theme toggle)
3. Format: `00:00` with red pulsing dot
4. Timer should increment every second

### Part B: Timer During Conversation
1. Have a 2-minute conversation
2. **Expected:** Timer shows `02:00` or higher
3. Timer should be visible throughout

### Part C: Timer Persistence
1. Check database after ending session:
```sql
SELECT session_id, duration_seconds, ended_at 
FROM agent_sessions 
ORDER BY ended_at DESC 
LIMIT 5;
```
2. **Expected:** Recent session has duration_seconds filled (e.g., 120 for 2 minutes)

## Test 6: Multiple Tool Notifications

1. Ask question requiring web search
2. Approve search
3. **Expected toast sequence:**
   - Blue info: "Searching the web..."
   - Green success: "Web search completed successfully"

4. Ask another question
5. Approve search again
6. **Expected:** New toasts appear, old ones fade out

## Test 7: Knowledge Base Questions (No Notifications)

**Ask series of banking questions:**
- "What is mobile banking?"
- "How do I transfer money?"
- "What are the transaction limits?"

**Expected:**
- All answered from knowledge base
- No permission requests
- No tool notifications (RAG doesn't send notifications)
- Only web search sends notifications

## Visual Checks

### Header Layout (Top-Left)
Expected order:
1. Company icon
2. Theme toggle button
3. **Conversation timer** (when connected)

### Timer Styling
- Rounded pill shape
- Semi-transparent background with blur
- Red pulsing dot on left
- Monospace font for time
- Format: MM:SS

### Toast Notifications (Top-Right)
- **Info (blue):** Tool starting
- **Success (green):** Tool completed
- **Error (red):** Tool failed/denied
- Auto-dismiss after 3-5 seconds
- Multiple toasts stack vertically

## Error Scenarios

### Database Connection Lost
1. Stop PostgreSQL
2. Ask banking question
3. **Expected:** 
   - Agent may fail gracefully
   - Error in logs, but no crash
   - Timer still works (client-side)

### RAG Service Unavailable
1. Stop Ollama
2. Ask banking question
3. **Expected:**
   - Agent asks permission (RAG returned nothing)
   - Warning in logs
   - Flow continues normally

## Performance Checks

### Timer Accuracy
1. Start conversation
2. Use phone stopwatch
3. Compare after 5 minutes
4. **Expected:** Within ±2 seconds

### Notification Latency
1. Approve web search
2. Measure time from approval to "Searching..." toast
3. **Expected:** < 500ms

### Database Write
1. End session
2. Check database immediately
3. **Expected:** duration_seconds written within 1 second

## Common Issues & Solutions

### Timer Not Appearing
- Check: Is session connected?
- Check: Browser console for errors
- Fix: Hard refresh (Ctrl+Shift+R)

### Notifications Not Showing
- Check: Browser console for "dataReceived" events
- Check: Sonner library loaded (network tab)
- Fix: Clear cache and rebuild frontend

### Permission Not Detected
- Check: Agent logs for "User approved/declined web search"
- Check: user_session attributes exist
- Fix: Restart agent with updated code

### Duration Not Saved
- Check: Database logs for end_session query
- Check: Column exists: `\d agent_sessions`
- Fix: Run migration: `add_duration_column.sql`

## Success Criteria

✅ All knowledge base questions answered without permission
✅ Unknown questions trigger permission request
✅ "Yes" responses enable web search
✅ "No" responses are respected
✅ Timer visible and accurate
✅ Tool notifications appear at correct times
✅ Duration saved to database
✅ No crashes or errors in logs
