//! Slot manager for KV cache reuse across turns.
//!
//! Manages inference engine slots to maximize cache hits when
//! processing multi-turn conversations. Inspired by atomic-agent's
//! slot management pattern.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};

/// A slot for KV cache reuse.
#[derive(Debug, Clone)]
pub struct Slot {
    /// Unique identifier for this slot.
    pub id: usize,
    /// The prompt prefix hash that this slot's cache was built from.
    pub prefix_hash: Option<u64>,
    /// When this slot was last used.
    pub last_used: std::time::Instant,
    /// Whether this slot is currently reserved for a specific purpose.
    pub reserved_for: Option<String>,
}

/// Manages engine slots for KV cache reuse.
pub struct SlotManager {
    slots: Mutex<Vec<Slot>>,
    round_robin: Mutex<usize>,
    /// Slot reserved for reflection (background memory formation).
    reflection_slot: Mutex<Option<usize>>,
}

impl SlotManager {
    /// Create a new slot manager with the given number of slots.
    pub fn new(num_slots: usize) -> Arc<Self> {
        let slots: Vec<Slot> = (0..num_slots)
            .map(|id| Slot {
                id,
                prefix_hash: None,
                last_used: std::time::Instant::now(),
                reserved_for: None,
            })
            .collect();

        Arc::new(Self {
            slots: Mutex::new(slots),
            round_robin: Mutex::new(0),
            reflection_slot: Mutex::new(None),
        })
    }

    /// Reserve a slot for reflection (background memory formation).
    /// Returns the slot ID, or None if no slots are available.
    pub fn reserve_reflection_slot(&self) -> Option<usize> {
        let mut slots = self.slots.lock().unwrap();
        let mut reflection_slot = self.reflection_slot.lock().unwrap();

        // Find an unreserved slot
        for slot in slots.iter_mut() {
            if slot.reserved_for.is_none() {
                slot.reserved_for = Some("reflection".to_string());
                *reflection_slot = Some(slot.id);
                return Some(slot.id);
            }
        }
        None
    }

    /// Release the reflection slot.
    pub fn release_reflection_slot(&self) {
        let mut slots = self.slots.lock().unwrap();
        let mut reflection_slot = self.reflection_slot.lock().unwrap();

        if let Some(id) = *reflection_slot {
            if let Some(slot) = slots.iter_mut().find(|s| s.id == id) {
                slot.reserved_for = None;
                slot.prefix_hash = None;
            }
            *reflection_slot = None;
        }
    }

    /// Acquire a slot for a new inference request.
    /// Returns (slot_id, cache_hit) where cache_hit indicates if the
    /// prefix hash matches.
    pub fn acquire(&self, prompt_hash: u64) -> (usize, bool) {
        let mut slots = self.slots.lock().unwrap();
        let mut round_robin = self.round_robin.lock().unwrap();

        // First, try to find a slot with matching prefix hash
        for slot in slots.iter_mut() {
            if slot.reserved_for.is_none() {
                if let Some(hash) = slot.prefix_hash {
                    if hash == prompt_hash {
                        slot.last_used = std::time::Instant::now();
                        slot.reserved_for = Some("acquired".to_string());
                        return (slot.id, true);
                    }
                }
            }
        }

        // No cache hit, use round-robin to pick next slot
        let num_slots = slots.len();
        let mut attempts = 0;
        loop {
            let idx = *round_robin % num_slots;
            *round_robin = (*round_robin + 1) % num_slots;

            let slot = &mut slots[idx];
            if slot.reserved_for.is_none() {
                slot.prefix_hash = Some(prompt_hash);
                slot.last_used = std::time::Instant::now();
                slot.reserved_for = Some("acquired".to_string());
                return (slot.id, false);
            }

            attempts += 1;
            if attempts >= num_slots {
                // All slots reserved, use the oldest one
                let oldest_idx = slots
                    .iter()
                    .enumerate()
                    .filter(|(_, s)| s.reserved_for.is_none())
                    .min_by_key(|(_, s)| s.last_used)
                    .map(|(i, _)| i)
                    .unwrap_or(0);

                let slot = &mut slots[oldest_idx];
                slot.prefix_hash = Some(prompt_hash);
                slot.last_used = std::time::Instant::now();
                slot.reserved_for = Some("acquired".to_string());
                return (slot.id, false);
            }
        }
    }

    /// Release a slot after inference is complete.
    pub fn release(&self, slot_id: usize) {
        let mut slots = self.slots.lock().unwrap();
        if let Some(slot) = slots.iter_mut().find(|s| s.id == slot_id) {
            if slot.reserved_for == Some("reflection".to_string()) {
                slot.last_used = std::time::Instant::now();
            } else {
                // Clear acquisition but keep prefix_hash for cache reuse
                slot.reserved_for = None;
                slot.last_used = std::time::Instant::now();
            }
        }
    }

    /// Get the number of available slots.
    pub fn available_count(&self) -> usize {
        let slots = self.slots.lock().unwrap();
        slots.iter().filter(|s| s.reserved_for.is_none()).count()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_slot_manager_creation() {
        let manager = SlotManager::new(4);
        assert_eq!(manager.available_count(), 4);
    }

    #[test]
    fn test_acquire_and_release() {
        let manager = SlotManager::new(2);
        let (slot_id, cache_hit) = manager.acquire(12345);
        assert!(!cache_hit);
        assert_eq!(manager.available_count(), 1);

        manager.release(slot_id);
        assert_eq!(manager.available_count(), 2);
    }

    #[test]
    fn test_cache_hit() {
        let manager = SlotManager::new(2);
        let (slot1, _) = manager.acquire(12345);
        manager.release(slot1);

        let (slot2, cache_hit) = manager.acquire(12345);
        assert!(cache_hit);
        assert_eq!(slot1, slot2);
    }

    #[test]
    fn test_reflection_slot() {
        let manager = SlotManager::new(2);
        let reflection_id = manager.reserve_reflection_slot();
        assert!(reflection_id.is_some());
        assert_eq!(manager.available_count(), 1);

        manager.release_reflection_slot();
        assert_eq!(manager.available_count(), 2);
    }
}
