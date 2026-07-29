---
title: "Session: adding-oauth-login — 2026-02-15"
type: source
tags: [claude-code, session-transcript, demo, demo-todo-api, claude, oauth, cookie-sessions, database-migration, fastapi-auth, signed-cookies, alembic-migration]
date: 2026-02-15
source_file: raw/sessions/demo-todo-api/2026-02-15-adding-oauth-login.md
project: demo-todo-api
model: claude-sonnet-4-6
last_updated: 2026-07-29
---
## Summary

Implemented GitHub OAuth authentication for the todo app using `authlib` and `itsdangerous` for signed cookie sessions. Created a `User` table with a foreign key from `Todo`, gated all todo routes behind authentication via FastAPI's `Depends(current_user)`, and applied an Alembic schema migration. All 12 tests pass with updated fixtures for authenticated sessions.

## Key Claims

- GitHub OAuth implemented via `authlib` library with `/auth/login` and `/auth/callback` routes
- Sessions use signed cookies (via `itsdangerous`) to prevent tampering
- Each `Todo` is now associated with a `User` owner through a foreign key relationship
- All `/todos` routes are protected with `Depends(current_user)` dependency injection
- Schema migration `0002_add_user_table` was auto-generated and applied with Alembic
- Test suite updated to seed a test user and inject session cookies; 12 tests pass

## Key Quotes

> "All wired up. Migration is an Alembic revision (`0002_add_user_table`). Tests updated to seed a fake user and include the session cookie. 12 tests pass." — Indicates complete implementation with schema migration and test coverage.

## Connections

- [[demo-todo-api]] — project receiving OAuth authentication
- [[authlib]] — OAuth client library enabling GitHub login