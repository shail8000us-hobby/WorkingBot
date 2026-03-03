import React from 'react';
import CollapsibleCard from '../components/common/CollapsibleCard.tsx';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';
import TodoListPanel from '../components/TodoListPanel';

const TodosPage = React.memo(function TodosPage() {
  return (
    <div className="grid gap-2">
      <CollapsibleCard
        id="todo-list"
        title="📝 Improvement Todo List"
        subtitle="Track your ideas and improvements for the trading bot"
        accent="amber"
        defaultOpen={true}
      >
        <EnhancedErrorBoundary componentName="TodoListPanel">
          <TodoListPanel />
        </EnhancedErrorBoundary>
      </CollapsibleCard>
    </div>
  );
});

export default TodosPage;
