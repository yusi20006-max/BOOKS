# Keyboard and screen-reader accessibility audit

## Implemented baseline

- Native Streamlit widgets retain their built-in semantic roles and accessible
  names from their labels; the app does not replace them with custom clickable
  HTML.
- Every focused element receives a visible 3 px system-highlight outline with
  offset. The stylesheet does not remove focus outlines.
- Forced-colors mode keeps the platform Highlight color for keyboard focus.
- The `prefers-reduced-motion: reduce` preference disables smooth scrolling and
  reduces animation/transition duration.
- Existing Persian-first labels, safe error summaries, and explicit empty-state
  guidance remain available as text rather than color-only signals.

## Keyboard acceptance

Use Tab and Shift+Tab to traverse the sidebar navigation, filters, forms,
primary actions, file uploaders, download buttons, tables and pagination. Confirm
that focus is always visible, Enter/Space activates controls as expected, no
keyboard trap occurs, and the sidebar can be collapsed and reopened without
losing the user's place.

## Screen-reader acceptance

Check at least one desktop screen reader (NVDA or VoiceOver) and one mobile
screen reader (TalkBack or VoiceOver). Confirm that:
- page navigation, radio groups, selects, text inputs and action buttons have
  meaningful Persian accessible names;
- required fields and disabled actions are announced by the native widgets;
- empty states, success messages and recoverable errors are announced as text;
- tabular content is navigable and its column headers are understandable;
- LTR tokens (ISBN, URLs, code and credentials) are not interleaved confusingly
  with adjacent Persian text.

Also verify at 200% zoom and in operating-system high-contrast/forced-colors
mode. These manual checks are required because the CI suite can validate CSS
contracts but cannot prove actual screen-reader announcements across platforms.

## Automated regression tests

`tests/test_accessibility_styles.py` verifies visible focus, forced-colors
support, reduced-motion preferences, and use of the shared stylesheet by the
app. Run `python -m pytest tests/test_accessibility_styles.py -q`.
