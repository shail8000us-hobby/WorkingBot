/**
 * Claude AI Chat Component for React
 * Location: webui/frontend/src/components/claude/ClaudeChat.jsx
 * 
 * Features:
 * - Real-time chat with Claude
 * - Conversation history
 * - Loading states
 * - Error handling
 */

import React, { useState, useRef, useEffect } from 'react';
import './ClaudeChat.css';

const ClaudeChat = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [apiHealth, setApiHealth] = useState(null);
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Check Claude API health on component mount
  useEffect(() => {
    checkHealth();
  }, []);

  const checkHealth = async () => {
    try {
      const response = await fetch('http://localhost:5555/api/claude/health');
      const data = await response.json();
      setApiHealth(data.success ? 'connected' : 'error');
      if (!data.success) {
        setError(`API Error: ${data.message}`);
      }
    } catch (err) {
      setApiHealth('disconnected');
      setError('Cannot reach Claude API. Is the backend running?');
    }
  };

  const sendMessage = async (e) => {
    e.preventDefault();

    if (!input.trim()) return;

    // Add user message to chat
    const userMessage = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('http://localhost:5555/api/claude/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: input,
          system_prompt: systemPrompt || undefined,
          remember: true, // Keep conversation history
        }),
      });

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || 'Unknown error');
      }

      // Add Claude response to chat
      const assistantMessage = {
        role: 'assistant',
        content: data.response,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError(`Error: ${err.message}`);
      // Remove user message if request failed
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setLoading(false);
    }
  };

  const clearHistory = async () => {
    try {
      const response = await fetch('http://localhost:5555/api/claude/clear', {
        method: 'POST',
      });

      const data = await response.json();

      if (data.success) {
        setMessages([]);
        setError(null);
      } else {
        setError('Failed to clear history');
      }
    } catch (err) {
      setError(`Error: ${err.message}`);
    }
  };

  return (
    <div className="claude-chat-container">
      <div className="claude-header">
        <h1>🤖 Claude AI Assistant</h1>
        <div className="health-status">
          {apiHealth === 'connected' && (
            <span className="status-indicator connected" title="Claude API connected">
              ✓ Connected
            </span>
          )}
          {apiHealth === 'disconnected' && (
            <span className="status-indicator disconnected" title="Claude API disconnected">
              ✗ Disconnected
            </span>
          )}
          {!apiHealth && (
            <span className="status-indicator checking" title="Checking connection...">
              ⏳ Checking...
            </span>
          )}
        </div>
      </div>

      {/* System Prompt Input */}
      <div className="system-prompt-section">
        <label htmlFor="system-prompt">System Prompt (Optional):</label>
        <input
          id="system-prompt"
          type="text"
          placeholder="e.g., 'You are a trading analyst specializing in volatility measurement'"
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
          className="system-prompt-input"
        />
        <small>Customize Claude's behavior for specific tasks</small>
      </div>

      {/* Messages Display */}
      <div className="messages-container">
        {messages.length === 0 && (
          <div className="welcome-message">
            <p>👋 Start a conversation with Claude</p>
            <ul>
              <li>Ask for trading analysis</li>
              <li>Get help understanding market data</li>
              <li>Debug configuration issues</li>
              <li>Review strategy ideas</li>
            </ul>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`message ${msg.role}`}
          >
            <div className="message-avatar">
              {msg.role === 'user' ? '👤' : '🤖'}
            </div>
            <div className="message-content">
              <p>{msg.content}</p>
            </div>
          </div>
        ))}

        {loading && (
          <div className="message assistant loading">
            <div className="message-avatar">🤖</div>
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="error-message">
            <strong>⚠️ Error:</strong> {error}
            <button onClick={checkHealth} className="retry-button">
              Retry Connection
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <form onSubmit={sendMessage} className="input-form">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message here..."
          disabled={loading || apiHealth !== 'connected'}
          className="message-input"
        />
        <button
          type="submit"
          disabled={loading || !input.trim() || apiHealth !== 'connected'}
          className="send-button"
        >
          {loading ? '⏳' : '➤'} Send
        </button>
        <button
          type="button"
          onClick={clearHistory}
          className="clear-button"
          title="Clear conversation history"
        >
          🗑️
        </button>
      </form>
    </div>
  );
};

export default ClaudeChat;
