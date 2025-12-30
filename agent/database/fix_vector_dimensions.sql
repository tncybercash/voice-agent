-- Fix vector dimension mismatch
-- Changes rag_documents.embedding from vector(384) to vector(768)
-- Run this to fix the "expected 384 dimensions, not 768" error

-- Drop existing index (required before altering column type)
DROP INDEX IF EXISTS idx_rag_embedding;

-- Clear existing data (dimension mismatch makes it unusable anyway)
TRUNCATE TABLE rag_documents;

-- Change vector column from 384 to 768 dimensions
ALTER TABLE rag_documents 
ALTER COLUMN embedding TYPE vector(768);

-- Recreate index with new dimensions
CREATE INDEX idx_rag_embedding ON rag_documents 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Verify the change
SELECT 
    column_name, 
    data_type, 
    udt_name 
FROM information_schema.columns 
WHERE table_name = 'rag_documents' 
AND column_name = 'embedding';

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✓ Vector dimensions updated from 384 to 768';
    RAISE NOTICE '✓ Index recreated';
    RAISE NOTICE '✓ Ready to index documents with nomic-embed-text:latest';
END $$;
