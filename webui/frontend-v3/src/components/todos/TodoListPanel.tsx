'use client';

import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CheckCircle2, Circle, Trash2, Plus, Edit2, X, ListTodo, AlertTriangle } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';

interface Todo {
  id: string;
  text: string;
  completed: boolean;
  createdAt: string;
  priority?: 'low' | 'medium' | 'high';
}

async function fetchTodos(): Promise<Todo[]> {
  const response = await fetch('http://localhost:5555/api/todos');
  if (!response.ok) {
    throw new Error('Failed to fetch todos');
  }
  const data = await response.json();
  return data.todos || [];
}

async function createTodo(text: string): Promise<Todo> {
  const response = await fetch('http://localhost:5555/api/todos', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) throw new Error('Failed to create todo');
  return response.json();
}

async function updateTodo(id: string, updates: Partial<Todo>): Promise<Todo> {
  const response = await fetch(`http://localhost:5555/api/todos/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  if (!response.ok) throw new Error('Failed to update todo');
  return response.json();
}

async function deleteTodo(id: string): Promise<void> {
  const response = await fetch(`http://localhost:5555/api/todos/${id}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to delete todo');
}

export function TodoListPanel() {
  const queryClient = useQueryClient();
  const [newTodoText, setNewTodoText] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [filter, setFilter] = useState<'all' | 'active' | 'completed'>('all');
  const newTodoRef = useRef<HTMLInputElement>(null);
  const editInputRef = useRef<HTMLInputElement>(null);

  const { data: todos = [], isLoading, error, refetch } = useQuery({
    queryKey: ['todos'],
    queryFn: fetchTodos,
    refetchInterval: 30000,
  });

  const createMutation = useMutation({
    mutationFn: createTodo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['todos'] });
      setNewTodoText('');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, updates }: { id: string; updates: Partial<Todo> }) => updateTodo(id, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['todos'] });
      setEditingId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteTodo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['todos'] });
    },
  });

  const handleAddTodo = () => {
    if (newTodoText.trim()) {
      createMutation.mutate(newTodoText.trim());
    }
  };

  const handleToggleComplete = (todo: Todo) => {
    updateMutation.mutate({ id: todo.id, updates: { completed: !todo.completed } });
  };

  const handleStartEdit = (todo: Todo) => {
    setEditingId(todo.id);
    setEditText(todo.text);
    setTimeout(() => editInputRef.current?.focus(), 0);
  };

  const handleSaveEdit = (id: string) => {
    if (editText.trim()) {
      updateMutation.mutate({ id, updates: { text: editText.trim() } });
    } else {
      setEditingId(null);
    }
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditText('');
  };

  const handleDelete = (id: string) => {
    if (confirm('Delete this todo?')) {
      deleteMutation.mutate(id);
    }
  };

  const filteredTodos = todos.filter(todo => {
    if (filter === 'active') return !todo.completed;
    if (filter === 'completed') return todo.completed;
    return true;
  });

  const activeCount = todos.filter(t => !t.completed).length;
  const completedCount = todos.filter(t => t.completed).length;

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ListTodo className="h-5 w-5" />
            Todo List
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            Loading todos...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Todo List</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              Failed to load todos. The API endpoint may not be available.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ListTodo className="h-5 w-5" />
          Improvement Todo List
        </CardTitle>
        <CardDescription>
          Track your ideas and improvements for the trading bot
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Add Todo */}
        <div className="flex gap-2">
          <Input
            ref={newTodoRef}
            placeholder="Add a new todo..."
            value={newTodoText}
            onChange={(e) => setNewTodoText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleAddTodo();
            }}
            disabled={createMutation.isPending}
          />
          <Button onClick={handleAddTodo} disabled={createMutation.isPending || !newTodoText.trim()}>
            <Plus className="h-4 w-4 mr-2" />
            Add
          </Button>
        </div>

        {/* Filters */}
        <div className="flex gap-2">
          <Button
            variant={filter === 'all' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter('all')}
          >
            All ({todos.length})
          </Button>
          <Button
            variant={filter === 'active' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter('active')}
          >
            Active ({activeCount})
          </Button>
          <Button
            variant={filter === 'completed' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter('completed')}
          >
            Completed ({completedCount})
          </Button>
        </div>

        {/* Todo List */}
        <ScrollArea className="h-[400px]">
          {filteredTodos.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <ListTodo className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p>No todos {filter !== 'all' ? `(${filter})` : ''}</p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredTodos.map((todo) => (
                <div
                  key={todo.id}
                  className={`flex items-center gap-3 p-3 rounded-lg border ${
                    todo.completed ? 'bg-muted/50 opacity-75' : 'bg-background'
                  }`}
                >
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 shrink-0"
                    onClick={() => handleToggleComplete(todo)}
                  >
                    {todo.completed ? (
                      <CheckCircle2 className="h-5 w-5 text-green-500" />
                    ) : (
                      <Circle className="h-5 w-5" />
                    )}
                  </Button>

                  {editingId === todo.id ? (
                    <div className="flex-1 flex gap-2">
                      <Input
                        ref={editInputRef}
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSaveEdit(todo.id);
                          if (e.key === 'Escape') handleCancelEdit();
                        }}
                        className="flex-1"
                      />
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleSaveEdit(todo.id)}
                      >
                        <CheckCircle2 className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={handleCancelEdit}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ) : (
                    <>
                      <p
                        className={`flex-1 ${todo.completed ? 'line-through text-muted-foreground' : ''}`}
                        onClick={() => handleStartEdit(todo)}
                      >
                        {todo.text}
                      </p>
                      <div className="flex items-center gap-2">
                        {todo.priority && (
                          <Badge variant="outline" className="text-xs">
                            {todo.priority}
                          </Badge>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => handleStartEdit(todo)}
                        >
                          <Edit2 className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive"
                          onClick={() => handleDelete(todo.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </ScrollArea>

        {/* Summary */}
        <div className="text-xs text-muted-foreground text-center pt-2 border-t">
          {activeCount} active, {completedCount} completed
        </div>
      </CardContent>
    </Card>
  );
}

