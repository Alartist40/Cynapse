# CLAUDE_AGENT.md — Multi-Agent Architecture Specification (v4)

**Version**: 4.0.0  
**Date**: 2026-02-17  
**Engine**: Cynapse Go HiveMind  
**Goal**: High-performance, low-latency multi-agent orchestration

---

## Executive Summary

Cynapse v4.0.0 implements a **Go-Native Lead + Subagent** architecture. Unlike previous Python versions, the Go engine leverages goroutines for true non-blocking parallel execution and SQLite (Honeycomb) for high-integrity state persistence.

### Key Innovations in v4
- **Goroutine Workers**: Every subagent (Bee) runs in its own concurrent Go thread.
- **IPC Bridge**: Python-based AI subagents (Elara, Owl) communicate via ultra-low latency JSON streams.
- **Honeycomb Persistence**: All task states and agent logs are stored in a centralized SQLite database.
- **Channel-based Messaging**: Inter-agent communication is managed via Go channels and an async Event Bus.

---

## Part 1: Architecture Overview

### 1.1 The HiveMind Pattern

```
┌─────────────────────────────────────────────────────────────────────┐
│                         HIVEMIND ENGINE (Go)                        │
│  (The Lead Agent / Orchestrator)                                    │
│                                                                     │
│  Responsibilities:                                                  │
│  • Workflow Parsing (JSON/YAML)                                     │
│  • Resource Management (Goroutines)                                 │
│  • Signal Handling & Error Mitigation                               │
│  • State Persistence (Honeycomb)                                     │
└────────────────────────┬────────────────────────────────────────────┘
                         │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Go Neuron   │ │  Go Neuron   │ │  Py Bridge   │
│  (Native)    │ │  (Native)    │ │  (AI Model)  │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       └────────────────┴────────────────┘
                          │
                          ▼
               ┌───────────────────────┐
               │   HONEYCOMB STORAGE   │
               │   (SQLite Backend)    │
               └───────────────────────┘
```

---

## Part 2: Technical Specification

### 2.1 Core Handlers
- **NodeHandler**: Interface for all executable logic units.
- **NeuronHandler**: Specialized handler for local security tools.
- **LLMHandler**: High-performance bridge to Elara/Owl via the Python Bridge.

### 2.2 Performance Metrics
- **Context Switching**: < 1ms (Go scheduler).
- **Persistence Latency**: < 5ms (SQLite WAL mode).
- **Parallelism**: Efficiently manages 100+ concurrent Neurons.

---

## Part 3: Integration Checklist

- [x] Concurrent Workflow Engine (Go)
- [x] SQLite State Management (Honeycomb)
- [x] Python Bridge for AI Subagents
- [x] Thread-safe Event Bus for TUI
- [x] Go-native Security Neurons

---

*"Strength in unity, speed in Go."*
