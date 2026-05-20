## 2024-05-20 - Preserving Layout when Upgrading Form Labels
**Learning:** When upgrading stylised `<div>` tags to semantic `<label>` tags to improve form accessibility, the visual layout can break because `<label>` is an inline element while `<div>` is block-level.
**Action:** Always add `display: block` to the CSS class applied to the new `<label>` element. This ensures the original vertical spacing and layout pattern remains identical while significantly improving screen reader accessibility and label-input association.
