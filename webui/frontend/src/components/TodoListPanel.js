import { useEffect, useMemo, useState } from 'react';
import {
  CheckCircle2,
  Circle,
  Edit3,
  Loader2,
  Pin,
  PinOff,
  Plus,
  Trash2,
  X,
} from 'lucide-react';
import robustApiClient from '../utils/robustApiClient';

const MAX_TITLE_LENGTH = 120;
const MAX_WORK_LENGTH = 5000;

function toSafeString(value) {
  return typeof value === 'string' ? value : '';
}

function splitLegacyText(text) {
  const cleaned = toSafeString(text).trim();
  if (!cleaned) return { title: '', work: '' };

  const lines = cleaned.split('\n');
  const title = (lines[0] || '').trim();
  const work = lines.slice(1).join('\n').trim();

  return { title, work };
}

function normalizeTodo(rawTodo) {
  const todo = rawTodo && typeof rawTodo === 'object' ? rawTodo : {};
  const legacy = splitLegacyText(todo.text);

  const title = toSafeString(todo.title).trim() || legacy.title || 'Untitled';
  const work = toSafeString(todo.work).trim() || legacy.work;
  const createdAt = toSafeString(todo.createdAt) || new Date().toISOString();
  const updatedAt = toSafeString(todo.updatedAt) || createdAt;
  const id = String(todo.id ?? `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);

  return {
    ...todo,
    id,
    title,
    work,
    text: `${title}${work ? `\n${work}` : ''}`,
    completed: Boolean(todo.completed),
    pinned: Boolean(todo.pinned),
    createdAt,
    updatedAt,
  };
}

function sortByRecent(todos) {
  return [...todos].sort((a, b) => {
    if (a.pinned && !b.pinned) return -1;
    if (!a.pinned && b.pinned) return 1;

    const aTime = new Date(a.updatedAt || a.createdAt || 0).getTime();
    const bTime = new Date(b.updatedAt || b.createdAt || 0).getTime();
    return bTime - aTime;
  });
}

function formatTime(iso) {
  if (!iso) return '';

  const diffSeconds = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diffSeconds < 60) return 'just now';
  if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}m ago`;
  if (diffSeconds < 86400) return `${Math.floor(diffSeconds / 3600)}h ago`;
  if (diffSeconds < 604800) return `${Math.floor(diffSeconds / 86400)}d ago`;

  return new Date(iso).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
  });
}

function TodoCard({ todo, isBusy, onToggleDone, onTogglePin, onEdit, onDelete }) {
  return (
    <li className="rounded-lg bg-slate-900/35 p-3">
      <div className="flex items-start gap-3">
        <button
          type="button"
          onClick={() => onToggleDone(todo)}
          disabled={isBusy}
          title={todo.completed ? 'Mark as pending' : 'Mark as done'}
          className={`mt-0.5 transition-colors ${
            todo.completed
              ? 'text-emerald-400 hover:text-emerald-300'
              : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          {todo.completed ? <CheckCircle2 className="h-4 w-4" /> : <Circle className="h-4 w-4" />}
        </button>

        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-1.5">
            <p
              className={`text-sm font-semibold break-words ${
                todo.completed ? 'text-slate-500 line-through' : 'text-slate-100'
              }`}
            >
              {todo.title}
            </p>
            {todo.pinned && (
              <Pin className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-amber-400" />
            )}
          </div>

          <p
            className={`mt-1 whitespace-pre-wrap break-words text-[13px] leading-relaxed ${
              todo.completed ? 'text-slate-600' : 'text-slate-400'
            }`}
          >
            {todo.work || 'No work description yet.'}
          </p>

          <p className="mt-2 text-[10px] text-slate-600">
            Updated {formatTime(todo.updatedAt || todo.createdAt)}
          </p>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onTogglePin(todo)}
            disabled={isBusy}
            title={todo.pinned ? 'Unpin' : 'Pin'}
            className={`rounded-md p-1.5 transition-colors ${
              todo.pinned
                ? 'text-amber-400 hover:bg-amber-500/10 hover:text-amber-300'
                : 'text-slate-600 hover:bg-slate-800 hover:text-slate-300'
            }`}
          >
            {todo.pinned ? <Pin className="h-3.5 w-3.5" /> : <PinOff className="h-3.5 w-3.5" />}
          </button>

          <button
            type="button"
            onClick={() => onEdit(todo)}
            disabled={isBusy}
            title="Edit"
            className="rounded-md p-1.5 text-slate-500 hover:bg-slate-800 hover:text-slate-300 transition-colors"
          >
            <Edit3 className="h-3.5 w-3.5" />
          </button>

          <button
            type="button"
            onClick={() => onDelete(todo.id)}
            disabled={isBusy}
            title="Delete"
            className="rounded-md p-1.5 text-slate-600 hover:bg-rose-500/10 hover:text-rose-400 transition-colors"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </li>
  );
}

export default function TodoListPanel() {
  const [todos, setTodos] = useState([]);
  const [title, setTitle] = useState('');
  const [work, setWork] = useState('');
  const [editingId, setEditingId] = useState(null);

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchTodos();
  }, []);

  const pendingTodos = useMemo(
    () => sortByRecent(todos.filter((todo) => !todo.completed)),
    [todos]
  );

  const doneTodos = useMemo(
    () => sortByRecent(todos.filter((todo) => todo.completed)),
    [todos]
  );

  const fetchTodos = async () => {
    setLoading(true);
    setError('');

    try {
      const data = await robustApiClient.get('/api/todos');
      if (!data?.success) throw new Error('Failed to load todos');

      const normalized = Array.isArray(data.todos)
        ? data.todos.map(normalizeTodo)
        : [];

      setTodos(sortByRecent(normalized));
    } catch {
      setError('Unable to load todos right now.');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setTitle('');
    setWork('');
    setEditingId(null);
  };

  const applyTodosFromResponse = (responseData) => {
    if (Array.isArray(responseData?.todos)) {
      setTodos(sortByRecent(responseData.todos.map(normalizeTodo)));
      return true;
    }

    return false;
  };

  const validateInput = () => {
    const cleanTitle = title.trim();
    const cleanWork = work.trim();

    if (!cleanTitle) {
      setError('Please enter a title.');
      return null;
    }

    if (!cleanWork) {
      setError('Please describe the work to do.');
      return null;
    }

    return {
      title: cleanTitle.slice(0, MAX_TITLE_LENGTH),
      work: cleanWork.slice(0, MAX_WORK_LENGTH),
    };
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (busy) return;

    const payload = validateInput();
    if (!payload) return;

    setBusy(true);
    setError('');

    try {
      const body = {
        ...payload,
        text: `${payload.title}\n${payload.work}`,
      };

      if (editingId) {
        const data = await robustApiClient.put(`/api/todos/${editingId}`, body);

        if (!data?.success) throw new Error('Failed to update todo');

        if (!applyTodosFromResponse(data)) {
          setTodos((previous) =>
            sortByRecent(
              previous.map((todo) =>
                todo.id === editingId
                  ? normalizeTodo({
                      ...todo,
                      ...body,
                      updatedAt: new Date().toISOString(),
                    })
                  : todo
              )
            )
          );
        }
      } else {
        const data = await robustApiClient.post('/api/todos', body);

        if (!data?.success || !data.todo) throw new Error('Failed to create todo');

        const newTodo = normalizeTodo(data.todo);
        setTodos((previous) => sortByRecent([newTodo, ...previous]));
      }

      resetForm();
    } catch {
      setError('Unable to save your todo. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const handleToggleDone = async (todo) => {
    if (busy) return;

    setBusy(true);
    setError('');

    try {
      const data = await robustApiClient.put(`/api/todos/${todo.id}`, {
        completed: !todo.completed,
      });

      if (!data?.success) throw new Error('Failed to toggle todo');

      if (!applyTodosFromResponse(data)) {
        setTodos((previous) =>
          sortByRecent(
            previous.map((item) =>
              item.id === todo.id
                ? {
                    ...item,
                    completed: !todo.completed,
                    updatedAt: new Date().toISOString(),
                  }
                : item
            )
          )
        );
      }
    } catch {
      setError('Unable to update task state.');
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (todoId) => {
    if (busy) return;

    setBusy(true);
    setError('');

    try {
      const data = await robustApiClient.delete(`/api/todos/${todoId}`);

      if (!data?.success) throw new Error('Failed to delete todo');

      if (!applyTodosFromResponse(data)) {
        setTodos((previous) => previous.filter((todo) => todo.id !== todoId));
      }

      if (editingId === todoId) {
        resetForm();
      }
    } catch {
      setError('Unable to delete this task.');
    } finally {
      setBusy(false);
    }
  };

  const handleTogglePin = async (todo) => {
    if (busy) return;

    setBusy(true);
    setError('');

    try {
      const data = await robustApiClient.put(`/api/todos/${todo.id}`, {
        pinned: !todo.pinned,
      });

      if (!data?.success) throw new Error('Failed to toggle pin');

      if (!applyTodosFromResponse(data)) {
        setTodos((previous) =>
          sortByRecent(
            previous.map((item) =>
              item.id === todo.id
                ? {
                    ...item,
                    pinned: !todo.pinned,
                    updatedAt: new Date().toISOString(),
                  }
                : item
            )
          )
        );
      }
    } catch {
      setError('Unable to update pin state.');
    } finally {
      setBusy(false);
    }
  };

  const startEditing = (todo) => {
    setEditingId(todo.id);
    setTitle(todo.title);
    setWork(todo.work || '');
    setError('');
  };

  const emptyState = (
    <div className="rounded-lg bg-slate-900/25 px-4 py-6 text-center">
      <p className="text-xs text-slate-600">No tasks yet.</p>
    </div>
  );

  return (
    <div className="rounded-xl bg-slate-950/80 p-3 sm:p-4 md:p-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-slate-100">Simple To-do List</h3>
        <p className="mt-1 text-xs text-slate-500">
          Write a title and the work to do in plain human language.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3.5">
        <div>
          <label htmlFor="todo-title" className="mb-1 block text-xs font-medium text-slate-400">
            Title
          </label>
          <input
            id="todo-title"
            type="text"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            maxLength={MAX_TITLE_LENGTH}
            disabled={busy}
            placeholder="What is this task?"
            className="w-full rounded-lg border border-slate-800/70 bg-slate-900/70 px-3 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-sky-600/50"
          />
        </div>

        <div>
          <label htmlFor="todo-work" className="mb-1 block text-xs font-medium text-slate-400">
            Work to do
          </label>
          <textarea
            id="todo-work"
            rows={7}
            value={work}
            onChange={(event) => setWork(event.target.value)}
            maxLength={MAX_WORK_LENGTH}
            disabled={busy}
            placeholder="Describe what you want to do later..."
            className="min-h-[150px] w-full resize-y rounded-lg border border-slate-800/70 bg-slate-900/70 px-3 py-2.5 text-sm leading-relaxed text-slate-100 placeholder-slate-600 focus:outline-none focus:border-sky-600/50"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="submit"
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-lg bg-sky-500 px-3 py-2 text-xs font-semibold text-white hover:bg-sky-400 disabled:opacity-60"
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
            {editingId ? 'Update task' : 'Add task'}
          </button>

          {editingId && (
            <button
              type="button"
              onClick={resetForm}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 px-3 py-2 text-xs font-medium text-slate-300 hover:border-slate-600 hover:text-slate-200"
            >
              <X className="h-3.5 w-3.5" />Cancel edit
            </button>
          )}
        </div>
      </form>

      {error && (
        <p className="mt-3 rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
          {error}
        </p>
      )}

      <div className="mt-5 space-y-5">
        <section className="space-y-2.5">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-slate-300">
              To do ({pendingTodos.length})
            </h4>
          </div>

          {loading ? (
            <div className="rounded-lg bg-slate-900/25 px-4 py-6 text-center">
              <Loader2 className="mx-auto h-4 w-4 animate-spin text-slate-600" />
              <p className="mt-2 text-xs text-slate-600">Loading tasks...</p>
            </div>
          ) : pendingTodos.length === 0 ? (
            emptyState
          ) : (
            <ul className="space-y-2">
              {pendingTodos.map((todo) => (
                <TodoCard
                  key={todo.id}
                  todo={todo}
                  isBusy={busy}
                  onToggleDone={handleToggleDone}
                  onTogglePin={handleTogglePin}
                  onEdit={startEditing}
                  onDelete={handleDelete}
                />
              ))}
            </ul>
          )}
        </section>

        <section className="space-y-2.5">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-slate-300">
              Done ({doneTodos.length})
            </h4>
          </div>

          {loading ? (
            <div className="rounded-lg bg-slate-900/25 px-4 py-6 text-center">
              <Loader2 className="mx-auto h-4 w-4 animate-spin text-slate-600" />
              <p className="mt-2 text-xs text-slate-600">Loading tasks...</p>
            </div>
          ) : doneTodos.length === 0 ? (
            <div className="rounded-lg bg-slate-900/25 px-4 py-6 text-center">
              <p className="text-xs text-slate-600">No completed tasks yet.</p>
            </div>
          ) : (
            <ul className="space-y-2">
              {doneTodos.map((todo) => (
                <TodoCard
                  key={todo.id}
                  todo={todo}
                  isBusy={busy}
                  onToggleDone={handleToggleDone}
                  onTogglePin={handleTogglePin}
                  onEdit={startEditing}
                  onDelete={handleDelete}
                />
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
