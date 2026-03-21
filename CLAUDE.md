# CLAUDE.md

This file provides guidance for AI assistants (Claude and others) working with this repository.

## Repository Overview

**Repository**: parkjoo000/LNP
**Status**: Newly initialized repository — no source code has been committed yet.

> When the project is populated, update this section with a description of what the project does, its purpose, and its main components.

---

## Repository Structure

_To be updated once the project is set up. A typical structure might look like:_

```
LNP/
├── CLAUDE.md          # This file
├── README.md          # Project documentation for humans
├── .gitignore         # Git ignore rules
├── src/               # Source code
├── tests/             # Test files
└── docs/              # Additional documentation
```

---

## Development Workflow

### Branching Strategy

- `main` / `master` — stable, production-ready code
- `claude/<description>-<id>` — AI-assisted feature branches (e.g., `claude/add-claude-documentation-Mys4C`)
- Feature branches should be short-lived and merged via pull request

### Starting Work

```bash
# Fetch latest from remote
git fetch origin

# Create or switch to a feature branch
git checkout -b <branch-name>
```

### Committing

- Write clear, imperative commit messages (e.g., `Add authentication module`, `Fix null pointer in parser`)
- Keep commits focused and atomic — one logical change per commit
- Reference issue numbers when applicable (e.g., `Fix login redirect (#42)`)

### Pushing

```bash
git push -u origin <branch-name>
```

For AI-assisted branches, always push to the designated `claude/` branch. Do not push to `main` directly.

---

## AI Assistant Guidelines

### General Principles

1. **Read before modifying** — always read a file fully before editing it
2. **Minimal changes** — only change what is needed; avoid refactoring unrelated code
3. **No speculative features** — do not add features or abstractions beyond what was requested
4. **Security first** — never introduce command injection, SQL injection, XSS, or other OWASP vulnerabilities
5. **Ask when uncertain** — if requirements are ambiguous, clarify before implementing

### Code Conventions

_Update this section with project-specific conventions once the stack is chosen (e.g., language, framework, style guide)._

- Follow the style of existing code in each file
- Do not add comments to code that is self-explanatory
- Do not add docstrings to functions you did not write unless asked
- Prefer editing existing files over creating new ones

### Testing

_Update with actual test commands once the project is set up._

```bash
# Example — replace with actual test command
npm test        # or: pytest, cargo test, go test ./..., etc.
```

- Run tests before committing
- Do not mark a task as complete if tests are failing

### Building

_Update with actual build commands once the project is set up._

```bash
# Example — replace with actual build command
npm run build   # or: make build, cargo build, etc.
```

---

## Git Operations for AI Assistants

- **Always** use `git push -u origin <branch-name>` when pushing
- AI-assisted branches must follow the pattern: `claude/<description>-<session-id>`
- On push failure due to network error, retry up to 4 times with exponential backoff (2s, 4s, 8s, 16s)
- Never force-push without explicit user permission
- Never push to `main`/`master` directly

---

## What to Update in This File

When the project grows, keep this file current by updating:

1. **Repository Overview** — what the project does
2. **Repository Structure** — actual directory layout
3. **Tech Stack** — language(s), frameworks, libraries
4. **Build & Test commands** — exact commands to build, test, and run
5. **Code Conventions** — linting rules, formatting tools, naming conventions
6. **Environment Setup** — how to configure local development (`.env`, dependencies, etc.)
7. **CI/CD** — how automated pipelines are configured
