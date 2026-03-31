# JARVIS Dashboard — OpenClaw Voice Interface

## Concept
A glassmorphic, floating-panel command center for OpenClaw. Voice-first with real-time agent visualization. Think Perplexity Voice + JARVIS from Iron Man + iOS Control Center.

**Target:** Linux Ubuntu, served locally, runs in browser.

---

## Design Language

### Aesthetic
- **Style:** Glassmorphism (frosted glass), floating rounded panels, particle system
- **Background:** Dark (#0a0a0f) with subtle animated gradient mesh
- **Glass panels:** `backdrop-filter: blur(20px)`, `background: rgba(255,255,255,0.05)`, `border: 1px solid rgba(255,255,255,0.1)`
- **Border radius:** 20-30px for panels, full-round for central orb
- **Shadows:** `box-shadow: 0 8px 32px rgba(0,0,0,0.4)`

### Color Palette
| Element | Idle | Active | Error |
|---------|------|--------|-------|
| Orb core | `#1a3a6a` (deep blue) | `#f5a623` (amber) | `#e74c3c` |
| Orb particles | `#4a9eff` → `#00d4ff` | `#ffcc00` → `#ff6b00` | `#ff4444` |
| Panel glow | `rgba(74,158,255,0.3)` | `rgba(245,166,35,0.3)` | `rgba(231,76,60,0.3)` |
| Text primary | `#ffffff` | `#ffffff` | `#ff6b6b` |
| Text secondary | `#8899aa` | `#aabbcc` | `#cc8888` |

### Typography
- **Font:** Inter (system fallback: -apple-system, sans-serif)
- **Headings:** 600 weight, 14-18px
- **Body:** 400 weight, 12-14px
- **Mono (logs):** JetBrains Mono, 11px

---

## Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│ [≡] JARVIS                           [🎤] [📷] [⌨] [⏹] [⚙] │  ← Top bar
├─────────────┬─────────────────────────┬────────────────────┤
│             │                         │                    │
│  TASKS      │    CENTRAL ORB +        │   AGENT STATUS     │
│  (left)     │    PARTICLES            │   (right top)      │
│             │                         │                    │
│  ─────────  │    ┌─────────────┐       │   ─────────────    │
│             │    │  🎙️ ORB    │       │                    │
│  PLAN       │    │  animation │       │   CALENDAR         │
│  (left bot) │    └─────────────┘       │   (right mid)      │
│             │                         │                    │
│             │    [💬 chat input  ]    │   ─────────────    │
│             │                         │                    │
├─────────────┴─────────────────────────┴────────────────────┤
│ [Tab: Tasks | Plan | Subagents | Controls | Settings]       │  ← Bottom tabs
└─────────────────────────────────────────────────────────────┘

FLOATING LAYERS (overlay):
- Virtual Keyboard (when active)
- Drawing Canvas (camera mode)
- Camera Feed (picture-in-picture)
- Agent Activity Popup (center, expandable)
- Scheduled Interfaces (floating windows)
```

---

## Core Components

### 1. Central Orb (JARVIS core)
- **Idle state:** Blue pulsing particle sphere, slow rotation
- **Listening:** Blue intensifies, particles contract inward
- **Speaking:** Amber/yellow glow, particles expand outward with speech visualization
- **Thinking:** Blue with white sparks, particles swirl faster
- **Error:** Red tint, particles scatter
- **Canvas-based particle system:** 200-400 particles with physics (gravity, repulsion, attraction)

### 2. Left Panel
- **Tasks tab:** Scrollable task list, status icons (pending/running/done/failed), click to expand
- **Plan tab:** Current objective with progress bar, sub-steps, click to modify
- **Subagents tab:** Active sub-agents list, spawn/kill controls
- **Controls tab:** Quick action buttons (created dynamically by agent)

### 3. Right Panel  
- **Agent Status:** Animated icon + description of current action, streaming text
- **Live Activity:** Real-time log of agent operations (file edits, web searches, etc.)
- **Calendar:** Weekly view, clickable slots for scheduling, shows briefings

### 4. Chat Input
- Always visible below orb
- Subtitle shows last agent response
- Send on Enter, voice on mic button
- Typing indicator when agent is processing

### 5. Top Bar Controls
- **Voice toggle** (🎤) — mute/unmute voice mode
- **Camera toggle** (📷) — activate hand tracking / gesture input
- **Keyboard toggle** (⌨) — virtual keyboard overlay
- **Stop button** (⏹) — emergency stop agent
- **Settings** (⚙) — preferences

### 6. Floating Layers
- **Virtual Keyboard:** Canvas-based, finger-tracking compatible, 3D floating keys
- **Drawing Canvas:** Camera feed + canvas overlay, draw with finger to communicate
- **Camera PiP:** Small floating window showing camera feed
- **Activity Popup:** Center overlay showing what agent is focused on (zoomed)
- **Scheduled Interfaces:** Agent-created popups at scheduled times (greeting, reminder, etc.)

---

## Features Checklist

### Voice & Animation
- [x] Particle orb with 5 states (idle/listening/speaking/thinking/error)
- [x] Voice activity detection (amplitude → particle expansion)
- [x] Smooth color transitions between states
- [x] Perplexity-style waveform visualization
- [x] TTS visualization (text → mouth movement via particle mouth)

### Interaction
- [x] Text chat input (always visible)
- [x] Voice recording with push-to-talk
- [x] Virtual keyboard (canvas-based, floating)
- [x] Drawing canvas (camera overlay, draw with finger)
- [x] Camera hand tracking (MediaPipe or built-in)
- [x] Emergency stop button (always accessible)
- [x] Focus mode (dims everything except central action)

### Panels
- [x] Task list (scrollable, expandable, editable)
- [x] Plan/objective viewer + editor
- [x] Calendar with clickable scheduling
- [x] Agent activity live log
- [x] Sub-agents management tab
- [x] Controls board (agent-created buttons)

### Agent Capabilities
- [x] Create UI buttons for user to click
- [x] Show/hide scheduled interfaces
- [x] Popup requests (password, confirmation, choice)
- [x] Stream what it's doing to Activity panel
- [x] Zoom on current action (picture-in-picture)
- [x] Create floating windows at scheduled times

### UI Polish
- [x] Glassmorphism throughout
- [x] Floating panels with subtle parallax
- [x] Color theming (agent can change particle colors)
- [x] Minimalist — information density vs. whitespace balance
- [x] Responsive (works on different screen sizes)

---

## Technical Stack
- **Frontend:** Vanilla HTML/CSS/JS (no framework, max performance)
- **Particle system:** HTML5 Canvas + requestAnimationFrame
- **Camera:** getUserMedia API + MediaPipe Hands (optional)
- **Audio:** Web Audio API for voice detection
- **Backend:** Python Flask/FastAPI for OpenClaw API integration
- **Real-time:** WebSocket or SSE for agent updates
- **Port:** 8787 (JARVIS专用)

---

## API Integration (OpenClaw)
- `GET /api/status` — agent state, current task
- `GET /api/tasks` — task list
- `POST /api/tasks/:id` — update task
- `POST /api/chat` — send message
- `GET /api/stream` — SSE for agent activity
- `POST /api/stop` — emergency stop
- `WS /ws/jarvis` — real-time bidirectional

---

*JARVIS Dashboard v1.0 — Build for L-VS on ThinkPad-X250, Ubuntu*
