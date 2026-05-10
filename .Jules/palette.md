## 2026-05-10 - Adding placeholder text to TUI input
**Learning:** In terminal UIs using block cursors, adding an empty state placeholder requires explicitly preserving the block cursor character (█) at the start of the line, otherwise users lose their visual focus point.
**Action:** When adding placeholders to TUI inputs, always ensure the cursor indicator remains visible to maintain interface clarity.
