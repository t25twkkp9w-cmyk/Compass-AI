"""Real Qdrant dense search + BM25 + RRF, with explicit local/live embedding spaces."""
import hashlib
import math
import os
import re
import uuid
from collections import defaultdict

from langchain_core.embeddings import Embeddings
from qdrant_client import QdrantClient, models
from rank_bm25 import BM25Okapi

from .schemas import Evidence

SYNONYMS = {"approved":"approve", "approval":"approve", "allowed":"permit", "permitted":"permit", "permission":"permit",
    "emails":"email", "identifiers":"identifier", "confidentiality":"confidential", "uploading":"upload", "uploaded":"upload",
    "customers":"customer", "reviews":"review", "reviewers":"review", "models":"model", "tools":"tool", "deployments":"deployment"}
STOP = {"the","a","an","can","i","we","our","is","are","to","of","and","for","in","it","this","that","with","do","does"}

def tokens(text):
    return [SYNONYMS.get(t,t) for t in re.findall(r"[a-z0-9]+(?:[-_.][a-z0-9]+)*", text.lower()) if t not in STOP]

class LocalHashEmbeddings(Embeddings):
    """Deterministic lexical feature vectors, NOT a learned semantic embedding model."""
    dimensions = 384
    def embed_query(self, text):
        vec = [0.0] * self.dimensions
        for token in tokens(text):
            value = hashlib.sha256(token.encode()).digest()
            vec[int.from_bytes(value[:4],"big") % self.dimensions] += 1.0 if value[4] % 2 else -1.0
        norm = math.sqrt(sum(v*v for v in vec)) or 1
        return [v/norm for v in vec]
    def embed_documents(self, texts): return [self.embed_query(t) for t in texts]

class Retriever:
    def __init__(self, settings, corpus):
        self.settings, self.corpus = settings, corpus
        if settings.mode == "live":
            if not os.getenv("OPENAI_API_KEY"): raise ValueError("Live mode requires OPENAI_API_KEY. Local mode does not call a model.")
            from langchain_openai import OpenAIEmbeddings
            self.embeddings = OpenAIEmbeddings(model=settings.embedding_model, dimensions=1536, max_retries=1, request_timeout=25)
            self.embedding_name = settings.embedding_model
            dimensions = 1536
        else:
            self.embeddings = LocalHashEmbeddings(); self.embedding_name = "local-lexical-hash-v1"; dimensions = 384
        self.collection = "compass_" + hashlib.sha256((self.embedding_name + corpus.manifest).encode()).hexdigest()[:20]
        self.client = QdrantClient(url=settings.qdrant_url, api_key=os.getenv("QDRANT_API_KEY") or None, timeout=20) if settings.qdrant_url else QdrantClient(path=str(settings.runtime / "qdrant"))
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(self.collection, vectors_config=models.VectorParams(size=dimensions, distance=models.Distance.COSINE))
        if self.client.count(self.collection, exact=True).count != len(corpus.chunks):
            vectors = self.embeddings.embed_documents([d.page_content for d in corpus.chunks])
            self.client.upsert(self.collection, points=[models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL,d.metadata["chunk_id"])),
                vector=v, payload={**d.metadata, "text":d.page_content}) for d,v in zip(corpus.chunks,vectors)], wait=True)
        self.lexical_tokens = [tokens(d.page_content) for d in corpus.chunks]
        self.bm25 = BM25Okapi(self.lexical_tokens)

    def search(self, question, strategy="hybrid", top_k=5):
        if strategy not in {"hybrid","dense","bm25"}: raise ValueError("Unknown retrieval strategy")
        # All active knowledge units are employee-visible. Operational case records never enter this index.
        scope = models.Filter(must=[models.FieldCondition(key="tenant",match=models.MatchValue(value="northstar")),
            models.FieldCondition(key="status",match=models.MatchValue(value="published")),
            models.FieldCondition(key="visibility",match=models.MatchValue(value="employees")),
            models.FieldCondition(key="manifest",match=models.MatchValue(value=self.corpus.manifest))])
        dense=[]
        if strategy in {"hybrid","dense"}:
            points = self.client.query_points(collection_name=self.collection, query=self.embeddings.embed_query(question), query_filter=scope, limit=8).points
            dense=[p.payload["chunk_id"] for p in points if p.score>0]
        lexical=[]
        if strategy in {"hybrid","bm25"}:
            scores=self.bm25.get_scores(tokens(question))
            lexical=[self.corpus.chunks[i].metadata["chunk_id"] for i in sorted(range(len(scores)),key=lambda i:scores[i],reverse=True)[:8] if scores[i]>0]
        fused=defaultdict(float)
        for ranking in [dense,lexical]:
            for rank,cid in enumerate(ranking,1):fused[cid]+=1/(60+rank)
        by_chunk={d.metadata["chunk_id"]:d for d in self.corpus.chunks}
        ordered=sorted(fused,key=fused.get,reverse=True)
        # Optional BGE is an explicit configuration, never a hidden provider fallback.
        if os.getenv("COMPASS_RERANKER", "off") == "bge" and ordered:
            from FlagEmbedding import FlagReranker
            model_path=os.getenv("COMPASS_BGE_RERANKER_PATH")
            if not model_path:raise ValueError("Set COMPASS_BGE_RERANKER_PATH to a pinned local model checkout.")
            if not hasattr(self,"reranker"):self.reranker=FlagReranker(model_path,use_fp16=False)
            scores=self.reranker.compute_score([[question,by_chunk[c].page_content] for c in ordered],normalize=True)
            if not isinstance(scores,list):scores=[scores]
            ordered=[cid for _,cid in sorted(zip(scores,ordered),reverse=True)]
        results=[];seen=set()
        for cid in ordered:
            chunk=by_chunk[cid];parent_id=chunk.metadata["parent_id"]
            if parent_id in seen:continue
            seen.add(parent_id);parent=self.corpus.by_id[parent_id]
            results.append(Evidence(citation_id=parent_id,source_id=parent.metadata["source_id"],title=parent.metadata["title"],text=parent.page_content,
                score=fused[cid],kind=parent.metadata["kind"],metadata={**parent.metadata,"retrieval_stage":"parent expansion"}))
            if len(results)>=top_k:break
        return results, {"strategy":strategy,"dense_ids":dense,"lexical_ids":lexical,"fused_candidates":len(ordered),"embedding":self.embedding_name,"collection":self.collection,"reranker":os.getenv("COMPASS_RERANKER","off")}

    def expand(self, evidence, max_total=10):
        expanded=list(evidence);seen={e.citation_id for e in evidence}
        for item in list(evidence):
            for sid,section in re.findall(r"\b(POL-001|STD-003|PROC-004|RSK-006|ENG-007|AUTH-009)\s+(S\d{2})",item.text):
                cid=f"{sid}@3.0:{section}";d=self.corpus.reference(cid)
                if d and cid not in seen and len(expanded)<max_total:
                    expanded.append(Evidence(citation_id=cid,source_id=sid,title=d.metadata["title"],text=d.page_content,metadata={**d.metadata,"retrieval_stage":"cross-reference expansion"}));seen.add(cid)
        return expanded

    def close(self): self.client.close()
