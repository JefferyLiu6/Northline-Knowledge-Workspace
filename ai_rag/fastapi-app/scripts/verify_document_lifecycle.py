"""Disposable end-to-end upload/replace/reparse/delete test using real Ollama."""
import sys,tempfile,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from main import app
from service import file_service
from ai import vector_store
import psycopg

def run():
    original=file_service.UPLOAD_DIR
    with tempfile.TemporaryDirectory() as temp:
        file_service.UPLOAD_DIR=temp
        try:
            with TestClient(app) as client:
                def call(method,url,**kwargs):
                    data=client.request(method,url,**kwargs).json()
                    assert data["code"]=="200",(url,data)
                    return data.get("data")
                token=call("POST","/login",json={"username":"admin","password":"admin"})["token"]
                headers={"token":token}
                def api(method,url,**kwargs):return call(method,url,headers=headers,**kwargs)
                name="Unit test fixture lifecycle real Ollama " + uuid.uuid4().hex[:8]
                api("POST","/knowledgeBase/add",json={"name":name,"status":"Active"})
                kb=next(x["id"] for x in api("GET","/knowledgeBase/selectAll") if x["name"]==name)
                doc=None
                def upload(content):
                    return api("POST","/files/upload",files={"file":("same name.txt",content.encode(),"text/plain")})
                def vectors():
                    with psycopg.connect(vector_store._dsn()) as db, db.cursor() as c:
                        c.execute("SELECT content FROM knowledge_chunk_vector WHERE kb_id=%s",(kb,))
                        return [x[0] for x in c.fetchall()]
                def process():
                    for endpoint in [f"/knowledgeDocument/parse/{doc}",f"/knowledgeChunk/split/{doc}",f"/vectorize/document/{doc}"]:
                        api("POST",endpoint)
                    assert api("GET",f"/knowledgeDocument/selectById/{doc}")["vector_status"]=="Completed"
                try:
                    old=upload("The service code is OBSOLETEQUARTZ and the interval is 14 minutes.")
                    api("POST","/knowledgeDocument/add",json={"kb_id":kb,"name":name,"file_name":"same name.txt","file_url":old})
                    doc=api("GET",f"/knowledgeDocument/selectPage?kb_id={kb}")["list"][0]["id"]
                    process()
                    assert any("OBSOLETEQUARTZ" in x for x in vectors())
                    new=upload("The service code is CURRENTSAPPHIRE and the interval is 3 minutes.")
                    assert old!=new
                    assert b"OBSOLETEQUARTZ" in client.get(old,headers=headers).content
                    api("PUT","/knowledgeDocument/update",json={"id":doc,"kb_id":kb,"name":name,"file_name":"same name.txt","file_url":new})
                    assert vectors()==[]
                    process()
                    assert vectors() and all("OBSOLETEQUARTZ" not in x for x in vectors())
                    result=api("POST","/retrieval/search",json={"kb_ids":[kb],"strategy_id":1,"query":"What is the service code?"})
                    assert any("CURRENTSAPPHIRE" in x["content"] for x in result["results"])
                    assert all("OBSOLETEQUARTZ" not in x["content"] for x in result["results"])
                    api("POST",f"/knowledgeDocument/parse/{doc}")
                    assert vectors()==[]
                    process()
                    api("DELETE",f"/knowledgeDocument/delete/{doc}")
                    doc=None
                    assert vectors()==[]
                    print("PASS: real upload, parse, split, embed, replacement, retrieval, reparse, deletion; no stale vectors.")
                finally:
                    if doc:api("DELETE",f"/knowledgeDocument/delete/{doc}")
                    api("DELETE",f"/knowledgeBase/delete/{kb}")
        finally:
            file_service.UPLOAD_DIR=original
if __name__=="__main__":run()
