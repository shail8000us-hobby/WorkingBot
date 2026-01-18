# Frontend V1 Design System

## Overview
This design system provides a consistent set of UI components and design tokens for the GridBot WebUI.

## Colors

### Primary Colors
- **Sky**: Primary brand color for actions and links
  - `sky-500`: #0ea5e9 (Main)
  - `sky-400`: #38bdf8 (Light)
  - `sky-600`: #0284c7 (Dark)

### Status Colors
- **Success** (Emerald): #22c55e
- **Warning** (Amber): #f59e0b
- **Danger** (Rose): #ef4444
- **Info** (Sky): #0ea5e9

### Neutral Colors
- **Surface**: #0f172a (Background)
- **Surface Light**: #1e293b
- **Surface Dark**: #020617

## Typography

### Font Families
- **Sans**: Inter Variable
- **Mono**: Roboto Mono

### Scale
- `text-xs`: 0.75rem (12px)
- `text-sm`: 0.875rem (14px)
- `text-base`: 1rem (16px)
- `text-lg`: 1.125rem (18px)
- `text-xl`: 1.25rem (20px)
- `text-2xl`: 1.5rem (24px)

## Spacing

Consistent spacing scale based on 4px:
- `1`: 0.25rem (4px)
- `2`: 0.5rem (8px)
- `3`: 0.75rem (12px)
- `4`: 1rem (16px)
- `6`: 1.5rem (24px)
- `8`: 2rem (32px)
- `12`: 3rem (48px)

## Border Radius

- `rounded-lg`: 0.5rem (8px)
- `rounded-xl`: 0.75rem (12px)
- `rounded-2xl`: 1rem (16px)
- `rounded-full`: 9999px (Full circle)

## Components

### Button
```jsx
import { Button } from './components/ui';

<Button variant="primary" size="md">Click me</Button>
<Button variant="danger" size="sm">Delete</Button>
<Button variant="ghost" loading>Loading...</Button>
```

**Variants**: `primary`, `secondary`, `danger`, `success`, `ghost`, `outline`
**Sizes**: `sm`, `md`, `lg`

### Card
```jsx
import { Card } from './components/ui';

<Card variant="sky" padding="normal">
  Content here
</Card>
```

**Variants**: `default`, `sky`, `emerald`, `amber`, `rose`, `violet`
**Padding**: `none`, `sm`, `normal`, `lg`

### Badge
```jsx
import { Badge } from './components/ui';

<Badge variant="success" dot>Active</Badge>
<Badge variant="error" size="md">Error</Badge>
```

**Variants**: `success`, `warning`, `error`, `info`, `neutral`
**Sizes**: `sm`, `md`, `lg`

### Input
```jsx
import { Input } from './components/ui';

<Input
  label="Username"
  placeholder="Enter username"
  error={errors.username}
  helperText="Must be unique"
  required
/>
```

## Best Practices

1. **Consistency**: Always use design system components over custom styles
2. **Accessibility**: All components include proper ARIA labels and keyboard navigation
3. **Performance**: Components are memoized for optimal performance
4. **Responsive**: Mobile-first design with responsive breakpoints
5. **Dark Mode**: All components are designed for dark mode by default

## Migration Guide

### From Custom Styles
```jsx
// Before
<button className="bg-blue-500 text-white px-4 py-2 rounded">
  Click me
</button>

// After
<Button variant="primary">Click me</Button>
```

### From MUI Components
```jsx
// Before
import { Button as MUIButton } from '@mui/material';
<MUIButton variant="contained">Click me</MUIButton>

// After
import { Button } from './components/ui';
<Button variant="primary">Click me</Button>
```

## Future Enhancements

- [ ] Add Select component
- [ ] Add Checkbox component
- [ ] Add Radio component
- [ ] Add Switch component
- [ ] Add Tooltip component
- [ ] Add Modal component
- [ ] Add Toast notifications
- [ ] Add Skeleton loaders
- [ ] Add Table component
- [ ] Add Tabs component
