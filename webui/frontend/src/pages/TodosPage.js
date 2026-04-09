import React from 'react';
import CollapsibleCard from '../components/common/CollapsibleCard.tsx';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';
import TodoListPanel from '../components/TodoListPanel';

const TodosPage = React.memo(function TodosPage() {
  return (
    <div className="grid gap-2">
      <CollapsibleCard
        id="todo-list"
        title="📝 Simple To-do List"
        subtitle="Add a title and describe the work to do in plain language"
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
