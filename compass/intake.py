"""Build unpublished candidate indexes; the active policy snapshot is never overwritten."""
import hashlib
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import models
from .corpus import approximate_tokens
from .schemas import DomainError

SOURCE_IDS={1:'POL-001',2:'REG-002',3:'STD-003',4:'PROC-004',5:'FAQ-005',6:'RSK-006',7:'ENG-007',9:'AUTH-009'}

class IntakeService:
    def __init__(self,corpus,repository,retriever):self.corpus,self.repository,self.retriever=corpus,repository,retriever

    def _validate(self,name,content,number):
        units=self.corpus.preview(name,content,number)
        if number!=2:
            if any(u.metadata['source_id']!=SOURCE_IDS[number] for u in units):raise DomainError('Source identifier does not match the selected source number.')
            if len({u.metadata['citation_id'] for u in units})!=len(units):raise DomainError('Duplicate section identifiers.')
        else:
            payload=json.loads(content)
            tools={r['tool_id'] for r in payload['tools']};model_ids={r['model_version_id'] for r in payload['models']}
            deployments=payload['deployments']
            for kind,key in [('tools','tool_id'),('models','model_version_id'),('deployments','deployment_id')]:
                if len({r[key] for r in payload[kind]})!=len(payload[kind]):raise DomainError('Duplicate catalog identifiers.')
            for dep in deployments:
                if dep['tool_id'] not in tools or not set(dep['model_version_ids'])<=model_ids:raise DomainError('Deployment references an unknown tool or model version.')
                if dep['status'] not in {'Approved','Pilot only','Under review','Blocked','Revoked','Expired'}:raise DomainError('Unknown deployment status.')
        return {'validated_units':len(units),'source_id':SOURCE_IDS[number],'schema':'stable section IDs and catalog referential integrity'}

    def _index(self,name,content,number,upload_id):
        units=self.corpus.preview(name,content,number)
        splitter=RecursiveCharacterTextSplitter(chunk_size=600,chunk_overlap=60,length_function=approximate_tokens)
        chunks=splitter.split_documents(units)
        vectors=self.retriever.embeddings.embed_documents([u.page_content for u in chunks])
        collection='candidate_'+upload_id.lower().replace('-','_')
        self.retriever.client.create_collection(collection,vectors_config=models.VectorParams(size=len(vectors[0]),distance=models.Distance.COSINE))
        points=[]
        for i,(chunk,vector) in enumerate(zip(chunks,vectors)):
            points.append(models.PointStruct(id=str(uuid.uuid4()),vector=vector,payload={**chunk.metadata,'text':chunk.page_content,'status':'candidate','manifest':upload_id,'tenant':'northstar','upload_id':upload_id}))
        self.retriever.client.upsert(collection,points=points,wait=True)
        return {'candidate_collection':collection,'chunk_count':len(chunks),'embedding':self.retriever.embedding_name}

    def prepare(self,principal,name,content,number):
        upload_id=self.repository.stage_upload(principal,name,content,number)
        # Both branches consume the same staged bytes. Neither can activate a policy.
        with ThreadPoolExecutor(max_workers=2) as pool:
            validation=pool.submit(self._validate,name,content,number)
            index=pool.submit(self._index,name,content,number,upload_id)
            try:report={**validation.result(),**index.result()};status='Candidate ready; not published'
            except Exception as exc:
                # Candidate points remain unreachable from published retrieval even on partial failure.
                report={'error_type':type(exc).__name__};status='Validation/indexing failed; not published'
        with self.repository.engine.begin() as connection:
            item=self.repository._get(connection,'uploads',upload_id)
            item.update(status=status,report=report)
            self.repository._replace(connection,'uploads',upload_id,item)
        return {'upload_id':upload_id,'status':status,**report}
