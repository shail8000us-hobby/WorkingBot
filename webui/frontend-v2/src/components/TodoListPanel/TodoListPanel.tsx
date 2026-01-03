/**
 * TodoListPanel - Improvement Tracker
 * 
 * Track ideas and improvements for the trading bot.
 */

import React, { useState, useEffect, useCallback } from 'react';
import styles from './TodoListPanel.module.css';

interface TodoItem {
  id: string;
  title: string;
  description?: string;
  category: 'feature' | 'bug' | 'improvement' | 'research';
  priority: 'low' | 'medium' | 'high';
  status: 'todo' | 'in-progress' | 'done';
  createdAt: string;
  completedAt?: string;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';

const DEFAULT_TODOS: TodoItem[] = [
  { id: '1', title: 'Add trailing stop-loss', description: 'Implement trailing stop for better profit protection', category: 'feature', priority: 'high', status: 'todo', createdAt: new Date().toISOString() },
  { id: '2', title: 'Optimize grid recalculation', description: 'Reduce CPU usage during grid updates', category: 'improvement', priority: 'medium', status: 'in-progress', createdAt: new Date().toISOString() },
  { id: '3', title: 'Research dynamic grid spacing', category: 'research', priority: 'low', status: 'todo', createdAt: new Date().toISOString() },
];

export const TodoListPanel: React.FC = () => {
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [showForm, setShowForm] = useState(false);
  const [newTodo, setNewTodo] = useState({ title: '', description: '', category: 'feature', priority: 'medium' });

  const fetchTodos = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/todos`);
      const data = await response.json();
      if (data.success && data.todos) {
        setTodos(data.todos);
      } else {
        setTodos(DEFAULT_TODOS);
      }
    } catch (err) {
      // Load from localStorage or use defaults
      const saved = localStorage.getItem('gridbot-todos');
      setTodos(saved ? JSON.parse(saved) : DEFAULT_TODOS);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTodos();
  }, [fetchTodos]);

  const saveTodos = (newTodos: TodoItem[]) => {
    setTodos(newTodos);
    localStorage.setItem('gridbot-todos', JSON.stringify(newTodos));
  };

  const handleAddTodo = () => {
    if (!newTodo.title.trim()) return;
    
    const todo: TodoItem = {
      id: Date.now().toString(),
      title: newTodo.title,
      description: newTodo.description,
      category: newTodo.category as TodoItem['category'],
      priority: newTodo.priority as TodoItem['priority'],
      status: 'todo',
      createdAt: new Date().toISOString()
    };
    
    saveTodos([todo, ...todos]);
    setNewTodo({ title: '', description: '', category: 'feature', priority: 'medium' });
    setShowForm(false);
  };

  const handleStatusChange = (id: string, newStatus: TodoItem['status']) => {
    const updated = todos.map(t => 
      t.id === id 
        ? { ...t, status: newStatus, completedAt: newStatus === 'done' ? new Date().toISOString() : undefined }
        : t
    );
    saveTodos(updated);
  };

  const handleDelete = (id: string) => {
    saveTodos(todos.filter(t => t.id !== id));
  };

  const filteredTodos = todos.filter(t => {
    if (filter === 'all') return true;
    if (filter === 'active') return t.status !== 'done';
    return t.status === filter || t.category === filter;
  });

  const getCategoryIcon = (cat: string): string => {
    switch (cat) {
      case 'feature': return '✨';
      case 'bug': return '🐛';
      case 'improvement': return '📈';
      case 'research': return '🔬';
      default: return '📝';
    }
  };

  const getPriorityClass = (priority: string): string => {
    switch (priority) {
      case 'high': return styles.priorityHigh;
      case 'medium': return styles.priorityMedium;
      case 'low': return styles.priorityLow;
      default: return '';
    }
  };

  if (loading) {
    return <div className={styles.panel}><div className={styles.loading}>Loading todos...</div></div>;
  }

  const stats = {
    total: todos.length,
    done: todos.filter(t => t.status === 'done').length,
    inProgress: todos.filter(t => t.status === 'in-progress').length,
    todo: todos.filter(t => t.status === 'todo').length
  };

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2>📝 Todo List</h2>
        <button className={styles.addBtn} onClick={() => setShowForm(!showForm)}>
          {showForm ? '✕ Cancel' : '+ Add Todo'}
        </button>
      </div>

      {/* Stats */}
      <div className={styles.stats}>
        <span className={styles.stat}>Total: {stats.total}</span>
        <span className={styles.stat}>Todo: {stats.todo}</span>
        <span className={styles.stat}>In Progress: {stats.inProgress}</span>
        <span className={styles.stat}>Done: {stats.done}</span>
      </div>

      {/* Add Form */}
      {showForm && (
        <div className={styles.form}>
          <input
            type="text"
            placeholder="Todo title..."
            value={newTodo.title}
            onChange={(e) => setNewTodo({ ...newTodo, title: e.target.value })}
            className={styles.input}
          />
          <textarea
            placeholder="Description (optional)..."
            value={newTodo.description}
            onChange={(e) => setNewTodo({ ...newTodo, description: e.target.value })}
            className={styles.textarea}
          />
          <div className={styles.formRow}>
            <select
              value={newTodo.category}
              onChange={(e) => setNewTodo({ ...newTodo, category: e.target.value })}
              className={styles.select}
            >
              <option value="feature">✨ Feature</option>
              <option value="bug">🐛 Bug</option>
              <option value="improvement">📈 Improvement</option>
              <option value="research">🔬 Research</option>
            </select>
            <select
              value={newTodo.priority}
              onChange={(e) => setNewTodo({ ...newTodo, priority: e.target.value })}
              className={styles.select}
            >
              <option value="low">Low Priority</option>
              <option value="medium">Medium Priority</option>
              <option value="high">High Priority</option>
            </select>
            <button className={styles.submitBtn} onClick={handleAddTodo}>Add</button>
          </div>
        </div>
      )}

      {/* Filter */}
      <div className={styles.filters}>
        {['all', 'active', 'todo', 'in-progress', 'done'].map(f => (
          <button
            key={f}
            className={`${styles.filterBtn} ${filter === f ? styles.active : ''}`}
            onClick={() => setFilter(f)}
          >
            {f.charAt(0).toUpperCase() + f.slice(1).replace('-', ' ')}
          </button>
        ))}
      </div>

      {/* Todo List */}
      <div className={styles.list}>
        {filteredTodos.length === 0 ? (
          <p className={styles.noData}>No todos to display</p>
        ) : (
          filteredTodos.map(todo => (
            <div key={todo.id} className={`${styles.todoItem} ${styles[todo.status]}`}>
              <div className={styles.todoMain}>
                <span className={styles.todoIcon}>{getCategoryIcon(todo.category)}</span>
                <div className={styles.todoContent}>
                  <span className={`${styles.todoTitle} ${todo.status === 'done' ? styles.completed : ''}`}>
                    {todo.title}
                  </span>
                  {todo.description && (
                    <p className={styles.todoDesc}>{todo.description}</p>
                  )}
                  <div className={styles.todoMeta}>
                    <span className={`${styles.priority} ${getPriorityClass(todo.priority)}`}>
                      {todo.priority}
                    </span>
                    <span className={styles.category}>{todo.category}</span>
                  </div>
                </div>
              </div>
              <div className={styles.todoActions}>
                <select
                  value={todo.status}
                  onChange={(e) => handleStatusChange(todo.id, e.target.value as TodoItem['status'])}
                  className={styles.statusSelect}
                >
                  <option value="todo">Todo</option>
                  <option value="in-progress">In Progress</option>
                  <option value="done">Done</option>
                </select>
                <button
                  className={styles.deleteBtn}
                  onClick={() => handleDelete(todo.id)}
                  title="Delete"
                >
                  🗑️
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default TodoListPanel;
