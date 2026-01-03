# GridBot WebUI v3

Modern, real-time trading dashboard for GridBot built with Next.js 16, Tailwind CSS 4, and shadcn/ui.

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Start development server (port 3003)
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

## 📋 Requirements

- Node.js 18+
- GridBot backend running on port 5555

## 🎨 Features

### Phase 1: Foundation
- ✅ Type-safe API client with TanStack Query
- ✅ Real-time WebSocket updates
- ✅ Dark/light theme support
- ✅ Responsive layout with sidebar

### Phase 2: Data Display
- ✅ Live price display with animations
- ✅ Order management with filtering
- ✅ Position tracking with P&L
- ✅ Grid visualization
- ✅ Bot instance management

### Phase 3: Actions & Safety
- ✅ Emergency stop button (3-second hold)
- ✅ Pause/resume trading
- ✅ Guardian status integration
- ✅ Keyboard shortcuts (press `?` to see all)
- ✅ Command palette (`Ctrl+K` / `Cmd+K`)

### Phase 4: Polish
- ✅ Focus modes (Zen/Battle/Normal)
- ✅ Error boundaries per section
- ✅ Loading skeletons
- ✅ Empty state components
- ✅ Mobile responsive design
- ✅ Bottom navigation for mobile
- ✅ Vitest testing setup

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `?` | Show shortcuts help |
| `Ctrl+K` / `Cmd+K` | Open command palette |
| `1-5` | Navigate to pages |
| `R` | Refresh data |
| `P` | Pause/resume trading |
| `Escape` | Close dialogs |

## 🏗️ Project Structure

```
src/
├── app/                 # Next.js App Router pages
├── components/
│   ├── common/         # Reusable UI components
│   ├── dashboard/      # Dashboard widgets
│   ├── layout/         # App shell, header, sidebar
│   ├── orders/         # Order-related components
│   ├── positions/      # Position components
│   ├── providers/      # React context providers
│   ├── trading/        # Trading action components
│   └── ui/             # shadcn/ui components
├── hooks/              # Custom React hooks
├── lib/                # Utilities and API client
├── stores/             # Zustand state stores
├── test/               # Test utilities
└── types/              # TypeScript type definitions
```

## 🧪 Testing

```bash
# Run tests in watch mode
npm test

# Run tests once
npm run test:run

# Run with coverage
npm run test:coverage
```

## 🔧 Configuration

### Environment Variables

Create a `.env.local` file:

```env
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:5555

# WebSocket URL
NEXT_PUBLIC_WS_URL=ws://localhost:5555

# Environment
NEXT_PUBLIC_ENV=development
```

### Running Alongside v1

v3 runs on port 3003 by default, while v1 runs on port 3000. Both can run simultaneously:

```bash
# Terminal 1: v1 (port 3000)
cd webui/frontend
npm run dev

# Terminal 2: v3 (port 3003)
cd webui/frontend-v3
npm run dev
```

## 📱 Mobile Support

The UI is fully responsive with:
- Bottom navigation on mobile
- Touch-friendly buttons (44px minimum)
- Swipeable metrics carousel
- Collapsible sidebar
- Safe area insets for notched devices

## 🎯 Focus Modes

Switch between focus modes using the toggle in the header:

- **Normal**: Full UI with all features
- **Zen**: Minimal UI, hides sidebar and brain panel
- **Battle**: Enhanced visibility for active trading

## 🛠️ Development

### Type Checking

```bash
npm run typecheck
```

### Linting

```bash
npm run lint
```

### Building

```bash
npm run build
```

## 📄 License

Private - Part of GridBot trading system.
