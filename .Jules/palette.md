## 2024-05-18 - [Form Accessibility in Embedded Web UIs]
**Learning:** Adding semantic `<label for="...">` mapping to inputs instead of styled `<div class="label">` elements dramatically improves screen reader compatibility without altering visual layout if we set `display:block` to the label class. Furthermore, adding explicit `focus-visible` styling helps keyboard users navigate cleanly.
**Action:** Always prefer semantic `<label>` over stylized `<div>` for form fields, and globally apply explicit `focus-visible` outlines in raw HTML setups.
