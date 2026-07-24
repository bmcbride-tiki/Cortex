# Project Overview: Programmatic & AI Workflow Builder

This project is a visual and programmatic workflow engine built on FastAPI that maps, executes, and automates business process flows. It integrates Python operations, Microsoft 365, Power Platform, Copilot Agents, and Google Gemini Enterprise APIs/MCP tools.

---

## 1. Directory Structure Rules & Guidelines

All core architecture MUST adhere to the following directory schema:

*   **`00_System/`**: FastAPI app core, master router, database models, database connections (SQLAlchemy / Asyncpg), and workflow builder engine/visual rendering logic.
*   **`10_Skills/`**: Low-latency, direct system operations (e.g., high-speed DB queries, cache operations, local system tasks).
*   **`11_Processes/`**: Pure code tasks with zero parameters. Single-use, click-and-run execution units.
*   **`12_Tasks/`**: Interactive nodes requiring specific configuration inputs, runtime options, file uploads, or user parameters.
*   **`13_Functions/`**: Automation utilities, transformation helpers, and logic gates (e.g., Docx to JSON, JSON to XLSX, conditional routers, export functions).
*   **`14_Adapters/`**: Third-party connections and APIs (e.g., Google Gemini Enterprise, MS M365, Power Platform, local file system, external APIs).

---

## 2. API & MCP Tool Mocking Guidelines (Crucial)

Currently, external API access (Gemini, MS365, MCP tools) **is not connected**. All tools must look fully functional, pass typing checks, and simulate realistic input/output behavior.

### Principles for Mock Implementations:
1.  **Abstract Base Interfaces**: Every tool in `14_Adapters/` or `12_Tasks/` must inherit from a standardized abstract base class (`BaseAdapter` or `BaseTask`).
2.  **Toggleable Execution**: Implement a mock flag (`MOCK_MODE: bool = True` via env or settings).
3.  **Realistic Data Contracts**: Mocks must return valid structures matching real API responses (e.g., standard JSON, valid byte buffers for Docx/XLSX).
4.  **Graceful Degradation**: Throw clear `NotImplementedError` or warning logs when unsupported features are called without API credentials.

---

## 3. Reference Workflow Definition: Document Processing Engine

When building or testing execution pipelines, ensure the system supports the following standard workflow end-to-end:

[Docx File Input]
└──> (13_Functions) Convert Docx to cg.json
├──> (13_Functions) Transform cg.json to TOS (.xlsx)
└──> (14_Adapters/Gemini) Create Gemini Notebook LM
├──> Upload sources (PDFs, Docx, cg.json)
├──> Execute prompt loops sequentially
└──> Scrape responses into stem.json
└──> (13_Functions) Convert stem.json to .docx
└──> [Human Review Gate (FastAPI UI)]
└──> Convert reviewed .docx to .xlsx (Final Layout)


---

## 4. Engineering Standards & Code Patterns

### Standard Interface for Tasks / Functions / Adapters
Every executable component across folders `10_Skills` to `14_Adapters` MUST expose an async interface using Pydantic models:

```python
from pydantic import BaseModel, Field
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Any

InputSchema = TypeVar("InputSchema", bound=BaseModel)
OutputSchema = TypeVar("OutputSchema", bound=BaseModel)

class TaskResult(BaseModel):
    success: bool
    data: dict[str, Any]
    error: str | None = None

class BaseWorkflowNode(ABC, Generic[InputSchema, OutputSchema]):
    @abstractmethod
    async def execute(self, inputs: InputSchema) -> OutputSchema:
        """Core execution logic. Abstracted for easy MCP/API wiring."""
        pass
Python Package & Dependency Rules
Use FastAPI for API endpoints and visual pipeline server (00_System/).

Use Pydantic V2 for all data parsing, config validation, and serialization.

Use SQLAlchemy 2.0 (Async) for data models.

Use python-docx and openpyxl for Microsoft Office document manipulations.

Dependencies must be managed via standard pyproject.toml or requirements.txt. Install requirements automatically when writing new tool implementations.

5. Development & Testing Instructions for Claude Code
When generating code or installing components:

Always Type-Check: Use strict type hints on every function signature (mypy compliant).

Auto-Install Packages: If a required Python module (e.g., openpyxl, python-docx, pydantic) is missing, invoke terminal commands to install it.

Automated Verification: Create unit tests in tests/ for each newly created tool using synthetic file payloads. Run pytest after making changes.

Clean Abstractions: Keep external service clients inside 14_Adapters/ and reference them in tasks via dependency injection so real credentials can be plugged in seamlessly without touching core logic.


---

## Implementation Prompt for Claude Code

When starting a session with Claude Code to generate this architecture, use this task prompt:

> **Claude Code Task Directive:**
> 
> Read `CLAUDE.md` in the workspace root. Build out the scaffold for `00_System`, `10_Skills`, `11_Processes`, `12_Tasks`, `13_Functions`, and `14_Adapters`. 
> 
> Specifically:
> 1. Set up the core FastAPI application in `00_System/` with routing hooks for dynamic visual workflow execution.
> 2. Create the mock abstract interfaces in `14_Adapters/` for Google Gemini Enterprise API and M365/Power Automate services.
> 3. Implement the Docx -> JSON (`cg.json`) -> TOS Excel (`.xlsx`) transformation tools under `13_Functions/`.
> 4. Ensure all code contains Pydantic models, handles errors cleanly, and includes mock data generators so workflows can run locally without live API keys. Install any missing packages as needed and write unit tests to verify execution.