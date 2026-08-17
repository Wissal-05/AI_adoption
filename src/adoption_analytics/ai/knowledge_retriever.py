import os
import re
import math
import json
from collections import Counter
from typing import List, Dict, Any

class KnowledgeRetriever:
    """Retriever minimaliste basé sur BM25.
    
    Cette variante minimale a été choisie car ChromaDB et Sentence Transformers
    ne sont pas installés dans le projet, afin de garder l'implémentation
    légère, locale et sans polluer les dépendances avec des frameworks lourds
    pour un si petit corpus documentaire.
    """
    def __init__(self, docs_dir: str = "docs/knowledge"):
        self.docs_dir = docs_dir
        self.index_path = os.path.join("data", "rag", "index.json")
        self.documents = []
        self.idf = {}
        self.doc_len = []
        self.avgdl = 0
        self.k1 = 1.5
        self.b = 0.75
        
    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        return re.findall(r'\b[a-z0-9àáâäçèéêëìíîïñòóôöùúûü]+\b', text)
        
    def build_index(self) -> None:
        """Construit l'index documentaire de façon idempotente."""
        self.documents = []
        
        if not os.path.exists(self.docs_dir):
            return
            
        for filename in os.listdir(self.docs_dir):
            if not filename.endswith(".md"):
                continue
            path = os.path.join(self.docs_dir, filename)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Simple chunking by Markdown sections (H2)
            sections = content.split("\n## ")
            
            for i, sec in enumerate(sections):
                if i == 0:
                    continue  # Ignore prologue/H1
                    
                lines = sec.split("\n", 1)
                section_title = lines[0].strip()
                chunk_content = lines[1].strip() if len(lines) > 1 else ""
                
                if chunk_content:
                    self.documents.append({
                        "content": chunk_content,
                        "source": filename,
                        "section": section_title,
                        "chunk_id": f"{filename}-{i}"
                    })
                    
        # Build BM25 index
        df = Counter()
        self.doc_len = []
        for doc in self.documents:
            tokens = self._tokenize(doc["content"] + " " + doc["section"])
            self.doc_len.append(len(tokens))
            for term in set(tokens):
                df[term] += 1
                
        num_docs = len(self.documents)
        self.avgdl = sum(self.doc_len) / num_docs if num_docs > 0 else 1
        
        self.idf = {}
        for term, freq in df.items():
            self.idf[term] = math.log(1 + (num_docs - freq + 0.5) / (freq + 0.5))
            
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        
        # Save index to disk
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump({
                "documents": self.documents,
                "idf": self.idf,
                "doc_len": self.doc_len,
                "avgdl": self.avgdl
            }, f, ensure_ascii=False, indent=2)

    def _load_index(self):
        if not os.path.exists(self.index_path):
            self.build_index()
        else:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.documents = data["documents"]
                self.idf = data["idf"]
                self.doc_len = data["doc_len"]
                self.avgdl = data["avgdl"]

    def search(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """Recherche les documents les plus pertinents pour une requête."""
        self._load_index()
        tokens = self._tokenize(query)
        scores = []
        
        for idx, doc in enumerate(self.documents):
            # Le titre de section a plus de poids car on l'ajoute au contenu tokenisé
            doc_tokens = self._tokenize(doc["content"] + " " + doc["section"] + " " + doc["section"])
            doc_freqs = Counter(doc_tokens)
            score = 0
            for term in tokens:
                if term in self.idf:
                    freq = doc_freqs[term]
                    num = freq * (self.k1 + 1)
                    den = freq + self.k1 * (1 - self.b + self.b * self.doc_len[idx] / self.avgdl)
                    score += self.idf[term] * (num / den)
            scores.append((score, doc))
            
        scores.sort(key=lambda x: x[0], reverse=True)
        
        results = []
        for score, doc in scores[:top_k]:
            if score > 0:
                res = dict(doc)
                res["score"] = score
                results.append(res)
                
        return results
