import React, { useState, useEffect, useRef } from 'react';
import { CheckCircle2, Circle, Trash2, Plus, Edit2, X, ListTodo, Calendar, Clock } from 'lucide-react';
import robustApiClient from '../utils/robustApiClient';

const TodoListPanel = () => {
  const [todos, setTodos] = useState([]);
  const [newTodoText, setNewTodoText] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isAddingTodo, setIsAddingTodo] = useState(false);
  const [filter, setFilter] = useState('all'); // 'all', 'active', 'completed'
  const newTodoRef = useRef(null);
  const editInputRef = useRef(null);

  // Load todos on component mount
  useEffect(() => {
    loadTodos();
  }, []);

  const loadTodos = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await robustApiClient.get('/api/todos');
      if (response.success) {
        // Sort todos: newest first (last saved on top)
        const sortedTodos = (response.todos || []).sort((a, b) => {
          return new Date(b.createdAt) - new Date(a.createdAt);
        });
        setTodos(sortedTodos);
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
        text: newTodoText.trim()
      });

      if (response && response.success && response.todo) {
        // Add new todo at the top (newest first)
        setTodos([response.todo, ...todos]);
        setNewTodoText('');
        // Keep focus on input for quick consecutive additions
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
        completed: !currentCompleted
      });

      if (response && response.success && response.todos) {
        // Re-sort after toggle to maintain newest-first order
        const sortedTodos = response.todos.sort((a, b) => {
          return new Date(b.createdAt) - new Date(a.createdAt);
        });
        setTodos(sortedTodos);
      } else {
        setError('Failed to update todo: Invalid response');
      }
    } catch (err) {
      console.error('Error toggling todo:', err);
      setError(`Failed to update todo: ${err.message || 'Unknown error'}`);
    }
  };

  const deleteTodo = async (todoId) => {
    try {
      setError(null);
      
      const response = await robustApiClient.delete(`/api/todos/${todoId}`);

      if (response && response.success && response.todos) {
        // Re-sort after delete
        const sortedTodos = response.todos.sort((a, b) => {
          return new Date(b.createdAt) - new Date(a.createdAt);
        });
        setTodos(sortedTodos);
      } else {
        setError('Failed to delete todo: Invalid response');
      }
    } catch (err) {
      console.error('Error deleting todo:', err);
      setError(`Failed to delete todo: ${err.message || 'Unknown error'}`);
    }
  };

  const deleteCompleted = async () => {
    const completedIds = todos.filter(t => t.completed).map(t => t.id);
    if (completedIds.length === 0) return;
    
    if (!window.confirm(`Delete ${completedIds.length} completed todo(s)?`)) return;

    try {
      setError(null);
      for (const id of completedIds) {
        await robustApiClient.delete(`/api/todos/${id}`);
      }
      await loadTodos(); // Reload to ensure sync
    } catch (err) {
      console.error('Error deleting completed todos:', err);
      setError('Failed to delete completed todos');
    }
  };

  const startEdit = (todo) => {
    setEditingId(todo.id);
    setEditText(todo.text);
    // Focus will be set via ref in useEffect
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditText('');
  };

  const saveEdit = async (todoId) => {
    if (!editText.trim()) {
      cancelEdit();
      return;
    }

    try {
      setError(null);
      
      const response = await robustApiClient.put(`/api/todos/${todoId}`, {
        text: editText.trim()
      });

      if (response && response.success && response.todos) {
        // Re-sort after edit
        const sortedTodos = response.todos.sort((a, b) => {
          return new Date(b.createdAt) - new Date(a.createdAt);
        });
        setTodos(sortedTodos);
        cancelEdit();
      } else {
        setError('Failed to update todo: Invalid response');
      }
    } catch (err) {
      console.error('Error updating todo:', err);
      setError(`Failed to update todo: ${err.message || 'Unknown error'}`);
    }
  };

  // Auto-focus edit input when editing starts
  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus();
      // Select all text for easy replacement
      editInputRef.current.select();
    }
  }, [editingId]);

  const handleKeyDown = (e, action) => {
    // Shift+Enter for new line in textarea
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      action();
    } else if (e.key === 'Escape') {
      if (editingId) cancelEdit();
    }
  };

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

  const filteredTodos = todos.filter(todo => {
    if (filter === 'active') return !todo.completed;
    if (filter === 'completed') return todo.completed;
    return true;
  });

  const completedCount = todos.filter(t => t.completed).length;
  const totalCount = todos.length;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-sky-400 border-t-transparent"></div>
        <span className="ml-3 text-sm text-slate-400">Loading todos...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with Stats */}
      <div className="flex items-center justify-between rounded-lg border border-slate-700/50 bg-slate-900/40 p-4">
        <div className="flex items-center gap-3">
          <ListTodo className="h-5 w-5 text-sky-400" />
          <div>
            <h3 className="text-sm font-semibold text-slate-100">Improvement Todo List</h3>
            <p className="text-xs text-slate-400">
              Track ideas and improvements for your trading bot
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs text-slate-400">Progress</p>
          <p className="text-lg font-bold text-slate-100">
            {completedCount}/{totalCount}
          </p>
        </div>
      </div>

      {/* Filter Tabs */}
      {todos.length > 0 && (
        <div className="flex gap-2">
          <button
            onClick={() => setFilter('all')}
            className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium transition ${
              filter === 'all'
                ? 'bg-sky-500/20 text-sky-100 border border-sky-500/40'
                : 'bg-slate-900/40 text-slate-400 border border-slate-700/50 hover:bg-slate-900/60 hover:text-slate-300'
            }`}
          >
            All ({totalCount})
          </button>
          <button
            onClick={() => setFilter('active')}
            className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium transition ${
              filter === 'active'
                ? 'bg-sky-500/20 text-sky-100 border border-sky-500/40'
                : 'bg-slate-900/40 text-slate-400 border border-slate-700/50 hover:bg-slate-900/60 hover:text-slate-300'
            }`}
          >
            Active ({totalCount - completedCount})
          </button>
          <button
            onClick={() => setFilter('completed')}
            className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium transition ${
              filter === 'completed'
                ? 'bg-sky-500/20 text-sky-100 border border-sky-500/40'
                : 'bg-slate-900/40 text-slate-400 border border-slate-700/50 hover:bg-slate-900/60 hover:text-slate-300'
            }`}
          >
            Completed ({completedCount})
          </button>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">
          {error}
        </div>
      )}

      {/* Add New Todo */}
      <div className="space-y-2">
        <textarea
          ref={newTodoRef}
          value={newTodoText}
          onChange={(e) => setNewTodoText(e.target.value)}
          onKeyDown={(e) => handleKeyDown(e, addTodo)}
          placeholder="Add a new improvement idea... (Shift+Enter for new line)"
          rows={3}
          className="w-full rounded-lg border border-slate-700 bg-slate-900/60 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20 resize-y"
          disabled={isAddingTodo}
        />
        <div className="flex gap-2">
          <button
            onClick={addTodo}
            disabled={!newTodoText.trim() || isAddingTodo}
            className="flex items-center gap-2 rounded-lg border border-sky-500/40 bg-sky-500/10 px-4 py-2 text-sm font-semibold text-sky-100 transition hover:border-sky-400 hover:bg-sky-500/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            {isAddingTodo ? 'Adding...' : 'Add Todo'}
          </button>
          {newTodoText && (
            <button
              onClick={() => setNewTodoText('')}
              className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/60 px-4 py-2 text-sm font-semibold text-slate-400 transition hover:border-slate-600 hover:text-slate-300"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Todo List */}
      <div className="space-y-2">
        {filteredTodos.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-700/70 bg-slate-900/40 p-8 text-center">
            <ListTodo className="mx-auto mb-3 h-10 w-10 text-slate-600" />
            <p className="text-sm font-semibold text-slate-300">
              {filter === 'all' ? 'No todos yet' : filter === 'active' ? 'No active todos' : 'No completed todos'}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {filter === 'all' ? 'Add your first improvement idea above' : 'Try a different filter'}
            </p>
          </div>
        ) : (
          filteredTodos.map((todo) => (
            <div
              key={todo.id}
              className={`group rounded-lg border bg-slate-900/60 p-3 transition ${
                todo.completed 
                  ? 'border-slate-700/30 bg-slate-900/40' 
                  : 'border-slate-700/50 hover:border-slate-600 hover:bg-slate-900/80'
              }`}
            >
              <div className="flex items-start gap-3">
                {/* Checkbox */}
                <button
                  onClick={() => toggleTodo(todo.id, todo.completed)}
                  className="flex-shrink-0 mt-0.5 transition hover:scale-110"
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
                    <textarea
                      ref={editInputRef}
                      value={editText}
                      onChange={(e) => setEditText(e.target.value)}
                      onKeyDown={(e) => handleKeyDown(e, () => saveEdit(todo.id))}
                      rows={3}
                      className="w-full rounded border border-sky-500 bg-slate-900 px-2 py-1 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500/20 resize-y"
                    />
                  ) : (
                    <>
                      <p
                        className={`text-sm whitespace-pre-wrap break-words ${
                          todo.completed
                            ? 'text-slate-500 line-through'
                            : 'text-slate-200'
                        }`}
                      >
                        {todo.text}
                      </p>
                      {/* Timestamp */}
                      <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
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
                      </div>
                    </>
                  )}
                </div>

                {/* Action Buttons */}
                <div className="flex items-center gap-2 opacity-0 transition group-hover:opacity-100">
                  {editingId === todo.id ? (
                    <>
                      <button
                        onClick={() => saveEdit(todo.id)}
                        className="rounded p-1 text-emerald-400 transition hover:bg-emerald-500/10"
                        title="Save (Enter)"
                      >
                        <CheckCircle2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={cancelEdit}
                        className="rounded p-1 text-slate-400 transition hover:bg-slate-700/50"
                        title="Cancel (ESC)"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => startEdit(todo)}
                        className="rounded p-1 text-sky-400 transition hover:bg-sky-500/10"
                        title="Edit"
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => deleteTodo(todo.id)}
                        className="rounded p-1 text-rose-400 transition hover:bg-rose-500/10"
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Footer Stats and Actions */}
      {todos.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between rounded-lg border border-slate-700/30 bg-slate-900/30 px-4 py-2.5">
            <div className="flex items-center gap-4 text-xs text-slate-400">
              <span>
                {completedCount > 0 && `${completedCount} completed`}
                {completedCount > 0 && todos.length - completedCount > 0 && ' • '}
                {todos.length - completedCount > 0 && `${todos.length - completedCount} pending`}
              </span>
              {completedCount > 0 && (
                <button
                  onClick={deleteCompleted}
                  className="text-rose-400 hover:text-rose-300 transition font-medium"
                >
                  Clear completed
                </button>
              )}
            </div>
            <div className="text-xs text-slate-500">
              <span className="hidden sm:inline">Enter to save • Shift+Enter for new line • </span>ESC to cancel
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TodoListPanel;


