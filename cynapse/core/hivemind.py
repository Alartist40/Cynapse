#!/usr/bin/env python3
"""
HiveMind Core Engine — Workflow Orchestration System
====================================================
An n8n-style automation platform for AI model training and deployment.

Usage:
    python hivemind.py init
    python hivemind.py bee create --name my_bee --type training
    python hivemind.py run --bee <id>
"""

import os
import sys
import json
import yaml
import time
import sqlite3
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
import threading

# Lazy imports for heavy dependencies
_has_numpy = False

def _ensure_numpy():
    global _has_numpy
    if not _has_numpy:
        try:
            import numpy as np
            globals()['np'] = np
            _has_numpy = True
        except ImportError:
            raise ImportError("numpy is required for HiveMind")
    return globals()['np']

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class HiveConfig:
    """HiveMind configuration"""
    hive_name: str = "cynapse_hive"
    max_concurrent_bees: int = 5
    log_level: str = "INFO"
    db_path: str = "./hivemind.db"
    document_path: str = "./data/documents"
    workflow_path: str = "./workflows"
    queen_model: str = "./models/elara.gguf"
    sandbox_enabled: bool = True
    auto_approve: bool = False

    @classmethod
    def from_yaml(cls, path: str):
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data.get('hive', {}))

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class BeeState(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class BeeType(Enum):
    TRAINING = "training"
    DEPLOYMENT = "deployment"

@dataclass
class Node:
    """Single unit of work in a workflow"""
    id: str
    type: str
    config: Dict[str, Any] = field(default_factory=dict)
    inputs: Dict[str, str] = field(default_factory=dict)
    condition: Optional[str] = None

    def should_execute(self, context: Dict) -> bool:
        if not self.condition:
            return True
        try:
            return eval(self.condition, {"__builtins__": {}}, context)
        except:
            return False

@dataclass
class Bee:
    """Workflow definition"""
    id: str
    name: str
    type: BeeType
    nodes: List[Node]
    trigger: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type.value,
            'nodes': [{'id': n.id, 'type': n.type, 'config': n.config, 
                      'inputs': n.inputs, 'condition': n.condition} for n in self.nodes],
            'trigger': self.trigger,
            'created_at': self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Bee':
        nodes = [Node(n['id'], n['type'], n.get('config', {}), 
                     n.get('inputs', {}), n.get('condition')) 
                for n in data['nodes']]
        return cls(
            id=data['id'],
            name=data['name'],
            type=BeeType(data['type']),
            nodes=nodes,
            trigger=data.get('trigger', {}),
            created_at=data.get('created_at', time.time())
        )

@dataclass
class BeeInstance:
    """Running instance of a bee"""
    instance_id: str
    bee_id: str
    state: BeeState
    context: Dict[str, Any] = field(default_factory=dict)
    current_node: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    logs: List[str] = field(default_factory=list)

# ---------------------------------------------------------------------------
# Honeycomb (Storage Layer)
# ---------------------------------------------------------------------------

class Honeycomb:
    """Unified storage: SQLite for state, memory for vectors"""

    def __init__(self, db_path: str = "./hivemind.db"):
        self.db_path = db_path
        self._init_db()
        self.vectors: Dict[str, List] = {}

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bees (
                    id TEXT PRIMARY KEY, name TEXT, type TEXT,
                    definition TEXT, created_at REAL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS instances (
                    instance_id TEXT PRIMARY KEY, bee_id TEXT, state TEXT,
                    context TEXT, current_node TEXT, start_time REAL, end_time REAL, logs TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY, query TEXT, response TEXT,
                    correction TEXT, timestamp REAL, bee_id TEXT
                )
            """)

            conn.commit()

    def save_bee(self, bee: Bee):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT OR REPLACE INTO bees VALUES (?, ?, ?, ?, ?)',
                (bee.id, bee.name, bee.type.value, json.dumps(bee.to_dict()), bee.created_at)
            )

    def load_bee(self, bee_id: str) -> Optional[Bee]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT definition FROM bees WHERE id = ?', (bee_id,))
            row = cursor.fetchone()
            if row:
                return Bee.from_dict(json.loads(row[0]))
        return None

    def list_bees(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT id, name, type, created_at FROM bees ORDER BY created_at DESC')
            return [{'id': r[0], 'name': r[1], 'type': r[2], 'created_at': r[3]} for r in cursor.fetchall()]

    def create_instance(self, instance: BeeInstance):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT INTO instances VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (instance.instance_id, instance.bee_id, instance.state.value, 
                 json.dumps(instance.context), instance.current_node, instance.start_time, None, json.dumps(instance.logs))
            )

    def update_instance(self, instance_id: str, **kwargs):
        with sqlite3.connect(self.db_path) as conn:
            for key, value in kwargs.items():
                if isinstance(value, (list, dict)):
                    value = json.dumps(value)
                conn.execute(f'UPDATE instances SET {key} = ? WHERE instance_id = ?', (value, instance_id))

    def get_instance(self, instance_id: str) -> Optional[BeeInstance]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT bee_id, state, context, current_node, start_time, end_time, logs FROM instances WHERE instance_id = ?',
                (instance_id,)
            )
            row = cursor.fetchone()
            if row:
                return BeeInstance(
                    instance_id=instance_id, bee_id=row[0], state=BeeState(row[1]),
                    context=json.loads(row[2]) if row[2] else {},
                    current_node=row[3], start_time=row[4], end_time=row[5],
                    logs=json.loads(row[6]) if row[6] else []
                )
        return None

    def log_interaction(self, query: str, response: str, correction: str = None, bee_id: str = None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT INTO memory (query, response, correction, timestamp, bee_id) VALUES (?, ?, ?, ?, ?)',
                (query, response, correction, time.time(), bee_id)
            )

    def get_recent_memory(self, n: int = 10) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT query, response, correction, timestamp FROM memory ORDER BY timestamp DESC LIMIT ?',
                (n,)
            )
            return [{'query': r[0], 'response': r[1], 'correction': r[2], 'timestamp': r[3]} for r in cursor.fetchall()]

    def store_vectors(self, collection: str, texts: List[str], embeddings: List[List[float]]):
        np = _ensure_numpy()
        if collection not in self.vectors:
            self.vectors[collection] = {'texts': [], 'embeddings': np.array([])}
        self.vectors[collection]['texts'].extend(texts)
        new_emb = np.array(embeddings)
        if self.vectors[collection]['embeddings'].size == 0:
            self.vectors[collection]['embeddings'] = new_emb
        else:
            self.vectors[collection]['embeddings'] = np.vstack([self.vectors[collection]['embeddings'], new_emb])

    def search_vectors(self, collection: str, query_embedding: List[float], k: int = 5) -> List[Dict]:
        np = _ensure_numpy()
        if collection not in self.vectors:
            return []
        query = np.array(query_embedding)
        embeddings = self.vectors[collection]['embeddings']
        texts = self.vectors[collection]['texts']
        query_norm = query / np.linalg.norm(query)
        emb_norm = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        similarities = np.dot(emb_norm, query_norm)
        top_k_idx = np.argsort(similarities)[-k:][::-1]
        return [{'text': texts[i], 'score': float(similarities[i])} for i in top_k_idx]

# ---------------------------------------------------------------------------
# Node Handlers
# ---------------------------------------------------------------------------

class NodeHandler(ABC):
    @abstractmethod
    def execute(self, inputs: Dict[str, Any], config: Dict[str, Any], context: Dict) -> Dict[str, Any]:
        pass

    def validate(self, config: Dict[str, Any]) -> bool:
        return True

class FileReaderNode(NodeHandler):
    def execute(self, inputs, config, context):
        path = config.get('path', inputs.get('path'))
        if not path:
            raise ValueError("No path provided")
        resolved = Path(path).resolve()
        allowed = [Path(p).resolve() for p in context.get('allowed_paths', ['.'])]
        if not any(str(resolved).startswith(str(a)) for a in allowed):
            raise PermissionError(f"Access denied: {path}")
        with open(resolved, 'r', encoding='utf-8') as f:
            content = f.read()
        return {'content': content, 'path': str(resolved), 'size': len(content)}

class TextChunkerNode(NodeHandler):
    def execute(self, inputs, config, context):
        text = inputs.get('text', '')
        chunk_size = config.get('chunk_size', 512)
        overlap = config.get('overlap', 50)
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap
        return {'chunks': chunks, 'count': len(chunks)}

class LLMNode(NodeHandler):
    def execute(self, inputs, config, context):
        model = config.get('model', 'elara')
        prompt = inputs.get('prompt', '')
        temperature = config.get('temperature', 0.7)
        max_tokens = config.get('max_tokens', 100)

        try:
            from llama_cpp import Llama
            llm = Llama(model_path=context.get('queen_model', './elara.gguf'), verbose=False)
            output = llm(prompt, max_tokens=max_tokens, temperature=temperature)
            return {'text': output['choices'][0]['text'], 'model': model}
        except ImportError:
            pass

        try:
            import ollama
            response = ollama.generate(model=model, prompt=prompt, 
                                     options={'temperature': temperature, 'num_predict': max_tokens})
            return {'text': response['response'], 'model': model}
        except ImportError:
            raise RuntimeError("No LLM backend available")

class CodeExecuteNode(NodeHandler):
    def execute(self, inputs, config, context):
        if not context.get('sandbox_enabled', True):
            raise PermissionError("Code execution disabled")
        code = inputs.get('code', '')
        timeout = config.get('timeout', 30)
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=timeout)
        return {'stdout': result.stdout, 'stderr': result.stderr, 'returncode': result.returncode}

class VectorStoreNode(NodeHandler):
    def execute(self, inputs, config, context):
        honeycomb = context.get('honeycomb')
        collection = config.get('collection', 'default')
        texts = inputs.get('texts', [])
        embeddings = inputs.get('embeddings', [])
        honeycomb.store_vectors(collection, texts, embeddings)
        return {'stored': len(texts), 'collection': collection}

class OutputNode(NodeHandler):
    def execute(self, inputs, config, context):
        format_type = config.get('format', 'text')
        content = inputs.get('content', str(inputs))
        if format_type == 'json':
            output = json.dumps(content, indent=2)
        elif format_type == 'markdown':
            output = f"```\n{content}\n```"
        else:
            output = str(content)
        print(f"[OUTPUT] {output}")
        return {'output': output}

# ---------------------------------------------------------------------------
# HiveMind Engine
# ---------------------------------------------------------------------------

class HiveMind:
    def __init__(self, config: Optional[HiveConfig] = None):
        self.config = config or HiveConfig()
        self.honeycomb = Honeycomb(self.config.db_path)
        self.handlers: Dict[str, NodeHandler] = {}
        self.running_bees: Dict[str, threading.Thread] = {}
        self._register_default_handlers()
        Path(self.config.document_path).mkdir(parents=True, exist_ok=True)
        Path(self.config.workflow_path).mkdir(parents=True, exist_ok=True)

    def _register_default_handlers(self):
        self.handlers = {
            'file_reader': FileReaderNode(),
            'text_chunker': TextChunkerNode(),
            'llm': LLMNode(),
            'code_execute': CodeExecuteNode(),
            'vector_store': VectorStoreNode(),
            'output': OutputNode(),
        }

    def register_handler(self, node_type: str, handler: NodeHandler):
        self.handlers[node_type] = handler

    def create_bee(self, name: str, bee_type: BeeType, nodes: List[Node] = None) -> Bee:
        bee_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()[:12]
        bee = Bee(id=bee_id, name=name, type=bee_type, nodes=nodes or [])
        self.honeycomb.save_bee(bee)
        return bee

    def load_bee(self, bee_id: str) -> Optional[Bee]:
        return self.honeycomb.load_bee(bee_id)

    def list_bees(self) -> List[Dict]:
        return self.honeycomb.list_bees()

    def spawn_bee(self, bee_id: str, initial_context: Dict = None) -> str:
        bee = self.load_bee(bee_id)
        if not bee:
            raise ValueError(f"Bee {bee_id} not found")
        instance_id = f"{bee_id}_{int(time.time())}"
        instance = BeeInstance(instance_id=instance_id, bee_id=bee_id, state=BeeState.QUEUED, context=initial_context or {})
        self.honeycomb.create_instance(instance)
        thread = threading.Thread(target=self._execute_bee, args=(instance, bee))
        thread.daemon = True
        thread.start()
        self.running_bees[instance_id] = thread
        return instance_id

    def _execute_bee(self, instance: BeeInstance, bee: Bee):
        self.honeycomb.update_instance(instance.instance_id, state=BeeState.RUNNING.value)
        context = {
            'honeycomb': self.honeycomb,
            'queen_model': self.config.queen_model,
            'sandbox_enabled': self.config.sandbox_enabled,
            'auto_approve': self.config.auto_approve,
            'allowed_paths': ['.', self.config.document_path, self.config.workflow_path],
            **instance.context
        }
        node_outputs = {}

        try:
            for node in bee.nodes:
                if not node.should_execute(context):
                    continue
                self.honeycomb.update_instance(instance.instance_id, current_node=node.id)
                inputs = {}
                for key, ref in node.inputs.items():
                    if '.' in ref:
                        node_id, output_key = ref.split('.', 1)
                        inputs[key] = node_outputs.get(node_id, {}).get(output_key)
                    else:
                        inputs[key] = node_outputs.get(ref)
                handler = self.handlers.get(node.type)
                if not handler:
                    raise RuntimeError(f"Unknown node type: {node.type}")
                print(f"[Bee {instance.instance_id}] {node.type} ({node.id})...")
                outputs = handler.execute(inputs, node.config, context)
                node_outputs[node.id] = outputs
                instance.logs.append(f"Executed {node.id}")

            self.honeycomb.update_instance(instance.instance_id, state=BeeState.COMPLETED.value, 
                                          end_time=time.time(), logs=instance.logs)
            print(f"[Bee {instance.instance_id}] Completed")
        except Exception as e:
            instance.logs.append(f"ERROR: {str(e)}")
            self.honeycomb.update_instance(instance.instance_id, state=BeeState.FAILED.value,
                                          end_time=time.time(), logs=instance.logs)
            print(f"[Bee {instance.instance_id}] Failed: {e}")
        finally:
            if instance.instance_id in self.running_bees:
                del self.running_bees[instance.instance_id]

    def get_instance_status(self, instance_id: str) -> Optional[BeeInstance]:
        return self.honeycomb.get_instance(instance_id)

    def kill_bee(self, instance_id: str):
        if instance_id in self.running_bees:
            self.honeycomb.update_instance(instance_id, state=BeeState.CANCELLED.value)
            print(f"[Bee {instance_id}] Marked for cancellation")

    def train_from_documents(self, doc_path: str, collection: str = "knowledge"):
        bee = self.create_bee(
            name=f"train_docs_{int(time.time())}",
            bee_type=BeeType.TRAINING,
            nodes=[
                Node('read', 'file_reader', {'path': doc_path}),
                Node('chunk', 'text_chunker', {'chunk_size': 512}, {'text': 'read.content'}),
                Node('store', 'vector_store', {'collection': collection}, {'texts': 'chunk.chunks'}),
            ]
        )
        return self.spawn_bee(bee.id)

    def deploy_chat(self, query: str):
        bee = self.create_bee(
            name=f"chat_{int(time.time())}",
            bee_type=BeeType.DEPLOYMENT,
            nodes=[
                Node('llm', 'llm', {'model': 'elara'}, {'prompt': query}),
                Node('output', 'output', {'format': 'text'}, {'content': 'llm.text'}),
            ]
        )
        return self.spawn_bee(bee.id)

# ---------------------------------------------------------------------------
# CLI Interface
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="HiveMind — AI Workflow Orchestration")
    subparsers = parser.add_subparsers(dest='command')

    subparsers.add_parser('init', help='Initialize HiveMind')

    bee_parser = subparsers.add_parser('bee', help='Manage bees')
    bee_sub = bee_parser.add_subparsers(dest='bee_cmd')
    create_parser = bee_sub.add_parser('create', help='Create bee')
    create_parser.add_argument('--name', required=True)
    create_parser.add_argument('--type', choices=['training', 'deployment'], required=True)
    bee_sub.add_parser('list', help='List bees')

    run_parser = subparsers.add_parser('run', help='Run bee')
    run_parser.add_argument('--bee', required=True)
    run_parser.add_argument('--context')

    subparsers.add_parser('status', help='Show status')

    kill_parser = subparsers.add_parser('kill', help='Kill bee')
    kill_parser.add_argument('instance_id')

    train_parser = subparsers.add_parser('train', help='Quick train')
    train_parser.add_argument('--docs', required=True)

    chat_parser = subparsers.add_parser('chat', help='Quick chat')
    chat_parser.add_argument('--query', required=True)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    config_path = Path('./hivemind.yaml')
    config = HiveConfig.from_yaml(config_path) if config_path.exists() else HiveConfig()
    hive = HiveMind(config)

    if args.command == 'init':
        default_config = """
hive:
  name: "cynapse_hive"
  max_concurrent_bees: 5
  log_level: "INFO"
  db_path: "./hivemind.db"
  document_path: "./data/documents"
  workflow_path: "./workflows"
  queen_model: "./models/elara.gguf"
  sandbox_enabled: true
  auto_approve: false
"""
        with open('hivemind.yaml', 'w') as f:
            f.write(default_config.strip())
        print("Initialized HiveMind")
        Path('./data/documents').mkdir(parents=True, exist_ok=True)
        Path('./workflows').mkdir(parents=True, exist_ok=True)

    elif args.command == 'bee':
        if args.bee_cmd == 'create':
            bee_type = BeeType.TRAINING if args.type == 'training' else BeeType.DEPLOYMENT
            bee = hive.create_bee(args.name, bee_type)
            print(f"Created {args.type} bee: {bee.id}")
        elif args.bee_cmd == 'list':
            for b in hive.list_bees():
                print(f"{b['id']:<12} {b['name']:<20} {b['type']:<12}")

    elif args.command == 'run':
        context = json.loads(args.context) if args.context else {}
        instance_id = hive.spawn_bee(args.bee, context)
        print(f"Spawned: {instance_id}")

    elif args.command == 'status':
        print(f"Active: {len(hive.running_bees)}")

    elif args.command == 'kill':
        hive.kill_bee(args.instance_id)

    elif args.command == 'train':
        instance_id = hive.train_from_documents(args.docs)
        print(f"Training: {instance_id}")

    elif args.command == 'chat':
        instance_id = hive.deploy_chat(args.query)
        print(f"Chat: {instance_id}")

if __name__ == '__main__':
    main()