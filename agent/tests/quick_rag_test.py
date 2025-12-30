"""Quick RAG test"""
import asyncio
from database import get_db_pool
from database.rag import EmbeddingService, RAGIndexer, RAGService
from pathlib import Path

async def test():
    print('Connecting to database...')
    pool = await get_db_pool()
    print('Database connected!')
    
    print('Initializing embedding service...')
    emb = EmbeddingService()
    await emb.initialize()
    print(f'Embedding service ready (dim={emb.dimension})')
    
    print('Creating indexer...')
    docs_path = Path(__file__).parent / 'docs'
    indexer = RAGIndexer(
        docs_path=str(docs_path),
        db_pool=pool,
        embedding_service=emb,
        chunk_size=1000,
        chunk_overlap=200
    )
    
    print(f'Indexing documents from {docs_path}...')
    await indexer.index_directory()
    print('Indexing complete!')
    
    # Check what was indexed
    count = await pool.fetchval('SELECT COUNT(*) FROM rag_documents')
    print(f'Total chunks in database: {count}')
    
    files = await pool.fetch('SELECT DISTINCT filename FROM rag_documents')
    for f in files:
        print(f'  - {f["filename"]}')
    
    # Test search
    print('\nTesting search...')
    results = await indexer.search('bank opening hours', limit=3)
    print(f'Search results: {len(results)}')
    for r in results:
        print(f'  File: {r["filename"]} - {r["content"][:80]}...')

if __name__ == '__main__':
    asyncio.run(test())
