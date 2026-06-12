# Frontend UX Sprint

Date: 2026-06-13  
Status: Planned  
Scope: UI layout, workspace ergonomics, user profile controls, history management, visual polish, and pipeline status clarity.

## Sprint Goal

Improve the Academic Pipeline Engine frontend from a functional monitoring workspace into a more flexible desktop-grade interface. The sprint should make navigation resizable, history manageable, profile settings discoverable, pipeline progress clearer, and the visual system more harmonious across light and dark themes.

## Status Legend

- `[x] Done`
- `[~] In progress`
- `[ ] Planned`
- `[!] Needs design decision`

## Baseline Already Completed

- [x] Equalized the desktop height of the FSM monitor card and live document canvas.
- [x] Added scroll reset for the FSM tab so content no longer appears hidden under the top navbar.
- [x] Added safer dev server reuse behavior to avoid false fallback to port 3001 when a Next dev lock already exists.
- [x] Added fenced code block rendering in live document previews.
- [x] Improved language resolution rules for generated documents.

## Workstream 1: Resizable Sidebar

Status: `[ ] Planned`

Objective: Allow the left sidebar to be manually resized, similar to the bottom console panel.

Tasks:

- [ ] Replace fixed sidebar width with controlled state.
- [ ] Add a drag handle on the sidebar right edge.
- [ ] Set minimum, default, and maximum widths.
- [ ] Persist sidebar width in local storage.
- [ ] Preserve collapsed mode behavior.
- [ ] Verify desktop layout at narrow, default, and wide sidebar widths.

Definition of done:

- Sidebar can be resized smoothly with pointer drag.
- Width persists after reload.
- History item truncation remains readable.
- Main content does not overlap or jump.

## Workstream 2: Work History Management

Status: `[ ] Planned`

Objective: Add deletion and archiving for generated works.

Tasks:

- [ ] Extend metadata model with archived/deleted state.
- [ ] Add server endpoints for archive, unarchive, delete, and bulk unarchive.
- [ ] Add UI actions for each history item.
- [ ] Add confirmation for destructive deletion.
- [ ] Hide archived works from the default recent list.
- [ ] Preserve document metadata and export references when archiving.

Definition of done:

- Users can archive a work without deleting its files.
- Users can permanently delete a work after confirmation.
- Archived works disappear from the main history list.
- Backend and UI stay consistent after reload.

## Workstream 3: User Profile Modal

Status: `[ ] Planned`

Objective: Make the bottom-left user area clickable and move personal/interface settings into a profile modal.

Tasks:

- [ ] Turn the user footer button into an interactive trigger.
- [ ] Create a profile modal component.
- [ ] Move interface language selection into the modal.
- [ ] Move theme selection into the modal.
- [ ] Add editable nickname.
- [ ] Store nickname locally and/or in app config.
- [ ] Add avatar upload support for png, jpg, ico, and svg.
- [ ] Validate avatar file type and size.
- [ ] Render avatar in the sidebar footer.

Definition of done:

- Clicking the user footer opens the modal.
- Language and theme controls work from the modal.
- Nickname persists after reload.
- Avatar persists after reload and falls back gracefully.

## Workstream 4: Author Metadata

Status: `[ ] Planned`

Objective: Bind user nickname to generated document metadata.

Tasks:

- [ ] Include nickname in run request or current user profile payload.
- [ ] Store nickname in draft metadata.
- [ ] Store nickname in exported DOCX metadata JSON.
- [ ] Show author/nickname in history detail view.
- [ ] Preserve author metadata when archiving/unarchiving.

Definition of done:

- New generated works include the current nickname in metadata.
- Existing works without nickname still render safely.
- Metadata export remains backward compatible.

## Workstream 5: Archived Works Modal

Status: `[ ] Planned`

Objective: Add a dedicated modal for viewing archived works with richer metadata and bulk unarchive.

Tasks:

- [ ] Add "Archived works" entry in profile modal or history controls.
- [ ] Create archived works modal.
- [ ] Display extended metadata: topic, author, template, language, status, timestamps, export filename.
- [ ] Add multi-select mode.
- [ ] Add bulk unarchive action.
- [ ] Add empty state.
- [ ] Add loading and error states.

Definition of done:

- Archived works can be reviewed without polluting the main recent list.
- Multiple works can be selected and unarchived.
- Modal is usable on desktop and small screens.

## Workstream 6: Pipeline Step Icon Redesign

Status: `[!] Needs design decision`

Objective: Modernize the pipeline step icons, inspired by contemporary loading indicators such as Windows-style fluent spinners.

Tasks:

- [ ] Define visual states: idle, active, completed, failed, cancelled.
- [ ] Choose icon style: lucide-based, CSS spinner, or small custom SVG.
- [ ] Replace static dots/checks with modern state indicators.
- [ ] Ensure animations are subtle and not distracting.
- [ ] Verify dark and light theme contrast.

Definition of done:

- Active state is visually clear at a glance.
- Completed and idle states remain calm.
- Icons align with the new pastel color system.

## Workstream 7: SSE Status Inside Step Blocks

Status: `[ ] Planned`

Objective: Surface live SSE status details directly inside each pipeline step card.

Tasks:

- [ ] Define per-step status fields from existing server status/log data.
- [ ] Add compact secondary status line inside step cards.
- [ ] Show active section or current action where available.
- [ ] Avoid noisy log spam in the card UI.
- [ ] Keep the console as the detailed source of truth.

Definition of done:

- Each step card can show meaningful live progress.
- Active step status updates without layout jumps.
- The UI remains readable during long generations.

## Workstream 8: DOCX Export Placement

Status: `[!] Needs design decision`

Objective: Move DOCX export to a more discoverable and convenient location.

Options:

- Place export in the top navbar when a draft is ready.
- Place export in the document canvas header.
- Add a sticky action bar at the top of the FSM workspace.

Tasks:

- [ ] Choose final placement.
- [ ] Keep download/export state visible after export.
- [ ] Avoid duplicating export actions in multiple competing places.
- [ ] Preserve current export QA feedback.

Definition of done:

- Export is obvious when the draft is ready.
- Export is not visually buried inside the document card.
- Download remains available after successful export.

## Workstream 9: Typography Pass

Status: `[ ] Planned`

Objective: Improve font scale, spacing, hierarchy, and readability.

Tasks:

- [ ] Audit current font sizes in sidebar, cards, document preview, console, and modals.
- [ ] Define a compact but readable type scale.
- [ ] Reduce overly tiny labels where they harm readability.
- [ ] Ensure long Russian strings fit without awkward wrapping.
- [ ] Check document canvas typography separately from app chrome.

Definition of done:

- Text hierarchy is consistent.
- Russian UI labels remain readable.
- The app feels dense but not cramped.

## Workstream 10: Pastel Color System

Status: `[ ] Planned`

Objective: Rework the color palette into a softer, more harmonious system that works in both light and dark themes.

Tasks:

- [ ] Audit current colors in global CSS and component classes.
- [ ] Define semantic color tokens for primary, accent, success, warning, danger, surface, border, and muted text.
- [ ] Replace hard-coded one-off colors where practical.
- [ ] Tune active, hover, and focus states.
- [ ] Verify contrast in light and dark themes.
- [ ] Avoid overly saturated cyan/teal conflicts.

Definition of done:

- Light and dark themes feel like one coherent design system.
- Status colors are clear without being harsh.
- Components no longer look like separate visual systems.

## Suggested Sprint Order

1. Resizable sidebar.
2. User profile modal shell.
3. Move language/theme controls into profile modal.
4. Nickname and author metadata.
5. Archive/delete backend and history UI.
6. Archived works modal.
7. DOCX export placement.
8. Pipeline icon redesign and SSE statuses.
9. Typography pass.
10. Pastel color system pass.

## Risks And Open Questions

- [!] Should profile settings be local-only, stored in `config/agents.yaml`, or stored in a new user preferences file?
- [!] Should archived works remain in the same metadata directory with an `archived` flag, or move to a separate archive index?
- [!] Should deletion remove DOCX/export assets, metadata only, or both?
- [!] Should avatar files be copied into an app-owned directory or stored as base64 in preferences?
- [!] Should theme/language changes apply immediately or only after saving the profile modal?
- [!] Should SSE step details be structured on the backend rather than inferred from logs?

## Current Backlog Summary

- [ ] Resizable left sidebar.
- [ ] Work archive/delete actions.
- [ ] User profile modal.
- [ ] Interface language moved to profile modal.
- [ ] User nickname.
- [ ] Nickname stored in document metadata.
- [ ] Theme moved to profile modal.
- [ ] Archived works modal with bulk unarchive.
- [ ] Avatar upload.
- [ ] Modern pipeline icons.
- [ ] SSE statuses inside step cards.
- [ ] Better DOCX export placement.
- [ ] Typography refresh.
- [ ] Pastel color system refresh.
