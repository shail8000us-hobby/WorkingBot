/**
 * IntelligencePanel - AI Insights & Documentation
 * 
 * Shows AI-powered insights, quick answers, and documentation.
 */

import React, { useState, useCallback } from 'react';
import styles from './IntelligencePanel.module.css';

interface Message {
  id: number;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  suggestions?: string[];
  links?: { title: string; section: string }[];
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';

// Quick questions for easy access
const QUICK_QUESTIONS = [
  "Why is trading stopped?",
  "What is volatility safety?",
  "How do I manage risk?",
  "Explain my current positions",
  "What are grid levels?",
  "How does RSI safety work?",
  "What is the guardian?",
  "How to restart the bot?"
];

// Documentation sections
const DOCS_SECTIONS = [
  { id: 'overview', title: '📋 Overview', content: 'GridBot is an automated trading bot that uses grid trading strategies to profit from market volatility.' },
  { id: 'grid', title: '📊 Grid Trading', content: 'Grid trading places multiple buy and sell orders at predetermined price levels. When price moves, orders are filled and new orders are placed.' },
  { id: 'safety', title: '🛡️ Safety Features', content: 'Includes RSI monitoring, volatility pause, max position limits, daily loss limits, and emergency stop functionality.' },
  { id: 'guardian', title: '👁️ Guardian Mode', content: 'The guardian monitors bot health, restarts on errors, and ensures continuous operation.' },
  { id: 'config', title: '⚙️ Configuration', content: 'Configure grid levels, spacing, order sizes, take profit, stop loss, and safety parameters through the config panel.' },
  { id: 'positions', title: '📈 Positions', content: 'View and manage all open positions across different symbols and trading modes.' }
];

export const IntelligencePanel: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0,
      type: 'assistant',
      content: "👋 Hello! I'm your AI trading assistant. Ask me anything about the bot, trading strategies, or troubleshooting.",
      timestamp: new Date(),
      suggestions: QUICK_QUESTIONS.slice(0, 4)
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'chat' | 'docs'>('chat');

  // Send message to AI
  const sendMessage = useCallback(async (question: string) => {
    if (!question.trim()) return;

    const userMessage: Message = {
      id: Date.now(),
      type: 'user',
      content: question,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/ai/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question })
      });

      const data = await response.json();

      const assistantMessage: Message = {
        id: Date.now() + 1,
        type: 'assistant',
        content: data.success ? data.answer : generateLocalAnswer(question),
        timestamp: new Date(),
        suggestions: data.suggestions || [],
        links: data.related_links || []
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (err) {
      // Fallback to local responses if API fails
      const assistantMessage: Message = {
        id: Date.now() + 1,
        type: 'assistant',
        content: generateLocalAnswer(question),
        timestamp: new Date(),
        suggestions: QUICK_QUESTIONS.slice(0, 3)
      };

      setMessages(prev => [...prev, assistantMessage]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Generate local answer when API is unavailable
  const generateLocalAnswer = (question: string): string => {
    const q = question.toLowerCase();

    if (q.includes('stop') && q.includes('trading')) {
      return "Trading might be stopped due to:\n• RSI thresholds exceeded\n• High volatility detected\n• Max daily loss reached\n• Manual pause enabled\n• Guardian safety triggered\n\nCheck the Bot Management panel for current status.";
    }

    if (q.includes('volatility')) {
      return "Volatility safety pauses trading when market volatility exceeds configured thresholds. This protects against rapid price swings that could cause significant losses. Configure in Safety settings.";
    }

    if (q.includes('risk') || q.includes('manage')) {
      return "Risk management tips:\n• Set appropriate position size limits\n• Use stop-loss orders\n• Monitor RSI thresholds\n• Enable volatility pause\n• Set daily loss limits\n• Review positions regularly";
    }

    if (q.includes('position')) {
      return "Positions show your current open trades. Each position displays:\n• Symbol and mode (LONG/SHORT)\n• Entry price and current price\n• Unrealized P&L\n• Position size\n\nView all positions in the Positions panel.";
    }

    if (q.includes('grid') && q.includes('level')) {
      return "Grid levels are predefined price points where the bot places orders. Spacing between levels and number of levels are configurable. When price moves between levels, orders are filled generating profits.";
    }

    if (q.includes('rsi')) {
      return "RSI (Relative Strength Index) safety:\n• Long mode: Pauses when RSI > 70 (overbought)\n• Short mode: Pauses when RSI < 30 (oversold)\n• Configurable thresholds and periods\n• Helps avoid entering positions at extreme prices";
    }

    if (q.includes('guardian')) {
      return "The Guardian:\n• Monitors bot health continuously\n• Auto-restarts on errors\n• Checks for stale orders\n• Validates positions\n• Sends alerts on issues\n\nEnable in Bot Management panel.";
    }

    if (q.includes('restart') || q.includes('start') || q.includes('stop')) {
      return "To control the bot:\n• Start: Use Bot Management > Start Bot\n• Stop: Use Bot Management > Stop Bot\n• Restart: Use Bot Management > Restart\n• Emergency: Use Emergency Stop button\n\nAlways wait for confirmation after actions.";
    }

    return "I can help with:\n• Understanding trading status\n• Explaining safety features\n• Troubleshooting issues\n• Configuration guidance\n\nTry asking a specific question about the bot!";
  };

  // Handle quick question click
  const handleQuickQuestion = (question: string) => {
    sendMessage(question);
  };

  // Clear chat
  const handleClearChat = () => {
    setMessages([{
      id: Date.now(),
      type: 'assistant',
      content: "Chat cleared! How can I help you?",
      timestamp: new Date(),
      suggestions: QUICK_QUESTIONS.slice(0, 4)
    }]);
  };

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2>🧠 Intelligence Hub</h2>
        <div className={styles.tabs}>
          <button
            className={`${styles.tab} ${activeTab === 'chat' ? styles.active : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            💬 AI Assistant
          </button>
          <button
            className={`${styles.tab} ${activeTab === 'docs' ? styles.active : ''}`}
            onClick={() => setActiveTab('docs')}
          >
            📚 Documentation
          </button>
        </div>
      </div>

      {activeTab === 'chat' ? (
        <div className={styles.chatContainer}>
          {/* Messages */}
          <div className={styles.messages}>
            {messages.map(msg => (
              <div
                key={msg.id}
                className={`${styles.message} ${msg.type === 'user' ? styles.userMessage : styles.assistantMessage}`}
              >
                <div className={styles.messageContent}>
                  {msg.content.split('\n').map((line, i) => (
                    <React.Fragment key={i}>
                      {line}
                      {i < msg.content.split('\n').length - 1 && <br />}
                    </React.Fragment>
                  ))}
                </div>
                
                {/* Suggestions */}
                {msg.suggestions && msg.suggestions.length > 0 && (
                  <div className={styles.suggestions}>
                    {msg.suggestions.map((suggestion, i) => (
                      <button
                        key={i}
                        className={styles.suggestionBtn}
                        onClick={() => handleQuickQuestion(suggestion)}
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                )}

                <span className={styles.timestamp}>
                  {msg.timestamp.toLocaleTimeString()}
                </span>
              </div>
            ))}

            {loading && (
              <div className={`${styles.message} ${styles.assistantMessage}`}>
                <div className={styles.typing}>
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            )}
          </div>

          {/* Quick Questions */}
          <div className={styles.quickQuestions}>
            <span className={styles.quickLabel}>Quick:</span>
            {QUICK_QUESTIONS.slice(0, 4).map((q, i) => (
              <button
                key={i}
                className={styles.quickBtn}
                onClick={() => handleQuickQuestion(q)}
                disabled={loading}
              >
                {q}
              </button>
            ))}
          </div>

          {/* Input */}
          <div className={styles.inputArea}>
            <input
              type="text"
              placeholder="Ask me anything..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && sendMessage(input)}
              disabled={loading}
              className={styles.input}
            />
            <button
              className={styles.sendBtn}
              onClick={() => sendMessage(input)}
              disabled={loading || !input.trim()}
            >
              {loading ? '...' : '📤'}
            </button>
            <button
              className={styles.clearBtn}
              onClick={handleClearChat}
              title="Clear chat"
            >
              🗑️
            </button>
          </div>
        </div>
      ) : (
        <div className={styles.docsContainer}>
          {DOCS_SECTIONS.map(section => (
            <div key={section.id} className={styles.docSection}>
              <h3>{section.title}</h3>
              <p>{section.content}</p>
            </div>
          ))}

          <div className={styles.docSection}>
            <h3>🔗 Quick Links</h3>
            <div className={styles.quickLinks}>
              <a href="https://github.com" target="_blank" rel="noopener noreferrer">
                📂 GitHub Repository
              </a>
              <a href="#" onClick={(e) => { e.preventDefault(); setActiveTab('chat'); }}>
                💬 Ask AI Assistant
              </a>
            </div>
          </div>

          <div className={styles.docSection}>
            <h3>⌨️ Keyboard Shortcuts</h3>
            <div className={styles.shortcuts}>
              <div className={styles.shortcut}>
                <kbd>Ctrl</kbd> + <kbd>S</kbd>
                <span>Save configuration</span>
              </div>
              <div className={styles.shortcut}>
                <kbd>Ctrl</kbd> + <kbd>R</kbd>
                <span>Refresh data</span>
              </div>
              <div className={styles.shortcut}>
                <kbd>Esc</kbd>
                <span>Close dialogs</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default IntelligencePanel;
