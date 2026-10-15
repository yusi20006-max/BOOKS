# Empty states and error recovery

## Shared feedback contract

The Streamlit UI uses `books.ui_feedback` for a consistent Persian-first
empty-state and error presentation.

- Empty states state what is absent and give one concrete next step.
- Recoverable errors use a safe Persian summary plus a suggested recovery action.
- Raw exception text is not shown for common operational failures because it may
  include local paths, remote endpoints, or implementation details.
- Connection, missing-file, permission, database-constraint, invalid-input,
  storage, and unexpected failures have distinct messages.
- Error handling does not silently retry destructive operations or claim that a
  failed operation succeeded.

## Integrated flows

- Empty library and no catalog results.
- ISBN image decoding.
- Backup creation, backup restore, and JSON/CSV import.
- AI assistant action, book summary, chapter summary, and reading-plan generation.

Existing page-specific validation messages remain where they are already
actionable and safe. The common helper is the default for operational failures
that previously displayed raw exception strings.

## Regression tests

`tests/test_ui_feedback.py` verifies Persian recovery guidance for connection,
file, database, input, storage, and unexpected errors, and asserts that private
paths, tokens, and raw exception details are not echoed into the UI.

Run:

```sh
python -m pytest tests/test_ui_feedback.py -q
```

## Manual acceptance

Check that empty library, empty search, unavailable catalog sources, missing
backup files, malformed imports, denied file access, and unavailable AI
providers each show a useful next step. Verify that the user can retry without
losing existing local data or repeating a destructive action unintentionally.
