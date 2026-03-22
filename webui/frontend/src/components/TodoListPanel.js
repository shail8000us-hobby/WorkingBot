import { useState, useEffect, useRef, useMemo } from 'react';
import {
  Plus,
  Search,
  Trash2,
  Pin,
  PinOff,
  CheckCircle2,
  Circle,
  Code2,
  Copy,
  Check,
  Bug,
  Lightbulb,
  Wrench,
  BookOpen,
  FileText,
  AlertCircle,
  ArrowUp,
  ArrowDown,
  Minus,
  ListTodo,
  Clock,
  ChevronDown,
  X,
} from 'lucide-react';
import robustApiClient from '../utils/robustApiClient';

// ─── Constants ────────────────────────────────────────────────────────────────

const PRIORITIES = {
  urgent: { label: 'Urgent', icon: AlertCircle, dot: 'bg-rose-500',   badge: 'text-rose-400 bg-rose-500/15 border-rose-500/30'   },
  high:   { label: 'High',   icon: ArrowUp,     dot: 'bg-orange-400', badge: 'text-orange-400 bg-orange-500/15 border-orange-500/30' },
  medium: { label: 'Medium', icon: Minus,       dot: 'bg-sky-500',    badge: 'text-sky-400 bg-sky-500/15 border-sky-500/30'    },
  low:    { label: 'Low',    icon: ArrowDown,   dot: 'bg-slate-500',  badge: 'text-slate-400 bg-slate-600/30 border-slate-600/30'  },
};

const CATEGORIES = {
  bug:      { label: 'Bug',      icon: Bug,       cls: 'text-rose-300    bg-rose-500/15    border-rose-500/30'    },
  feature:  { label: 'Feature',  icon: Lightbulb, cls: 'text-emerald-300 bg-emerald-500/15 border-emerald-500/30' },
  refactor: { label: 'Refactor', icon: Wrench,    cls: 'text-violet-300  bg-violet-500/15  border-violet-500/30'  },
  research: { label: 'Research', icon: BookOpen,  cls: 'text-amber-300   bg-amber-500/15   border-amber-500/30'   },
  note:     { label: 'Note',     icon: FileText,  cls: 'text-sky-300     bg-sky-500/15     border-sky-500/30'     },
  code:     { label: 'Code',     icon: Code2,     cls: 'text-cyan-300    bg-cyan-500/15    border-cyan-500/30'    },
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatTime(iso) {
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso)) / 1000;
  if (diff < 60)     return 'just now';
  if (diff < 3600)   return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400)  return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
}

function getNoteTitle(text) {
  if (!text?.trim()) return 'Untitled Note';
  const first = text.trim().split('\n')[0].replace(/^#+\s*/, '').replace(/\*\*/g, '').trim();
  return first || 'Untitled Note';
}

function getNotePreview(text) {
  if (!text?.trim()) return '';
  const lines = text.trim().split('\n').filter(l => l.trim() && !l.startsWith('```'));
  return lines.slice(1).join(' ').replace(/`/g, '').trim();
}

// ─── Small UI pieces ──────────────────────────────────────────────────────────

const CategoryBadge = ({ category }) => {
  const c = CATEGORIES[category];
  if (!c) return null;
  const Icon = c.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-medium border ${c.cls}`}>
      <Icon className="h-2.5 w-2.5" />{c.label}
    </span>
  );
};

const CopyButton = ({ text }) => {
  const [copied, setCopied] = useState(false);
  const handle = async () => {
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch {}
  };
  return (
    <button onClick={handle} className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white transition-all">
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
      {copied ? 'Copied!' : 'Copy all'}
    </button>
  );
};

// Custom styled dropdown
const DropdownMenu = ({ options, value, onChange, placeholder = 'Select' }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const fn = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', fn);
    return () => document.removeEventListener('mousedown', fn);
  }, []);

  const current = options.find(o => o.value === value);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg border border-slate-700 bg-slate-800/80 text-slate-200 hover:bg-slate-700 hover:border-slate-600 transition-all whitespace-nowrap"
      >
        {current?.icon && <current.icon className="h-3.5 w-3.5 flex-shrink-0 opacity-80" />}
        <span className="font-medium">{current?.label || placeholder}</span>
        <ChevronDown className="h-3.5 w-3.5 text-slate-500 ml-0.5" />
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1.5 z-50 min-w-[140px] rounded-xl border border-slate-700 bg-slate-900 shadow-2xl overflow-hidden">
          {options.map(opt => (
            <button
              key={String(opt.value)}
              onClick={() => { onChange(opt.value); setOpen(false); }}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 text-xs text-left transition-colors ${
                value === opt.value
                  ? 'bg-sky-500/15 text-sky-300'
                  : 'text-slate-300 hover:bg-slate-800'
              }`}
            >
              {opt.icon && <opt.icon className="h-3.5 w-3.5 flex-shrink-0 opacity-70" />}
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

// Note card in left panel
const NoteCard = ({ note, isSelected, onClick }) => {
  const title   = getNoteTitle(note.text);
  const preview = getNotePreview(note.text);
  const pri = PRIORITIES[note.priority] || PRIORITIES.medium;

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3.5 border-b border-slate-800/80 border-l-[3px] transition-all group ${
        isSelected
          ? 'bg-slate-700/50 border-l-sky-400'
          : 'border-l-transparent hover:bg-slate-800/50 hover:border-l-slate-600'
      }`}
    >
      {/* Title row */}
      <div className="flex items-start gap-2.5 mb-1.5">
        <div className={`mt-[5px] h-2 w-2 rounded-full flex-shrink-0 ${pri.dot}`} />
        <span
          className={`text-[13px] font-semibold leading-snug flex-1 ${
            note.completed
              ? 'line-through text-slate-600'
              : isSelected ? 'text-white' : 'text-slate-100'
          }`}
          style={{ wordBreak: 'break-word' }}
        >
          {title}
        </span>
        {note.pinned && <Pin className="h-3 w-3 text-amber-400 flex-shrink-0 mt-1" />}
      </div>

      {/* Preview */}
      {preview && (
        <p
          className="text-[11px] text-slate-500 ml-[18px] leading-relaxed mb-2"
          style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
        >
          {preview}
        </p>
      )}

      {/* Footer */}
      <div className="flex items-center gap-1.5 ml-[18px]">
        {note.category && <CategoryBadge category={note.category} />}
        <span className="text-[10px] text-slate-600 ml-auto font-medium">{formatTime(note.updatedAt || note.createdAt)}</span>
      </div>
    </button>
  );
};

// ─── Code block renderer ──────────────────────────────────────────────────────

const CodeBlock = ({ code, language }) => {
  const [copied, setCopied] = useState(false);
  const handle = async () => {
    try { await navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch {}
  };
  return (
    <div className="my-3 rounded-xl border border-slate-700 bg-slate-950 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-slate-800/60 border-b border-slate-700">
        <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
          <Code2 className="h-3 w-3" />{language}
        </span>
        <button onClick={handle} className="flex items-center gap-1 text-[10px] text-slate-500 hover:text-slate-300 transition-colors">
          {copied ? <><Check className="h-3 w-3 text-emerald-400" /><span className="text-emerald-400">Copied</span></> : <><Copy className="h-3 w-3" /><span>Copy</span></>}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto">
        <code className="font-mono text-[12px] text-slate-300 leading-relaxed">{code}</code>
      </pre>
    </div>
  );
};

const renderInline = (text) => {
  if (!text) return null;
  return text.split(/(`[^`]+`)/g).map((part, i) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} className="mx-0.5 rounded-md bg-slate-800 px-1.5 py-0.5 font-mono text-xs text-cyan-300 border border-slate-700">{part.slice(1, -1)}</code>;
    }
    return part;
  });
};

const renderPreview = (text) => {
  if (!text) return null;
  const parts = [];
  const re = /```(\w+)?\n?([\s\S]*?)```/g;
  let last = 0, key = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(<span key={key++} className="whitespace-pre-wrap">{renderInline(text.slice(last, m.index))}</span>);
    parts.push(<CodeBlock key={key++} code={m[2].trim()} language={m[1] || 'code'} />);
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(<span key={key++} className="whitespace-pre-wrap">{renderInline(text.slice(last))}</span>);
  return parts.length > 0 ? parts : <span className="whitespace-pre-wrap">{text}</span>;
};

// ─── Toolbar button ───────────────────────────────────────────────────────────

const TBtn = ({ onClick, children, mono = false }) => (
  <button
    onClick={onClick}
    className={`px-3 py-1.5 text-xs rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white hover:border-slate-600 transition-all ${mono ? 'font-mono' : ''}`}
  >
    {children}
  </button>
);

// ─── Dropdown options ─────────────────────────────────────────────────────────

const PRIORITY_OPTIONS = [
  { value: 'urgent', label: 'Urgent', icon: AlertCircle },
  { value: 'high',   label: 'High',   icon: ArrowUp    },
  { value: 'medium', label: 'Medium', icon: Minus      },
  { value: 'low',    label: 'Low',    icon: ArrowDown  },
];

const CATEGORY_OPTIONS = [
  { value: null,       label: 'No category', icon: X        },
  { value: 'bug',      label: 'Bug',         icon: Bug      },
  { value: 'feature',  label: 'Feature',     icon: Lightbulb },
  { value: 'refactor', label: 'Refactor',    icon: Wrench   },
  { value: 'research', label: 'Research',    icon: BookOpen },
  { value: 'note',     label: 'Note',        icon: FileText },
  { value: 'code',     label: 'Code',        icon: Code2    },
];

// ─── Main Component ───────────────────────────────────────────────────────────

export default function TodoListPanel() {
  const [notes, setNotes]             = useState([]);
  const [selectedId, setSelectedId]   = useState(null);
  const [titleText, setTitleText]     = useState('');
  const [bodyText, setBodyText]       = useState('');
  const [isDirty, setIsDirty]         = useState(false);
  const [saveStatus, setSaveStatus]   = useState('idle');
  const [previewMode, setPreviewMode] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterCat, setFilterCat]     = useState('all');
  const [filterPri, setFilterPri]     = useState('all');
  const [showDone, setShowDone]       = useState(false);
  const [loading, setLoading]         = useState(true);

  const saveTimerRef = useRef(null);
  const titleRef     = useRef(null);
  const bodyRef      = useRef(null);
  const searchRef    = useRef(null);
  // Always holds the latest combined text so Cmd+S handler isn't stale
  const latestRef    = useRef('');

  const selectedNote = notes.find(n => n.id === selectedId) || null;

  useEffect(() => { loadNotes(); }, []);

  useEffect(() => {
    const h = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); searchRef.current?.focus(); }
    };
    document.addEventListener('keydown', h);
    return () => document.removeEventListener('keydown', h);
  }, []);

  // Keep latestRef in sync
  const fullText = titleText + (bodyText ? '\n' + bodyText : '');
  latestRef.current = fullText;

  // Auto-save 1.5s after any edit (does NOT depend on isDirty — blur saves can't cancel this)
  useEffect(() => {
    if (!selectedId || !isDirty) return;
    setSaveStatus('saving');
    clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => doSave(selectedId, latestRef.current), 1500);
    return () => clearTimeout(saveTimerRef.current);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [titleText, bodyText, selectedId]); // intentionally excludes isDirty from deps

  // ⌘S / Ctrl+S — save immediately
  useEffect(() => {
    const h = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        if (selectedId) {
          clearTimeout(saveTimerRef.current);
          doSave(selectedId, latestRef.current);
        }
      }
    };
    document.addEventListener('keydown', h);
    return () => document.removeEventListener('keydown', h);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  // ── Actions ────────────────────────────────────────

  const loadNotes = async () => {
    try {
      const data = await robustApiClient.get('/api/todos');
      if (data?.success) {
        setNotes(data.todos);
        const first = data.todos.find(n => !n.completed) || data.todos[0];
        if (first) selectNote(first);
      }
    } catch {}
    finally { setLoading(false); }
  };

  const selectNote = (note) => {
    // Save any pending changes before switching notes
    if (isDirty && selectedId) {
      clearTimeout(saveTimerRef.current);
      doSave(selectedId, latestRef.current);
    }
    const lines = (note.text || '').split('\n');
    setSelectedId(note.id);
    setTitleText(lines[0] || '');
    setBodyText(lines.slice(1).join('\n'));
    setIsDirty(false);
    setSaveStatus('idle');
    setPreviewMode(false);
  };

  const doSave = async (id, text) => {
    try {
      const data = await robustApiClient.put(`/api/todos/${id}`, { text });
      if (data?.success) {
        setNotes(prev => prev.map(n => n.id === id ? { ...n, text, updatedAt: new Date().toISOString() } : n));
        setSaveStatus('saved');
        // DO NOT reset isDirty here — it would cancel a pending body auto-save
      }
    } catch { setSaveStatus('idle'); }
  };

  const createNote = async () => {
    try {
      const data = await robustApiClient.post('/api/todos', { text: '', priority: 'medium', category: null, pinned: false });
      if (data?.success) {
        const n = data.todo;
        setNotes(prev => [n, ...prev]);
        selectNote(n);
        setTimeout(() => titleRef.current?.focus(), 50);
      }
    } catch {}
  };

  const deleteNote = async (id) => {
    try {
      const data = await robustApiClient.delete(`/api/todos/${id}`);
      if (data?.success) {
        const remaining = notes.filter(n => n.id !== id);
        setNotes(remaining);
        if (selectedId === id) {
          if (remaining.length > 0) selectNote(remaining[0]);
          else { setSelectedId(null); setTitleText(''); setBodyText(''); setIsDirty(false); setSaveStatus('idle'); }
        }
      }
    } catch {}
  };

  const updateMeta = async (id, updates) => {
    try {
      const data = await robustApiClient.put(`/api/todos/${id}`, updates);
      if (data?.success) {
        setNotes(prev => prev.map(n => n.id === id ? { ...n, ...updates, updatedAt: new Date().toISOString() } : n));
      }
    } catch {}
  };

  // ── Editor handlers (with optimistic sidebar update) ──

  const handleTitleChange = (e) => {
    const val = e.target.value;
    setTitleText(val);
    setIsDirty(true);
    // Update sidebar card immediately (optimistic) so user sees title change
    setNotes(prev => prev.map(n =>
      n.id === selectedId ? { ...n, text: val + (bodyText ? '\n' + bodyText : '') } : n
    ));
  };

  const handleBodyChange = (e) => {
    const val = e.target.value;
    setBodyText(val);
    setIsDirty(true);
  };

  // Save immediately when focus leaves editor
  const handleBlur = () => {
    if (isDirty && selectedId) {
      clearTimeout(saveTimerRef.current);
      doSave(selectedId, latestRef.current);
    }
  };

  const insertAtCursor = (before, after = '') => {
    const el = bodyRef.current;
    if (!el) return;
    const s = el.selectionStart, e2 = el.selectionEnd;
    const sel = bodyText.slice(s, e2);
    const next = bodyText.slice(0, s) + before + sel + after + bodyText.slice(e2);
    setBodyText(next);
    setIsDirty(true);
    setTimeout(() => {
      el.selectionStart = s + before.length;
      el.selectionEnd   = s + before.length + sel.length;
      el.focus();
    }, 0);
  };

  // ── Filtered list ──────────────────────────────────

  const filtered = useMemo(() => {
    let list = notes.filter(n => showDone || !n.completed);
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      list = list.filter(n => n.text?.toLowerCase().includes(q));
    }
    if (filterCat !== 'all') list = list.filter(n => n.category === filterCat);
    if (filterPri !== 'all') list = list.filter(n => n.priority === filterPri);
    list.sort((a, b) => {
      if (a.pinned && !b.pinned) return -1;
      if (!a.pinned && b.pinned) return 1;
      return new Date(b.updatedAt || b.createdAt) - new Date(a.updatedAt || a.createdAt);
    });
    return list;
  }, [notes, searchQuery, filterCat, filterPri, showDone]);

  // ── Render ─────────────────────────────────────────

  return (
    <div
      className="flex overflow-hidden rounded-xl border border-slate-700/60 bg-slate-950"
      style={{ height: '74vh', minHeight: 520 }}
    >
      {/* ══════════════ LEFT SIDEBAR ══════════════ */}
      <div className="w-72 flex-shrink-0 flex flex-col border-r border-slate-800 bg-[#0f1117]">

        {/* Top controls */}
        <div className="p-3 space-y-2.5 border-b border-slate-800">

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500 pointer-events-none" />
            <input
              ref={searchRef}
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search notes... (⌘K)"
              className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-800 bg-slate-900 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-600/50 focus:bg-slate-800/80 transition-colors"
            />
          </div>

          {/* Filters */}
          <div className="grid grid-cols-2 gap-1.5">
            <select
              value={filterCat}
              onChange={e => setFilterCat(e.target.value)}
              className="text-[11px] py-1.5 px-2 rounded-lg border border-slate-800 bg-slate-900 text-slate-400 focus:outline-none cursor-pointer"
            >
              <option value="all">All categories</option>
              {Object.entries(CATEGORIES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
            <select
              value={filterPri}
              onChange={e => setFilterPri(e.target.value)}
              className="text-[11px] py-1.5 px-2 rounded-lg border border-slate-800 bg-slate-900 text-slate-400 focus:outline-none cursor-pointer"
            >
              <option value="all">All priorities</option>
              {Object.entries(PRIORITIES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </div>

          {/* Actions row */}
          <div className="flex items-center justify-between">
            <button
              onClick={() => setShowDone(s => !s)}
              className={`text-[11px] transition-colors font-medium ${showDone ? 'text-sky-400' : 'text-slate-600 hover:text-slate-400'}`}
            >
              {showDone ? '✓ Showing done' : 'Show done'}
            </button>
            <button
              onClick={createNote}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-semibold bg-sky-500 rounded-lg text-white hover:bg-sky-400 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />New Note
            </button>
          </div>
        </div>

        {/* Note list */}
        <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
          {loading ? (
            <div className="p-8 text-center text-xs text-slate-600">Loading notes...</div>
          ) : filtered.length === 0 ? (
            <div className="p-8 text-center">
              <ListTodo className="h-10 w-10 text-slate-800 mx-auto mb-3" />
              <p className="text-xs text-slate-600">{searchQuery ? 'No results' : 'No notes yet'}</p>
            </div>
          ) : (
            filtered.map(note => (
              <NoteCard
                key={note.id}
                note={note}
                isSelected={note.id === selectedId}
                onClick={() => selectNote(note)}
              />
            ))
          )}
        </div>

        {/* Sidebar footer */}
        <div className="px-4 py-2 border-t border-slate-800 flex items-center justify-between">
          <p className="text-[10px] text-slate-700 font-medium">{filtered.length} of {notes.length}</p>
          {notes.filter(n => n.completed).length > 0 && (
            <p className="text-[10px] text-slate-700">{notes.filter(n => n.completed).length} done</p>
          )}
        </div>
      </div>

      {/* ══════════════ RIGHT EDITOR ══════════════ */}
      {selectedNote ? (
        <div className="flex-1 flex flex-col min-w-0 bg-[#0c0e14]">

          {/* Top meta bar */}
          <div className="flex items-center gap-2 px-5 py-3 border-b border-slate-800 bg-[#0f1117]">
            <DropdownMenu
              options={PRIORITY_OPTIONS}
              value={selectedNote.priority || 'medium'}
              onChange={p => updateMeta(selectedNote.id, { priority: p })}
            />
            <DropdownMenu
              options={CATEGORY_OPTIONS}
              value={selectedNote.category || null}
              onChange={c => updateMeta(selectedNote.id, { category: c })}
              placeholder="No category"
            />

            <div className="ml-auto flex items-center gap-1">
              {/* Save button */}
              <button
                onClick={() => { clearTimeout(saveTimerRef.current); doSave(selectedId, latestRef.current); }}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border font-semibold transition-all ${
                  isDirty
                    ? 'bg-emerald-500 border-emerald-400 text-white hover:bg-emerald-400'
                    : 'bg-transparent border-slate-700 text-slate-600 cursor-default'
                }`}
                title="Save (⌘S)"
              >
                <Check className="h-3.5 w-3.5" />
                {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? 'Saved' : 'Save'}
              </button>

              {/* Preview toggle */}
              <button
                onClick={() => setPreviewMode(m => !m)}
                className={`px-3 py-1.5 text-xs rounded-lg border transition-all font-medium ${
                  previewMode
                    ? 'bg-sky-500/15 border-sky-600/40 text-sky-300'
                    : 'bg-transparent border-slate-700 text-slate-500 hover:text-slate-300 hover:border-slate-600'
                }`}
              >
                {previewMode ? 'Edit' : 'Preview'}
              </button>

              <div className="w-px h-5 bg-slate-800 mx-1" />

              {/* Done */}
              <button
                onClick={() => updateMeta(selectedNote.id, { completed: !selectedNote.completed })}
                title={selectedNote.completed ? 'Mark active' : 'Mark done'}
                className={`p-2 rounded-lg transition-all ${
                  selectedNote.completed
                    ? 'text-emerald-400 bg-emerald-500/10'
                    : 'text-slate-600 hover:text-slate-300 hover:bg-slate-800'
                }`}
              >
                {selectedNote.completed ? <CheckCircle2 className="h-4 w-4" /> : <Circle className="h-4 w-4" />}
              </button>

              {/* Pin */}
              <button
                onClick={() => updateMeta(selectedNote.id, { pinned: !selectedNote.pinned })}
                title={selectedNote.pinned ? 'Unpin' : 'Pin'}
                className={`p-2 rounded-lg transition-all ${
                  selectedNote.pinned
                    ? 'text-amber-400 bg-amber-500/10'
                    : 'text-slate-600 hover:text-slate-300 hover:bg-slate-800'
                }`}
              >
                {selectedNote.pinned ? <Pin className="h-4 w-4" /> : <PinOff className="h-4 w-4" />}
              </button>

              {/* Delete */}
              <button
                onClick={() => deleteNote(selectedNote.id)}
                title="Delete note"
                className="p-2 rounded-lg text-slate-700 hover:text-rose-400 hover:bg-rose-500/10 transition-all"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Formatting toolbar (edit mode only) */}
          {!previewMode && (
            <div className="flex items-center gap-2 px-5 py-2.5 border-b border-slate-800/60 bg-[#0f1117]/60">
              <TBtn mono onClick={() => insertAtCursor('```bash\n', '\n```')}>```code</TBtn>
              <TBtn mono onClick={() => insertAtCursor('`', '`')}>`inline`</TBtn>
              <TBtn onClick={() => insertAtCursor('**', '**')}>
                <span className="font-bold">B</span>
              </TBtn>
              <TBtn mono onClick={() => insertAtCursor('# ')}># Heading</TBtn>
              <TBtn mono onClick={() => insertAtCursor('- ')}>• List</TBtn>
              <div className="ml-auto flex items-center gap-2">
                {/* Save status — always visible in toolbar */}
                {saveStatus !== 'idle' && (
                  <span className={`text-[11px] font-medium ${saveStatus === 'saved' ? 'text-emerald-400' : 'text-slate-500'}`}>
                    {saveStatus === 'saving' ? 'Saving...' : '✓ Saved'}
                  </span>
                )}
                {isDirty && (
                  <button
                    onClick={() => { clearTimeout(saveTimerRef.current); doSave(selectedId, latestRef.current); }}
                    className="flex items-center gap-1.5 px-3 py-1 text-xs rounded-lg bg-emerald-500 text-white font-semibold hover:bg-emerald-400 transition-colors"
                  >
                    <Check className="h-3 w-3" />Save
                  </button>
                )}
                <CopyButton text={fullText} />
              </div>
            </div>
          )}

          {/* Editor or Preview */}
          {previewMode ? (
            <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
              {/* Title in preview */}
              {titleText && (
                <h1 className="px-8 pt-6 pb-2 text-xl font-bold text-white border-b border-slate-800/60 mb-0">
                  {titleText}
                </h1>
              )}
              <div className="px-8 py-6 text-sm text-slate-300 leading-[1.9]">
                {bodyText.trim()
                  ? renderPreview(bodyText)
                  : <span className="text-slate-700 italic">No content yet.</span>}
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col min-h-0">
              {/* Title input */}
              <input
                ref={titleRef}
                type="text"
                value={titleText}
                onChange={handleTitleChange}
                onBlur={handleBlur}
                onKeyDown={e => {
                  if (e.key === 'Enter') { e.preventDefault(); bodyRef.current?.focus(); }
                }}
                placeholder="Note title..."
                spellCheck={false}
                className="w-full px-8 pt-5 pb-3 bg-transparent text-lg font-semibold text-white placeholder-slate-700 focus:outline-none border-b border-slate-800/60"
              />
              {/* Body textarea */}
              <textarea
                ref={bodyRef}
                value={bodyText}
                onChange={handleBodyChange}
                onBlur={handleBlur}
                placeholder="Start writing... (⌘S to save, auto-saves when you click away)"
                spellCheck={false}
                className="flex-1 w-full px-8 py-4 bg-transparent text-[13px] text-slate-200 placeholder-slate-600 resize-none focus:outline-none font-mono leading-[1.9]"
              />
            </div>
          )}

          {/* Status bar */}
          <div className="flex items-center justify-between px-5 py-2 border-t border-slate-800/60 bg-[#0f1117]/60">
            <div className="flex items-center gap-4 text-[11px] text-slate-700 font-medium">
              <span>{fullText.length} chars</span>
              <span>{fullText.split('\n').length} lines</span>
              <span>{fullText.trim().split(/\s+/).filter(Boolean).length} words</span>
            </div>
            <span className="text-[11px] text-slate-700 font-medium flex items-center gap-1.5">
              <Clock className="h-3 w-3" />
              Updated {formatTime(selectedNote.updatedAt || selectedNote.createdAt)}
            </span>
          </div>
        </div>
      ) : (
        /* Empty state */
        <div className="flex-1 flex items-center justify-center bg-[#0c0e14]">
          <div className="text-center">
            <div className="h-16 w-16 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center mx-auto mb-4">
              <ListTodo className="h-8 w-8 text-slate-700" />
            </div>
            <p className="text-sm text-slate-500 font-medium mb-1">No note selected</p>
            <p className="text-xs text-slate-700 mb-5">Pick one from the list or create a new one</p>
            <button
              onClick={createNote}
              className="flex items-center gap-2 mx-auto px-5 py-2.5 text-sm font-semibold bg-sky-500 rounded-xl text-white hover:bg-sky-400 transition-colors"
            >
              <Plus className="h-4 w-4" />New Note
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
