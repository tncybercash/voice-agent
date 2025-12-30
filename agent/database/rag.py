"""
RAG (Retrieval-Augmented Generation) service for document indexing and retrieval.
Monitors the docs folder and automatically indexes new/updated files.
Supports advanced document parsing with Docling (PDF, DOCX, PPTX, HTML, tables, OCR).
"""
import os
import logging
import asyncio
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import aiofiles
import aiofiles.os

try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    logging.warning("Docling not available. Advanced document parsing disabled.")

logger = logging.getLogger("rag")


class TextChunker:
    """Split text into chunks for embedding"""
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separator: str = "\n\n"
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator
    
    def split(self, text: str) -> List[str]:
        """Split text into overlapping chunks"""
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        
        # Try to split by separator first
        paragraphs = text.split(self.separator)
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) + len(self.separator) <= self.chunk_size:
                if current_chunk:
                    current_chunk += self.separator + para
                else:
                    current_chunk = para
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # If paragraph is too long, split it further
                if len(para) > self.chunk_size:
                    words = para.split()
                    current_chunk = ""
                    for word in words:
                        if len(current_chunk) + len(word) + 1 <= self.chunk_size:
                            current_chunk = current_chunk + " " + word if current_chunk else word
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = word
                else:
                    current_chunk = para
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # Add overlap between chunks
        if self.chunk_overlap > 0 and len(chunks) > 1:
            overlapped_chunks = [chunks[0]]
            for i in range(1, len(chunks)):
                prev_chunk = chunks[i-1]
                overlap = prev_chunk[-self.chunk_overlap:] if len(prev_chunk) > self.chunk_overlap else prev_chunk
                overlapped_chunks.append(overlap + " " + chunks[i])
            chunks = overlapped_chunks
        
        return chunks


class EmbeddingService:
    """Generate embeddings for text using various providers"""
    
    def __init__(self, provider: str = "ollama", model: str = None, ollama_url: str = "http://localhost:11434"):
        self.provider = provider
        self.model_name = model or "nomic-embed-text:latest"
        self.ollama_url = ollama_url
        self._model = None
        self._dimension = 768  # Default for nomic-embed-text
    
    async def initialize(self):
        """Initialize the embedding model"""
        if self._model is not None:
            return
        
        if self.provider == "ollama":
            # Use Ollama for embeddings
            import httpx
            self._model = httpx.AsyncClient(timeout=30.0)
            # Test connection and get dimension
            try:
                response = await self._model.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={"model": self.model_name, "prompt": "test"}
                )
                if response.status_code == 200:
                    test_embedding = response.json()["embedding"]
                    self._dimension = len(test_embedding)
                    logger.info(f"Loaded Ollama embedding model: {self.model_name} (dim={self._dimension})")
                else:
                    raise ValueError(f"Ollama embedding test failed: {response.text}")
            except Exception as e:
                logger.error(f"Failed to initialize Ollama embeddings: {e}")
                raise
        elif self.provider == "sentence-transformers":
            # Load sentence-transformers model
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
            logger.info(f"Loaded embedding model: {self.model_name} (dim={self._dimension})")
        elif self.provider == "openai":
            # OpenAI embeddings - dimension is 1536 for text-embedding-ada-002
            self._dimension = 1536
            logger.info(f"Using OpenAI embeddings (dim={self._dimension})")
        else:
            raise ValueError(f"Unknown embedding provider: {self.provider}")
    
    @property
    def dimension(self) -> int:
        return self._dimension
    
    async def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        await self.initialize()
        
        if self.provider == "ollama":
            # Use Ollama embeddings API
            response = await self._model.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": self.model_name, "prompt": text}
            )
            if response.status_code == 200:
                return response.json()["embedding"]
            else:
                raise ValueError(f"Ollama embedding failed: {response.text}")
        elif self.provider == "sentence-transformers":
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, 
                lambda: self._model.encode(text, convert_to_numpy=True).tolist()
            )
            return embedding
        elif self.provider == "openai":
            import openai
            client = openai.AsyncOpenAI()
            response = await client.embeddings.create(
                model=self.model_name or "text-embedding-ada-002",
                input=text
            )
            return response.data[0].embedding
        
        return []
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        await self.initialize()
        
        if self.provider == "ollama":
            # Ollama API doesn't have batch endpoint, process sequentially
            embeddings = []
            for text in texts:
                response = await self._model.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={"model": self.model_name, "prompt": text}
                )
                if response.status_code == 200:
                    embeddings.append(response.json()["embedding"])
                else:
                    raise ValueError(f"Ollama embedding failed: {response.text}")
            return embeddings
        elif self.provider == "sentence-transformers":
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: self._model.encode(texts, convert_to_numpy=True).tolist()
            )
            return embeddings
        elif self.provider == "openai":
            import openai
            client = openai.AsyncOpenAI()
            response = await client.embeddings.create(
                model=self.model_name or "text-embedding-ada-002",
                input=texts
            )
            return [item.embedding for item in response.data]
        
        return []


class RAGIndexer:
    """
    Document indexer for RAG system.
    Monitors docs folder and indexes files for semantic search.
    Supports advanced parsing for PDF, DOCX, PPTX, HTML via Docling.
    """
    
    # Basic text files
    BASIC_TEXT_EXTENSIONS = {'.txt', '.md', '.py', '.json', '.csv', '.log'}
    
    # Advanced document formats (requires Docling)
    DOCLING_EXTENSIONS = {'.pdf', '.docx', '.pptx', '.html', '.htm', '.xlsx'}
    
    @property
    def SUPPORTED_EXTENSIONS(self):
        """Return all supported extensions based on available parsers"""
        if DOCLING_AVAILABLE:
            return self.BASIC_TEXT_EXTENSIONS | self.DOCLING_EXTENSIONS
        return self.BASIC_TEXT_EXTENSIONS
    
    def __init__(
        self,
        docs_path: str,
        db_pool,  # DatabasePool
        embedding_service: EmbeddingService = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        self.docs_path = Path(docs_path)
        self.db_pool = db_pool
        self.embedding_service = embedding_service or EmbeddingService()
        self.chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self._file_hashes: Dict[str, str] = {}
        self._running = False
        self._docling_converter = None
        
        # Initialize Docling converter if available
        if DOCLING_AVAILABLE:
            self._docling_converter = DocumentConverter()
            logger.info("Docling document converter initialized")
    
    async def _calculate_file_hash(self, filepath: Path) -> str:
        """Calculate MD5 hash of file for change detection"""
        async with aiofiles.open(filepath, 'rb') as f:
            content = await f.read()
            return hashlib.md5(content).hexdigest()
    
    async def _read_file(self, filepath: Path) -> str:
        """Read file content"""
        async with aiofiles.open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return await f.read()
    
    async def _parse_with_docling(self, filepath: Path) -> Optional[str]:
        """Parse document using Docling for advanced extraction"""
        if not DOCLING_AVAILABLE or not self._docling_converter:
            return None
        
        try:
            loop = asyncio.get_event_loop()
            # Run Docling conversion in thread pool to avoid blocking
            result = await loop.run_in_executor(
                None,
                lambda: self._docling_converter.convert(str(filepath))
            )
            
            # Extract text content from document
            content_parts = []
            
            # Get main text content
            if hasattr(result, 'document'):
                doc = result.document
                
                # Extract text from all elements
                if hasattr(doc, 'texts'):
                    for text_elem in doc.texts:
                        if hasattr(text_elem, 'text'):
                            content_parts.append(text_elem.text)
                
                # Extract tables (Docling preserves table structure)
                if hasattr(doc, 'tables'):
                    for table in doc.tables:
                        if hasattr(table, 'export_to_markdown'):
                            content_parts.append(table.export_to_markdown())
                        elif hasattr(table, 'data'):
                            content_parts.append(str(table.data))
                
                # Extract metadata if available
                metadata = {}
                if hasattr(doc, 'title'):
                    metadata['title'] = doc.title
                if hasattr(doc, 'authors'):
                    metadata['authors'] = doc.authors
                
                content = "\n\n".join(content_parts)
                
                # Add metadata as header
                if metadata:
                    header = "\n".join([f"{k}: {v}" for k, v in metadata.items()])
                    content = f"{header}\n\n{content}"
                
                logger.info(f"Docling parsed {filepath.name}: {len(content)} chars, {len(content_parts)} sections")
                return content
            
            return None
            
        except Exception as e:
            logger.warning(f"Docling parsing failed for {filepath.name}: {e}")
            return None
    
    async def index_file(self, filepath: Path) -> int:
        """Index a single file into the database"""
        from .repository import RAGDocumentRepository
        
        if filepath.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            logger.debug(f"Skipping unsupported file: {filepath}")
            return 0
        
        try:
            # Calculate hash for change detection
            file_hash = await self._calculate_file_hash(filepath)
            filename = filepath.name
            
            # Check database for existing file with same hash
            repo = RAGDocumentRepository(self.db_pool)
            existing = await repo.get_by_filename(filename)
            
            if existing:
                # Check if file hash matches any existing chunk metadata
                existing_hash = existing[0].metadata.get('file_hash') if existing[0].metadata else None
                if existing_hash == file_hash:
                    logger.debug(f"File unchanged (hash match), skipping: {filename}")
                    self._file_hashes[filename] = file_hash
                    return len(existing)  # Return number of existing chunks
            
            # File is new or changed, proceed with indexing
            # Determine parsing method based on file type
            file_ext = filepath.suffix.lower()
            
            # Try Docling for advanced formats
            if file_ext in self.DOCLING_EXTENSIONS and DOCLING_AVAILABLE:
                content = await self._parse_with_docling(filepath)
                if content is None:
                    logger.warning(f"Docling parsing failed, skipping: {filepath}")
                    return 0
            else:
                # Use basic text reading for simple formats
                content = await self._read_file(filepath)
            
            if not content.strip():
                logger.debug(f"Skipping empty file: {filepath}")
                return 0
            
            # Split into chunks
            chunks = self.chunker.split(content)
            total_chunks = len(chunks)
            
            # Generate embeddings for all chunks
            embeddings = await self.embedding_service.embed_batch(chunks)
            
            # Delete old chunks first (if file was updated)
            if existing:
                await repo.delete_by_filename(filename)
                logger.info(f"Updating {filename} (hash changed)")
            
            # Insert new chunks
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                await repo.upsert_document(
                    filename=filename,
                    content=chunk,
                    chunk_index=i,
                    total_chunks=total_chunks,
                    embedding=embedding,
                    metadata={
                        "filepath": str(filepath),
                        "indexed_at": datetime.utcnow().isoformat(),
                        "file_hash": file_hash
                    }
                )
            
            self._file_hashes[filename] = file_hash
            logger.info(f"Indexed {filename}: {total_chunks} chunks")
            return total_chunks
            
        except Exception as e:
            logger.error(f"Failed to index {filepath}: {e}")
            return 0
    
    async def index_directory(self) -> Dict[str, int]:
        """Index all supported files in the docs directory"""
        results = {}
        
        if not self.docs_path.exists():
            logger.warning(f"Docs path does not exist: {self.docs_path}")
            return results
        
        for filepath in self.docs_path.iterdir():
            if filepath.is_file():
                # Skip Word temp files (start with ~$)
                if filepath.name.startswith('~$'):
                    continue
                chunks = await self.index_file(filepath)
                if chunks > 0:
                    results[filepath.name] = chunks
        
        logger.info(f"Indexed {len(results)} files with total chunks: {sum(results.values())}")
        return results
    
    async def search(
        self,
        query: str,
        limit: int = 5,
        similarity_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search: combines semantic similarity with keyword matching.
        Keyword matches get a boost to ensure relevant content ranks higher.
        """
        from .repository import RAGDocumentRepository
        
        # Generate query embedding
        query_embedding = await self.embedding_service.embed(query)
        
        # Search in database - now returns dicts with similarity included
        repo = RAGDocumentRepository(self.db_pool)
        results = await repo.search_similar(
            query_embedding=query_embedding,
            limit=limit * 2,  # Get more results for re-ranking
            similarity_threshold=similarity_threshold
        )
        
        # Extract keywords from query for hybrid scoring
        # Remove common question words and focus on meaningful terms
        query_lower = query.lower()
        stop_words = {'what', 'is', 'the', 'are', 'how', 'do', 'can', 'your', 'my', 'a', 'an', 'to', 'of', 'for', 'and', 'or', 'in'}
        keywords = [word for word in query_lower.split() if len(word) > 2 and word not in stop_words]
        
        # Re-rank with keyword boost
        for result in results:
            content_lower = result['content'].lower()
            base_similarity = result.get('similarity', 0.0)
            
            # Keyword boost: stronger weight for exact matches
            keyword_boost = 0.0
            for keyword in keywords:
                if keyword in content_lower:
                    # Higher boost for important terms
                    keyword_boost += 0.25
            
            # Cap the boost at 0.7
            keyword_boost = min(keyword_boost, 0.7)
            
            # Combined score (weighted)
            result['base_similarity'] = base_similarity
            result['keyword_boost'] = keyword_boost
            result['similarity'] = base_similarity + keyword_boost
        
        # Sort by combined similarity score
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Return top results
        return [
            {
                "filename": result['filename'],
                "content": result['content'],
                "chunk_index": result['chunk_index'],
                "metadata": result['metadata'],
                "similarity": result.get('similarity', 0.0)
            }
            for result in results[:limit]
        ]
    
    async def watch_directory(self, interval: int = 30):
        """Watch directory for changes and re-index"""
        self._running = True
        logger.info(f"Starting directory watcher for {self.docs_path}")
        
        while self._running:
            try:
                await self.index_directory()
            except Exception as e:
                logger.error(f"Error during directory watch: {e}")
            
            await asyncio.sleep(interval)
    
    def stop_watching(self):
        """Stop the directory watcher"""
        self._running = False


class RAGService:
    """High-level RAG service for the agent"""
    
    def __init__(self, indexer: RAGIndexer):
        self.indexer = indexer
    
    async def get_context(self, query: str, max_tokens: int = 2000) -> str:
        """Get relevant context for a query"""
        # Use very low threshold to ensure results are returned
        # Similarity values: 1.0 = perfect match, 0.0 = no similarity, -1.0 = opposite
        logger.info(f"RAG searching for: '{query}'")
        results = await self.indexer.search(query, limit=5, similarity_threshold=-1.0)  # Get all results
        
        if not results:
            logger.info(f"❌ No RAG results found for query: '{query}'")
            return ""
        
        logger.info(f"✓ Found {len(results)} RAG results:")
        for idx, result in enumerate(results, 1):
            similarity = result.get('similarity', 0)
            filename = result.get('filename', 'unknown')
            content_preview = result.get('content', '')[:100]
            logger.info(f"  {idx}. [{filename}] similarity={similarity:.4f} - {content_preview}...")
        
        # Build context string - only use results with reasonable similarity
        context_parts = []
        total_chars = 0
        
        for result in results:
            content = result.get('content', '')
            if not content:
                continue
            if total_chars + len(content) > max_tokens * 4:  # Rough char estimate
                break
            similarity = result.get('similarity', 0)
            context_parts.append(f"[From {result['filename']} (relevance: {similarity:.2f})]:\n{content}")
            total_chars += len(content)
        
        context = "\n\n---\n\n".join(context_parts)
        logger.info(f"✓ Built context string: {len(context)} chars from {len(context_parts)} chunks")
        return context
    
    async def augment_prompt(self, user_query: str, base_instructions: str) -> str:
        """Augment the agent instructions with relevant context"""
        context = await self.get_context(user_query)
        
        if context:
            return f"""{base_instructions}

#CRITICAL: Knowledge Base Context (USE THIS INFORMATION)
The user asked: "{user_query}"

You MUST use the following verified information from TN CyberTech Bank's official knowledge base to answer. DO NOT make up information - use ONLY what is provided below:

---BEGIN KNOWLEDGE BASE---
{context}
---END KNOWLEDGE BASE---

IMPORTANT RULES:
1. Answer ONLY using the information from the knowledge base above
2. If the knowledge base contains the answer, use it EXACTLY as stated
3. DO NOT invent or guess information not in the knowledge base
4. If the knowledge base doesn't contain the answer, say you'll need to check and get back to them
5. Quote specific details (like codes, numbers, hours) exactly as they appear in the knowledge base
"""
        
        return base_instructions
