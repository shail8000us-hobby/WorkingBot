'use client';

import { TodoListPanel } from '@/components/todos';

export default function TodosPage() {
  return (
    <div className="container mx-auto p-4 md:p-6">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Todo List</h1>
          <p className="text-muted-foreground mt-2">
            Track improvements and ideas for the trading bot
          </p>
        </div>
        <TodoListPanel />
      </div>
    </div>
  );
}

