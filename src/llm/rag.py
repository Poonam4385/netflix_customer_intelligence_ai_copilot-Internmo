from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import faiss
from src.llm.client import LLMClient
from src.utils.config import get_settings, ROOT

INDEX_PATH = ROOT / "models" / "support_feedback.faiss"
DOCS_PATH = ROOT / "models" / "support_feedback_docs.jsonl"

class Embeddings:
    def __init__(self):
        self.s=get_settings(); self.provider=self.s.rag_embedding_provider.lower(); self.model=None
    def encode(self,texts:list[str])->np.ndarray:
        if self.provider=="openai":
            arr=np.asarray(LLMClient().embed_openai(texts),dtype="float32")
        else:
            if self.model is None:
                from sentence_transformers import SentenceTransformer
                self.model=SentenceTransformer(self.s.local_embedding_model)
            arr=np.asarray(self.model.encode(texts,show_progress_bar=False,normalize_embeddings=True),dtype="float32")
        faiss.normalize_L2(arr)
        return arr

def build_index(batch_size:int=256):
    data=ROOT/"data"/"processed"
    t=pd.read_csv(data/"support_tickets.csv")
    f=pd.read_csv(data/"customer_feedback.csv")
    docs=[]
    for r in t.itertuples(index=False):
        docs.append({"source":"ticket","id":r.ticket_id,"customer_id":r.customer_id,"date":str(r.ticket_date),
                     "category":r.issue_category,"subcategory":r.issue_subcategory,"rating":None,
                     "text":str(r.ticket_description)})
    for r in f.itertuples(index=False):
        docs.append({"source":"feedback","id":r.feedback_id,"customer_id":r.customer_id,"date":str(r.feedback_date),
                     "category":"Customer Feedback","subcategory":str(r.sentiment_label),"rating":int(r.rating),
                     "text":str(r.feedback_text)})
    emb=Embeddings(); chunks=[]
    for i in range(0,len(docs),batch_size):
        chunks.append(emb.encode([d["text"] for d in docs[i:i+batch_size]]))
    vectors=np.vstack(chunks).astype("float32")
    index=faiss.IndexFlatIP(vectors.shape[1]); index.add(vectors); faiss.write_index(index,str(INDEX_PATH))
    with DOCS_PATH.open("w",encoding="utf-8") as h:
        for d in docs: h.write(json.dumps(d,ensure_ascii=False)+"\n")
    print(f"Indexed {len(docs):,} support/feedback documents")

def _load_docs():
    return [json.loads(x) for x in DOCS_PATH.read_text(encoding="utf-8").splitlines() if x.strip()]

def retrieve(question:str,top_k:int=8):
    if not INDEX_PATH.exists() or not DOCS_PATH.exists(): build_index()
    index=faiss.read_index(str(INDEX_PATH)); docs=_load_docs(); q=Embeddings().encode([question])
    scores,ids=index.search(q,top_k)
    return [{**docs[i],"similarity":float(s)} for i,s in zip(ids[0],scores[0]) if i>=0]

def ask(question:str,top_k:int=8):
    hits=retrieve(question,top_k)
    context="\n\n".join(
        f"[{h['source'].upper()}:{h['id']}] date={h['date']} category={h['category']} subcategory={h['subcategory']} rating={h['rating']}\n{h['text']}"
        for h in hits
    )
    prompt=f"Question: {question}\n\nRetrieved records ({len(hits)}):\n{context}\n\nSummarize themes grounded only in these records. Cite record IDs in square brackets. State that the answer is based on {len(hits)} retrieved records and avoid generalizing beyond them."
    answer=LLMClient().generate(prompt,"You are a grounded customer-support intelligence analyst. Never invent evidence beyond retrieved records.",1200)
    return {"answer":answer,"records":hits,"count":len(hits)}

if __name__=="__main__": build_index()
