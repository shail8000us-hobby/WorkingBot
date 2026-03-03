#!/usr/bin/env python3
"""
Amazon Bedrock Claude 3.5 Sonnet v2 Interactive CLI
Type 'amazon' to start this CLI interface for interactive chat with Claude via Bedrock
"""

import os
import sys
import json
import readline
from pathlib import Path
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

# Color codes for terminal output
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    CYAN = '\033[36m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    RED = '\033[31m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    WHITE = '\033[37m'
    BWHITE = '\033[1;37m'


class BedrockCLI:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.config_dir = self.project_root / ".bedrock_config"
        self.history_file = self.config_dir / "history.json"
        self.sessions_dir = self.config_dir / "sessions"
        
        # Create directories
        self.config_dir.mkdir(exist_ok=True)
        self.sessions_dir.mkdir(exist_ok=True)
        
        # Initialize Bedrock client
        self.client = self._init_bedrock_client()
        self.conversation_history = []
        self.current_session = None
        
    def _init_bedrock_client(self):
        """Initialize Bedrock client with credentials"""
        try:
            # Get credentials from environment
            api_key = os.getenv('AWS_BEARER_TOKEN_BEDROCK')
            
            if not api_key:
                print(f"{Colors.RED}[ERROR] AWS_BEARER_TOKEN_BEDROCK not set{Colors.RESET}")
                print(f"{Colors.YELLOW}Set with: export AWS_BEARER_TOKEN_BEDROCK=<your_key>{Colors.RESET}")
                sys.exit(1)
            
            # Initialize boto3 client for Bedrock
            client = boto3.client(
                'bedrock-runtime',
                region_name='us-east-1'
            )
            return client
        except Exception as e:
            print(f"{Colors.RED}[ERROR] Failed to initialize Bedrock client: {e}{Colors.RESET}")
            sys.exit(1)
    
    def _get_system_prompt(self):
        """Get system prompt for Claude"""
        return """You are Claude 3.5 Sonnet v2, an expert AI assistant running in an interactive terminal CLI powered by Amazon Bedrock.
You provide clear, helpful, and accurate responses to user queries.
You can help with programming, analysis, writing, math, and much more.
Be concise but thorough. Format your responses clearly."""
    
    def _call_bedrock(self, user_message):
        """Call Claude Opus 4.6 via Bedrock"""
        try:
            # Add user message to history
            self.conversation_history.append({
                "role": "user",
                "content": [{"text": user_message}]
            })
            
            # Prepare messages for API
            messages = self.conversation_history
            
            # Call Bedrock API
            response = self.client.converse(
                modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                system=[{"text": self._get_system_prompt()}],
                messages=messages,
                inferenceConfig={
                    "maxTokens": 2048,
                    "temperature": 0.7,
                    "topP": 0.9,
                }
            )
            
            # Extract response
            assistant_message = response['output']['message']['content'][0]['text']
            
            # Add assistant response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": [{"text": assistant_message}]
            })
            
            return assistant_message
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            print(f"{Colors.RED}[API ERROR] {error_code}: {error_msg}{Colors.RESET}")
            return None
        except Exception as e:
            print(f"{Colors.RED}[ERROR] Failed to get response: {e}{Colors.RESET}")
            return None
    
    def _save_session(self):
        """Save current chat session"""
        if self.conversation_history:
            session_name = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            session_path = self.sessions_dir / session_name
            
            with open(session_path, 'w') as f:
                json.dump(self.conversation_history, f, indent=2)
            
            return session_path
        return None
    
    def _load_history(self):
        """Load command history for readline"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    history = json.load(f)
                    for cmd in history[-50:]:  # Load last 50 commands
                        readline.add_history(cmd)
            except:
                pass
    
    def _save_history(self, command):
        """Save command to history"""
        try:
            history = []
            if self.history_file.exists():
                with open(self.history_file, 'r') as f:
                    history = json.load(f)
            
            history.append(command)
            history = history[-100:]  # Keep last 100 commands
            
            with open(self.history_file, 'w') as f:
                json.dump(history, f)
        except:
            pass
    
    def print_welcome(self):
        """Print welcome message"""
        print(f"\n{Colors.BWHITE}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.BWHITE}║  Amazon Bedrock CLI - Claude 3.5 Sonnet v2 Chat          ║{Colors.RESET}")
        print(f"{Colors.BWHITE}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print(f"\n{Colors.CYAN}Type your questions or commands below.{Colors.RESET}")
        print(f"{Colors.YELLOW}Commands:{Colors.RESET}")
        print(f"  {Colors.GREEN}/help{Colors.RESET}          - Show help")
        print(f"  {Colors.GREEN}/clear{Colors.RESET}         - Clear conversation history")
        print(f"  {Colors.GREEN}/save{Colors.RESET}          - Save current session")
        print(f"  {Colors.GREEN}/history{Colors.RESET}       - Show conversation history")
        print(f"  {Colors.GREEN}/exit{Colors.RESET}          - Exit CLI")
        print(f"\n{Colors.DIM}Type 'amazon' to use this CLI from terminal{Colors.RESET}\n")
    
    def show_help(self):
        """Show help information"""
        help_text = f"""
{Colors.BWHITE}Available Commands:{Colors.RESET}

{Colors.GREEN}/help{Colors.RESET}       - Display this help message
{Colors.GREEN}/clear{Colors.RESET}      - Clear conversation history and start fresh
{Colors.GREEN}/save{Colors.RESET}       - Save current conversation to a session file
{Colors.GREEN}/history{Colors.RESET}    - Show current conversation history
{Colors.GREEN}/exit{Colors.RESET}       - Exit the CLI

{Colors.BWHITE}Features:{Colors.RESET}
- Interactive chat with Claude Opus 4.6
- Persistent conversation history within session
- Session saving and management
- Command history support (use arrow keys)

{Colors.BWHITE}Setup:{Colors.RESET}
1. Set API key: export AWS_BEARER_TOKEN_BEDROCK=<your_key>
2. Run: python bedrock_cli.py
3. Or use: amazon (if alias configured)
"""
        print(help_text)
    
    def show_history(self):
        """Show conversation history"""
        if not self.conversation_history:
            print(f"{Colors.YELLOW}No conversation history yet.{Colors.RESET}")
            return
        
        print(f"\n{Colors.BWHITE}Conversation History:{Colors.RESET}\n")
        for i, msg in enumerate(self.conversation_history, 1):
            role = f"{Colors.GREEN}You{Colors.RESET}" if msg['role'] == 'user' else f"{Colors.CYAN}Claude{Colors.RESET}"
            # Extract text from content list
            content_text = msg['content'][0]['text'] if isinstance(msg['content'], list) else msg['content']
            content = content_text[:100] + "..." if len(content_text) > 100 else content_text
            print(f"{Colors.DIM}[{i}] {role}:{Colors.RESET} {content}")
        print()
    
    def run(self):
        """Main CLI loop"""
        self.print_welcome()
        self._load_history()
        
        try:
            while True:
                try:
                    user_input = input(f"{Colors.BLUE}You:{Colors.RESET} ").strip()
                    
                    if not user_input:
                        continue
                    
                    # Save to history
                    self._save_history(user_input)
                    
                    # Handle commands
                    if user_input.lower() == '/exit':
                        print(f"\n{Colors.YELLOW}Exiting...{Colors.RESET}")
                        break
                    elif user_input.lower() == '/help':
                        self.show_help()
                        continue
                    elif user_input.lower() == '/clear':
                        self.conversation_history = []
                        print(f"{Colors.GREEN}Conversation cleared.{Colors.RESET}")
                        continue
                    elif user_input.lower() == '/history':
                        self.show_history()
                        continue
                    elif user_input.lower() == '/save':
                        session_path = self._save_session()
                        if session_path:
                            print(f"{Colors.GREEN}Session saved to: {session_path}{Colors.RESET}")
                        continue
                    
                    # Get response from Claude
                    print(f"{Colors.CYAN}Claude:{Colors.RESET} ", end="", flush=True)
                    response = self._call_bedrock(user_input)
                    
                    if response:
                        print(response)
                        print()
                    
                except KeyboardInterrupt:
                    print(f"\n{Colors.YELLOW}Interrupted. Type '/exit' to quit or Continue...{Colors.RESET}")
                    continue
                    
        except EOFError:
            print(f"\n{Colors.YELLOW}Exiting...{Colors.RESET}")


def main():
    """Main entry point"""
    try:
        cli = BedrockCLI()
        cli.run()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrupted.{Colors.RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"{Colors.RED}[FATAL ERROR] {e}{Colors.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
