## 2024-05-18 - Semantic labels and aria-labels missing in web_ui.go
**Learning:** Found an accessibility pattern where `div`s with `form-label` class are used instead of semantic `<label>` tags. Also found missing `aria-label`s on icon-only buttons.
**Action:** Always use `<label for="...">` for form elements and `aria-label` on icon-only buttons. Set display:block on labels if substituting block-level divs.
