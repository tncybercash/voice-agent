import os
import json
import logging
import httpx
import asyncio
import smtplib
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from livekit.agents import function_tool, RunContext, get_job_context, ToolError
from langchain_community.tools import DuckDuckGoSearchRun

logger = logging.getLogger(__name__)

# ============================================
# SESSION STATE MANAGEMENT
# ============================================
@dataclass
class SessionState:
    bank_api_token: str = ""
    current_user: dict = field(default_factory=dict)
    user_profile: dict = field(default_factory=lambda: {"profile": None, "divisionId": None, "divisions": []})
    awaiting_division_choice: bool = False
    # Unlock flow state
    unlock_uuid: str = ""
    unlock_verified_otp: bool = False
    unlock_question_verified: bool = False
    unlock_question_attempts: int = 0
    unlock_question_id: Optional[int] = None

    def reset(self):
        self.bank_api_token = ""
        self.current_user = {}
        self.user_profile = {"profile": None, "divisionId": None, "divisions": []}
        self.awaiting_division_choice = False
        self.unlock_uuid = ""
        self.unlock_verified_otp = False
        self.unlock_question_verified = False
        self.unlock_question_attempts = 0
        self.unlock_question_id = None

    def is_authenticated(self) -> bool:
        return bool(self.bank_api_token)

def get_session_state(context: RunContext) -> SessionState:
    try:
        userdata = context.userdata
        if userdata is None:
            userdata = {}
            context.userdata = userdata
    except (ValueError, AttributeError):
        logger.warning("context.userdata not available, using fallback session state")
        return SessionState()
    if 'session_state' not in userdata:
        userdata['session_state'] = SessionState()
        logger.info("Created new session state for user")
    return userdata['session_state']

def parse_natural_date(date_str: str) -> str:
    """Parse natural language date strings into YYYY-MM-DD format"""
    try:
        # Simple parsing for common formats
        date_str = date_str.lower().strip()
        today = datetime.now()

        if 'today' in date_str:
            return today.strftime('%Y-%m-%d')
        elif 'yesterday' in date_str:
            yesterday = today - timedelta(days=1)
            return yesterday.strftime('%Y-%m-%d')
        elif 'last week' in date_str:
            last_week = today - timedelta(weeks=1)
            return last_week.strftime('%Y-%m-%d')
        elif 'last month' in date_str:
            last_month = today - timedelta(days=30)
            return last_month.strftime('%Y-%m-%d')
        else:
            # Try to parse as direct date
            parsed = datetime.strptime(date_str, '%Y-%m-%d')
            return parsed.strftime('%Y-%m-%d')
    except:
        return date_str  # Return as-is if parsing fails

def format_date_for_display(date_str: str) -> str:
    """Format date string for user display"""
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        return date_obj.strftime('%B %d, %Y')
    except:
        return date_str

async def send_frontend_notification(event_type: str, data: dict):
    """Send notification to frontend via LiveKit data channel"""
    try:
        context = get_job_context()
        if context and hasattr(context, 'room'):
            notification_data = {
                "type": "notification",
                "event": event_type,
                "data": data
            }
            logger.info(f"📤 Sending notification: {event_type} - {data}")
            await context.room.local_participant.publish_data(
                json.dumps(notification_data).encode(),
                reliable=True
            )
            logger.info(f"[OK] Notification sent successfully: {event_type}")
        else:
            logger.warning(f"⚠️ Cannot send notification - no room context available")
    except Exception as e:
        logger.warning(f"Failed to send frontend notification: {e}")
        import traceback
        traceback.print_exc()

def get_bank_auth_url() -> str:
    """Get the bank authentication API URL"""
    return os.getenv("BANK_API_URL", "https://api.stewardbank.co.zw/api/open-bank/v1/auth")

def get_bank_transaction_url() -> str:
    """Get the bank transaction API URL"""
    return f"{get_bank_auth_url()}/transactions"

# ============================================
# BANKING TOOLS
# ============================================

@function_tool
async def authenticate_bank(context: RunContext, username: str, password: str) -> str:
    """Authenticate user with bank API"""
    try:
        state = get_session_state(context)
        if state.is_authenticated():
            return json.dumps({"success": False, "error": "Already authenticated"})

        url = get_bank_auth_url()
        payload = {"username": username, "password": password}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=30)
            data = response.json()

            if data.get("success"):
                token = data.get("token", "")
                user_info = data.get("user", {})
                state.bank_api_token = token
                state.current_user = user_info
                await send_frontend_notification("auth_success", {"username": username})
                return json.dumps({"success": True, "message": "Authentication successful", "user": user_info})
            else:
                error_msg = data.get("message", "Authentication failed")
                return json.dumps({"success": False, "error": error_msg})
    except Exception as e:
        logger.error(f"Bank auth error: {e}")
        return json.dumps({"success": False, "error": "Authentication service unavailable"})

@function_tool
async def select_user_profile(context: RunContext, profile_index: int = 0) -> str:
    """Select user profile if multiple divisions exist"""
    try:
        state = get_session_state(context)
        if not state.is_authenticated():
            return json.dumps({"success": False, "error": "Not authenticated"})

        if not state.user_profile.get("divisions"):
            return json.dumps({"success": False, "error": "No divisions available"})

        divisions = state.user_profile["divisions"]
        if profile_index >= len(divisions):
            return json.dumps({"success": False, "error": f"Invalid profile index. Available: 0-{len(divisions)-1}"})

        selected = divisions[profile_index]
        state.user_profile["profile"] = selected
        state.user_profile["divisionId"] = selected.get("id")
        state.awaiting_division_choice = False

        await send_frontend_notification("profile_selected", {"profile": selected})
        return json.dumps({"success": True, "message": f"Selected profile: {selected.get('name', 'Unknown')}", "profile": selected})
    except Exception as e:
        logger.error(f"Profile selection error: {e}")
        return json.dumps({"success": False, "error": "Failed to select profile"})

@function_tool
async def get_current_user_info(context: RunContext) -> str:
    """Get current authenticated user information"""
    try:
        state = get_session_state(context)
        if not state.is_authenticated():
            return json.dumps({"success": False, "error": "Not authenticated"})

        user_info = state.current_user
        profile = state.user_profile.get("profile")

        return json.dumps({
            "success": True,
            "user": user_info,
            "profile": profile,
            "division_id": state.user_profile.get("divisionId")
        })
    except Exception as e:
        logger.error(f"Get user info error: {e}")
        return json.dumps({"success": False, "error": "Failed to get user information"})

@function_tool
async def get_account_balance(context: RunContext) -> str:
    """Get account balance for authenticated user"""
    try:
        state = get_session_state(context)
        if not state.is_authenticated():
            return json.dumps({"success": False, "error": "Not authenticated"})

        url = f"{get_bank_auth_url()}/balance"
        headers = {"Authorization": f"Bearer {state.bank_api_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30)
            data = response.json()

            if data.get("success"):
                balance_info = data.get("balance", {})
                await send_frontend_notification("balance_retrieved", balance_info)
                return json.dumps({"success": True, "balance": balance_info})
            else:
                error_msg = data.get("message", "Failed to get balance")
                return json.dumps({"success": False, "error": error_msg})
    except Exception as e:
        logger.error(f"Get balance error: {e}")
        return json.dumps({"success": False, "error": "Balance service unavailable"})

@function_tool
async def get_account_statement(context: RunContext, start_date: str = "", end_date: str = "", limit: int = 20) -> str:
    """Get account statement/transactions"""
    try:
        state = get_session_state(context)
        if not state.is_authenticated():
            return json.dumps({"success": False, "error": "Not authenticated"})

        # Parse dates
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        start_date = parse_natural_date(start_date)
        end_date = parse_natural_date(end_date)

        url = f"{get_bank_transaction_url()}/statement"
        headers = {"Authorization": f"Bearer {state.bank_api_token}"}
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "limit": str(limit)
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params, timeout=30)
            data = response.json()

            if data.get("success"):
                transactions = data.get("transactions", [])
                await send_frontend_notification("statement_retrieved", {
                    "count": len(transactions),
                    "period": f"{format_date_for_display(start_date)} to {format_date_for_display(end_date)}"
                })
                return json.dumps({"success": True, "transactions": transactions, "period": {"start": start_date, "end": end_date}})
            else:
                error_msg = data.get("message", "Failed to get statement")
                return json.dumps({"success": False, "error": error_msg})
    except Exception as e:
        logger.error(f"Get statement error: {e}")
        return json.dumps({"success": False, "error": "Statement service unavailable"})

@function_tool
async def process_internal_transfer(context: RunContext, recipient_account: str, amount: float, description: str = "") -> str:
    """Process internal bank transfer"""
    try:
        state = get_session_state(context)
        if not state.is_authenticated():
            return json.dumps({"success": False, "error": "Not authenticated"})

        if amount <= 0:
            return json.dumps({"success": False, "error": "Invalid transfer amount"})

        url = f"{get_bank_auth_url()}/transfer/internal"
        headers = {"Authorization": f"Bearer {state.bank_api_token}"}
        payload = {
            "recipient_account": recipient_account,
            "amount": amount,
            "description": description or "Transfer via voice agent"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=30)
            data = response.json()

            if data.get("success"):
                transfer_info = data.get("transfer", {})
                await send_frontend_notification("transfer_completed", {
                    "type": "internal",
                    "amount": amount,
                    "recipient": recipient_account
                })
                return json.dumps({"success": True, "message": "Internal transfer completed successfully", "transfer": transfer_info})
            else:
                error_msg = data.get("message", "Transfer failed")
                return json.dumps({"success": False, "error": error_msg})
    except Exception as e:
        logger.error(f"Internal transfer error: {e}")
        return json.dumps({"success": False, "error": "Transfer service unavailable"})

@function_tool
async def process_rtgs_transfer(context: RunContext, recipient_bank: str, recipient_account: str, amount: float, description: str = "") -> str:
    """Process RTGS (Real Time Gross Settlement) transfer"""
    try:
        state = get_session_state(context)
        if not state.is_authenticated():
            return json.dumps({"success": False, "error": "Not authenticated"})

        if amount <= 0:
            return json.dumps({"success": False, "error": "Invalid transfer amount"})

        url = f"{get_bank_auth_url()}/transfer/rtgs"
        headers = {"Authorization": f"Bearer {state.bank_api_token}"}
        payload = {
            "recipient_bank": recipient_bank,
            "recipient_account": recipient_account,
            "amount": amount,
            "description": description or "RTGS Transfer via voice agent"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=30)
            data = response.json()

            if data.get("success"):
                transfer_info = data.get("transfer", {})
                await send_frontend_notification("transfer_completed", {
                    "type": "rtgs",
                    "amount": amount,
                    "recipient_bank": recipient_bank,
                    "recipient_account": recipient_account
                })
                return json.dumps({"success": True, "message": "RTGS transfer initiated successfully", "transfer": transfer_info})
            else:
                error_msg = data.get("message", "RTGS transfer failed")
                return json.dumps({"success": False, "error": error_msg})
    except Exception as e:
        logger.error(f"RTGS transfer error: {e}")
        return json.dumps({"success": False, "error": "RTGS transfer service unavailable"})

@function_tool
async def process_cardless_withdrawal(context: RunContext, amount: float, agent_location: str = "") -> str:
    """Process cardless cash withdrawal"""
    try:
        state = get_session_state(context)
        if not state.is_authenticated():
            return json.dumps({"success": False, "error": "Not authenticated"})

        if amount <= 0:
            return json.dumps({"success": False, "error": "Invalid withdrawal amount"})

        url = f"{get_bank_auth_url()}/withdrawal/cardless"
        headers = {"Authorization": f"Bearer {state.bank_api_token}"}
        payload = {
            "amount": amount,
            "agent_location": agent_location or "Voice agent withdrawal"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=30)
            data = response.json()

            if data.get("success"):
                withdrawal_info = data.get("withdrawal", {})
                await send_frontend_notification("withdrawal_completed", {
                    "amount": amount,
                    "type": "cardless"
                })
                return json.dumps({"success": True, "message": "Cardless withdrawal initiated successfully", "withdrawal": withdrawal_info})
            else:
                error_msg = data.get("message", "Withdrawal failed")
                return json.dumps({"success": False, "error": error_msg})
    except Exception as e:
        logger.error(f"Cardless withdrawal error: {e}")
        return json.dumps({"success": False, "error": "Withdrawal service unavailable"})

# ============================================
# ACCOUNT UNLOCK TOOLS (Security Questions Flow)
# ============================================
def get_square_lab_url() -> str:
    return os.getenv("SQUARE_LAB_URL", "https://square.stewardbank.co.zw/lab")

@function_tool
async def unlock_account_send_otp(context: RunContext, username: str) -> str:
    try:
        if not username:
            return json.dumps({"success": False, "error": "Please provide the username (phone number or email) to send the OTP."})
        base_url = get_square_lab_url()
        url = f"{base_url}/v1/omnisquare/password/otp"
        payload = {"username": username}
        logging.info(f"Sending unlock OTP for username: {username}")
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
            logging.info(f"OTP response status: {response.status_code}, body: {response.text[:500]}")
            data = response.json()
            if data.get("success") == True:
                uuid = data.get("body", {}).get("uuid", "")
                message = data.get("message", "OTP sent successfully")
                state = get_session_state(context)
                state.unlock_uuid = uuid
                state.unlock_verified_otp = False
                state.unlock_question_verified = False
                state.unlock_question_attempts = 0
                state.unlock_question_id = None
                await send_frontend_notification("unlock_otp_sent", {"username": username, "message": message})
                return json.dumps({"success": True, "uuid": uuid, "message": message, "next_step": "Ask the user for the OTP code they received, then call unlock_account_verify_otp with the uuid and otp."})
            else:
                error_msg = data.get("message", "Failed to send OTP")
                return json.dumps({"success": False, "error": error_msg})
    except Exception as e:
        logging.error(f"Error sending unlock OTP: {str(e)}")
        return json.dumps({"success": False, "error": "We couldn't send the verification code. Please try again later."})

@function_tool
async def unlock_account_verify_otp(context: RunContext, uuid: str, otp: str) -> str:
    try:
        if not uuid or not otp:
            return json.dumps({"success": False, "error": "Please provide both the session UUID and the OTP code."})
        otp_clean = otp.strip().replace(" ", "")
        base_url = get_square_lab_url()
        url = f"{base_url}/v1/omnisquare/password/verify"
        payload = {"uuid": uuid, "otp": otp_clean}
        logging.info(f"Verifying unlock OTP for uuid: {uuid}")
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
            logging.info(f"OTP verify response: {response.status_code}, body: {response.text[:500]}")
            data = response.json()
            if data.get("success") == True:
                await send_frontend_notification("unlock_otp_verified", {"message": "OTP verification successful"})
                state = get_session_state(context)
                state.unlock_verified_otp = True
                return json.dumps({"success": True, "uuid": uuid, "message": data.get("message", "OTP verification was successful"), "next_step": "Call unlock_account_get_security_questions with the uuid to get the security questions."})
            else:
                error_msg = data.get("message", "OTP verification failed")
                return json.dumps({"success": False, "error": error_msg, "hint": "The OTP may be incorrect or expired. Ask the user to double-check the code."})
    except Exception as e:
        logging.error(f"Error verifying unlock OTP: {str(e)}")
        return json.dumps({"success": False, "error": "We couldn't verify the code. Please try again."})

@function_tool
async def unlock_account_get_security_questions(context: RunContext, uuid: str) -> str:
    import random
    try:
        if not uuid:
            return json.dumps({"success": False, "error": "Please provide the session UUID."})
        base_url = get_square_lab_url()
        url = f"{base_url}/v1/omnisquare/password/get-question"
        payload = {"uuid": uuid}
        logging.info(f"Getting security questions for uuid: {uuid}")
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
            logging.info(f"Security questions response: {response.status_code}, body: {response.text[:500]}")
            data = response.json()
            if data.get("success") == True:
                questions = data.get("body", {}).get("questions", [])
                if not questions:
                    return json.dumps({"success": False, "error": "No security questions found for this account."})
                selected_question = random.choice(questions)
                question_id = selected_question.get("id")
                question_text = selected_question.get("question")
                logging.info(f"Selected question ID {question_id}: {question_text}")
                state = get_session_state(context)
                state.unlock_question_id = question_id
                state.unlock_question_attempts = 0
                await send_frontend_notification("unlock_security_question", {"question_id": question_id, "question": question_text, "message": "Security question retrieved"})
                return json.dumps({"success": True, "uuid": uuid, "selected_question": {"id": question_id, "question": question_text}, "message": f"Please ask the user: {question_text}", "instruction": f"Ask the user this question: '{question_text}'. Remember the question_id is {question_id} - you will need this for the next step.", "next_step": f"After the user answers, call unlock_account_answer_question with uuid='{uuid}', question_id={question_id}, and their answer."})
            else:
                error_msg = data.get("message", "Failed to get security questions")
                logging.error(f"Failed to get security questions: {error_msg}")
                return json.dumps({"success": False, "error": error_msg})
    except Exception as e:
        logging.error(f"Error getting security questions: {str(e)}")
        return json.dumps({"success": False, "error": "We couldn't retrieve the security questions. Please try again."})

@function_tool
async def unlock_account_answer_question(context: RunContext, uuid: str, question_id: int, answer: str) -> str:
    try:
        state = get_session_state(context)
        if not uuid or not question_id or not answer:
            return json.dumps({"success": False, "error": "Please provide the session UUID, question ID, and answer."})
        base_url = get_square_lab_url()
        url = f"{base_url}/v1/omnisquare/password/answer-question"
        payload = {"uuid": uuid, "question_id": question_id, "answer": answer.strip()}
        logging.info(f"Answering security question {question_id} for uuid: {uuid}")
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
            logging.info(f"Answer question response: {response.status_code}, body: {response.text[:500]}")
            data = response.json()
            if data.get("success") == True:
                state.unlock_question_verified = True
                await send_frontend_notification("unlock_question_answered", {"message": "Security question answered correctly"})
                return json.dumps({"success": True, "uuid": uuid, "message": data.get("message", "Security question verification successful"), "next_step": "Ask the user to provide a new 4-digit PIN, then call unlock_account_reset_pin with uuid and the new pin."})
            else:
                attempts = getattr(state, 'unlock_question_attempts', 0) + 1
                state.unlock_question_attempts = attempts
                await send_frontend_notification("unlock_question_wrong", {"question_id": question_id, "attempts": attempts, "message": "Wrong security answer provided"})
                remaining = max(0, 3 - attempts)
                error_msg = data.get("message", "Answer verification failed")
                return json.dumps({"success": False, "error": error_msg, "attempts": attempts, "remaining_attempts": remaining, "hint": "The answer may be incorrect. Ask the user to try again or try a different question."})
    except Exception as e:
        logging.error(f"Error answering security question: {str(e)}")
        return json.dumps({"success": False, "error": "We couldn't verify your answer. Please try again."})

@function_tool
async def unlock_account_reset_pin(context: RunContext, uuid: str, new_pin: str) -> str:
    try:
        if not uuid or not new_pin:
            return json.dumps({"success": False, "error": "Please provide the session UUID and the new PIN."})
        state = get_session_state(context)
        if not getattr(state, 'unlock_question_verified', False):
            return json.dumps({"success": False, "error": "Security question not yet verified. Please answer the security question before setting a new PIN."})
        pin_clean = new_pin.strip().replace(" ", "")
        if not pin_clean.isdigit() or len(pin_clean) != 4:
            return json.dumps({"success": False, "error": "The PIN must be exactly 4 digits. Please ask the user for a valid 4-digit PIN."})
        base_url = get_square_lab_url()
        url = f"{base_url}/v1/omnisquare/password/reset-pin"
        payload = {"uuid": uuid, "channel": "MOBILE", "password": pin_clean}
        logging.info(f"Resetting PIN for uuid: {uuid}")
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
            logging.info(f"Reset PIN response: {response.status_code}, body: {response.text[:500]}")
            data = response.json()
            if data.get("success") == True:
                await send_frontend_notification("unlock_complete", {"message": "Account unlocked and PIN reset successfully"})
                return json.dumps({"success": True, "message": "Great news! Your account has been unlocked and your PIN has been reset successfully.", "next_step": "Ask the user if they would like to try logging in again with their new PIN."})
            else:
                error_msg = data.get("message", "Failed to reset PIN")
                return json.dumps({"success": False, "error": error_msg})
    except Exception as e:
        logging.error(f"Error resetting PIN: {str(e)}")
        return json.dumps({"success": False, "error": "We couldn't reset your PIN. Please try again or contact support."})

@function_tool
async def send_email(context: RunContext, to_email: str, subject: str, body: str) -> str:
    """
    Send an email using Gmail SMTP.
    
    CRITICAL: You MUST collect ALL information from the user BEFORE calling this tool:
    1. First ASK: "What is your email address?"
    2. WAIT for user to speak their email clearly
    3. CONFIRM: "Just to confirm, your email is [email]?"
    4. Only after user confirms, call this tool
    
    DO NOT call this tool with guessed, misheard, or placeholder emails.
    """
    try:
        # Validate email address - reject placeholders and invalid patterns
        invalid_patterns = [
            # Placeholder patterns
            '[', ']', '{', '}', '<', '>', 
            'your email', 'customer email', 'user email', 'email address', 
            'recipient', 'placeholder', 'example.com', '@example',
            # Invalid characters that indicate garbled speech
            '/', '\\', ' ', '(', ')', '*', '!', '#', '$', '%', '^', '&',
            # Common garbled patterns
            'bn/', 'bn@', 'user@', 'auser', 'test@', 'email@', 'abc@',
            'unknown', 'none', 'null', 'undefined', 'n/a',
            # Speech recognition artifacts
            'at the rate', 'at symbol', 'dot com', 'gmail dot', 'yahoo dot'
        ]
        
        to_email_lower = to_email.lower().strip()
        
        # Check for placeholder patterns
        if any(pattern in to_email_lower for pattern in invalid_patterns):
            await send_frontend_notification("tool_error", {
                "tool": "send_email",
                "message": "Invalid email - cannot send",
                "error": f"Email '{to_email}' appears invalid or garbled"
            })
            return json.dumps({
                "success": False, 
                "error": f"REJECTED: '{to_email}' is not a valid email. You must ASK the user: 'What is your email address?' then WAIT for their response, then CONFIRM it back to them before trying again.",
                "instruction": "STOP. Do not call send_email again until you have clearly asked for and confirmed the email address with the user."
            })
        
        # Validate basic email format with regex - must be standard format
        email_regex = r'^[a-zA-Z0-9][a-zA-Z0-9._%+-]*[a-zA-Z0-9]@[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, to_email) or len(to_email) < 6:
            await send_frontend_notification("tool_error", {
                "tool": "send_email",
                "message": "Invalid email format",
                "error": f"Email '{to_email}' format is invalid"
            })
            return json.dumps({
                "success": False,
                "error": f"REJECTED: '{to_email}' is not a valid email format. Ask the user clearly: 'Could you please spell out your email address?' and wait for their response.",
                "instruction": "Valid emails look like: john@gmail.com, mary@company.co.zw. Do not guess or assume."
            })
        
        # Additional check: must have reasonable local part (before @)
        local_part = to_email.split('@')[0]
        if len(local_part) < 2 or len(local_part) > 64:
            await send_frontend_notification("tool_error", {
                "tool": "send_email",
                "message": "Invalid email - unusual format",
                "error": f"Email '{to_email}' has unusual format"
            })
            return json.dumps({
                "success": False,
                "error": f"REJECTED: '{to_email}' doesn't look like a real email. Please ask the user to repeat their email address clearly.",
                "instruction": "Ask: 'Could you please say your email address again, spelling it out if needed?'"
            })
        
        gmail_user = os.getenv("GMAIL_USER")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")
        if not gmail_user or not gmail_password:
            await send_frontend_notification("tool_error", {
                "tool": "send_email",
                "message": "Email service not configured",
                "error": "Missing GMAIL_USER or GMAIL_APP_PASSWORD"
            })
            return json.dumps({"success": False, "error": "Email configuration not set up"})

        # Notify frontend that email is being sent
        await send_frontend_notification("tool_started", {
            "tool": "send_email",
            "message": f"Sending email to {to_email}"
        })

        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user, gmail_password)
        text = msg.as_string()
        server.sendmail(gmail_user, to_email, text)
        server.quit()

        # Notify success
        await send_frontend_notification("tool_success", {
            "tool": "send_email",
            "message": f"Email sent successfully to {to_email}",
            "recipient": to_email
        })

        return json.dumps({"success": True, "message": f"Email sent to {to_email}"})
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        
        # Notify error
        await send_frontend_notification("tool_error", {
            "tool": "send_email",
            "message": "Failed to send email",
            "error": str(e)
        })
        
        return json.dumps({"success": False, "error": "Failed to send email"})

@function_tool
async def search_web(context: RunContext, query: str) -> str:
    """
    Search the web using DuckDuckGo.
    IMPORTANT: Only call this tool after getting explicit permission from the user!
    """
    try:
        # Check if user has approved web search
        agent_context = get_job_context()
        if agent_context and hasattr(agent_context, 'user_session'):
            session = agent_context.user_session
            if not getattr(session, 'web_search_approved', False):
                await send_frontend_notification("tool_error", {
                    "tool": "search_web",
                    "message": "Web search attempted without user permission",
                    "error": "permission_denied"
                })
                return "I need your permission before searching the web. Would you like me to search online for this information?"
        
        # Notify frontend that search is starting
        await send_frontend_notification("tool_started", {
            "tool": "search_web",
            "message": f"Searching the web for: {query}"
        })
        
        # Perform search
        search = DuckDuckGoSearchRun()
        result = search.run(query)
        
        # Log the search results
        logger.info(f"🔍 Search results for '{query}': {result[:200]}...")
        
        # Notify success
        await send_frontend_notification("tool_success", {
            "tool": "search_web",
            "message": "Web search completed successfully",
            "query": query,
            "preview": result[:100] if result else "No results found"
        })
        
        # Return plain text results so the LLM can read them directly
        if result and isinstance(result, str) and len(result.strip()) > 0:
            return f"Web search results for '{query}':\n\n{result}"
        else:
            return f"No search results found for '{query}'. The search engine may be temporarily unavailable."
        
    except Exception as e:
        logger.error(f"Error searching web: {str(e)}")
        
        # Notify error
        await send_frontend_notification("tool_error", {
            "tool": "search_web",
            "message": "Failed to search the web",
            "error": str(e)
        })
        
        # Return error as plain text for the LLM to communicate to the user
        return f"I encountered an error while searching: {str(e)}. Please try again or rephrase your question."
