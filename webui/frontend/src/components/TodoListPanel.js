import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  CheckCircle2,
  Circle,
  Trash2,
  Plus,
  Edit2,
  X,
  ListTodo,
  Clock,
  Search,
  Tag,
  Code2,
  Bug,
  Lightbulb,
  Wrench,
  BookOpen,
  FileText,
  AlertCircle,
  ArrowUp,
  ArrowDown,
  Minus,
  Copy,
  Check,
  Sparkles,
  Filter,
  SortDesc,
  Keyboard,
  Eye,
  EyeOff,
  Hash,
  MoreHorizontal,
  Pin,
  PinOff,
  Archive,
  Zap,
  Target,
  AlertTriangle,
} from 'lucide-react';
import robustApiClient from '../utils/robustApiClient';

// Priority configuration
const PRIORITIES = {
  urgent: { label: 'Urgent', color: 'rose', icon: AlertCircle, order: 0 },
  high: { label: 'High', color: 'orange', icon: ArrowUp, order: 1 },
  medium: { label: 'Medium', color: 'sky', icon: Minus, order: 2 },
  low: { label: 'Low', color: 'slate', icon: ArrowDown, order: 3 },
};

// Category configuration
const CATEGORIES = {
  bug: { label: 'Bug', color: 'rose', icon: Bug, bgClass: 'bg-rose-500/20', borderClass: 'border-rose-500/40', textClass: 'text-rose-300' },
  feature: { label: 'Feature', color: 'emerald', icon: Lightbulb, bgClass: 'bg-emerald-500/20', borderClass: 'border-emerald-500/40', textClass: 'text-emerald-300' },
  refactor: { label: 'Refactor', color: 'violet', icon: Wrench, bgClass: 'bg-violet-500/20', borderClass: 'border-violet-500/40', textClass: 'text-violet-300' },
  research: { label: 'Research', color: 'amber', icon: BookOpen, bgClass: 'bg-amber-500/20', borderClass: 'border-amber-500/40', textClass: 'text-amber-300' },
  note: { label: 'Note', color: 'sky', icon: FileText, bgClass: 'bg-sky-500/20', borderClass: 'border-sky-500/40', textClass: 'text-sky-300' },
  code: { label: 'Code', color: 'cyan', icon: Code2, bgClass: 'bg-cyan-500/20', borderClass: 'border-cyan-500/40', textClass: 'text-cyan-300' },
};

// Code block component with copy functionality
const CodeBlock = ({ code, language }) => {
  const [copied, setCopied] = useState(false);
  
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };
  
  return (
    <div className="my-2 rounded-lg border border-slate-700/60 bg-slate-950/80 overflow-hidden group/code">
      <div className="flex items-center justify-between px-3 py-1.5 bg-slate-800/50 border-b border-slate-700/50">
        <span className="text-[10px] font-medium text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          <Code2 className="h-3 w-3" />
          {language}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-emerald-400" />
              <span className="text-emerald-400">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-3 overflow-x-auto scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
        <code className="font-mono text-xs text-slate-300 leading-relaxed">{code}</code>
      </pre>
    </div>
  );
};

// Render inline formatting (inline code, bold, italic)
const renderInlineFormatting = (text) => {
  if (!text) return null;
  
  // Split by inline code (`...`)
  const parts = text.split(/(`[^`]+`)/g);
  
  return parts.map((part, i) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={i}
          className="mx-0.5 rounded bg-slate-800/80 px-1.5 py-0.5 font-mono text-xs text-cyan-300 border border-slate-700/50"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
};

// Simple Markdown-like renderer for code blocks and basic formatting
const renderFormattedText = (text) => {
  if (!text) return null;
  
  const parts = [];
  let remaining = text;
  let key = 0;
  
  // Match code blocks first (```...```)
  const codeBlockRegex = /```(\w+)?\n?([\s\S]*?)```/g;
  let lastIndex = 0;
  let match;
  
  while ((match = codeBlockRegex.exec(text)) !== null) {
    // Add text before code block
    if (match.index > lastIndex) {
      parts.push(
        <span key={key++} className="whitespace-pre-wrap">
          {renderInlineFormatting(text.slice(lastIndex, match.index))}
        </span>
      );
    }
    
    // Add code block
    const language = match[1] || 'code';
    const code = match[2].trim();
    parts.push(
      <CodeBlock key={key++} code={code} language={language} />
    );
    
    lastIndex = match.index + match[0].length;
  }
  
  // Add remaining text
  if (lastIndex < text.length) {
    parts.push(
      <span key={key++} className="whitespace-pre-wrap">
        {renderInlineFormatting(text.slice(lastIndex))}
      </span>
    );
  }
  
  return parts.length > 0 ? parts : <span className="whitespace-pre-wrap">{text}</span>;
};

// Priority selector component
const PrioritySelector = ({ value, onChange, compact = false }) => {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef(null);
  
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  
  const current = PRIORITIES[value] || PRIORITIES.medium;
  const Icon = current.icon;
  
  const colorClasses = {
    rose: 'text-rose-400 bg-rose-500/20 border-rose-500/40 hover:bg-rose-500/30',
    orange: 'text-orange-400 bg-orange-500/20 border-orange-500/40 hover:bg-orange-500/30',
    sky: 'text-sky-400 bg-sky-500/20 border-sky-500/40 hover:bg-sky-500/30',
    slate: 'text-slate-400 bg-slate-500/20 border-slate-500/40 hover:bg-slate-500/30',
  };
  
  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium transition-all ${colorClasses[current.color]}`}
        title="Set priority"
      >
        <Icon className="h-3 w-3" />
        {!compact && current.label}
      </button>
      
      {isOpen && (
        <div className="absolute top-full left-0 mt-1 z-50 min-w-[120px] rounded-lg border border-slate-700/60 bg-slate-900/95 backdrop-blur-xl shadow-xl py-1 animate-in fade-in slide-in-from-top-2 duration-200">
          {Object.entries(PRIORITIES).map(([key, priority]) => {
            const PIcon = priority.icon;
            return (
              <button
                key={key}
                onClick={() => {
                  onChange(key);
                  setIsOpen(false);
                }}
                className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-slate-800/80 transition-colors ${
                  value === key ? 'bg-slate-800/60' : ''
                } ${colorClasses[priority.color].split(' ')[0]}`}
              >
                <PIcon className="h-3 w-3" />
                {priority.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

// Category selector component
const CategorySelector = ({ value, onChange, compact = false }) => {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef(null);
  
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  
  const current = CATEGORIES[value];
  
  if (compact && !current) {
    return (
      <div ref={ref} className="relative">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-1 rounded-md border border-slate-700/50 bg-slate-800/50 px-2 py-1 text-xs text-slate-500 hover:text-slate-400 hover:bg-slate-800/80 transition-all"
          title="Add category"
        >
          <Tag className="h-3 w-3" />
        </button>
        {isOpen && (
          <div className="absolute top-full left-0 mt-1 z-50 min-w-[130px] rounded-lg border border-slate-700/60 bg-slate-900/95 backdrop-blur-xl shadow-xl py-1 animate-in fade-in slide-in-from-top-2 duration-200">
            {Object.entries(CATEGORIES).map(([key, category]) => {
              const CIcon = category.icon;
              return (
                <button
                  key={key}
                  onClick={() => {
                    onChange(key);
                    setIsOpen(false);
                  }}
                  className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-slate-800/80 transition-colors ${category.textClass}`}
                >
                  <CIcon className="h-3 w-3" />
                  {category.label}
                </button>
              );
            })}
          </div>
        )}
      </div>
    );
  }
  
  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium transition-all ${
          current 
            ? `${current.bgClass} ${current.borderClass} ${current.textClass} hover:opacity-80`
            : 'border-slate-700/50 bg-slate-800/50 text-slate-500 hover:text-slate-400 hover:bg-slate-800/80'
        }`}
        title="Set category"
      >
        {current ? (
          <>
            <current.icon className="h-3 w-3" />
            {!compact && current.label}
          </>
        ) : (
          <>
            <Tag className="h-3 w-3" />
            {!compact && 'Category'}
          </>
        )}
      </button>
      
      {isOpen && (
        <div className="absolute top-full left-0 mt-1 z-50 min-w-[130px] rounded-lg border border-slate-700/60 bg-slate-900/95 backdrop-blur-xl shadow-xl py-1 animate-in fade-in slide-in-from-top-2 duration-200">
          <button
            onClick={() => {
              onChange(null);
              setIsOpen(false);
            }}
            className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs text-slate-500 hover:bg-slate-800/80 transition-colors ${
              !value ? 'bg-slate-800/60' : ''
            }`}
          >
            <X className="h-3 w-3" />
            None
          </button>
          {Object.entries(CATEGORIES).map(([key, category]) => {
            const CIcon = category.icon;
            return (
              <button
                key={key}
                onClick={() => {
                  onChange(key);
                  setIsOpen(false);
                }}
                className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-slate-800/80 transition-colors ${
                  value === key ? 'bg-slate-800/60' : ''
                } ${category.textClass}`}
              >
                <CIcon className="h-3 w-3" />
                {category.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

// Keyboard shortcuts modal
const KeyboardShortcutsModal = ({ isOpen, onClose }) => {
  if (!isOpen) return null;
  
  const shortcuts = [
    { keys: ['⌘/Ctrl', 'Enter'], action: 'Save todo' },
    { keys: ['Shift', 'Enter'], action: 'New line' },
    { keys: ['Esc'], action: 'Cancel editing' },
    { keys: ['⌘/Ctrl', 'K'], action: 'Focus search' },
    { keys: ['```'], action: 'Insert code block' },
    { keys: ['`code`'], action: 'Inline code' },
  ];
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200" onClick={onClose}>
      <div 
        className="w-full max-w-md rounded-2xl border border-slate-700/60 bg-slate-900/95 backdrop-blur-xl shadow-2xl p-6 animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            <Keyboard className="h-5 w-5 text-sky-400" />
            Keyboard Shortcuts
          </h3>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-colors">
            <X className="h-5 w-5" />
          </button>
        </div>
        
        <div className="space-y-2">
          {shortcuts.map((shortcut, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-slate-800/50 last:border-0">
              <span className="text-sm text-slate-400">{shortcut.action}</span>
              <div className="flex items-center gap-1">
                {shortcut.keys.map((key, j) => (
                  <React.Fragment key={j}>
                    <kbd className="px-2 py-1 rounded bg-slate-800 border border-slate-700 text-xs font-mono text-slate-300">
                      {key}
                    </kbd>
                    {j < shortcut.keys.length - 1 && <span className="text-slate-600 text-xs">+</span>}
                  </React.Fragment>
                ))}
              </div>
            </div>
          ))}
        </div>
        
        <div className="mt-4 p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">
          <p className="text-xs text-slate-400">
            <span className="text-sky-400 font-medium">Pro tip:</span> Use triple backticks (```) to create code blocks with syntax highlighting. Specify the language after the opening backticks.
          </p>
        </div>
      </div>
    </div>
  );
};

// Stats card component
const StatsCard = ({ icon: Icon, label, value, color = 'sky' }) => {
  const colorClasses = {
    sky: 'from-sky-500/20 to-sky-600/10 border-sky-500/30 text-sky-400',
    emerald: 'from-emerald-500/20 to-emerald-600/10 border-emerald-500/30 text-emerald-400',
    amber: 'from-amber-500/20 to-amber-600/10 border-amber-500/30 text-amber-400',
    rose: 'from-rose-500/20 to-rose-600/10 border-rose-500/30 text-rose-400',
    violet: 'from-violet-500/20 to-violet-600/10 border-violet-500/30 text-violet-400',
  };
  
  return (
    <div className={`flex-1 rounded-xl border bg-gradient-to-br p-3 ${colorClasses[color]} backdrop-blur-sm`}>
      <div className="flex items-center justify-between">
        <Icon className="h-4 w-4 opacity-80" />
      </div>
      <p className="mt-2 text-2xl font-bold text-slate-100">{value}</p>
      <p className="text-[10px] uppercase tracking-wider opacity-60">{label}</p>
    </div>
  );
};

// Main TodoListPanel component
const TodoListPanel = () => {
  const [todos, setTodos] = useState([]);
  const [newTodoText, setNewTodoText] = useState('');
  const [newTodoPriority, setNewTodoPriority] = useState('medium');
  const [newTodoCategory, setNewTodoCategory] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState('');
  const [editPriority, setEditPriority] = useState('medium');
  const [editCategory, setEditCategory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isAddingTodo, setIsAddingTodo] = useState(false);
  const [filter, setFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState(null);
  const [priorityFilter, setPriorityFilter] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('newest');
  const [showCompleted, setShowCompleted] = useState(true);
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const [showKeyboardShortcuts, setShowKeyboardShortcuts] = useState(false);
  const [isCompactView, setIsCompactView] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const newTodoRef = useRef(null);
  const editInputRef = useRef(null);
  const searchRef = useRef(null);

  // Load todos on component mount
  useEffect(() => {
    loadTodos();
  }, []);

  // Global keyboard shortcuts
  useEffect(() => {
    const handleGlobalKeyDown = (e) => {
      // Ctrl/Cmd + K for search
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        searchRef.current?.focus();
      }
      // Escape to clear search
      if (e.key === 'Escape' && searchQuery) {
        setSearchQuery('');
      }
    };
    
    document.addEventListener('keydown', handleGlobalKeyDown);
    return () => document.removeEventListener('keydown', handleGlobalKeyDown);
  }, [searchQuery]);

  const loadTodos = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await robustApiClient.get('/api/todos');
      if (response.success) {
        // Enhance todos with default priority/category if not present
        const enhancedTodos = (response.todos || []).map(todo => ({
          ...todo,
          priority: todo.priority || 'medium',
          category: todo.category || null,
          pinned: todo.pinned || false,
        }));
        setTodos(enhancedTodos);
      } else {
        setError('Failed to load todos');
      }
    } catch (err) {
      console.error('Error loading todos:', err);
      setError('Failed to load todos');
    } finally {
      setLoading(false);
    }
  };

  const addTodo = async () => {
    if (!newTodoText.trim()) return;

    try {
      setIsAddingTodo(true);
      setError(null);

      const response = await robustApiClient.post('/api/todos', {
        text: newTodoText.trim(),
        priority: newTodoPriority,
        category: newTodoCategory,
      });

      if (response && response.success && response.todo) {
        const enhancedTodo = {
          ...response.todo,
          priority: response.todo.priority || newTodoPriority,
          category: response.todo.category || newTodoCategory,
        };
        setTodos([enhancedTodo, ...todos]);
        setNewTodoText('');
        setNewTodoPriority('medium');
        setNewTodoCategory(null);
        if (newTodoRef.current) {
          newTodoRef.current.focus();
        }
      } else {
        setError('Failed to add todo: Invalid response from server');
      }
    } catch (err) {
      console.error('Error adding todo:', err);
      setError(`Failed to add todo: ${err.message || 'Unknown error'}`);
    } finally {
      setIsAddingTodo(false);
    }
  };

  const toggleTodo = async (todoId, currentCompleted) => {
    try {
      setError(null);

      const response = await robustApiClient.put(`/api/todos/${todoId}`, {
        completed: !currentCompleted,
      });

      if (response && response.success && response.todos) {
        const enhancedTodos = response.todos.map(todo => ({
          ...todo,
          priority: todo.priority || 'medium',
          category: todo.category || null,
        }));
        setTodos(enhancedTodos);
      } else {
        setError('Failed to update todo: Invalid response');
      }
    } catch (err) {
      console.error('Error toggling todo:', err);
      setError(`Failed to update todo: ${err.message || 'Unknown error'}`);
    }
  };

  const togglePin = async (todoId, currentPinned) => {
    try {
      setError(null);

      const response = await robustApiClient.put(`/api/todos/${todoId}`, {
        pinned: !currentPinned,
      });

      if (response && response.success && response.todos) {
        const enhancedTodos = response.todos.map(todo => ({
          ...todo,
          priority: todo.priority || 'medium',
          category: todo.category || null,
        }));
        setTodos(enhancedTodos);
      } else {
        // Optimistic update if server doesn't return updated list
        setTodos(todos.map(t => 
          t.id === todoId ? { ...t, pinned: !currentPinned } : t
        ));
      }
    } catch (err) {
      console.error('Error toggling pin:', err);
    }
  };

  const deleteTodo = async (todoId) => {
    try {
      setError(null);

      const response = await robustApiClient.delete(`/api/todos/${todoId}`);

      if (response && response.success && response.todos) {
        const enhancedTodos = response.todos.map(todo => ({
          ...todo,
          priority: todo.priority || 'medium',
          category: todo.category || null,
        }));
        setTodos(enhancedTodos);
      } else {
        setError('Failed to delete todo: Invalid response');
      }
    } catch (err) {
      console.error('Error deleting todo:', err);
      setError(`Failed to delete todo: ${err.message || 'Unknown error'}`);
    }
  };

  const deleteCompleted = async () => {
    const completedIds = todos.filter((t) => t.completed).map((t) => t.id);
    if (completedIds.length === 0) return;

    if (!window.confirm(`Delete ${completedIds.length} completed todo(s)?`)) return;

    try {
      setError(null);
      for (const id of completedIds) {
        await robustApiClient.delete(`/api/todos/${id}`);
      }
      await loadTodos();
    } catch (err) {
      console.error('Error deleting completed todos:', err);
      setError('Failed to delete completed todos');
    }
  };

  const startEdit = (todo) => {
    setEditingId(todo.id);
    setEditText(todo.text);
    setEditPriority(todo.priority || 'medium');
    setEditCategory(todo.category || null);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditText('');
    setEditPriority('medium');
    setEditCategory(null);
  };

  const saveEdit = async (todoId) => {
    if (!editText.trim()) {
      cancelEdit();
      return;
    }

    try {
      setError(null);

      const response = await robustApiClient.put(`/api/todos/${todoId}`, {
        text: editText.trim(),
        priority: editPriority,
        category: editCategory,
      });

      if (response && response.success && response.todos) {
        const enhancedTodos = response.todos.map(todo => ({
          ...todo,
          priority: todo.priority || 'medium',
          category: todo.category || null,
        }));
        setTodos(enhancedTodos);
        cancelEdit();
      } else {
        setError('Failed to update todo: Invalid response');
      }
    } catch (err) {
      console.error('Error updating todo:', err);
      setError(`Failed to update todo: ${err.message || 'Unknown error'}`);
    }
  };

  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingId]);

  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  // Filter and sort todos
  const filteredAndSortedTodos = useMemo(() => {
    let result = [...todos];
    
    // Apply status filter
    if (filter === 'active') {
      result = result.filter(t => !t.completed);
    } else if (filter === 'completed') {
      result = result.filter(t => t.completed);
    } else if (!showCompleted) {
      result = result.filter(t => !t.completed);
    }
    
    // Apply category filter
    if (categoryFilter) {
      result = result.filter(t => t.category === categoryFilter);
    }
    
    // Apply priority filter
    if (priorityFilter) {
      result = result.filter(t => t.priority === priorityFilter);
    }
    
    // Apply search
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(t => t.text.toLowerCase().includes(query));
    }
    
    // Sort
    result.sort((a, b) => {
      // Pinned items always first
      if (a.pinned && !b.pinned) return -1;
      if (!a.pinned && b.pinned) return 1;
      
      switch (sortBy) {
        case 'oldest':
          return new Date(a.createdAt) - new Date(b.createdAt);
        case 'priority':
          return (PRIORITIES[a.priority]?.order || 2) - (PRIORITIES[b.priority]?.order || 2);
        case 'category':
          return (a.category || 'zzz').localeCompare(b.category || 'zzz');
        case 'newest':
        default:
          return new Date(b.createdAt) - new Date(a.createdAt);
      }
    });
    
    return result;
  }, [todos, filter, categoryFilter, priorityFilter, searchQuery, sortBy, showCompleted]);

  // Calculate stats
  const stats = useMemo(() => {
    const total = todos.length;
    const completed = todos.filter(t => t.completed).length;
    const active = total - completed;
    const urgent = todos.filter(t => !t.completed && t.priority === 'urgent').length;
    const high = todos.filter(t => !t.completed && t.priority === 'high').length;
    
    return { total, completed, active, urgent, high };
  }, [todos]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <div className="relative">
          <div className="h-12 w-12 rounded-full border-2 border-sky-500/30"></div>
          <div className="absolute inset-0 h-12 w-12 animate-spin rounded-full border-2 border-sky-400 border-t-transparent"></div>
        </div>
        <span className="mt-4 text-sm text-slate-400">Loading your notes...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4 pb-4">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-2xl border border-slate-700/50 bg-gradient-to-br from-slate-900/90 via-slate-900/70 to-slate-800/50 p-5 backdrop-blur-xl">
        <div className="absolute inset-0 bg-gradient-to-br from-sky-500/5 via-transparent to-violet-500/5"></div>
        <div className="absolute top-0 right-0 w-64 h-64 bg-sky-500/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2"></div>
        
        <div className="relative flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500 to-violet-500 shadow-lg shadow-sky-500/20">
              <Code2 className="h-6 w-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                Dev Notes
                <Sparkles className="h-4 w-4 text-amber-400" />
              </h2>
              <p className="text-sm text-slate-400">
                Track bugs, features, and coding ideas
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowKeyboardShortcuts(true)}
              className="p-2 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-800/50 transition-all"
              title="Keyboard shortcuts"
            >
              <Keyboard className="h-4 w-4" />
            </button>
            <button
              onClick={() => setIsCompactView(!isCompactView)}
              className={`p-2 rounded-lg transition-all ${
                isCompactView 
                  ? 'text-sky-400 bg-sky-500/10' 
                  : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/50'
              }`}
              title="Toggle compact view"
            >
              <MoreHorizontal className="h-4 w-4" />
            </button>
          </div>
        </div>
        
        {/* Quick Stats */}
        <div className="relative mt-4 grid grid-cols-4 gap-3">
          <StatsCard icon={Target} label="Total" value={stats.total} color="sky" />
          <StatsCard icon={Zap} label="Active" value={stats.active} color="amber" />
          <StatsCard icon={CheckCircle2} label="Done" value={stats.completed} color="emerald" />
          <StatsCard icon={AlertTriangle} label="Urgent" value={stats.urgent + stats.high} color="rose" />
        </div>
      </div>

      {/* Search and Filters Bar */}
      <div className="space-y-3">
        <div className="flex gap-2">
          {/* Search */}
          <div className={`relative flex-1 transition-all ${isSearchFocused ? 'ring-2 ring-sky-500/30' : ''} rounded-xl`}>
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              ref={searchRef}
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onFocus={() => setIsSearchFocused(true)}
              onBlur={() => setIsSearchFocused(false)}
              placeholder="Search notes... (⌘K)"
              className="w-full rounded-xl border border-slate-700/50 bg-slate-900/60 py-2.5 pl-10 pr-4 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-500/50 focus:outline-none transition-all"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          
          {/* Filter Toggle */}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-4 rounded-xl border transition-all ${
              showFilters || categoryFilter || priorityFilter
                ? 'border-sky-500/50 bg-sky-500/10 text-sky-300'
                : 'border-slate-700/50 bg-slate-900/60 text-slate-400 hover:text-slate-300'
            }`}
          >
            <Filter className="h-4 w-4" />
            <span className="text-sm">Filters</span>
            {(categoryFilter || priorityFilter) && (
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-sky-500 text-[10px] font-bold text-white">
                {(categoryFilter ? 1 : 0) + (priorityFilter ? 1 : 0)}
              </span>
            )}
          </button>
          
          {/* Sort */}
          <div className="relative">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="appearance-none rounded-xl border border-slate-700/50 bg-slate-900/60 px-4 py-2.5 pr-8 text-sm text-slate-300 focus:border-sky-500/50 focus:outline-none cursor-pointer"
            >
              <option value="newest">Newest</option>
              <option value="oldest">Oldest</option>
              <option value="priority">Priority</option>
              <option value="category">Category</option>
            </select>
            <SortDesc className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500 pointer-events-none" />
          </div>
        </div>
        
        {/* Expanded Filters */}
        {showFilters && (
          <div className="flex flex-wrap gap-2 p-3 rounded-xl border border-slate-700/50 bg-slate-900/40 animate-in slide-in-from-top-2 duration-200">
            {/* Status Filter */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Status:</span>
              {['all', 'active', 'completed'].map((status) => (
                <button
                  key={status}
                  onClick={() => setFilter(status)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                    filter === status
                      ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40'
                      : 'text-slate-400 hover:text-slate-300 border border-transparent hover:bg-slate-800/50'
                  }`}
                >
                  {status.charAt(0).toUpperCase() + status.slice(1)}
                </button>
              ))}
            </div>
            
            <div className="w-px h-6 bg-slate-700/50 mx-2"></div>
            
            {/* Category Filter */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-slate-500">Category:</span>
              <button
                onClick={() => setCategoryFilter(null)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                  !categoryFilter
                    ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40'
                    : 'text-slate-400 hover:text-slate-300 border border-transparent hover:bg-slate-800/50'
                }`}
              >
                All
              </button>
              {Object.entries(CATEGORIES).map(([key, cat]) => {
                const CIcon = cat.icon;
                return (
                  <button
                    key={key}
                    onClick={() => setCategoryFilter(categoryFilter === key ? null : key)}
                    className={`flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                      categoryFilter === key
                        ? `${cat.bgClass} ${cat.textClass} border ${cat.borderClass}`
                        : 'text-slate-400 hover:text-slate-300 border border-transparent hover:bg-slate-800/50'
                    }`}
                  >
                    <CIcon className="h-3 w-3" />
                    {cat.label}
                  </button>
                );
              })}
            </div>
            
            <div className="w-px h-6 bg-slate-700/50 mx-2"></div>
            
            {/* Priority Filter */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Priority:</span>
              <button
                onClick={() => setPriorityFilter(null)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                  !priorityFilter
                    ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40'
                    : 'text-slate-400 hover:text-slate-300 border border-transparent hover:bg-slate-800/50'
                }`}
              >
                All
              </button>
              {Object.entries(PRIORITIES).map(([key, priority]) => {
                const PIcon = priority.icon;
                const colorMap = {
                  rose: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
                  orange: 'bg-orange-500/20 text-orange-300 border-orange-500/40',
                  sky: 'bg-sky-500/20 text-sky-300 border-sky-500/40',
                  slate: 'bg-slate-500/20 text-slate-300 border-slate-500/40',
                };
                return (
                  <button
                    key={key}
                    onClick={() => setPriorityFilter(priorityFilter === key ? null : key)}
                    className={`flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                      priorityFilter === key
                        ? `${colorMap[priority.color]} border`
                        : 'text-slate-400 hover:text-slate-300 border border-transparent hover:bg-slate-800/50'
                    }`}
                  >
                    <PIcon className="h-3 w-3" />
                    {priority.label}
                  </button>
                );
              })}
            </div>
            
            {/* Clear All Filters */}
            {(categoryFilter || priorityFilter || filter !== 'all') && (
              <>
                <div className="w-px h-6 bg-slate-700/50 mx-2"></div>
                <button
                  onClick={() => {
                    setCategoryFilter(null);
                    setPriorityFilter(null);
                    setFilter('all');
                  }}
                  className="flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-medium text-rose-400 hover:bg-rose-500/10 transition-all"
                >
                  <X className="h-3 w-3" />
                  Clear all
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="flex items-center gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200 animate-in slide-in-from-top-2">
          <AlertCircle className="h-5 w-5 flex-shrink-0" />
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-auto">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Add New Todo */}
      <div className="rounded-2xl border border-slate-700/50 bg-gradient-to-br from-slate-900/80 to-slate-800/50 p-4 backdrop-blur-sm">
        <div className="space-y-3">
          <textarea
            ref={newTodoRef}
            value={newTodoText}
            onChange={(e) => setNewTodoText(e.target.value)}
            onKeyDown={(e) => {
              if ((e.key === 'Enter' && (e.ctrlKey || e.metaKey))) {
                e.preventDefault();
                addTodo();
              }
            }}
            placeholder="Add a new note... (use ``` for code blocks, ⌘+Enter to save)"
            rows={3}
            className="w-full rounded-xl border border-slate-700/50 bg-slate-950/50 px-4 py-3 text-sm text-slate-100 placeholder-slate-500 transition focus:border-sky-500/50 focus:outline-none focus:ring-2 focus:ring-sky-500/20 resize-y font-mono"
            disabled={isAddingTodo}
          />
          
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <PrioritySelector value={newTodoPriority} onChange={setNewTodoPriority} />
              <CategorySelector value={newTodoCategory} onChange={setNewTodoCategory} />
            </div>
            
            <div className="flex items-center gap-2">
              {newTodoText && (
                <button
                  onClick={() => {
                    setNewTodoText('');
                    setNewTodoPriority('medium');
                    setNewTodoCategory(null);
                  }}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-300 hover:bg-slate-800/50 transition-all"
                >
                  Clear
                </button>
              )}
              <button
                onClick={addTodo}
                disabled={!newTodoText.trim() || isAddingTodo}
                className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-500 to-violet-500 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-sky-500/20 transition-all hover:shadow-sky-500/30 hover:scale-[1.02] disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
              >
                <Plus className="h-4 w-4" />
                {isAddingTodo ? 'Adding...' : 'Add Note'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Todo List */}
      <div className="space-y-2">
        {filteredAndSortedTodos.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-700/50 bg-slate-900/30 p-12 text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-slate-800 to-slate-700">
              <ListTodo className="h-8 w-8 text-slate-500" />
            </div>
            <p className="text-base font-semibold text-slate-300">
              {searchQuery ? 'No matching notes' : filter === 'all' ? 'No notes yet' : filter === 'active' ? 'No active notes' : 'No completed notes'}
            </p>
            <p className="mt-2 text-sm text-slate-500">
              {searchQuery ? 'Try a different search term' : filter === 'all' ? 'Add your first coding note above' : 'Try a different filter'}
            </p>
          </div>
        ) : (
          filteredAndSortedTodos.map((todo) => {
            const category = CATEGORIES[todo.category];
            const priority = PRIORITIES[todo.priority] || PRIORITIES.medium;
            const PriorityIcon = priority.icon;
            
            return (
              <div
                key={todo.id}
                className={`group relative rounded-xl border backdrop-blur-sm transition-all duration-200 ${
                  todo.completed
                    ? 'border-slate-700/30 bg-slate-900/30'
                    : todo.pinned
                      ? 'border-amber-500/30 bg-gradient-to-r from-amber-500/5 to-transparent'
                      : 'border-slate-700/50 bg-slate-900/60 hover:border-slate-600/50 hover:bg-slate-900/80'
                } ${isCompactView ? 'p-2' : 'p-4'}`}
              >
                {/* Priority indicator bar */}
                <div className={`absolute left-0 top-0 bottom-0 w-1 rounded-l-xl ${
                  todo.completed 
                    ? 'bg-slate-700/50' 
                    : priority.color === 'rose' 
                      ? 'bg-rose-500' 
                      : priority.color === 'orange' 
                        ? 'bg-orange-500' 
                        : priority.color === 'sky' 
                          ? 'bg-sky-500' 
                          : 'bg-slate-600'
                }`}></div>
                
                <div className="flex items-start gap-3 pl-2">
                  {/* Checkbox */}
                  <button
                    onClick={() => toggleTodo(todo.id, todo.completed)}
                    className="flex-shrink-0 mt-0.5 transition-all hover:scale-110"
                  >
                    {todo.completed ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                    ) : (
                      <Circle className="h-5 w-5 text-slate-500 hover:text-slate-400" />
                    )}
                  </button>

                  {/* Todo Content */}
                  <div className="flex-1 min-w-0">
                    {editingId === todo.id ? (
                      <div className="space-y-3">
                        <textarea
                          ref={editInputRef}
                          value={editText}
                          onChange={(e) => setEditText(e.target.value)}
                          onKeyDown={(e) => {
                            if ((e.key === 'Enter' && (e.ctrlKey || e.metaKey))) {
                              e.preventDefault();
                              saveEdit(todo.id);
                            } else if (e.key === 'Escape') {
                              cancelEdit();
                            }
                          }}
                          rows={4}
                          className="w-full rounded-lg border border-sky-500/50 bg-slate-950/80 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500/20 resize-y font-mono"
                        />
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <PrioritySelector value={editPriority} onChange={setEditPriority} compact />
                            <CategorySelector value={editCategory} onChange={setEditCategory} compact />
                          </div>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={cancelEdit}
                              className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-300 hover:bg-slate-800/50 transition-all"
                            >
                              Cancel
                            </button>
                            <button
                              onClick={() => saveEdit(todo.id)}
                              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500/20 text-xs font-medium text-sky-300 hover:bg-sky-500/30 transition-all"
                            >
                              <Check className="h-3 w-3" />
                              Save
                            </button>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <>
                        {/* Tags Row */}
                        {(category || todo.pinned) && (
                          <div className="flex items-center gap-2 mb-2">
                            {todo.pinned && (
                              <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/20 border border-amber-500/40 text-[10px] font-medium text-amber-300">
                                <Pin className="h-2.5 w-2.5" />
                                Pinned
                              </span>
                            )}
                            {category && (
                              <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full ${category.bgClass} border ${category.borderClass} text-[10px] font-medium ${category.textClass}`}>
                                <category.icon className="h-2.5 w-2.5" />
                                {category.label}
                              </span>
                            )}
                          </div>
                        )}
                        
                        {/* Text Content */}
                        <div className={`text-sm break-words ${
                          todo.completed ? 'text-slate-500 line-through' : 'text-slate-200'
                        }`}>
                          {renderFormattedText(todo.text)}
                        </div>
                        
                        {/* Footer */}
                        {!isCompactView && (
                          <div className="flex items-center gap-3 mt-2 text-[10px] text-slate-500">
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {formatDate(todo.createdAt)}
                            </span>
                            {todo.updatedAt && todo.updatedAt !== todo.createdAt && (
                              <span className="flex items-center gap-1">
                                <Edit2 className="h-3 w-3" />
                                Updated {formatDate(todo.updatedAt)}
                              </span>
                            )}
                            <span className={`flex items-center gap-1 ${
                              priority.color === 'rose' ? 'text-rose-400' :
                              priority.color === 'orange' ? 'text-orange-400' :
                              priority.color === 'sky' ? 'text-sky-400' :
                              'text-slate-500'
                            }`}>
                              <PriorityIcon className="h-3 w-3" />
                              {priority.label}
                            </span>
                          </div>
                        )}
                      </>
                    )}
                  </div>

                  {/* Action Buttons */}
                  {editingId !== todo.id && (
                    <div className="flex items-center gap-1 opacity-0 transition-all group-hover:opacity-100">
                      <button
                        onClick={() => togglePin(todo.id, todo.pinned)}
                        className={`rounded-lg p-1.5 transition-all ${
                          todo.pinned 
                            ? 'text-amber-400 bg-amber-500/10' 
                            : 'text-slate-500 hover:text-amber-400 hover:bg-slate-800/50'
                        }`}
                        title={todo.pinned ? 'Unpin' : 'Pin'}
                      >
                        {todo.pinned ? <PinOff className="h-4 w-4" /> : <Pin className="h-4 w-4" />}
                      </button>
                      <button
                        onClick={() => startEdit(todo)}
                        className="rounded-lg p-1.5 text-slate-500 hover:text-sky-400 hover:bg-slate-800/50 transition-all"
                        title="Edit"
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => deleteTodo(todo.id)}
                        className="rounded-lg p-1.5 text-slate-500 hover:text-rose-400 hover:bg-slate-800/50 transition-all"
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer */}
      {todos.length > 0 && (
        <div className="flex items-center justify-between rounded-xl border border-slate-700/30 bg-slate-900/30 px-4 py-3">
          <div className="flex items-center gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1.5">
              <Hash className="h-3 w-3" />
              {filteredAndSortedTodos.length} of {todos.length} notes
            </span>
            {stats.completed > 0 && (
              <button
                onClick={deleteCompleted}
                className="flex items-center gap-1 text-rose-400 hover:text-rose-300 transition-colors font-medium"
              >
                <Archive className="h-3 w-3" />
                Clear {stats.completed} completed
              </button>
            )}
          </div>
          <button
            onClick={() => setShowCompleted(!showCompleted)}
            className={`flex items-center gap-1.5 text-xs transition-colors ${
              showCompleted ? 'text-slate-500 hover:text-slate-400' : 'text-sky-400'
            }`}
          >
            {showCompleted ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
            {showCompleted ? 'Hide' : 'Show'} completed
          </button>
        </div>
      )}

      {/* Keyboard Shortcuts Modal */}
      <KeyboardShortcutsModal 
        isOpen={showKeyboardShortcuts} 
        onClose={() => setShowKeyboardShortcuts(false)} 
      />
    </div>
  );
};

export default TodoListPanel;
