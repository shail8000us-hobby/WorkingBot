# Next.js WebUI Migration Plan - Modern Architecture Alongside Legacy System

**Created:** February 5, 2026  
**Status:** 📋 Planning Phase  
**Approach:** Incremental migration without disrupting production

---

## 🎯 Vision

Build a modern Next.js-based WebUI **alongside** the existing React WebUI, allowing:
- ✅ Zero disruption to current production system
- ✅ Gradual feature migration one at a time
- ✅ Easy switching between old and new UI
- ✅ Modern tech stack (Next.js 14+, TypeScript, Tailwind)
- ✅ Both UIs share the same Flask backend (port 5555)

---

## 🏗️ Architecture Overview

### Current System (Untouched)
```
┌─────────────────────────────────────────────────┐
│  Production (Current)                           │
├─────────────────────────────────────────────────┤
│  Flask Backend (Port 5555)                      │
│    ├── Serves React build from /build/         │
│    ├── API endpoints: /api/*                    │
│    └── WebSocket: /socket.io                    │
│                                                  │
│  React App (Legacy)                             │
│    ├── Dev: Port 3000 (proxies to 5555)        │
│    └── Prod: Served by Flask from /build/      │
└─────────────────────────────────────────────────┘
```

### New System (Alongside)
```
┌─────────────────────────────────────────────────┐
│  Development Phase                              │
├─────────────────────────────────────────────────┤
│  Flask Backend (Port 5555) - SAME              │
│    ├── API endpoints: /api/*                    │
│    ├── WebSocket: /socket.io                    │
│    ├── Serves Legacy React: / (root)           │
│    └── Proxies to Next.js: /next/* (optional)  │
│                                                  │
│  React App (Legacy) - UNCHANGED                │
│    └── Port 3000 (dev) / :5555/ (prod)         │
│                                                  │
│  Next.js App (New) - NEW                       │
│    ├── Port 3001 (dev)                          │
│    └── Port 3002 (prod standalone)             │
│    └── Talks to Flask API: localhost:5555/api  │
└─────────────────────────────────────────────────┘
```

---

## 📊 Proposed Architecture Options

### Option A: Separate Ports (Recommended for Development)

**Structure:**
```
Legacy React:  http://localhost:5555      (production)
               http://localhost:3000      (development)

Next.js App:   http://localhost:3001      (development)
               http://localhost:3002      (production)

Backend API:   http://localhost:5555/api  (shared by both)
```

**Pros:**
- ✅ Complete isolation - zero interference
- ✅ Both UIs can run simultaneously
- ✅ Easy to switch between UIs (different URLs)
- ✅ No changes to existing code
- ✅ Independent deployments

**Cons:**
- ⚠️ Need to manage two production processes
- ⚠️ Users must manually switch URLs
- ⚠️ Need to handle CORS for Next.js

**Best For:** Initial development and testing

---

### Option B: Path-Based Routing (Recommended for Production)

**Structure:**
```
http://localhost:5555/           → Legacy React App
http://localhost:5555/next       → New Next.js App (proxied)
http://localhost:5555/api/*      → Backend API (shared)
```

**Implementation:**
```python
# In Flask backend (app.py)
@app.route('/next')
@app.route('/next/<path:path>')
def nextjs_proxy(path=''):
    """Proxy to Next.js app running on port 3002"""
    return proxy_to_nextjs(path)
```

**Pros:**
- ✅ Single entry point (port 5555)
- ✅ Easy UI switching with a link
- ✅ Cleaner user experience
- ✅ No CORS issues
- ✅ Same domain/port

**Cons:**
- ⚠️ Need to add proxy logic to Flask
- ⚠️ Slight complexity in routing

**Best For:** Production deployment

---

### Option C: Hybrid (Recommended Overall) ⭐

**Development:**
- Legacy: `http://localhost:3000` (React dev server)
- Next.js: `http://localhost:3001` (Next.js dev server)
- Backend: `http://localhost:5555` (Flask API)
- Both UIs proxy to same backend

**Production:**
- Single entry: `http://localhost:5555`
- Flask serves Legacy React from `/build/` (default)
- Flask proxies `/next/*` to Next.js standalone server (port 3002)
- Users toggle with UI switch/link

**Best of Both Worlds!**

---

## 🛠️ Technology Stack

### Next.js WebUI (New)

**Core:**
- **Next.js 14+** (App Router, Server Components)
- **React 18+** (with TypeScript)
- **TypeScript** (strict mode)
- **Tailwind CSS** (utility-first styling)

**State Management:**
- **Zustand** (lightweight, modern alternative to Redux)
- **React Query / TanStack Query** (server state, caching, API calls)

**UI Components:**
- **shadcn/ui** (modern, accessible components)
- **Radix UI** (headless components)
- **Lucide Icons** (modern icon library)
- **Recharts** (for options charts, payoff diagrams)

**Real-time:**
- **Socket.IO Client** (connect to existing Flask WebSocket)
- **Next.js API Routes** (optional middleware if needed)

**Development:**
- **ESLint** (strict TypeScript rules)
- **Prettier** (code formatting)
- **Husky** (pre-commit hooks)
- **@tanstack/react-dev-tools** (debugging)

**Testing (Future):**
- **Vitest** (modern, fast testing)
- **Playwright** (E2E testing)
- **Testing Library** (component tests)

---

## 📁 Project Structure

```
/Users/ssr/Projects/WorkingBot/
│
├── webui/
│   │
│   ├── backend/               # Flask Backend (UNCHANGED)
│   │   ├── app.py            # Main Flask app
│   │   ├── routes/           # API routes
│   │   └── ...
│   │
│   ├── frontend/              # Legacy React (UNCHANGED)
│   │   ├── src/
│   │   ├── public/
│   │   ├── build/            # Production build
│   │   └── package.json
│   │
│   └── nextjs/                # NEW Next.js App
│       ├── app/              # App Router
│       │   ├── layout.tsx    # Root layout
│       │   ├── page.tsx      # Home page
│       │   ├── options/      # Options trading pages
│       │   ├── positions/    # Positions pages
│       │   └── api/          # API routes (if needed)
│       │
│       ├── components/       # Reusable components
│       │   ├── ui/          # shadcn/ui components
│       │   ├── features/    # Feature components
│       │   └── layouts/     # Layout components
│       │
│       ├── lib/             # Utilities
│       │   ├── api.ts       # API client (calls Flask)
│       │   ├── socket.ts    # Socket.IO setup
│       │   └── utils.ts     # Helpers
│       │
│       ├── store/           # Zustand stores
│       │   ├── usePositionsStore.ts
│       │   ├── useOptionsStore.ts
│       │   └── useAuthStore.ts
│       │
│       ├── types/           # TypeScript types
│       │   ├── positions.ts
│       │   ├── options.ts
│       │   └── api.ts
│       │
│       ├── public/          # Static assets
│       ├── next.config.js   # Next.js config
│       ├── tsconfig.json    # TypeScript config
│       ├── tailwind.config.ts
│       └── package.json
│
├── backend_frontend.md        # UPDATED with Next.js info
└── NEXTJS_MIGRATION_PLAN.md  # This file
```

---

## 🚀 Implementation Phases

### Phase 0: Setup (Week 1)

**Goal:** Setup Next.js project without touching existing code

**Tasks:**
1. Create `/webui/nextjs/` directory
2. Initialize Next.js 14 with TypeScript
3. Setup Tailwind CSS
4. Install shadcn/ui
5. Configure API client to talk to Flask (localhost:5555)
6. Setup Socket.IO client
7. Create basic layout and home page
8. Test connectivity to Flask backend

**Deliverable:** Next.js app running on port 3001, connects to Flask API

**Files Created:**
- `webui/nextjs/*` (all new files)

**Files Modified:**
- None (zero changes to existing system)

---

### Phase 1: UI Switch & Basic Layout (Week 2)

**Goal:** Add toggle switch in legacy UI, create Next.js layout

**Tasks:**
1. **In Legacy React (minimal change):**
   - Add "Try New UI" button in header/footer
   - Link to `http://localhost:3001` (dev) or `/next` (prod)
   
2. **In Next.js:**
   - Create main layout with navigation
   - Add "Back to Classic UI" link
   - Implement responsive design
   - Setup theme (light/dark mode)
   - Create placeholder pages for all features

**Deliverable:** Users can switch between UIs easily

**Files Modified:**
- `webui/frontend/src/App.js` (add single link/button)
- OR `webui/frontend/src/components/Header.js`

---

### Phase 2: Migrate Feature #1 - Positions View (Week 3-4)

**Goal:** Build first real feature - options positions table

**Tasks:**
1. Create types for positions data
2. Build API client functions
3. Create Zustand store for positions
4. Build positions table component
5. Add real-time updates via WebSocket
6. Match existing functionality
7. Add modern improvements (sorting, filtering, search)

**Deliverable:** Positions page fully functional in Next.js

**Existing Endpoint Used:**
- `GET /api/options/positions`
- WebSocket events for updates

**New Files:**
- `webui/nextjs/app/positions/page.tsx`
- `webui/nextjs/components/features/PositionsTable.tsx`
- `webui/nextjs/store/usePositionsStore.ts`
- `webui/nextjs/types/positions.ts`

---

### Phase 3: Migrate Feature #2 - Options Chain (Week 5-6)

**Goal:** Build options chain viewer

**Tasks:**
1. Create types for options chain data
2. Build chain table component
3. Add strike selection
4. Add order placement dialog
5. Integrate with existing Flask endpoints

**Deliverable:** Options chain page fully functional

**Existing Endpoints Used:**
- `GET /api/options/chain`
- `POST /api/options/order`

---

### Phase 4: Migrate Feature #3 - SSR Algo (Week 7-8)

**Goal:** Build SSR Algo dashboard

**Tasks:**
1. Migrate SSR algo components
2. Build session management
3. Add payoff charts
4. Add strategy configuration

**Deliverable:** SSR Algo page functional

---

### Phase 5: Migrate Feature #4 - Take Profit System (Week 9-10)

**Goal:** Build Take Profit/Loss UI (new feature just implemented!)

**Tasks:**
1. Build Target P&L dialog
2. Add indicator component
3. Integrate with take profit API
4. Add activity log view

**Deliverable:** Take Profit system in Next.js

**Existing Endpoints Used:**
- `GET /api/options/take-profit/strike/all`
- `POST /api/options/take-profit/strike/set`
- `POST /api/options/take-profit/strike/remove`

---

### Phase 6: Migrate Remaining Features (Week 11-16)

**Features:**
- Max Loss settings
- SL/TP settings
- Order history
- Liquidation monitoring
- Guardian status
- Configuration panels

**Gradual migration, one feature at a time**

---

### Phase 7: Production Deployment (Week 17)

**Goal:** Deploy Next.js to production alongside legacy

**Tasks:**
1. Build Next.js for production (`npm run build`)
2. Setup Next.js standalone server on port 3002
3. Configure Flask to proxy `/next/*` to port 3002
4. Update LaunchAgent to manage both processes
5. Test switching between UIs
6. Update documentation

**Deliverable:** Both UIs running in production

---

### Phase 8: Migration Complete & Deprecation (Week 18+)

**Goal:** Fully switch to Next.js, deprecate legacy

**Tasks:**
1. Verify all features migrated
2. User acceptance testing
3. Gradual rollout (default to Next.js)
4. Archive legacy React code
5. Remove legacy UI proxy

**Deliverable:** Next.js is primary UI

---

## 🔌 Backend Integration

### API Client (Next.js)

**File:** `webui/nextjs/lib/api.ts`

```typescript
// Example API client structure
import axios from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5555';

export const apiClient = axios.create({
  baseURL: `${API_BASE}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Positions API
export const positionsAPI = {
  getAll: () => apiClient.get('/options/positions'),
  getBySymbol: (symbol: string) => apiClient.get(`/options/positions/${symbol}`),
};

// Take Profit API
export const takeProfitAPI = {
  getAll: () => apiClient.get('/options/take-profit/strike/all'),
  set: (symbol: string, target: number, quantity: number) =>
    apiClient.post('/options/take-profit/strike/set', {
      symbol,
      target_profit: target,
      exit_quantity: quantity,
    }),
  remove: (symbol: string) =>
    apiClient.post('/options/take-profit/strike/remove', { symbol }),
};
```

### WebSocket Client (Next.js)

**File:** `webui/nextjs/lib/socket.ts`

```typescript
// Example Socket.IO setup
import { io, Socket } from 'socket.io-client';

const SOCKET_URL = process.env.NEXT_PUBLIC_SOCKET_URL || 'http://localhost:5555';

let socket: Socket | null = null;

export const getSocket = () => {
  if (!socket) {
    socket = io(SOCKET_URL, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });
  }
  return socket;
};

// Usage in components:
// const socket = getSocket();
// socket.on('positions_update', (data) => { ... });
```

### CORS Configuration (Flask Backend)

**File:** `webui/backend/app.py` (minor addition)

```python
# Add Next.js dev server to CORS allowed origins
from flask_cors import CORS

CORS(app, origins=[
    "http://localhost:3000",  # Legacy React dev
    "http://localhost:3001",  # Next.js dev - NEW
])
```

**This is the ONLY change needed in existing Flask code!**

---

## 🔀 UI Switching Mechanism

### Option 1: Simple Link (Minimal Change)

**In Legacy React Header:**
```jsx
// webui/frontend/src/components/Header.js
<a 
  href="http://localhost:3001" 
  target="_blank"
  style={{ marginLeft: '20px', color: '#4CAF50' }}
>
  🚀 Try New UI (Beta)
</a>
```

**In Next.js Layout:**
```tsx
// webui/nextjs/app/layout.tsx
<a href="http://localhost:5555">
  ← Back to Classic UI
</a>
```

### Option 2: Toggle Switch (Better UX)

**In Legacy React:**
```jsx
<Button 
  onClick={() => window.open('http://localhost:3001', '_blank')}
  variant="outlined"
  color="success"
>
  Try Beta UI →
</Button>
```

**In Next.js:**
```tsx
<Button 
  onClick={() => window.location.href = 'http://localhost:5555'}
  variant="ghost"
>
  ← Classic UI
</Button>
```

### Option 3: Dropdown Menu (Advanced)

Both UIs have a dropdown:
```
UI Version: 
  ○ Classic (Stable)
  ● Modern (Beta) ✨
```

---

## 🧪 Development Workflow

### Daily Development

```bash
# Terminal 1: Backend (always running)
cd /Users/ssr/Projects/WorkingBot
launchctl start com.gridbot.webui

# Terminal 2: Legacy React (optional, if testing legacy)
cd webui/frontend
npm start
# → http://localhost:3000

# Terminal 3: Next.js (new development)
cd webui/nextjs
npm run dev
# → http://localhost:3001
```

### Testing Both UIs

1. **Legacy UI:** Open `http://localhost:3000`
2. **Next.js UI:** Open `http://localhost:3001`
3. **Both talk to:** `http://localhost:5555/api/*`
4. **Test switching:** Click UI toggle links

---

## 📊 Port Management (Updated)

| Service | Dev Port | Prod Port | Purpose |
|---------|----------|-----------|---------|
| Flask Backend | 5555 | 5555 | API + WebSocket |
| Legacy React | 3000 | 5555 (served by Flask) | Current UI |
| Next.js | 3001 | 3002 (standalone) | New UI |

**Production Serving Strategy:**
- Flask on port 5555 serves legacy React from `/build/`
- Flask proxies `/next/*` to Next.js standalone server (port 3002)
- OR: Next.js runs independently on port 3002 (users access directly)

---

## 🛡️ Safety Guarantees

### Zero Risk to Production

**What Stays Exactly the Same:**
- ✅ Flask backend code (except CORS origin addition)
- ✅ All API endpoints
- ✅ All backend logic
- ✅ Legacy React app code
- ✅ Database
- ✅ Trading bot
- ✅ Guardian monitoring
- ✅ LaunchAgent services

**What's New (Isolated):**
- ✨ Next.js app in separate directory
- ✨ New frontend code only
- ✨ Additional dev server (port 3001)

**Rollback Strategy:**
- If anything breaks: Just stop Next.js server
- Legacy UI continues working as always
- No migration = no risk

---

## 📈 Advantages of Next.js Approach

### Technical Benefits

**Performance:**
- ⚡ Server-side rendering (SSR)
- ⚡ Static site generation (SSG) for docs
- ⚡ Image optimization
- ⚡ Automatic code splitting
- ⚡ Built-in caching

**Developer Experience:**
- 💻 TypeScript by default
- 💻 Better error messages
- 💻 Fast refresh (hot reload)
- 💻 Modern syntax (async/await everywhere)
- 💻 Better IDE support

**Code Quality:**
- 🎯 Type safety (catch errors at compile time)
- 🎯 Better component organization
- 🎯 Cleaner state management (Zustand)
- 🎯 Better testing support
- 🎯 Modern best practices

**UI/UX:**
- 🎨 Modern design (Tailwind + shadcn/ui)
- 🎨 Consistent styling
- 🎨 Better accessibility
- 🎨 Responsive by default
- 🎨 Dark mode built-in

**Maintainability:**
- 📦 Smaller bundle size
- 📦 Tree-shaking
- 📦 Better dependency management
- 📦 Easier to add features
- 📦 Less technical debt

---

## 🎯 Migration Strategy Benefits

### Why This Approach Wins

**1. Zero Risk:**
- Legacy system untouched
- Rollback = stop Next.js server
- Production never affected

**2. Gradual Learning:**
- Team learns Next.js incrementally
- One feature at a time
- No "big bang" rewrite

**3. Feature Parity:**
- Build each feature properly
- Add modern improvements
- User testing at each step

**4. User Choice:**
- Users can try new UI when ready
- Fall back to classic if needed
- Smooth transition

**5. Future Proof:**
- Modern tech stack
- Easier to maintain
- Easier to hire developers
- Better performance

---

## ⚠️ Challenges & Solutions

### Challenge 1: Managing Two Codebases

**Problem:** Maintaining both UIs during transition

**Solution:**
- Feature freeze legacy UI (only critical fixes)
- All new features go to Next.js only
- Clear deprecation timeline

### Challenge 2: State Synchronization

**Problem:** If user switches UIs mid-session

**Solution:**
- Both UIs read same API
- WebSocket updates both
- No local state persistence needed initially
- Later: Sync via localStorage or session API

### Challenge 3: Development Overhead

**Problem:** Running 3 servers (Flask + 2 UIs)

**Solution:**
- Normal dev: Only Flask + Next.js
- Legacy testing: Only when needed
- Use Docker Compose (optional)

### Challenge 4: User Adoption

**Problem:** Users might not switch to new UI

**Solution:**
- Add new features only to Next.js
- Beta period with benefits
- Gradual rollout with feedback
- Eventually deprecate legacy

### Challenge 5: API Compatibility

**Problem:** Existing API might not be TypeScript-friendly

**Solution:**
- Create TypeScript types for all API responses
- Add validation/parsing layer
- Document API contracts
- Eventually: Generate types from OpenAPI spec

---

## 📋 Initial Setup Checklist

### Prerequisites

- [x] Node.js 18+ installed
- [x] npm or yarn
- [x] Flask backend running (port 5555)
- [x] Legacy React working
- [ ] Next.js knowledge (or willingness to learn)

### Setup Steps

```bash
# 1. Create Next.js app
cd /Users/ssr/Projects/WorkingBot/webui
npx create-next-app@latest nextjs --typescript --tailwind --app --no-src-dir

# 2. Navigate to Next.js directory
cd nextjs

# 3. Install additional dependencies
npm install axios socket.io-client zustand @tanstack/react-query
npm install -D @types/node @types/react @types/react-dom

# 4. Install shadcn/ui
npx shadcn-ui@latest init

# 5. Configure API URL
echo "NEXT_PUBLIC_API_URL=http://localhost:5555" > .env.local
echo "NEXT_PUBLIC_SOCKET_URL=http://localhost:5555" >> .env.local

# 6. Update next.config.js for port 3001
# (add: port: 3001 in dev server config)

# 7. Start dev server
npm run dev

# 8. Verify
curl http://localhost:3001
```

---

## 📚 Documentation Updates Needed

### New Files to Create

1. **NEXTJS_SETUP.md**
   - How to setup Next.js environment
   - How to run dev servers
   - How to add new features

2. **NEXTJS_COMPONENTS.md**
   - Component organization
   - Styling guidelines
   - State management patterns

3. **NEXTJS_API_INTEGRATION.md**
   - How to call Flask APIs
   - WebSocket integration
   - Error handling

4. **UI_MIGRATION_CHECKLIST.md**
   - Feature migration checklist
   - Testing requirements
   - Sign-off process

### Files to Update

1. **backend_frontend.md**
   - Add Next.js port information
   - Update development workflow
   - Add switching instructions

2. **README.md** (if exists)
   - Mention dual UI system
   - Link to Next.js docs

---

## 🎓 Learning Resources

### Next.js 14
- Official Docs: https://nextjs.org/docs
- App Router Guide: https://nextjs.org/docs/app
- TypeScript Guide: https://nextjs.org/docs/app/building-your-application/configuring/typescript

### Tailwind CSS
- Docs: https://tailwindcss.com/docs
- UI Components: https://ui.shadcn.com

### Zustand
- Docs: https://zustand-demo.pmnd.rs

### TanStack Query
- Docs: https://tanstack.com/query/latest/docs/react/overview

---

## 🚀 Success Criteria

### Phase Completion

**Phase 0 (Setup) Complete When:**
- [ ] Next.js app running on port 3001
- [ ] Can fetch data from Flask API
- [ ] WebSocket connection working
- [ ] Basic layout rendered

**Phase 1 (UI Switch) Complete When:**
- [ ] Toggle link in legacy UI
- [ ] Can switch between UIs
- [ ] Next.js layout complete
- [ ] Navigation working

**Each Feature Phase Complete When:**
- [ ] Feature works identically to legacy
- [ ] TypeScript types defined
- [ ] Error handling implemented
- [ ] Real-time updates working
- [ ] UI/UX matches or improves
- [ ] User testing passed

**Full Migration Complete When:**
- [ ] All features migrated
- [ ] Production deployment tested
- [ ] User acceptance testing passed
- [ ] Performance benchmarks met
- [ ] Documentation complete
- [ ] Legacy UI deprecated

---

## 💰 Cost/Benefit Analysis

### Investment Required

**Time:**
- Initial setup: 1 week
- Per feature: 1-2 weeks
- Total migration: 16-20 weeks (~4-5 months)

**Effort:**
- No additional infrastructure costs
- Uses existing backend
- Learning curve for Next.js

### Benefits

**Immediate:**
- ✅ Modern development experience
- ✅ Better code quality
- ✅ Type safety

**Medium-term:**
- ✅ Faster feature development
- ✅ Better performance
- ✅ Easier maintenance

**Long-term:**
- ✅ Easier to hire developers (modern stack)
- ✅ Lower technical debt
- ✅ Better scalability
- ✅ Future-proof architecture

---

## 🎯 Recommendation

### ✅ This Approach is FEASIBLE and RECOMMENDED

**Why:**

1. **Zero Risk:** Legacy system untouched, can run indefinitely
2. **Gradual:** Build one feature at a time, learn as you go
3. **Flexible:** Can stop/pause/resume anytime
4. **Modern:** Next.js is industry standard, great ecosystem
5. **User-Friendly:** Users choose when to switch
6. **Maintainable:** TypeScript + modern tools = less bugs
7. **Scalable:** Easy to add features in the future

**When to Start:**
- ✅ Now (Current system is stable)
- ✅ Backend is solid (proven architecture)
- ✅ Features are well-defined (easy to replicate)

**First Steps:**
1. Create Next.js app (1 day)
2. Setup shadcn/ui + basic layout (2 days)
3. Add UI toggle in legacy React (1 hour)
4. Build first feature: Positions Table (1 week)
5. Show to users, gather feedback

---

## 📊 Timeline Summary

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| 0: Setup | 1 week | Next.js running, connects to API |
| 1: UI Switch | 1 week | Toggle between UIs |
| 2: Positions | 2 weeks | First feature migrated |
| 3: Options Chain | 2 weeks | Second feature migrated |
| 4: SSR Algo | 2 weeks | Third feature migrated |
| 5: Take Profit | 2 weeks | Fourth feature migrated |
| 6: Remaining | 6 weeks | All features migrated |
| 7: Production | 1 week | Deployed to production |
| 8: Deprecation | Ongoing | Legacy removed |

**Total:** ~4-5 months for complete migration

---

## 🎉 Conclusion

**YES, this approach is not only possible but RECOMMENDED.**

The architecture in [backend_frontend.md](backend_frontend.md) is perfect for this - the backend is already well-abstracted and API-driven. Adding a Next.js frontend is simply adding another API consumer.

**Key Success Factors:**
1. Don't touch existing code (isolation)
2. One feature at a time (incremental)
3. Users can switch (gradual adoption)
4. Modern tech stack (future-proof)
5. Zero production risk (run alongside)

**Next Step:**
Review this plan, adjust timeline/features as needed, then execute Phase 0 (Setup).

**Ready to build the future! 🚀**

---

**Questions to Answer Before Starting:**

1. ❓ Timeline: Is 4-5 months acceptable?
2. ❓ Resources: Who will develop the Next.js UI?
3. ❓ Priority: Which features to migrate first?
4. ❓ Users: how to announce/promote the new UI?
5. ❓ Testing: Who will do user acceptance testing?

Once these are answered, we can proceed with Phase 0! 🎯
