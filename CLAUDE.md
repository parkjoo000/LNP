# CLAUDE.md

This file provides guidance for AI assistants (Claude and others) working with this repository.

---

## Repository Overview

**Repository**: parkjoo000/LNP
**Source Reference**: https://github.com/Leonxlnx/taste-skill
**Purpose**: A collection of high-agency design system "skills" for AI coding agents (Claude Code, Cursor, GitHub Copilot, Antigravity, etc.) that prevent generic, uninspired frontend code generation. The project gives AI agents "good taste" by providing systematic design guidelines, anti-pattern enforcement, and production-quality output standards.

**Key Stats (as of 2026-03-21)**: 5,000+ stars, 462 forks, actively maintained
**Distribution**: `npx skills add https://github.com/Leonxlnx/taste-skill`
**Contact**: hello@learn2vibecode.dev

---

## Repository Structure

```
taste-skill/
├── CLAUDE.md                         # This file
├── README.md                         # Project overview and installation
├── .github/
│   ├── FUNDING.yml                   # GitHub Sponsors config
│   └── copilot-instructions.md       # GitHub Copilot system instructions
├── skills/
│   ├── llms.txt                      # Framework overview for LLM context
│   ├── taste-skill/
│   │   └── SKILL.md                  # Core design system (layout, typography, color, motion)
│   ├── soft-skill/
│   │   └── SKILL.md                  # Premium/luxury aesthetic
│   ├── minimalist-skill/
│   │   └── SKILL.md                  # Editorial, Notion/Linear-inspired style
│   ├── brutalist-skill/
│   │   └── SKILL.md                  # Swiss industrial + tactical telemetry aesthetic
│   ├── output-skill/
│   │   └── SKILL.md                  # Complete, non-truncated code generation enforcement
│   ├── redesign-skill/
│   │   └── SKILL.md                  # Audit and upgrade methodology for existing projects
│   └── stitch-skill/
│       └── SKILL.md                  # Google Stitch semantic design system integration
├── examples/
│   ├── floria-full.webp              # Full design preview
│   ├── floria-top.webp
│   └── floria-bottom.webp
└── research/
    ├── README.md
    └── laziness/                     # Research on AI lazy/truncated outputs
        ├── README.md
        ├── findings/
        ├── root-causes/
        └── remediation/
```

---

## Tech Stack

This is a **documentation-only repository** — there is no build pipeline or runtime code.

| Concern          | Details                                                   |
|------------------|-----------------------------------------------------------|
| Format           | Markdown (`.md`) — all skills are plain text documents    |
| Distribution     | `npx skills add <url>` — no npm package to publish        |
| Target frameworks | React / Next.js + Tailwind CSS (v3/v4)                  |
| Animation refs   | Framer Motion, CSS spring physics                         |
| Icon libraries   | Phosphor, Radix (Lucide/Feather explicitly banned)        |
| Fonts referenced | Geist Sans, SF Pro Display, Lyon Text, JetBrains Mono    |

---

## The Seven Skills

### 1. `taste-skill` — Core Design System
The foundational skill. Covers layout, typography, colors, spacing, and motion with three adjustable dials (1–10 scale):

- `DESIGN_VARIANCE: 8` — asymmetric, artsy layouts
- `MOTION_INTENSITY: 6` — fluid, physics-based animation
- `VISUAL_DENSITY: 4` — balanced "daily app mode" spacing

Key rules: no centered Hero sections at high variance, spring physics over linear easing, perpetual micro-interactions (Pulse, Typewriter, Float, Shimmer).

### 2. `soft-skill` — Premium Aesthetic
Agency-level luxury UI. Emphasizes double-bezel architecture (nested enclosures for depth), premium whitespace, and three vibe archetypes × three layout patterns.

### 3. `minimalist-skill` — Editorial Style
Notion/Linear-inspired. Warm bone-white canvas (`#F7F6F3–#FBFBFA`), strict 1px `#EAEAEA` borders, typographic contrast as the primary design tool, 600ms fade-in reveals.

### 4. `brutalist-skill` — Swiss Industrial / Tactical (Beta)
Two modes: *Swiss Industrial Print* or *Tactical Telemetry* (CRT aesthetic). Monospace data layers, 90-degree corners, halftone dithering, bimodal density (data clusters alternating with expansive negative space).

### 5. `output-skill` — Quality Assurance
Enforces complete, production-ready output. Bans `// ...` shortcuts, placeholder comments, and truncated code. When approaching context limits: write at full quality to a clean breakpoint, pause explicitly, resume without recaps.

### 6. `redesign-skill` — Audit & Upgrade
Three-step methodology: **Scan → Diagnose → Fix**. Works within the existing tech stack (no framework migrations). Targets: typography, color, layout, interactivity, content, components, and code quality.

### 7. `stitch-skill` — Google Stitch Integration
Generates `DESIGN.md` files for Google Stitch. Enforces max one accent color, mobile-first collapse below 768px, spring physics animations.

---

## Universal Design Rules (All Skills)

**Banned across the entire project:**
- Emojis — use Phosphor or Radix icons instead
- Inter, Roboto, Georgia, Times New Roman fonts
- "AI Purple / AI Blue Neon" aesthetics and oversaturated gradients
- Three-equal-column card grids and symmetric Hero layouts
- Stock imagery and AI marketing clichés ("Seamless," "Elevate")
- Placeholder code, `// TODO:`, `// ...rest follows same pattern`

**Required:**
- Spring physics easing (`cubic-bezier` with stiffness/damping), never `linear`
- Hardware-accelerated animations via `transform` and `opacity` only
- Semantic HTML with labels above inputs, errors below
- Extreme typographic contrast for hierarchy differentiation
- Maximum one saturated accent color per design
- CSS Grid preferred over Flexbox; z-index restraint
- `100dvh` for viewport standardization

---

## Development Workflow

### Branching Strategy

- `main` — stable, published documentation
- `claude/<description>-<id>` — AI-assisted branches (e.g., `claude/add-output-skill-Abc12`)
- Feature branches should be short-lived and merged via pull request

### Starting Work

```bash
git fetch origin
git checkout -b claude/<description>-<session-id>
```

### Committing

- Clear imperative messages: `Add brutalist-skill SKILL.md`, `Harden output-skill token-limit rules`
- One logical change per commit
- Reference GitHub issues when applicable: `Fix truncation behavior (#12)`

### Pushing

```bash
git push -u origin claude/<description>-<session-id>
```

Never push directly to `main`.

---

## AI Assistant Guidelines

### General Principles

1. **Read before modifying** — read any SKILL.md fully before editing it
2. **Minimal changes** — only change what was requested; do not refactor adjacent content
3. **No speculative features** — do not add new skills or bans not explicitly requested
4. **Consistency** — new content must match the tone, structure, and formatting of existing skills
5. **No truncation** — when writing or updating SKILL.md files, write complete content (honor `output-skill` rules)

### Editing SKILL.md Files

- Preserve existing dial values and config blocks unless instructed to change them
- Maintain the explicit ban lists — do not silently remove entries
- Keep examples concrete and runnable (no pseudo-code or abbreviated snippets)
- Follow the same heading hierarchy as the existing skill being edited

### Adding a New Skill

1. Create `skills/<skill-name>/SKILL.md`
2. Include: Purpose, Configuration dials (if applicable), Core rules, Explicit ban list, Implementation examples
3. Register the new skill in `skills/llms.txt`
4. Update the repository structure section of this file

### Research Files (`research/`)

- Research documents follow a Findings / Root-causes / Remediation structure
- Keep findings empirical and concrete; avoid speculation
- Changes to research should reference the skill they inform (typically `output-skill`)

---

## Build & Test Commands

This is a documentation-only project. There are no build or test commands.

**Distribution** (for end users):
```bash
npx skills add https://github.com/Leonxlnx/taste-skill
```

**Local usage** — include the relevant `SKILL.md` in AI agent context:
```
Include skills/taste-skill/SKILL.md in your system prompt or Claude context.
```

---

## Git Operations for AI Assistants

- Always use `git push -u origin <branch-name>` when pushing
- Branch names must follow `claude/<description>-<session-id>` pattern
- On push failure due to network error, retry up to 4 times with exponential backoff (2s → 4s → 8s → 16s)
- Never force-push without explicit user permission
- Never push to `main` directly

---

## What to Update in This File

Keep this file current as the project evolves:

1. **Skills section** — add entries when new skills are introduced
2. **Universal Design Rules** — add new bans or requirements as they emerge across skills
3. **Repository Structure** — reflect new directories or files
4. **Research** — note any new research topics and which skills they inform
