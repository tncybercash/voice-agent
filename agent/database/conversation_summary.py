"""
Conversation Summarization Service
Generates summaries and extracts profile information from conversations
"""
import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("summarization")


class ConversationSummarizer:
    """
    Analyzes conversations to generate summaries and extract user profile information
    """
    
    def __init__(self, llm_provider=None):
        """
        Initialize with an LLM provider for generating summaries
        llm_provider: Optional LLM client (OpenAI-compatible) for AI summaries
        """
        self.llm_provider = llm_provider
    
    async def summarize_conversation(
        self,
        messages: List[Dict[str, str]],
        session_duration_seconds: int = None
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive summary of a conversation
        
        Args:
            messages: List of {"role": "user|assistant", "content": "..."}
            session_duration_seconds: Duration of the conversation
        
        Returns:
            {
                "summary": str,
                "extracted_info": {...},
                "sentiment": str,
                "resolution_status": str,
                "topics": [...]
            }
        """
        if not messages:
            return {
                "summary": "No conversation",
                "extracted_info": {},
                "sentiment": "neutral",
                "resolution_status": "incomplete",
                "topics": []
            }
        
        # Extract basic info first
        extracted_info = self._extract_basic_info(messages)
        topics = self._extract_topics(messages)
        sentiment = self._detect_sentiment(messages)
        
        # Generate summary (with or without LLM)
        if self.llm_provider:
            summary = await self._generate_llm_summary(messages)
            resolution_status = await self._determine_resolution(messages, summary)
        else:
            summary = self._generate_rule_based_summary(messages, topics, extracted_info)
            resolution_status = self._simple_resolution_check(messages)
        
        return {
            "summary": summary,
            "extracted_info": extracted_info,
            "sentiment": sentiment,
            "resolution_status": resolution_status,
            "topics": topics
        }
    
    def _extract_basic_info(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Extract basic information from conversation (name, intents, etc.)"""
        info = {
            "user_name": None,
            "primary_intent": None,
            "mentioned_accounts": [],
            "authentication_attempted": False
        }
        
        conversation_text = " ".join([msg.get("content", "") for msg in messages]).lower()
        
        # Look for name introductions
        name_patterns = [
            "my name is ", "i'm ", "i am ", "this is ",
            "call me ", "name's "
        ]
        for pattern in name_patterns:
            if pattern in conversation_text:
                idx = conversation_text.index(pattern)
                # Extract next few words
                after = conversation_text[idx + len(pattern):].split()[:3]
                potential_name = " ".join(after).strip(".,!?")
                if potential_name and len(potential_name) < 30:
                    info["user_name"] = potential_name.title()
                    break
        
        # Detect primary intent
        intent_keywords = {
            "balance_check": ["balance", "how much", "account balance"],
            "transfer": ["transfer", "send money", "pay"],
            "cardless": ["cardless", "withdraw without card", "atm code"],
            "statement": ["statement", "transaction history"],
            "authentication": ["login", "username", "password", "pin"],
            "help": ["help", "how do i", "how to", "can you help"]
        }
        
        for intent, keywords in intent_keywords.items():
            if any(kw in conversation_text for kw in keywords):
                info["primary_intent"] = intent
                break
        
        # Check authentication
        if any(word in conversation_text for word in ["username", "password", "pin", "login", "authenticate"]):
            info["authentication_attempted"] = True
        
        return info
    
    def _extract_topics(self, messages: List[Dict[str, str]]) -> List[str]:
        """Extract main topics discussed"""
        topics = set()
        conversation_text = " ".join([msg.get("content", "") for msg in messages]).lower()
        
        topic_keywords = {
            "balance_check": ["balance", "how much money", "account balance"],
            "money_transfer": ["transfer", "send money", "payment"],
            "cardless_withdrawal": ["cardless", "withdraw", "atm code", "*236"],
            "statement_request": ["statement", "transaction history", "transactions"],
            "account_opening": ["open account", "new account", "create account"],
            "card_issues": ["card", "atm card", "debit card", "card blocked"],
            "banking_hours": ["hours", "open", "working hours", "office hours"],
            "branch_location": ["branch", "location", "where is", "address"],
            "fees_charges": ["fee", "charge", "cost", "how much does"],
            "loan_inquiry": ["loan", "borrow", "credit"],
            "authentication": ["login", "username", "password", "authenticate"]
        }
        
        for topic, keywords in topic_keywords.items():
            if any(kw in conversation_text for kw in keywords):
                topics.add(topic)
        
        return sorted(list(topics))
    
    def _detect_sentiment(self, messages: List[Dict[str, str]]) -> str:
        """Detect overall conversation sentiment"""
        # Look at user messages only
        user_messages = [msg.get("content", "").lower() for msg in messages if msg.get("role") == "user"]
        
        if not user_messages:
            return "neutral"
        
        text = " ".join(user_messages)
        
        # Positive indicators
        positive_words = ["thank", "thanks", "great", "good", "perfect", "excellent", "appreciate", "helpful"]
        positive_count = sum(1 for word in positive_words if word in text)
        
        # Negative indicators
        negative_words = ["problem", "issue", "error", "wrong", "bad", "terrible", "frustrated", "annoying"]
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _simple_resolution_check(self, messages: List[Dict[str, str]]) -> str:
        """Simple rule-based resolution detection"""
        if len(messages) < 2:
            return "incomplete"
        
        last_messages = " ".join([msg.get("content", "").lower() for msg in messages[-3:]])
        
        # Check for completion indicators
        if any(word in last_messages for word in ["thank", "goodbye", "bye", "that's all", "perfect", "done"]):
            return "resolved"
        
        # Check for escalation indicators
        if any(word in last_messages for word in ["speak to human", "call me", "contact", "complaint"]):
            return "escalated"
        
        return "in_progress"
    
    def _generate_rule_based_summary(
        self,
        messages: List[Dict[str, str]],
        topics: List[str],
        extracted_info: Dict[str, Any]
    ) -> str:
        """Generate a basic summary without LLM"""
        message_count = len(messages)
        user_messages = [m for m in messages if m.get("role") == "user"]
        assistant_messages = [m for m in messages if m.get("role") == "assistant"]
        
        summary_parts = []
        
        # Basic stats
        summary_parts.append(f"Conversation with {message_count} messages ({len(user_messages)} from user).")
        
        # Name if available
        if extracted_info.get("user_name"):
            summary_parts.append(f"User identified as {extracted_info['user_name']}.")
        
        # Primary intent
        if extracted_info.get("primary_intent"):
            intent = extracted_info["primary_intent"].replace("_", " ").title()
            summary_parts.append(f"Primary purpose: {intent}.")
        
        # Topics
        if topics:
            topic_str = ", ".join([t.replace("_", " ").title() for t in topics[:3]])
            summary_parts.append(f"Topics discussed: {topic_str}.")
        
        # Authentication
        if extracted_info.get("authentication_attempted"):
            summary_parts.append("User attempted authentication.")
        
        return " ".join(summary_parts)
    
    async def _generate_llm_summary(self, messages: List[Dict[str, str]]) -> str:
        """Generate AI summary using LLM"""
        try:
            # Build conversation text
            conversation = "\n".join([
                f"{msg['role'].upper()}: {msg['content']}" 
                for msg in messages
            ])
            
            prompt = f"""Summarize this customer service conversation in 2-3 sentences. Focus on:
1. What the user wanted
2. What information was provided
3. Outcome/next steps

Conversation:
{conversation}

Summary:"""
            
            response = await self.llm_provider.chat.completions.create(
                model="llama3.2:latest",  # Will use whatever model is configured
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content.strip()
            logger.info(f"Generated LLM summary: {summary[:100]}...")
            return summary
            
        except Exception as e:
            logger.warning(f"LLM summary failed, using fallback: {e}")
            return self._generate_rule_based_summary(messages, self._extract_topics(messages), self._extract_basic_info(messages))
    
    async def _determine_resolution(self, messages: List[Dict[str, str]], summary: str) -> str:
        """Determine resolution status with LLM help"""
        try:
            prompt = f"""Based on this conversation summary, was the issue resolved?
Answer with one word: 'resolved', 'escalated', or 'incomplete'

Summary: {summary}

Status:"""
            
            response = await self.llm_provider.chat.completions.create(
                model="llama3.2:latest",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0
            )
            
            status = response.choices[0].message.content.strip().lower()
            if status in ["resolved", "escalated", "incomplete"]:
                return status
            return "in_progress"
            
        except Exception as e:
            logger.warning(f"Resolution detection failed: {e}")
            return self._simple_resolution_check(messages)
