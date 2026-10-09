# ⚖️ LegalMind AI
### AI-Powered Legal Document Intelligence & Research Platform

LegalMind AI is an AI-powered legal research platform designed to help users explore legal judgments, search relevant case law, analyze legal documents, compare cases, and discover similar judgments.

The system combines **Natural Language Processing (NLP), semantic search, keyword-based retrieval, and Large Language Models (LLMs)** to make legal document research more accessible and efficient.

> **Project status:** Under active development  
> **Primary focus:** Legal document intelligence and case-law research

---

## 📌 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Technology Stack](#-technology-stack)
- [System Architecture](#-system-architecture)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Installation and Setup](#-installation-and-setup)
- [Environment Configuration](#-environment-configuration)
- [Running the Application](#-running-the-application)
- [API Endpoints](#-api-endpoints)
- [How It Works](#-how-it-works)
- [Data and Index Setup](#-data-and-index-setup)
- [Security](#-security)
- [Limitations](#-limitations)
- [Future Enhancements](#-future-enhancements)
- [Disclaimer](#-disclaimer)

---

## 🎯 Overview

Legal professionals, researchers, and students often need to examine lengthy judgments, identify relevant legal provisions, and find precedents related to a particular legal issue.

LegalMind AI aims to simplify this process through an intelligent legal research workflow.

The platform processes legal documents, extracts text and metadata, creates searchable document chunks, generates semantic embeddings, and retrieves relevant passages using a hybrid search approach.

The retrieved information can then be used to generate AI-assisted responses with supporting legal sources.

### Project Objectives

- Simplify legal judgment discovery and research.
- Enable natural-language searches across indexed legal documents.
- Identify judgments relevant to a legal question or case.
- Support the analysis and comparison of legal cases.
- Provide AI-assisted answers grounded in retrieved legal documents.
- Reduce the time required to locate potentially relevant legal information.

---

## ✨ Key Features

### 1. Intelligent Legal Search
Search indexed legal documents using natural-language queries and retrieve potentially relevant judgments and passages.

### 2. Hybrid Retrieval System
Combines semantic retrieval using vector embeddings with keyword-based retrieval using BM25 to improve document discovery.

### 3. AI-Powered Legal Question Answering
Uses a retrieval-augmented generation (RAG) workflow to generate responses using relevant retrieved legal material.

### 4. Legal Document Processing
Extracts text from PDF documents and prepares it for metadata extraction, chunking, embedding, and indexing.

### 5. Case Comparison
Supports comparison of legal cases and identification of similarities and differences between them.

### 6. Similar Judgment Discovery
Analyzes an uploaded case and searches the indexed collection for potentially similar judgments using hybrid retrieval and reranking.

### 7. Current Case Upload and Analysis
Allows users to upload a current-case PDF for analysis and retrieval of potentially relevant historical judgments.

### 8. Metadata and Source Tracking
Maintains legal document metadata such as case name, court, judgment date, citation, Acts, sections, jurisdiction, and source URL when available.

### 9. Document Ingestion Management
Includes components for document ingestion, duplicate tracking, ingestion history, and scheduled updates.

### 10. Web-Based User Interface
Provides a React-based interface for interacting with legal research and document analysis functionality.

---

## 🛠️ Technology Stack

| Component | Technologies |
|---|---|
| Frontend | React, JavaScript, Vite, CSS |
| Backend | Python, FastAPI |
| API Server | Uvicorn |
| PDF Processing | PyMuPDF |
| Embeddings | Sentence Transformers |
| Vector Search | FAISS |
| Keyword Retrieval | BM25 |
| Reranking | Cross-encoder reranking |
| AI Integration | Google Gemini API |
| Data Processing | Text extraction, chunking, metadata processing |
| Version Control | Git and GitHub |

The exact dependency versions are maintained in `requirements.txt` and `frontend/package-lock.json`.

---

## 🏗️ System Architecture

The application follows a frontend–backend architecture.

```text
                  USER
                   |
                   v
          React Frontend (Vite)
                   |
                   v
             FastAPI Backend
                   |
                   v
           Legal Research Pipeline
                   |
          +--------+---------+
          |                  |
          v                  v
   Semantic Retrieval   Keyword Retrieval
       (FAISS)              (BM25)
          |                  |
          +--------+---------+
                   |
                   v
             Hybrid Results
                   |
                   v
            Cross-Encoder
               Reranking
                   |
                   v
          Gemini-Assisted RAG
                   |
                   v
        Answer with Legal Sources
```

### Document Ingestion Pipeline

```text
Legal Judgment PDFs
        |
        v
   PDF Text Extraction
        |
        v
 Metadata Extraction
        |
        v
   Text Chunking
        |
        v
 Embedding Generation
        |
        v
     FAISS Index
        +
      BM25 Index
        |
        v
 Searchable Legal Knowledge Base
```

---

## 📁 Project Structure

```text
LegalAI/
│
├── app/
│   ├── api/
│   │   └── main.py
│   │
│   ├── documents/
│   │   ├── parser.py
│   │   ├── chunker.py
│   │   ├── case_metadata.py
│   │   ├── metadata_extractor.py
│   │   ├── ingestion_manager.py
│   │   ├── ingestion_tracker.py
│   │   └── scheduler.py
│   │
│   ├── embeddings/
│   │   ├── embeddings.py
│   │   └── vector_store.py
│   │
│   ├── ingestion/
│   │   ├── judgment_downloader.py
│   │   ├── import_local_pdfs.py
│   │   └── auto_update.py
│   │
│   └── rag/
│       ├── build_index.py
│       ├── multi_index.py
│       ├── hybrid_retriever.py
│       ├── reranker.py
│       ├── generator.py
│       ├── rag_pipeline.py
│       ├── case_search.py
│       ├── case_comparator.py
│       ├── case_analyzer.py
│       ├── citation_verifier.py
│       └── similar_judgments.py
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── index.css
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
│
├── data/                  # Local documents and indexes
├── .env                   # Local API credentials; never commit
├── .gitignore
├── requirements.txt
└── README.md
```

Some files and directories under `data/` are created during ingestion and indexing and may not exist in a fresh clone.

---

## 💻 Prerequisites

Install the following software before setting up the project:

- **Python 3.10.x** — the development environment uses Python 3.10.
- **Node.js and npm** — for the React frontend.
- **Git** — to clone the repository.
- **Google Gemini API key** — for AI functionality that uses Gemini.
- **VS Code** — recommended for development.

---

## 🚀 Installation and Setup

### Step 1: Clone the repository

Open Command Prompt or PowerShell and run:

```bash
git clone https://github.com/Nikhu2005/LegalMind-AI.git
cd LegalMind-AI
```

### Step 2: Create a Python virtual environment

On Windows:

```bash
py -3.10 -m venv .venv
```

Activate it in Command Prompt:

```cmd
.venv\Scripts\activate.bat
```

Or activate it in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

If activation is unavailable or blocked, use the virtual environment's Python executable directly.

### Step 3: Install Python dependencies

Upgrade pip:

```bash
python -m pip install --upgrade pip
```

Install the project dependencies:

```bash
pip install -r requirements.txt
```

If installation fails, check the error message and the dependency versions before changing packages.

### Step 4: Configure environment variables

Create a `.env` file in the project root.

Add the following template:

```dotenv
GEMINI_API_KEY=your_gemini_api_key_here
```

Replace the placeholder with your own valid API key. Use the variable name expected by the application's configuration code if it differs.

**Never commit `.env` or expose API credentials in source code.**

### Step 5: Install frontend dependencies

Open a new terminal:

```bash
cd frontend
npm install
```

This installs the packages defined in `frontend/package.json`.

### Step 6: Prepare the legal document index

The application requires the appropriate legal document data and search indexes to be available for retrieval features.

The repository may not include downloaded judgments or generated FAISS indexes. If the required indexes are absent, follow the project's ingestion and indexing workflow before testing search functionality.

Review the available scripts under:

- `app/ingestion/`
- `app/documents/`
- `app/rag/`

Use the indexing entry point and configuration defined in the current source code.

---

## ▶️ Running the Application

Run the backend and frontend in separate terminals.

### Terminal 1: Start the FastAPI backend

From the project root:

```bash
python -m uvicorn app.api.main:app --reload
```

The backend should be available at:

```text
http://127.0.0.1:8000
```

Open the interactive API documentation at:

```text
http://127.0.0.1:8000/docs
```

### Terminal 2: Start the React frontend

```bash
cd frontend
npm run dev
```

Vite will display the local frontend URL in the terminal, commonly:

```text
http://localhost:5173
```

Open the displayed URL in your browser.

> If the backend or frontend fails to start, check the terminal output, installed dependencies, environment variables, and whether the configured ports are already in use.

---

## 🔌 API Endpoints

The backend includes the following API routes in its current implementation.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Root endpoint |
| GET | `/health` | Health check |
| GET | `/cases` | Access case-related information |
| POST | `/search` | Search legal documents |
| POST | `/ask` | Ask a legal research question |
| POST | `/upload-current-case` | Upload and analyze a current case |
| POST | `/find-similar-judgments` | Find potentially similar judgments |

Open `http://127.0.0.1:8000/docs` to inspect request schemas, parameters, and response formats.

---

## 🔍 How It Works

### Legal Question Answering

1. The user submits a legal question.
2. The backend searches the indexed legal document collection.
3. Hybrid retrieval combines semantic and keyword-based results.
4. A reranking component refines the retrieved passages.
5. The RAG workflow uses relevant retrieved material to generate an answer.
6. The response can include supporting legal sources and metadata.

### Similar Judgment Discovery

1. The user uploads a current-case PDF.
2. The backend extracts the document text.
3. The case-analysis workflow identifies relevant facts, issues, Acts, sections, and legal concepts when available.
4. The search pipeline retrieves potentially related historical judgments.
5. Reranking helps prioritize relevant results.
6. The application returns candidate judgments for further review.

The uploaded current case is analyzed for retrieval; it is not automatically added to the historical judgment database by this workflow.

---

## 📚 Data and Index Setup

LegalMind AI uses local data and generated search indexes.

Depending on the indexing configuration, local data may include:

- Original judgment PDFs.
- Extracted text and metadata.
- Document chunks.
- FAISS vector indexes.
- BM25 retrieval data.
- Ingestion manifests and processing logs.
- Backups of generated indexes.

Generated indexes may need to be rebuilt when setting up the project on a new computer.

Only ingest documents from sources you are authorized to access and process. Follow the relevant website's terms of use and access policies.

---

## 🔐 Security

Follow these practices when running or contributing to LegalMind AI:

- Keep `.env` out of Git.
- Never hardcode API keys in Python or JavaScript files.
- Do not commit `.venv/`, `node_modules/`, or Python cache files.
- Avoid publishing private, confidential, or restricted legal documents.
- Keep dependencies updated and review security advisories.
- Rotate any API key accidentally exposed in a public repository.

---

## ⚠️ Limitations

- Search quality depends on the coverage and quality of the indexed documents.
- Metadata extraction may be incomplete for scanned or inconsistently formatted PDFs.
- AI-generated responses may contain errors or omit relevant legal authorities.
- Retrieval and reranking scores are relevance indicators, not probabilities of legal applicability.
- A similar judgment is not necessarily binding, controlling, or legally applicable.
- Current-case analysis depends on the quality of the uploaded document and the available indexed material.

---

## 🔮 Future Enhancements

Potential improvements include:

- Broader coverage of authorized Supreme Court and High Court judgments.
- Improved OCR support for scanned PDFs.
- More reliable citation verification.
- Better filtering by court, date, jurisdiction, Acts, and sections.
- Expanded evaluation of retrieval accuracy and answer grounding.
- User authentication and secure document management.
- Deployment with production-grade logging, monitoring, and access controls.

These are possible enhancements, not claims that all of these capabilities are already implemented.

---

## ⚖️ Disclaimer

LegalMind AI is an educational and research-oriented legal technology project. It is intended to assist with legal information retrieval and document analysis.

It does not replace a qualified lawyer, professional legal advice, independent verification of legal authorities, or review of the applicable law.

Always verify judgments, citations, statutes, amendments, and legal interpretations against authoritative sources before relying on them.

---

## 👨‍💻 Author and Repository

**Project:** LegalMind AI  
**GitHub:** https://github.com/Nikhu2005/LegalMind-AI

Contributions, bug reports, and suggestions for improvement are welcome.
