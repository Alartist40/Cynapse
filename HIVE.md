# HiveMind — AI Workflow Orchestration System

**Version**: 1.0.0  
**Date**: 2026-02-03  
**Author**: Alejandro Eduardo Garcia Romero  
**Status**: Architecture Definition Phase  
**Philosophy**: *"A colony is greater than the sum of its bees"*

---

## Executive Summary

HiveMind is **not** an AI model. It is a workflow orchestration system—similar to n8n, Zapier, or Claude Code—that connects AI models (primarily Elara), documents, tools, and external services through automated workflows called **"Bees"**.

The system operates like a biological beehive:
- **Queen** (Elara): The central AI model that makes decisions
- **Bees** (Workflows): Automated task executors that gather knowledge and perform actions
- **Honeycomb** (Memory): Storage for learned knowledge and workflow states
- **Hive Structure** (Engine): The framework that routes bees, manages the colony, and maintains order

### Core Purpose

Enable Elara to:
1. **LEARN** from any source (documents, other models, datasets) through Training Bees
2. **ACT** through any tool (file system, APIs, databases) through Deployment Bees
3. **EVOLVE** continuously via feedback loops between training and deployment

---

## 1. Conceptual Architecture

### 1.1 The Beehive Metaphor

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           THE HIVEMIND HIVE                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                     TRAINING CHAMBER (Brood)                     │   │
│   │  Where young knowledge is gathered, processed, and fed to Queen  │   │
│   ├─────────────────────────────────────────────────────────────────┤   │
│   │                                                                  │   │
│   │   External Docs ──► Parsing Bee ──► Vectorizing Bee ──┐         │   │
│   │                                                         │         │   │
│   │   Ollama/Llama3 ──► Distillation Bee ──► Fine-tune Bee │         │   │
│   │                                                         ▼         │   │
│   │   Local Files ──► Ingestion Bee ──► Embedding Bee ──► [QUEEN]   │   │
│   │                                                            ▲      │   │
│   │   Feedback Loop ◄── Correction Bee ◄── Evaluation Bee ────┘      │   │
│   │                                                                  │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    DEPLOYMENT CHAMBER (Field)                    │   │
│   │     Where trained Queen sends bees to perform real-world tasks   │   │
│   ├─────────────────────────────────────────────────────────────────┤   │
│   │                                                                  │   │
│   │   [QUEEN] ──► Decision Bee ──► Tool Selection Bee ──┐            │   │
│   │                                                      │            │   │
│   │   ┌────────────────┬────────────────┬────────────────┤            │   │
│   │   ▼                ▼                ▼                ▼            │   │
│   │ File Bee     Browser Bee      API Bee       Code Bee            │   │
│   │ (read/write) (web search)     (POST/GET)    (execute py)        │   │
│   │   │                │                │                │            │   │
│   │   └────────────────┴────────────────┴────────────────┘            │   │
│   │                      │                                            │   │
│   │                      ▼                                            │   │
│   │              Result Bee ──► Output to User                       │   │
│   │                                                                  │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                      HONEYCOMB (Memory)                          │   │
│   │              Shared storage for all bees                         │   │
│   │   - Vector DB (document embeddings)                              │   │
│   │   - Interaction logs (training history)                          │   │
│   │   - Workflow states (bee locations)                              │   │
│   │   - Tool registry (available flowers)                            │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Key Design Principles

**1. Node-Based Workflows (Bees)**
Every bee is a workflow composed of nodes:
- **Trigger Node**: What starts the workflow (file upload, scheduled time, API call)
- **Processing Node**: Transform data (parse PDF, call model, filter results)
- **Action Node**: Execute operations (write file, send request, train model)
- **Conditional Node**: Branch logic (if/else based on content)

**2. Unified Runtime**
Both training and deployment use the same workflow engine—only the node types differ:
- Training nodes focus on *data ingestion and model updates*
- Deployment nodes focus on *tool execution and result delivery*

**3. Queen-Centric Design**
Elara is the only persistent AI in the system. Other models (Ollama, etc.) are ephemeral tools accessed via nodes—Elara decides when to call them.

**4. Local-First, Privacy-Preserving**
All workflows run locally. External APIs are optional nodes, not requirements. Data never leaves the hive unless explicitly sent by a deployment bee.

---

## 2. System Components

### 2.1 The Hive Core (hivemind.py)

**Responsibility**: Central orchestrator, workflow scheduler, node registry

**Functions**:
```python
class HiveMind:
    """Main orchestration engine"""

    def register_node(self, node_type: str, handler: Callable):
        """Add new node types to the hive (plugin system)"""
        pass

    def create_workflow(self, name: str, nodes: List[Node]) -> Bee:
        """Compile a list of nodes into an executable bee"""
        pass

    def execute_training(self, workflow_id: str, data_source: Source):
        """Run a training workflow to feed knowledge to Elara"""
        pass

    def execute_deployment(self, workflow_id: str, query: str):
        """Run a deployment workflow where Elara acts on the world"""
        pass

    def spawn_bee(self, workflow: Bee, context: Dict) -> BeeInstance:
        """Launch a workflow execution (async)"""
        pass
```

### 2.2 Bees (Workflows)

**Definition**: JSON/YAML-defined sequences of nodes that execute tasks

**Training Bee Example** (Document → Elara):
```yaml
# workflows/train_from_docs.yaml
name: document_ingestion_bee
type: training
trigger: file_upload
nodes:
  - id: read_file
    type: file_reader
    config: { path: "{{trigger.path}}" }

  - id: chunk_text
    type: text_chunker
    config: { chunk_size: 512, overlap: 50 }
    input: read_file.content

  - id: embed_chunks
    type: embedding_generator
    config: { model: "local" }
    input: chunk_text.chunks

  - id: store_vectors
    type: vector_store
    config: { collection: "knowledge_base" }
    input: embed_chunks.embeddings

  - id: fine_tune_trigger
    type: model_trainer
    config: { 
      target: "elara",
      method: "lora",
      epochs: 3
    }
    input: store_vectors.confirmation
```

**Deployment Bee Example** (Elara → Action):
```yaml
# workflows/code_assistant.yaml
name: code_helper_bee
type: deployment
trigger: user_query
nodes:
  - id: classify_intent
    type: llm_router
    config: { model: "elara", prompt: "Classify: code/math/chat" }
    input: "{{trigger.query}}"

  - id: fetch_context
    type: vector_retrieval
    config: { collection: "code_snippets", k: 3 }
    input: "{{trigger.query}}"
    condition: classify_intent.result == "code"

  - id: generate_code
    type: llm_generation
    config: { model: "elara", temperature: 0.2 }
    input: 
      prompt: "{{trigger.query}}"
      context: "{{fetch_context.documents}}"

  - id: execute_code
    type: code_executor
    config: { sandbox: true, timeout: 30 }
    input: generate_code.text
    condition: classify_intent.result == "code"

  - id: return_result
    type: output_formatter
    config: { format: "markdown" }
    input: execute_code.result
```

### 2.3 Nodes (The Worker Units)

**Core Node Types**:

| Category | Node | Function | Chamber |
|----------|------|----------|---------|
| **Input** | File Watcher | Monitor directory for new files | Training |
| **Input** | API Endpoint | HTTP listener for external triggers | Both |
| **Input** | Schedule | Cron-like time-based triggers | Both |
| **Process** | Text Parser | PDF, DOCX, TXT extraction | Training |
| **Process** | LLM Call | Invoke Elara or Ollama models | Both |
| **Process** | Vector Search | Query Honeycomb memory | Both |
| **Process** | Code Runner | Execute Python/bash in sandbox | Deployment |
| **Process** | Web Scraper | Fetch URLs, parse content | Both |
| **Action** | File Writer | Save to disk | Both |
| **Action** | API Request | POST/PUT/DELETE to external | Deployment |
| **Action** | Model Trainer | Trigger LoRA fine-tuning | Training |
| **Logic** | Conditional | If/else branching | Both |
| **Logic** | Loop | For-each over lists | Both |

**Node Interface**:
```python
@dataclass
class Node:
    id: str
    type: str
    config: Dict[str, Any]
    input_mapping: Dict[str, str]  # Maps previous outputs to inputs
    condition: Optional[str] = None  # Execute only if condition met

class NodeHandler(ABC):
    @abstractmethod
    def execute(self, inputs: Dict, config: Dict) -> Dict:
        """Execute node logic, return outputs"""
        pass

    @abstractmethod
    def validate(self, config: Dict) -> bool:
        """Validate configuration before execution"""
        pass
```

### 2.4 Honeycomb (Memory Layer)

**Responsibility**: Persistent storage for workflows, vectors, logs, and state

**Components**:
```python
class Honeycomb:
    """Unified storage layer"""

    # 1. Vector Store (RAG for Elara)
    def store_embeddings(self, documents: List[str], embeddings: List[List[float]]):
        """Store document chunks with embeddings"""
        pass

    def search_vectors(self, query_embedding: List[float], k: int = 5):
        """Retrieve similar documents"""
        pass

    # 2. Workflow State (Bee tracking)
    def save_execution_state(self, bee_id: str, node_id: str, data: Dict):
        """Resume workflows from interruptions"""
        pass

    # 3. Training Memory
    def log_interaction(self, query: str, response: str, correction: str = None):
        """Store feedback for future training"""
        pass

    # 4. Tool Registry
    def register_tool(self, name: str, endpoint: str, auth: Dict):
        """Available tools for deployment bees"""
        pass
```

**Storage Backends** (pluggable):
- **SQLite**: Workflow states, logs, config (default)
- **NumPy/JSON**: Simple vector storage (no FAISS dependency)
- **File System**: Document storage, model checkpoints

---

## 3. Training Chamber (Brood)

### 3.1 Purpose
Enable Elara to learn continuously from diverse sources without manual intervention.

### 3.2 Training Workflows

**Type A: Document Ingestion**
```
User drops PDF ──► Parse Bee ──► Chunk Bee ──► Embed Bee ──► Store Bee
                                                              │
                                                              ▼
                                                      Trigger Fine-tune Bee
                                                              │
                                                              ▼
                                                    Elara updates weights
```

**Type B: Model Distillation**
```
User query ──► Teacher Bee (Llama3-70b) ──► Generate response
                                                │
                                                ▼
Student Bee (Elara) ──► Generate response ──► Compare Bee
                                                │
                                                ▼
Loss Calculation Bee ──► Weight Update Bee ──► Save Checkpoint Bee
```

**Type C: Feedback Loop**
```
Deployment Bee output ──► User sees output ──► User provides correction
                                                      │
                                                      ▼
                                              Correction stored in Honeycomb
                                                      │
                                                      ▼
                                              Weekly: Aggregate Bee ──► Fine-tune Bee
```

### 3.3 Training Nodes Reference

| Node | Input | Output | Description |
|------|-------|--------|-------------|
| `file_reader` | path | content, metadata | Read any file type |
| `text_chunker` | text | chunks | Split with overlap |
| `embedding_generator` | texts | embeddings | Use local model |
| `vector_store` | embeddings | ids | Save to Honeycomb |
| `llm_teacher` | prompt | response | Call Ollama/AirLLM |
| `knowledge_distiller` | teacher_out, student_out | loss | Calculate KL divergence |
| `lora_trainer` | dataset_path | adapter_path | Fine-tune Elara |
| `checkpoint_manager` | model_path | version_id | Save/load snapshots |

---

## 4. Deployment Chamber (Field)

### 4.1 Purpose
Enable trained Elara to interact with the world through tools and APIs.

### 4.2 Deployment Workflows

**Type A: Assistant Mode**
```
User asks question ──► Context Bee (fetch relevant docs) ──► Elara Bee
                                                                   │
                                                                   ▼
                                                          Generate response
                                                                   │
                                                                   ▼
                                                          Output to user
```

**Type B: Agent Mode (Autonomous)**
```
User gives goal: "Analyze competitor website"
                    │
                    ▼
            Planning Bee (Elara breaks down steps)
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   Scrape Bee  Analysis Bee  Report Bee
   (fetch site) (Elara thinks) (write file)
        │           │           │
        └───────────┴───────────┘
                    │
                    ▼
            Completion Bee (notify user)
```

**Type C: Tool-Using Mode**
```
User: "Delete old logs"
    │
    ▼
Elara decides: Need file_system tool
    │
    ▼
Permission Bee (ask user confirm?)
    │
    ▼
Execute Bee (rm logs/*.log)
    │
    ▼
Confirm Bee (report success)
```

### 4.3 Deployment Nodes Reference

| Node | Input | Output | Description |
|------|-------|--------|-------------|
| `user_input` | - | text | Capture CLI/GUI input |
| `llm_elara` | prompt, context | response | Call Queen model |
| `file_system` | path, operation | result | Read/write/delete files |
| `web_request` | url, method, body | response | HTTP operations |
| `code_sandbox` | code, language | stdout, stderr | Safe execution |
| `database_query` | connection, query | rows | SQL operations |
| `notification` | message, channel | status | Send alerts |
| `human_approval` | request_details | approved | Pause for human input |

---

## 5. Integration with Cynapse

### 5.1 HiveMind as a Neuron

HiveMind is registered as the `elara` neuron in Cynapse Hub:

```json
{
  "name": "elara",
  "entry_point": "hivemind.py",
  "commands": {
    "train": "Execute training workflow",
    "deploy": "Start deployment workflow",
    "chat": "Interactive deployment mode"
  }
}
```

### 5.2 Ghost Shell Integration

HiveMind respects the Ghost Shell security model:
- **Training**: Can only access documents from mounted USB shards
- **Deployment**: Elara model loaded from assembled shards (RAM-only)
- **Audit**: All workflow executions logged to NDJSON

### 5.3 TUI Integration

Synaptic Fortress shows HiveMind status:
- **Zone 3 (Activation)**: Current workflow visualization
- **Zone 4 (Operations)**: Training progress or chat interface
- **Perimeter**: Workflow execution status (running/complete/error)

---

## 6. Usage Patterns

### 6.1 CLI Interface

```bash
# Initialize HiveMind
python hivemind.py init

# Create new workflow
python hivemind.py workflow create --name doc_trainer --type training

# Edit workflow (opens YAML editor)
python hivemind.py workflow edit doc_trainer

# Execute training
python hivemind.py train --workflow doc_trainer --source ./docs/

# Interactive deployment
python hivemind.py deploy --workflow code_assistant --interactive

# List running bees
python hivemind.py status

# Kill a bee
python hivemind.py kill <bee_id>
```

### 6.2 Python API

```python
from hivemind import HiveMind, Bee

# Initialize hive
hive = HiveMind()

# Define a training bee programmatically
bee = Bee(name="pdf_learner", type="training")
bee.add_node("file_watcher", path="/uploads")
bee.add_node("pdf_parser", input="file_watcher.file")
bee.add_node("elara_trainer", input="pdf_parser.text", epochs=3)

# Execute
hive.spawn_bee(bee)

# Define deployment bee
deploy_bee = Bee(name="assistant", type="deployment")
deploy_bee.add_node("chat_input")
deploy_bee.add_node("elara_generate", model="elara", context=True)
deploy_bee.add_node("markdown_output")

hive.spawn_bee(deploy_bee)
```

### 6.3 Configuration

**hivemind.yaml**:
```yaml
hive:
  name: "cynapse_hive"
  max_concurrent_bees: 5
  log_level: INFO

storage:
  vector_backend: "numpy"  # or "faiss" if installed
  state_backend: "sqlite"
  document_path: "./data/documents"

models:
  queen:
    path: "./models/elara.gguf"
    context_length: 4096
    gpu_layers: -1
  teachers:
    - name: "llama3-70b"
      endpoint: "http://localhost:11434"
    - name: "gpt-4"
      endpoint: "${OPENAI_API_URL}"
      api_key: "${OPENAI_API_KEY}"

security:
  sandbox_enabled: true
  max_file_size: "100MB"
  allowed_paths:
    - "./workspace"
    - "./uploads"
  blocked_commands:
    - "rm -rf /"
    - "format"
```

---

## 7. Future Roadmap

### Phase 1: Core Engine (v1.0)
- [ ] YAML/JSON workflow parser
- [ ] Node registry system
- [ ] Basic node types (file, llm, code)
- [ ] SQLite state management
- [ ] CLI interface

### Phase 2: Training Pipeline (v1.1)
- [ ] Document ingestion workflows
- [ ] Ollama integration node
- [ ] LoRA training node
- [ ] Feedback capture system
- [ ] Vector search (numpy-based)

### Phase 3: Advanced Deployment (v1.2)
- [ ] Autonomous agent loops
- [ ] Tool use with human approval
- [ ] Multi-step planning
- [ ] Webhook/API triggers
- [ ] Parallel bee execution

### Phase 4: Ecosystem (v2.0)
- [ ] Visual workflow editor (TUI/GUI)
- [ ] Community node marketplace
- [ ] Remote hive federation
- [ ] Distributed training across hives

---

## 8. Comparison Table

| Feature | n8n | Zapier | Claude Code | HiveMind |
|---------|-----|--------|-------------|----------|
| **Self-hosted** | ✅ | ❌ | ❌ | ✅ |
| **AI-Native** | ❌ | ❌ | ✅ | ✅ (Elara-centric) |
| **Training Workflows** | ❌ | ❌ | ❌ | ✅ |
| **Local Models** | ❌ | ❌ | ❌ | ✅ |
| **Code Execution** | ✅ | ❌ | ✅ | ✅ (sandboxed) |
| **Open Source** | ✅ | ❌ | ❌ | ✅ |
| **Privacy** | ⚠️ | ❌ | ❌ | ✅ (air-gapped) |
| **Hardware Cost** | Server | SaaS | API | Consumer GPU |

---

## 9. Terminology

- **Bee**: A workflow instance—autonomous, task-specific, disposable
- **Queen**: Elara—the central AI model that guides the hive
- **Honeycomb**: Vector database + state storage
- **Brood**: Training chamber where knowledge is cultivated
- **Field**: Deployment chamber where actions are executed
- **Node**: Single unit of work within a bee
- **Swarm**: Multiple bees executing in parallel
- **Nectar**: Raw data/documents brought into the hive
- **Honey**: Processed knowledge (embeddings, fine-tuned weights)

---

## 10. Design Principles

1. **Queen is Sovereign**: Only Elara makes decisions; other models are tools
2. **Bees are Stateless**: All context comes from Honeycomb; bees can die and respawn
3. **Privacy by Design**: Local-first, no cloud required, audit everything
4. **Extensibility**: Node-based plugin system for custom tools
5. **Resilience**: Failed bees retry; dead nodes skipped; state preserved
6. **Simplicity**: If it can be a YAML file, it should be

---

*"A single bee is a curiosity. A hive is intelligence."*
