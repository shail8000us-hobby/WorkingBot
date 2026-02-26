#!/usr/bin/env python3
"""
Claude AI API Routes
Provides Flask endpoints for Claude integration

Available endpoints:
  POST /api/claude/chat - Send a message to Claude
  POST /api/claude/analyze - Analyze trading data
  POST /api/claude/error - Get error explanation
  POST /api/claude/clear - Clear conversation history
  GET  /api/claude/health - Check Claude API status
"""

import logging
from flask import Blueprint, request, jsonify
from claude_helper import get_claude_bot, ClaudeBot

log = logging.getLogger(__name__)

# Create blueprint
claude_bp = Blueprint('claude', __name__, url_prefix='/api/claude')


@claude_bp.route('/health', methods=['GET'])
def health():
    """
    Check Claude API connection status
    
    Returns:
        {
            'success': bool,
            'status': 'healthy' | 'error',
            'model': string,
            'message': string
        }
    """
    try:
        bot = get_claude_bot()
        return jsonify({
            'success': True,
            'status': 'healthy',
            'model': bot.model,
            'message': '✅ Claude API connected'
        })
    except Exception as e:
        log.error(f"Claude health check failed: {e}")
        return jsonify({
            'success': False,
            'status': 'error',
            'message': str(e)
        }), 503


@claude_bp.route('/chat', methods=['POST'])
def chat():
    """
    Send a message to Claude and get response
    
    Request body:
        {
            'message': string (required) - User message
            'system_prompt': string (optional) - System context
            'remember': boolean (optional, default=true) - Keep conversation history
        }
    
    Returns:
        {
            'success': bool,
            'response': string,
            'model': string,
            'tokens_used': integer
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: message'
            }), 400
        
        message = data.get('message')
        system_prompt = data.get('system_prompt')
        remember = data.get('remember', True)
        
        # Get bot instance
        bot = get_claude_bot()
        
        # Send message to Claude
        response = bot.chat(
            user_message=message,
            system_prompt=system_prompt,
            remember=remember
        )
        
        return jsonify({
            'success': True,
            'response': response,
            'model': bot.model,
            'message': 'Chat completed successfully'
        })
    
    except Exception as e:
        log.error(f"Claude chat error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to get response from Claude'
        }), 500


@claude_bp.route('/analyze', methods=['POST'])
def analyze():
    """
    Analyze trading data with Claude
    
    Request body:
        {
            'data': string (required) - Data description/metrics
            'type': string (optional) - Analysis type (technical, risk, opportunity, etc.)
        }
    
    Returns:
        {
            'success': bool,
            'analysis': string,
            'type': string,
            'model': string
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'data' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: data'
            }), 400
        
        data_description = data.get('data')
        analysis_type = data.get('type', 'general')
        
        # Get bot instance
        bot = get_claude_bot()
        
        # Perform analysis
        analysis = bot.analyze_data(
            data_description=data_description,
            analysis_type=analysis_type
        )
        
        return jsonify({
            'success': True,
            'analysis': analysis,
            'type': analysis_type,
            'model': bot.model
        })
    
    except Exception as e:
        log.error(f"Claude analysis error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to analyze data'
        }), 500


@claude_bp.route('/error', methods=['POST'])
def explain_error():
    """
    Get Claude's explanation of a bot error
    
    Request body:
        {
            'error': string (required) - Error message
            'context': string (optional) - Additional context
        }
    
    Returns:
        {
            'success': bool,
            'explanation': string,
            'suggestion': string
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'error' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: error'
            }), 400
        
        error_message = data.get('error')
        context = data.get('context', '')
        
        # Get bot instance
        bot = get_claude_bot()
        
        # Get explanation
        explanation = bot.explain_error(
            error_message=error_message,
            context=context
        )
        
        return jsonify({
            'success': True,
            'explanation': explanation,
            'error': error_message
        })
    
    except Exception as e:
        log.error(f"Claude error explanation failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to explain error'
        }), 500


@claude_bp.route('/clear', methods=['POST'])
def clear_history():
    """
    Clear conversation history for fresh context
    
    Returns:
        {
            'success': bool,
            'message': string
        }
    """
    try:
        bot = get_claude_bot()
        bot.clear_history()
        
        return jsonify({
            'success': True,
            'message': '✅ Conversation history cleared'
        })
    
    except Exception as e:
        log.error(f"Failed to clear history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@claude_bp.route('/status', methods=['GET'])
def status():
    """
    Get Claude bot status and metadata
    
    Returns:
        {
            'success': bool,
            'model': string,
            'max_tokens': integer,
            'history_length': integer
        }
    """
    try:
        bot = get_claude_bot()
        
        return jsonify({
            'success': True,
            'model': bot.model,
            'max_tokens': bot.max_tokens,
            'history_length': len(bot.conversation_history),
            'status': 'ready'
        })
    
    except Exception as e:
        log.error(f"Failed to get status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'status': 'offline'
        }), 503


if __name__ == "__main__":
    print("Claude Routes Blueprint loaded")
    print(f"Available endpoints:")
    print(f"  GET  /api/claude/health - Check API status")
    print(f"  GET  /api/claude/status - Get bot metadata")
    print(f"  POST /api/claude/chat - Send message")
    print(f"  POST /api/claude/analyze - Analyze data")
    print(f"  POST /api/claude/error - Explain error")
    print(f"  POST /api/claude/clear - Clear history")
