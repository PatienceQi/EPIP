# EPIP — Enterprise Policy Insight Platform

<div align="center">

**GraphRAG-powered Policy & Regulation Q&A System with Knowledge Graph, Hybrid Retrieval, and Hallucination Detection**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Neo4j 5.x](https://img.shields.io/badge/Neo4j-5.x-brightgreen.svg)](https://neo4j.com/)

</div>

---

## Overview

EPIP is a production-grade intelligent Q&A platform for policy and regulation consultation, built on **Retrieval-Augmented Generation (RAG)** and **Knowledge Graph (GraphRAG)** technologies. It delivers accurate, trustworthy, and explainable answers with full source traceability.

### Key Results

- **85%+ QA accuracy** on policy domain queries
- **Software Copyright** registered (Reg. No. 2026SR0067490)
- **¥100,000 industry-funded research project** secured based on this system
- Served **52 clients** with **250,000+ inquiries**

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      Frontend Layer                           │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────┐  │
│  │  Chat UI      │  │  GraphRAG UI   │  │  Diagnostic UI   │  │
│  └──────────────┘  └───────────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│                    API Layer (Flask/FastAPI)                   │
│  Chat Routes │ Session Mgmt │ Health Check │ Metrics Monitor  │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│                      Core Engine Layer                        │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  GraphRAG Engine                        │  │
│  │  Entity Extraction → Hybrid Retrieval → Answer Gen      │  │
│  │  Hallucination Detection → Quality Evaluation           │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│                     Storage Layer                             │
│  Neo4j (KG) │ ChromaDB (Vectors) │ Redis │ JSON Policies     │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│                    LLM Service (Ollama / Cloud API)           │
└──────────────────────────────────────────────────────────────┘
```

---

## Core Features

### GraphRAG Hybrid Retrieval
- **Dual-mode retrieval**: Vector search (ChromaDB + bge-m3) + Knowledge graph traversal (Neo4j Cypher)
- **Dynamic routing**: Automatically selects optimal retrieval mode per query in **<50ms**
- **Context fusion**: Weighted merging of vector and graph results, improving knowledge coverage by **67%**

### Knowledge Graph Construction
- **Entity extraction**: Rule-based + LLM semantic extraction of policy entities, institutions, regions, and clauses
- **Cypher query builder**: Dynamic translation of semantic queries into graph traversal operations
- **Graph query service**: Entity lookup, relationship queries, shortest path, entity network expansion

### 5-Dimension Hallucination Detection
Real-time credibility scoring **without reference answers**:
1. Entity Coverage (25%) — Are key entities from source documents present?
2. Faithfulness (30%) — Is the answer grounded in retrieved context?
3. Relevance (25%) — Does the answer address the user's question?
4. Sufficiency (10%) — Is the answer complete enough?
5. Hallucination Risk (10%) — Statistical anomaly detection

### Auto-Diagnosis & Self-Repair
- **3-level diagnostics**: BASIC (connectivity) → FULL (component integrity) → REPAIR (auto-fix)
- **9 repair strategies**: Python path, dependency installation, env config, Ollama service, Neo4j connection, etc.

### Engineering Quality
- 9-layer architecture with 5-phase iterative refactoring (code reduced by **36%**, modularity increased by **118%**)
- **30+ test files** covering 7 test layers (API, core, services, infrastructure, monitoring, diagnostic, validation)
- Multi-session dialogue with entity tracking and context maintenance

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, Flask/FastAPI, Pydantic |
| Knowledge Graph | Neo4j 5.x, Cypher |
| Vector Store | ChromaDB, bge-m3 embeddings |
| LLM | Ollama (Llama 3.2) / Cloud API |
| Frontend | HTML5, CSS3, JavaScript |
| Monitoring | Prometheus metrics, liveness/readiness probes |
| DevOps | Docker, Docker Compose, CI/CD (GitHub Actions) |
| Testing | pytest, pytest-cov |

---

## Quick Start

```bash
# Clone
git clone https://github.com/PatienceQi/EPIP.git
cd EPIP

# Install
make install  # or: pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your Neo4j, Redis, and LLM settings

# Run
make run
```

---

## Publications & Recognition

- **Software Copyright**: Reg. No. 2026SR0067490 (National Copyright Administration of China)
- **Industry Funding**: ¥100,000 horizontal research project based on this system
- **Related Paper**: "Hybrid Precision: A Novel Evaluation Metric for Hybrid Retrieval Systems" (Under Review)

---

## Author

**Jingxuan Qi** — South China University of Technology, Software Engineering

- Research: NLP, RAG Systems, Knowledge Graphs
- Email: qi1312750677@163.com
- Website: [patienceqi.github.io](https://patienceqi.github.io)

## License

MIT License
