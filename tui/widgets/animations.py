"""
Animation System

Efficient animations using minimal character updates.
Based on the "Thinking Dot" and "Signal Propagation" protocols.
"""

import time
from typing import List, Generator


class ThinkingDot:
    """
    The "Thinking Dot" animation protocol.
    
    Single character toggle to indicate activity with minimal CPU usage.
    """
    
    FRAMES = ['●', '∙']
    CYCLE_MS = 500  # 500ms per frame
    
    def __init__(self):
        self._tick = 0
        self._last_update = time.time()
    
    def get_frame(self, colored: bool = True) -> str:
        """Get the current animation frame."""
        from ..colors import CYAN_ELECTRIC, DORMANT_GRAY, RESET
        
        frame = self.FRAMES[self._tick % len(self.FRAMES)]
        
        if colored:
            color = CYAN_ELECTRIC if self._tick % 2 == 0 else DORMANT_GRAY
            return f"{color}{frame}{RESET}"
        return frame
    
    def tick(self) -> bool:
        """
        Check if it's time to advance and do so.
        
        Returns:
            True if frame changed, False otherwise
        """
        now = time.time()
        if (now - self._last_update) * 1000 >= self.CYCLE_MS:
            self._tick += 1
            self._last_update = now
            return True
        return False


class SignalPropagation:
    """
    Signal propagation animation for neural pathways.
    
    Updates only the position of the signal character,
    not the entire pathway string.
    """
    
    FRAME_MS = 250  # 250ms per frame (4fps)
    
    def __init__(self, pathway_length: int):
        self.length = pathway_length
        self.position = 0
        self._tick = 0
        self._last_update = time.time()
        self._complete = False
    
    def get_pathway(self, colored: bool = True) -> str:
        """
        Generate the pathway string with signal at current position.
        
        Returns:
            Pathway string like ">───●───>"
        """
        from ..colors import CYAN_ELECTRIC, SYNAPSE_VIOLET, RESET
        
        parts = []
        for i in range(self.length):
            if i == self.position:
                if colored:
                    parts.append(f"{CYAN_ELECTRIC}●{RESET}")
                else:
                    parts.append("●")
            elif i == self.position - 1 and self.position > 0:
                # Trail behind signal
                if colored:
                    parts.append(f"{SYNAPSE_VIOLET}▸{RESET}")
                else:
                    parts.append("▸")
            else:
                parts.append("─")
        
        return ''.join(parts)
    
    def tick(self) -> bool:
        """
        Check if it's time to advance the signal.
        
        Returns:
            True if position changed, False otherwise
        """
        if self._complete:
            return False
        
        now = time.time()
        if (now - self._last_update) * 1000 >= self.FRAME_MS:
            self._tick += 1
            self.position = min(self.position + 1, self.length - 1)
            self._last_update = now
            
            if self.position >= self.length - 1:
                self._complete = True
            
            return True
        return False
    
    def is_complete(self) -> bool:
        return self._complete
    
    def reset(self):
        """Reset the animation."""
        self.position = 0
        self._tick = 0
        self._complete = False
        self._last_update = time.time()


class Spinner:
    """
    Simple spinner animation for loading states.
    
    Uses the pharmacode pulse style: |, /, -, \\
    """
    
    FRAMES = ['|', '/', '-', '\\']
    CYCLE_MS = 150  # Fast spin
    
    def __init__(self):
        self._tick = 0
        self._last_update = time.time()
    
    def get_frame(self, colored: bool = True) -> str:
        """Get the current spinner frame."""
        from ..colors import WARNING_AMBER, RESET
        
        frame = self.FRAMES[self._tick % len(self.FRAMES)]
        
        if colored:
            return f"{WARNING_AMBER}{frame}{RESET}"
        return frame
    
    def tick(self) -> bool:
        """
        Check if it's time to advance.
        
        Returns:
            True if frame changed
        """
        now = time.time()
        if (now - self._last_update) * 1000 >= self.CYCLE_MS:
            self._tick += 1
            self._last_update = now
            return True
        return False


class AnimationManager:
    """
    Manages all active animations with coordinated updates.
    
    Provides a central tick() method for the main loop.
    """
    
    def __init__(self):
        self._animations = {}
        self._last_tick = time.time()
    
    def add(self, name: str, animation):
        """Add an animation to manage."""
        self._animations[name] = animation
    
    def remove(self, name: str):
        """Remove an animation."""
        self._animations.pop(name, None)
    
    def get(self, name: str):
        """Get an animation by name."""
        return self._animations.get(name)
    
    def tick_all(self) -> List[str]:
        """
        Tick all animations and return list of changed animation names.
        
        Returns:
            List of animation names that changed
        """
        changed = []
        for name, animation in self._animations.items():
            if hasattr(animation, 'tick') and animation.tick():
                changed.append(name)
        return changed
    
    def clear(self):
        """Remove all animations."""
        self._animations.clear()
