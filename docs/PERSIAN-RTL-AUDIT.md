# Persian RTL UX audit

## Scope

The shared page configuration applies to all Streamlit pages before routing.
This audit focuses on direction, alignment, mixed Persian/Latin values, and
responsive spacing. It does not claim to replace a visual review on every
browser/OS combination.

The reviewed page groups are:

- Library, add/edit/confirm/delete book, discovery and ISBN scanning.
- Personal data, organization, shelves/tags, transfer, backup and settings.
- Reading status, statistics, sessions, goals/calendar, loans and audiobooks.
- Notes, knowledge base, digital annotations, editions/catalog and reports.
- OCR and AI assistant.

## Changes

- Keep the application root LTR so Streamlit's native sidebar placement and
  collapse behavior are not inverted; apply RTL to the main content and sidebar
  content regions instead.
- Right-align Persian paragraphs, headings, labels, list items, table cells and
  form controls.
- Restore LTR direction for numeric, URL, email, password and date/time inputs,
  code/preformatted output, and any element explicitly marked with `dir="ltr"`
  or class `.ltr`. Use `unicode-bidi: isolate` so Latin tokens do not reorder
  adjacent Persian text.
- Apply RTL direction to buttons and table/dataframe containers while retaining
  the existing small-screen spacing rules.
- Centralize the stylesheet in `src/books/rtl.py` so changes are reviewable and
  regression-tested rather than embedded as an opaque string inside the app.

## Regression checks

`tests/test_rtl_styles.py` verifies the direction contract, LTR exceptions for
machine-oriented values, use of the shared stylesheet by the app entrypoint,
and the mobile breakpoint. Run `python -m pytest tests/test_rtl_styles.py -q`.

## Manual visual acceptance

Before release, inspect the UI at narrow and wide viewports in at least one
Chromium-based browser and one mobile browser. Verify that sidebar collapse,
radio/select labels, ISBN and URL entry, JSON/code output, dataframes, image
captions, error messages, and mixed Persian/Latin titles remain readable. CSS
selectors are based on Streamlit's rendered DOM and should be rechecked after
Streamlit upgrades.
