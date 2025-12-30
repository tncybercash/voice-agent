# Test Files

This folder contains various test and debugging scripts used during development.

## RAG Testing
- `test_rag.py` - Basic RAG functionality test
- `test_full_rag.py` - Complete RAG pipeline test
- `test_agent_rag.py` - Agent RAG integration test
- `test_agent_rag_flow.py` - Simulates exact agent RAG flow
- `test_context_modification.py` - Tests chat context modification for RAG
- `debug_rag.py` - RAG debugging utilities
- `quick_rag_test.py` - Quick RAG functionality check
- `quick_check.py` - Quick system check

## Database & Embeddings
- `check_dimensions.py` - Verify embedding dimensions in database
- `migrate_embeddings.py` - Migrate embeddings to new dimensions (384→768)
- `reindex_rag.py` - Reindex RAG documents

## Chunk Analysis
- `analyze_chunks.py` - Analyze document chunks
- `check_chunk11.py` - Verify specific chunk content
- `find_ussd.py` - Search for USSD code in chunks

## Agent Testing
- `test_hook_called.py` - Test LiveKit agent hook behavior
- `check_instructions.py` - Verify agent instructions
- `check_full_instructions.py` - Check complete instruction set

## Usage

Run tests from the parent directory:
```bash
cd ..
python tests/test_full_rag.py
```

Or with proper environment:
```bash
cd ..
python -m tests.test_full_rag
```
