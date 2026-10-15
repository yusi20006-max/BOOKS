# Mobile and responsive interaction audit

## Responsive behavior

The shared Streamlit stylesheet now applies three viewport bands:

- Above 900 px: retain the desktop layout.
- 641–900 px: allow multi-column form/control groups to wrap into two columns.
- 640 px and below: stack Streamlit columns vertically, expand action buttons to the available width, and use a minimum 44 px target height for interactive controls.

The main content keeps a compact horizontal padding on phones. Tables/dataframes can scroll horizontally instead of forcing the entire page wider, and images remain constrained to their container. The app canvas stays LTR for Streamlit's sidebar mechanics; the content retains the Persian RTL rules from the RTL audit.

## Screens and interactions reviewed

- Four-column library filters and two-column sorting controls.
- Pagination controls and the book list/grid.
- Book covers and candidate cards.
- Form fields, select boxes, primary actions and download buttons.
- Dataframes for annotations, reading sessions, reports and other tabular views.
- Restore/import file pickers and confirmation controls.

## Regression coverage

`tests/test_rtl_styles.py` checks the responsive breakpoints, wrapping/stacking rules,
button touch target, table overflow, and image sizing. This guards the CSS
contract; it is not a pixel screenshot test.

## Manual acceptance

At 360 px, 390–430 px, tablet width, and desktop width, confirm that no primary
action is clipped, multi-column forms remain usable, table overflow is contained,
the sidebar can still collapse, and Persian labels remain readable. Recheck these
selectors after Streamlit upgrades because test IDs are framework-rendered DOM
details.
