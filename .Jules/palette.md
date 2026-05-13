## 2024-05-13 - Add Placeholder Text to Bubble Tea TUI
**Learning:** Adding a placeholder to TUI input fields (like in Bubble Tea/Lipgloss) provides users with an immediate hint on what to type or how to access menus (e.g., typing `/`), which is especially useful in empty states.
**Action:** Use conditional rendering based on input length `len(m.input) == 0` to display dimmed text alongside the block cursor when input is empty.
