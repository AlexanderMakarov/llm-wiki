---
title: "Session: dark-mode-toggle — 2026-04-01"
type: source
tags: [claude-code, session-transcript, demo, demo-blog-engine, gemini, dark-mode, css-custom-properties, localstorage, prefers-color-scheme]
date: 2026-04-01
source_file: raw/sessions/demo-blog-engine/2026-04-01-dark-mode-toggle.md
project: demo-blog-engine
model: gemini-2.5-pro
last_updated: 2026-07-29
---
## Summary

The session implemented a dark mode toggle for the blog engine that respects the system preference by default but allows users to override it. The implementation uses CSS custom properties to swap theme values and localStorage to persist the user's choice across page navigations. An inline script in the document head prevents a flash of unstyled content by reading localStorage before the page renders.

## Key Claims

- The implementation uses a `data-theme` attribute on the `<html>` element to switch between light and dark CSS variable sets
- localStorage persists the user's theme preference, enabling it to survive page navigations
- An inline script in the document `<head>` reads localStorage before first paint to prevent a flash of unstyled content
- The solution respects `prefers-color-scheme` media query by default, automatically using the system preference until the user clicks the toggle

## Key Quotes

> "Using `data-theme` on `<html>` and swapping CSS custom properties" — explains the core theming strategy

> "a tiny inline script in `<head>` reads it before first paint to avoid a flash" — demonstrates the technique for preventing flash of unstyled content (FOUC)

> "The toggle button writes `localStorage.setItem('theme', next)`" — shows how user preference is persisted

## Connections

- [[demo-blog-engine]] — the project being modified
- [[DarkMode]] — the feature/system being implemented
- [[CSSCustomProperties]] — the CSS technique used for theming
- [[LocalStorage]] — the browser API used for persistence