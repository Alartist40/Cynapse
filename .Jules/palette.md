## 2024-05-18 - Accessibility in single-file embedded UIs
**Learning:** Found that when building single-file HTML/CSS/JS UIs without component libraries, semantic elements like `<label>` are often overlooked in favor of styled `<div>` tags. Also, icon-only buttons often miss `aria-label` and `title` attributes.
**Action:** Always verify that form inputs have associated `<label>` tags (or `aria-label`s) and icon-only buttons have proper screen reader and tooltip affordances, especially in lightweight/embedded UIs that don't rely on accessible primitives.
