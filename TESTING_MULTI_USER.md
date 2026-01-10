# Quick Multi-User Testing Guide

## Test Your Multi-Customer System

### Quick Test (2 Minutes)

1. **Open Customer A** (Browser 1 - Chrome):
   ```
   http://localhost:3000
   ```
   - Click "Start Call"
   - Say: "Hello, I need help with my account"

2. **Open Customer B** (Browser 2 - Firefox or Chrome Incognito):
   ```
   http://localhost:3000
   ```
   - Click "Start Call"
   - Say: "Can you tell me about loan options?"

3. **Verify Isolation**:
   - Customer A hears only their agent (talking about accounts)
   - Customer B hears only their agent (talking about loans)
   - No audio crossover

### Verify Process Isolation

Run this command while both customers are connected:

```powershell
Get-Process python | Where-Object {$_.ProcessName -eq "python"} | Select-Object Id,WorkingSet64,StartTime | Format-Table
```

**Expected Result**: You'll see multiple Python processes, each handling one customer.

### Check Room Assignments

Open browser console (F12) on both customer browsers and look for:

```
Customer A Console:
roomName: "voice_assistant_room_4521"

Customer B Console:
roomName: "voice_assistant_room_7832"
```

Different room numbers = complete isolation ✅

### Load Test (10+ Concurrent Users)

Use this PowerShell script to simulate 10 customers:

```powershell
# Open 10 browser windows simultaneously
1..10 | ForEach-Object {
    Start-Process "http://localhost:3000" -WindowStyle Normal
}
```

**What to watch**:
- Check memory: `docker stats`
- Check processes: `Get-Process python`
- Each customer should connect within 1-2 seconds

### Performance Monitoring

```powershell
# See all agent processes with memory usage
Get-Process python | Where-Object {$_.WorkingSet -gt 100MB} | Sort-Object WorkingSet -Descending | Format-Table ProcessName,Id,@{Label="Memory(MB)";Expression={[math]::Round($_.WorkingSet/1MB,2)}}

# Expected output (with 3 customers):
ProcessName    Id Memory(MB)
-----------    -- ----------
python      40428    1234.56
python      40512    1198.23
python      40648    1205.87
```

## System Status Commands

### Check All Services
```bash
# LiveKit (WebRTC server)
docker logs ai-voice-agent-livekit-1 --tail 20

# Agent Worker
ps aux | grep "agent.py" | grep -v grep

# Frontend
curl http://localhost:3000 -I
```

### Check Database Sessions
```bash
# Connect to PostgreSQL
psql -h localhost -U postgres -d voice_agent

# See active sessions
SELECT session_id, room_id, participant_id, created_at
FROM conversation_sessions
WHERE ended_at IS NULL;
```

## Troubleshooting

### Problem: Second customer can't connect

**Check**: Agent worker has enough idle processes

```bash
# See agent worker configuration
grep "num_idle_processes" agent/agent.py

# Increase if needed (edit .env):
WORKER_IDLE_PROCESSES=5
```

Then restart:
```bash
./restart.sh
```

### Problem: Customers hearing each other

**This should NEVER happen** due to room isolation. If it does:

1. Check room names are unique:
   - Open browser console on both customers
   - Verify `roomName` is different

2. Restart LiveKit:
   ```bash
   docker restart ai-voice-agent-livekit-1
   ```

### Problem: High memory usage

**Normal**: Each agent uses ~1.5GB RAM

**Solution**: For many concurrent users:
1. Increase server RAM, OR
2. Run multiple agent workers on different servers

## Success Criteria

Your system is working correctly when:

✅ Each customer connects within 1-2 seconds  
✅ Each customer has a unique room ID  
✅ Multiple Python agent processes are running  
✅ No audio crossover between customers  
✅ Each conversation is saved to database with unique session_id  
✅ Memory usage is stable (~1.5GB per active customer)  

## Ready to Test!

Your system is **production-ready** for multiple concurrent customers. Start testing with 2-3 users first, then scale up!

**Quick Start**:
```bash
./start.sh
```

**Access**: http://localhost:3000

**Monitor**: Watch terminal for agent logs showing multiple rooms connecting.
