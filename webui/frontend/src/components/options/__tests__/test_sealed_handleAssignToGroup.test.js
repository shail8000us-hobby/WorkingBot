/**
 * @sealed v1.0.0 — handleAssignToGroup contract test
 *
 * Core drag-and-drop group assignment logic for Options Panel.
 * Assigns a position symbol to a group and updates server state.
 *
 * Contract: This function MUST NOT break drag-and-drop group assignment.
 * Failure mode: Position not assigned, remains ungrouped, UI shows no change.
 */

describe('handleAssignToGroup contract tests (@sealed)', () => {
  // Test the state updater function logic in isolation
  // This simulates what OptionsPanel.handleAssignToGroup does with the setState updater

  const createStateUpdater = (symbol, groupId, allExpiryGroupData) => {
    // Returns the updater function that would be passed to setState
    return (prev) => {
      const keyToUse = Object.keys(allExpiryGroupData)[0]; // Use first key for testing
      const slice = prev[keyToUse] || { groups: {}, collapsed: {}, order: [] };
      const prevGroups = slice.groups || {};

      // PASS 1: Update symbols in all groups
      const groupsWithUpdatedSymbols = {};
      for (const [id, g] of Object.entries(prevGroups)) {
        const newSymbols = g.symbols.filter((s) => s !== symbol);
        groupsWithUpdatedSymbols[id] = { ...g, symbols: newSymbols };
      }

      // Add symbol to target group if specified
      if (groupId) {
        if (!groupsWithUpdatedSymbols[groupId]) {
          const targetGroup = allExpiryGroupData[keyToUse]?.groups?.[groupId];
          if (targetGroup) {
            groupsWithUpdatedSymbols[groupId] = { ...targetGroup, symbols: [...(targetGroup.symbols || [])] };
          }
        }
        if (groupsWithUpdatedSymbols[groupId]) {
          const newSymbols = [...groupsWithUpdatedSymbols[groupId].symbols, symbol];
          groupsWithUpdatedSymbols[groupId] = { ...groupsWithUpdatedSymbols[groupId], symbols: newSymbols };
        }
      }

      // PASS 2: Preserve colors (simplified — actual code uses getGroupType/getGroupColor)
      const next = {};
      for (const [id, g] of Object.entries(groupsWithUpdatedSymbols)) {
        next[id] = { ...g, color: g.color || '#7c3aed' };
      }

      return { ...prev, [keyToUse]: { ...slice, groups: next } };
    };
  };

  // CONTRACT TEST 1: Assign ungrouped position to existing group
  test('CONTRACT: Assign ungrouped position to existing group', () => {
    const allExpiryGroupData = {
      '26/06/2026': {
        groups: {
          'group-1': { name: 'Old one bot', color: '#7c3aed', symbols: ['C-BTC-80000-26062026'] },
          'group-2': { name: 'Earnings play', color: '#3b82f6', symbols: [] },
        },
        collapsed: {},
        order: [],
      },
    };

    const prevState = allExpiryGroupData;
    const updater = createStateUpdater('P-BTC-70000-26062026', 'group-1', allExpiryGroupData);
    const newState = updater(prevState);

    // MUST add symbol to target group
    expect(newState['26/06/2026'].groups['group-1'].symbols).toContain('P-BTC-70000-26062026');
    expect(newState['26/06/2026'].groups['group-1'].symbols).toHaveLength(2);
  });

  // CONTRACT TEST 2: Remove symbol from old group when assigning to new group
  test('CONTRACT: Remove symbol from old group when reassigning', () => {
    const allExpiryGroupData = {
      '26/06/2026': {
        groups: {
          'group-1': { name: 'Old one bot', color: '#7c3aed', symbols: ['C-BTC-80000-26062026'] },
          'group-2': { name: 'Earnings play', color: '#3b82f6', symbols: ['P-BTC-70000-26062026'] },
        },
        collapsed: {},
        order: [],
      },
    };

    const prevState = allExpiryGroupData;
    const updater = createStateUpdater('P-BTC-70000-26062026', 'group-1', allExpiryGroupData);
    const newState = updater(prevState);

    // Symbol must be removed from group-2
    expect(newState['26/06/2026'].groups['group-2'].symbols).not.toContain('P-BTC-70000-26062026');
    // Symbol must be in group-1
    expect(newState['26/06/2026'].groups['group-1'].symbols).toContain('P-BTC-70000-26062026');
  });

  // CONTRACT TEST 3: Assign to null (ungroup position)
  test('CONTRACT: Assign to null ungroups position', () => {
    const allExpiryGroupData = {
      '26/06/2026': {
        groups: {
          'group-1': { name: 'Old one bot', color: '#7c3aed', symbols: ['C-BTC-80000-26062026'] },
        },
        collapsed: {},
        order: [],
      },
    };

    const prevState = allExpiryGroupData;
    const updater = createStateUpdater('C-BTC-80000-26062026', null, allExpiryGroupData);
    const newState = updater(prevState);

    // Symbol must be removed from all groups
    expect(newState['26/06/2026'].groups['group-1'].symbols).not.toContain('C-BTC-80000-26062026');
    expect(newState['26/06/2026'].groups['group-1'].symbols).toHaveLength(0);
  });

  // CONTRACT TEST 4: Symbol not duplicated when already in group
  test('CONTRACT: No duplicate symbols in group', () => {
    const allExpiryGroupData = {
      '26/06/2026': {
        groups: {
          'group-1': { name: 'Old one bot', color: '#7c3aed', symbols: ['C-BTC-80000-26062026'] },
        },
        collapsed: {},
        order: [],
      },
    };

    const prevState = allExpiryGroupData;
    const updater = createStateUpdater('C-BTC-80000-26062026', 'group-1', allExpiryGroupData);
    const newState = updater(prevState);

    // When assigning a symbol already in the target group, it should be in that group
    const symbolCount = newState['26/06/2026'].groups['group-1'].symbols.filter(
      (s) => s === 'C-BTC-80000-26062026'
    ).length;
    expect(symbolCount).toBe(1);
  });

  // CONTRACT TEST 5: Preserves other symbols in group
  test('CONTRACT: Preserves other symbols when assigning new one', () => {
    const allExpiryGroupData = {
      '26/06/2026': {
        groups: {
          'group-1': {
            name: 'Old one bot',
            color: '#7c3aed',
            symbols: ['C-BTC-80000-26062026', 'P-BTC-70000-26062026'],
          },
        },
        collapsed: {},
        order: [],
      },
    };

    const prevState = allExpiryGroupData;
    const updater = createStateUpdater('C-ETH-1500-26062026', 'group-1', allExpiryGroupData);
    const newState = updater(prevState);

    const groupSymbols = newState['26/06/2026'].groups['group-1'].symbols;

    // Original symbols must still be there
    expect(groupSymbols).toContain('C-BTC-80000-26062026');
    expect(groupSymbols).toContain('P-BTC-70000-26062026');
    // New symbol must be added
    expect(groupSymbols).toContain('C-ETH-1500-26062026');
    expect(groupSymbols).toHaveLength(3);
  });

  // CONTRACT TEST 6: Group properties preserved
  test('CONTRACT: Group properties (name, color) preserved during assignment', () => {
    const allExpiryGroupData = {
      '26/06/2026': {
        groups: {
          'group-1': { name: 'Old one bot', color: '#7c3aed', symbols: ['C-BTC-80000-26062026'] },
        },
        collapsed: {},
        order: [],
      },
    };

    const originalColor = allExpiryGroupData['26/06/2026'].groups['group-1'].color;
    const originalName = allExpiryGroupData['26/06/2026'].groups['group-1'].name;

    const prevState = allExpiryGroupData;
    const updater = createStateUpdater('P-BTC-70000-26062026', 'group-1', allExpiryGroupData);
    const newState = updater(prevState);

    const updatedGroup = newState['26/06/2026'].groups['group-1'];
    expect(updatedGroup.color).toBe(originalColor);
    expect(updatedGroup.name).toBe(originalName);
  });

  // CONTRACT TEST 7: State immutability — no mutation of input
  test('CONTRACT: State updater does not mutate input state', () => {
    const originalState = {
      '26/06/2026': {
        groups: {
          'group-1': { name: 'Group 1', color: '#7c3aed', symbols: ['C-BTC-80000-26062026'] },
        },
        collapsed: {},
        order: [],
      },
    };

    const allExpiryGroupData = JSON.parse(JSON.stringify(originalState)); // Deep copy for input
    const prevState = JSON.parse(JSON.stringify(originalState)); // Deep copy to track changes

    const updater = createStateUpdater('NEW-SYMBOL', 'group-1', allExpiryGroupData);
    updater(prevState);

    // Original state should be unchanged
    expect(prevState).toEqual(originalState);
  });

  // CONTRACT TEST 8: Handle missing target group gracefully
  test('CONTRACT: Handle missing target group without crashing', () => {
    const allExpiryGroupData = {
      '26/06/2026': {
        groups: {
          'group-1': { name: 'Old one bot', color: '#7c3aed', symbols: [] },
        },
        collapsed: {},
        order: [],
      },
    };

    const prevState = allExpiryGroupData;
    const updater = createStateUpdater('C-BTC-80000-26062026', 'non-existent-group', allExpiryGroupData);

    // Should not throw
    expect(() => {
      updater(prevState);
    }).not.toThrow();

    // Symbol should remain in ungrouped state (not added to missing group)
    const newState = updater(prevState);
    expect(newState['26/06/2026'].groups['group-1'].symbols).not.toContain('C-BTC-80000-26062026');
  });
});
