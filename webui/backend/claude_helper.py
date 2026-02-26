#!/usr/bin/env python3
"""
Claude AI Integration Helper via POE
Provides a clean interface to interact with Claude via POE.com API
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv
import requests

# Setup logging
log = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Configuration for OpenAI-compatible API (FreeAI, OpenAI, etc.)
OPENAI_API_BASE_URL = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")


class ClaudeBot:
    """
    Wrapper around an OpenAI-compatible chat model (Claude via FreeAI etc.)

    Usage:
        bot = ClaudeBot()
        response = bot.chat("Analyze this trading data...")

    Features:
        - Reads API key/base from environment (`OPENAI_API_KEY`, `OPENAI_API_BASE`)
        - Configurable default model via `OPENAI_API_MODEL`
        - Conversation history support (stateful)
        - System prompts for role-based responses
        - Uses official OpenAI Python client for HTTP interactions
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        # load key and base from environment or provided args
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not configured in environment")

        self.base_url = os.getenv("OPENAI_API_BASE", OPENAI_API_BASE_URL)
        self.model = model or os.getenv("OPENAI_API_MODEL", "gpt-4")
        self.max_tokens = int(os.getenv("OPENAI_API_MAX_TOKENS", "4096"))

        # set up openai client
        try:
            import openai
            openai.api_key = self.api_key
            openai.api_base = self.base_url
            self._client = openai
        except ImportError as e:
            raise RuntimeError("openai library is required for ClaudeBot") from e

        # history
        self.conversation_history = []
        log.info(f"✅ Claude bot initialized: {self.model} at {self.base_url}")
    
    def chat(self, user_message: str, system_prompt: Optional[str] = None, remember: bool = True) -> str:
        """
        Send a message to the configured OpenAI-compatible model and return text
        """
        # assemble message list
        messages = []
        if remember and self.conversation_history:
            messages.extend(self.conversation_history)
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        try:
            resp = self._client.ChatCompletion.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=0.7,
            )
            response_text = resp.choices[0].message.content
        except Exception as e:
            log.error(f"AI chat error: {e}")
            raise

        if remember:
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": response_text})
            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]

        return response_text
    
    def analyze_data(self, data_description: str, analysis_type: str = "general") -> str:
        system_prompt = f"""You are an expert quantitative trading analyst specializing in {analysis_type} analysis.
Provide clear, actionable insights focused on trading implications.
Be concise and specific with numbers and metrics."""
    
    def explain_error(self, error_message: str, context: str = "") -> str:
        system_prompt = """You are a Python debugging expert for trading systems.
Explain errors clearly and suggest fixes."""
        prompt = f"Error: {error_message}"
        if context:
            prompt += f"\n\nContext: {context}"
        return self.chat(prompt, system_prompt=system_prompt, remember=False)
    
    def clear_history(self):
        """Clear conversation history for fresh context"""
        self.conversation_history = []
        log.info("🗑️  Conversation history cleared")


def get_claude_bot() -> ClaudeBot:
    """
    Get or create singleton Claude bot instance
    
    Usage:
        bot = get_claude_bot()
        response = bot.chat("Hello Claude!")
    """
    if not hasattr(get_claude_bot, '_instance'):
        try:
            get_claude_bot._instance = ClaudeBot()
        except Exception as e:
            log.error(f"❌ Failed to initialize Claude bot: {e}")
            raise
    
    return get_claude_bot._instance


if __name__ == "__main__":
    # Test Claude connection via POE
    print("🧪 Testing Claude API connection via POE...\n")
    
    try:
        bot = get_claude_bot()
        print("✅ Claude bot initialized successfully\n")
        
        # Test basic chat
        print("Testing chat...")
        response = bot.chat("What are the key considerations for algorithmic trading?")
        print(f"Claude: {response[:200]}...\n")
        
        print("✅ All tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        exit(1)
