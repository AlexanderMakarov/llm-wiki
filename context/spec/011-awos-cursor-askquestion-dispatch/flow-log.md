# Flow log: 011-awos-cursor-askquestion-dispatch

## specs (functional)
- Saved: `context/spec/011-awos-cursor-askquestion-dispatch/functional-spec.md` (Approved)
- Decision: keep #114's `AskUserQuestion` → native `AskQuestion` mapping; ban `CallDynamicTool` `cursor`/`AskQuestion`; prose numbered list only when the host did not inject the first-class tool
- No new GitHub issue — refinement of [#114](https://github.com/AlexanderMakarov/llm-wiki/issues/114)
- No product code; harness rule + wrappers + maintainer docs
