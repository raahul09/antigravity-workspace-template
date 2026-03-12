# 🛸 Antigravity Cognitive Architecture (v2.0)

> An AI Agent's capability ceiling = the quality of context it can read.
> These rules ARE the architecture. No plugins, no lock-in.

---

## 1. Think Before You Act

- **NEVER** start coding without a plan.
- Create `artifacts/plan_[task].md` FIRST.
- Use `<thought>...</thought>` blocks for non-trivial reasoning.
- Consider: edge cases, failure modes, security, scalability.

## 2. Verify Everything

- Run tests after every logic change.
- Save test output to `artifacts/logs/`.
- If modifying UI, capture screenshots in `artifacts/screenshots/`.

## 3. Learn From Mistakes (Self-Evolution) 🧬

When a bug is found or a wrong approach is taken:

1. **Document** in `artifacts/error_journal.md`:
   ```
   ## [DATE] [Title]
   - What happened:
   - Root cause:
   - Fix applied:
   - Lesson learned:
   - Prevention rule:
   ```
2. **Extract** generalizable lessons into this file or `.context/`.
3. **Never repeat** a documented mistake. Always scan the error journal first.

## 4. Coding Constraints

| Constraint | Applies To |
|:-----------|:-----------|
| Strict type hints | All functions |
| Google-style docstrings | All functions and classes |
| Pydantic models | All data structures and settings |
| Tool encapsulation | All external API calls → `tools/` |
| No silent exceptions | Every `except` must log or re-raise |
| Atomic commits | One logical change per commit |

## 5. Spec-Driven Changes

For non-trivial features or breaking changes:

1. Write a spec/proposal FIRST (in `artifacts/` or `openspec/`)
2. Get user approval
3. Implement the approved spec
4. Archive completed specs

## 6. Artifact Protocol

| Type | Path | When |
|:-----|:-----|:-----|
| Plans | `artifacts/plan_[task].md` | Before any implementation |
| Test logs | `artifacts/logs/` | After every test run |
| Error journal | `artifacts/error_journal.md` | After every bug or mistake |
| Screenshots | `artifacts/screenshots/` | After any UI change |

## 7. Permissions

- ✅ Read any project file
- ✅ Write to `src/`, `tests/`, `artifacts/`
- ✅ Run `pytest`, `git` commands
- ❌ Never `rm -rf` or destructive system commands
- ❌ Never modify `.git/` internals
- ❌ No form submissions or logins without explicit approval
