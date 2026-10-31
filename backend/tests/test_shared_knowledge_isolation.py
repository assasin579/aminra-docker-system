"""Real in-memory vector search must exclude private and unclassified legacy chunks."""
import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from pipeline import query

def test_every_search_branch_requires_explicit_public_reference(monkeypatch):
    client=QdrantClient(':memory:')
    client.create_collection(query.COLLECTION_NAME,vectors_config=VectorParams(size=2,distance=Distance.COSINE))
    client.upsert(query.COLLECTION_NAME,[PointStruct(id=i,vector=[1.0,0.0],payload={'text':name,'slide_title':'synthetic scope','source_file':name+'.pdf',**extra}) for i,name,extra in [(1,'private-a',{}),(2,'private-b',{'public_reference':False}),(3,'public-standard',{'public_reference':True})]])
    monkeypatch.setattr('qdrant_client.QdrantClient',lambda **kw:client)
    original_query = client.query_points
    filters=[]
    def audited_query(**kwargs):
        filters.append(kwargs['query_filter'])
        return original_query(**kwargs)
    monkeypatch.setattr(client,'query_points',audited_query)
    data={'vector':[1.0,0.0],'enhanced':{'original':'synthetic scope','expanded':['synthetic scope'],'type':'general','strategy':{'boost_title':1.0,'min_score':0.0}}}
    results=query.hybrid_search(data,top_k=10)
    assert [r['text'] for r in results]==['public-standard']
    assert all(r['payload']['public_reference'] is True for r in results)
    data['enhanced']['expanded']=['unmatched-keyword']
    assert [r['text'] for r in query.hybrid_search(data,top_k=10)]==['public-standard']
    assert len(filters)>=4
    assert all(any(getattr(condition,'key',None)=='public_reference' and condition.match.value is True for condition in f.must) for f in filters)
    client.close()


def test_ingestion_default_is_not_shared_and_only_explicit_public_flag_publishes(monkeypatch):
    from dataclasses import dataclass
    from pipeline import ingest
    @dataclass
    class Chunk:
        id: str = '12345678'
        text: str = 'synthetic private'
    class Client:
        def __init__(self): self.payloads=[]
        def upsert(self, **kwargs):self.payloads.extend(p.payload for p in kwargs['points'])
    client=Client()
    ingest.upsert_chunks(client,[Chunk()],[[1.0,0.0]])
    ingest.upsert_chunks(client,[Chunk()],[[1.0,0.0]],public_reference=True)
    ingest.upsert_chunks(client,[Chunk()],[[1.0,0.0]],public_reference='true')
    assert [p['public_reference'] for p in client.payloads]==[False,True,False]
