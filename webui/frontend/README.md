# GridBot WebUI Frontend V1

## Overview
Modern, high-performance React-based trading interface for GridBot with real-time WebSocket updates, comprehensive monitoring, and mobile optimization.

## Architecture

### Tech Stack
- **React** 18.2.0 - UI framework
- **Zustand** 5.0.8 - State management
- **Material-UI** 5.14.0 - Component library
- **Tailwind CSS** 3.4.13 - Utility-first styling
- **Framer Motion** 10.18.0 - Animations
- **Socket.IO** 4.8.1 - Real-time WebSocket communication
- **Monaco Editor** 0.54.0 - Code editing
- **Recharts** 2.9.0 - Data visualization

### Project Structure
```
webui/frontend/
├── src/
│   ├── components/          # React components
│   │   ├── ui/             # Design system components
│   │   ├── layout/         # Layout components (TopBar, Sidebar)
│   │   ├── common/         # Shared components (CollapsibleCard)
│   │   ├── options/        # Options trading components
│   │   ├── optionsChain/   # Options chain viewer
│   │   ├── optionsStrategy/ # Strategy builder
│   │   └── ...             # Feature-specific components
│   ├── hooks/              # Custom React hooks
│   ├── context/            # React context providers
│   ├── store/              # Zustand state management
│   ├── services/           # Business logic services
│   ├── utils/              # Utility functions
│   │   └── __tests__/      # Test utilities
│   └── App.js              # Main application component
├── build/                  # Production build output
├── public/                 # Static assets
└── config-overrides.js     # Webpack customization

```

## Getting Started

### Prerequisites
- Node.js 16+ 
- npm or yarn

### Installation
```bash
cd webui/frontend
npm install
```

### Development
```bash
# Start development server (port 3000)
npm start

# Run tests
npm test

# Run tests with coverage
npm run test:coverage

# Lint code
npm run lint

# Format code
npm run format

# Type check
npm run typecheck

# Analyze bundle
npm run analyze
```

### Production Build
```bash
# Build for production
npm run build

# Output: build/ directory (served by Flask backend on port 5555)
```

## Recent Modernizations (Jan 2026)

### 1. Testing Infrastructure ✅
- **Jest + React Testing Library** configured
- Test utilities for mocking providers and API calls
- Sample tests for critical components
- Coverage reporting setup
- Commands: `npm test`, `npm run test:coverage`

### 2. Error Handling & Resilience ✅
- **Enhanced Error Boundaries** with auto-recovery
- **Offline Storage** with IndexedDB fallback
- **Retry Logic** with exponential backoff in API client
- **Offline Indicator** component shows when cached data is displayed
- **Pending Actions Queue** syncs when connection restored

### 3. Code Splitting & Performance ✅
- **Lazy Loading** for all major dashboard sections
- **React.lazy** applied to 40+ heavy components
- **React.memo** wrapping for expensive renders
- **useMemo/useCallback** optimization in App.js
- Estimated 50-70% faster initial load

### 4. Build Optimization ✅
- **Webpack Chunk Splitting** strategy
  - vendor chunk (React, React-DOM)
  - ui-libs chunk (MUI, Framer Motion)
  - charts chunk (Recharts, ReactFlow)
  - editors chunk (Monaco)
  - icons chunk
- **Compression** with gzip for production builds
- **Tree Shaking** enabled for unused code
- **Minification** with TerserPlugin (console.log removal in production)
- Target: 3.2MB → ~1MB bundle size

### 5. Developer Experience ✅
- **ESLint** configuration for code quality
- **Prettier** for consistent formatting
- **Scripts** for lint, format, analyze
- **Jest** test configuration
- **Source Maps** disabled in production for security

### 6. State Management ✅
- **Zustand** store enhanced with:
  - Bot status tracking
  - Connection state management
  - Warning system
  - DevTools integration
- Centralized state for trading data, config, health

### 7. Design System ✅
- **Reusable UI Components**:
  - `Button` - Standardized button with variants
  - `Card` - Consistent panel/card styling
  - `Badge` - Status indicators
  - `Input` - Form inputs with validation
- **Design Tokens** documented
- **DESIGN_SYSTEM.md** guide created
- Migration path from custom styles and MUI

## Key Features

### Trading
- Real-time position tracking
- Order management (limit, market, conditional)
- PnL monitoring (realized, unrealized, daily)
- Multi-symbol portfolio view
- Risk metrics and safety thresholds

### Options Trading
- Options chain viewer with Greeks
- Multi-leg strategy builder
- ML-powered opportunity scanner
- Automated trade execution
- Max loss monitoring

### Monitoring
- 5-layer bot monitoring system
- Guardian health tracking
- System health dashboard
- Error intelligence with live log parsing
- Performance metrics

### Configuration
- Visual config editor
- YAML direct editing
- Validation and diff preview
- Auto-backup on changes
- Reconciliation tools

### Advanced Features
- File editor with AI assistance
- Strategy backtesting
- Bot brain decision flow visualization
- 0DTE autonomous trading
- Instance manager for multiple bots

## Performance Optimizations

### Initial Load
- Code splitting reduces initial bundle by ~70%
- Lazy loading defers non-critical components
- Compression reduces network transfer
- Service worker caching (optional)

### Runtime
- Memoization prevents unnecessary re-renders
- Virtual scrolling for large lists
- Debounced chart updates
- Throttled WebSocket updates
- Idle detection pauses updates

### Mobile
- Battery-aware polling intervals
- Network type detection (WiFi vs Cellular)
- Reduced update frequency on cellular
- Tailscale VPN optimization

## State Management

### Zustand Store
```javascript
import { useStore } from './store';

// In component
const positions = useStore(state => state.positions);
const updatePositions = useStore(state => state.updatePositions);
```

### Available State
- `positions` - Trading positions
- `orders` - Active orders
- `pnl` - Profit & Loss data
- `config` - Bot configuration
- `botStatus` - Bot running state
- `connection` - WebSocket connection
- `warnings` - System warnings

## Testing

### Running Tests
```bash
npm test                    # Watch mode
npm run test:coverage       # With coverage
npm run test:ci             # CI mode (no watch)
```

### Writing Tests
```javascript
import { renderWithProviders } from '../utils/__tests__/testUtils';

test('renders component', () => {
  const { getByText } = renderWithProviders(<MyComponent />);
  expect(getByText('Hello')).toBeInTheDocument();
});
```

### Test Utilities
- `renderWithProviders` - Wrap with all context providers
- `mockTradingData` - Factory for test data
- `createMockSocket` - Mock WebSocket
- `setupMockFetch` - Mock API calls

## Design System

See [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md) for complete guide.

### Quick Start
```jsx
import { Button, Card, Badge, Input } from './components/ui';

<Card variant="sky">
  <Input label="Price" type="number" required />
  <Button variant="primary" size="md">Submit</Button>
  <Badge variant="success" dot>Active</Badge>
</Card>
```

## Debugging

### Development Tools
- React DevTools - Component inspection
- Redux DevTools - Zustand state (via middleware)
- Network tab - WebSocket messages
- Console - Performance timings

### Common Issues

**Port 5555 conflict:**
```bash
lsof -ti:5555 | xargs kill -9
launchctl start com.gridbot.webui
```

**Build fails:**
```bash
rm -rf node_modules build
npm install
npm run build
```

**Tests fail:**
```bash
rm -rf node_modules
npm install
npm test -- --clearCache
npm test
```

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile Safari (iOS 14+)
- Chrome Mobile (Android 90+)

## Performance Benchmarks

### Before Optimization
- Initial load: ~5s
- Bundle size: 3.2MB
- Time to Interactive: ~8s
- Memory usage: ~150MB

### After Optimization (Target)
- Initial load: ~2s (60% faster)
- Bundle size: ~1MB (69% smaller)
- Time to Interactive: ~3s (62% faster)
- Memory usage: ~100MB (33% less)

## Security

- CSP headers in production
- XSS prevention with input sanitization
- No source maps in production
- Secure WebSocket (wss://) in production
- Token-based authentication
- Rate limiting on sensitive endpoints

## Contributing

### Code Style
- ESLint + Prettier configured
- Run `npm run format` before committing
- Follow design system guidelines
- Write tests for new features
- Update documentation

### Pull Request Process
1. Create feature branch
2. Make changes with tests
3. Run `npm run lint && npm run test`
4. Build successfully with `npm run build`
5. Submit PR with description

## License

Private - GridBot Trading System

## Support

For issues or questions:
1. Check [backend_frontend.md](../../backend_frontend.md)
2. Review error logs in `logs/`
3. Check browser console for errors
4. Verify backend is running on port 5555

---

**Last Updated:** January 18, 2026
**Version:** 1.0.0 (Modernized)
