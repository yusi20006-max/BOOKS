CREATE TABLE IF NOT EXISTS knowledge_nodes (
 id TEXT PRIMARY KEY,
 label TEXT NOT NULL,
 kind TEXT NOT NULL DEFAULT 'concept'
);
CREATE TABLE IF NOT EXISTS knowledge_edges (
 source_id TEXT NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
 target_id TEXT NOT NULL,
 relation TEXT NOT NULL,
 PRIMARY KEY(source_id,target_id,relation)
);
CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_label ON knowledge_nodes(label);
CREATE INDEX IF NOT EXISTS idx_knowledge_edges_source ON knowledge_edges(source_id);
