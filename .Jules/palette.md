## 2026-05-17 - Keyboard Nav in Custom JS Components
**Learning:** Vanilla JS UIs that generate elements (like `div`) used as interactive buttons lack native accessibility properties. Screen readers won't recognize them, and keyboard users cannot interact with them natively without explicit mapping.
**Action:** When designing or refactoring dynamic elements, manually attach `role="button"`, `tabIndex=0`, and specific keydown events mapping space/enter to actions, to provide baseline accessibility parity with native buttons.
