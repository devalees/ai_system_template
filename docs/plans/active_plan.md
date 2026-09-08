# Implementation Plan: Universal Django + Hermes Agent Starter Template

- **Status**: IN_PROGRESS <!-- PENDING | IN_PROGRESS | COMPLETED -->
- **Active Branch**: `main`
- **Last Updated**: 2026-09-08 13:17:00+03:00

## 1. Objective & Scope
Build a clean, domain-agnostic starter template integrating Django (backend + admin + DRF API) and Hermes Agent in Docker, with PostgreSQL, Redis, and a verified bidirectional connection handshake.

## 2. Task Checklist & Progress
- [x] **Sub-task 1: Wiki Initialization, Git Repo & Environment Scaffolding** - COMPLETED
- [/] **Sub-task 2: Docker Compose & Infrastructure Configuration** - IN PROGRESS
- [ ] **Sub-task 3: Django Backend Core & Handshake API** - PENDING
- [ ] **Sub-task 4: Hermes Agent Configuration & Handshake Skill** - PENDING
- [ ] **Sub-task 5: Verification & End-to-End Handshake Execution** - PENDING

## 3. Key Decisions & Deviations (If any)
- *2026-09-08*: Pivoted from specific domain (economy editor) to a generic starter template (`ai_system_template`) as requested by the user, keeping the journalism plan archived for later specialization.
- *2026-09-08*: Verified that `hermes-agent:local` is already built and available on the host, enabling direct container re-use without re-downloading large images.
- *2026-09-08*: Configured Git remote to `https://github.com/devalees/ai_system_template.git` with PAT for continuous commits and pushes.

## 4. Current Focus
Completing Sub-task 1: `.gitignore`, `.env.example`, and initial commit.
