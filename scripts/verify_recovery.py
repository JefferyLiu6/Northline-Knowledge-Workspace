"""Kill and restart an isolated Compose backend during each document-processing stage."""
import argparse, json, os, subprocess, time, urllib.request, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument("--port",type=int,default=8091)
parser.add_argument("--keep",action="store_true",help="Keep the isolated test stack after verification")
args=parser.parse_args()
project="northline-recovery-check"
env=dict(os.environ,APP_PORT=str(args.port))
base=f"http://127.0.0.1:{args.port}/api"
token=""
def compose(*commands, stage=None):
    command=["docker","compose","-p",project,"-f",str(ROOT/"compose.yaml")]
    if stage:command+=["-f",str(ROOT/"deploy/recovery.compose.yaml")]
    result=subprocess.run(command+list(commands),cwd=ROOT,env=dict(env,RECOVERY_TEST_STAGE=stage or ""),
                          stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    if result.returncode:raise RuntimeError(result.stdout[-5000:])
def api(method,path,payload=None,file=None):
    headers={"token":token}
    if file is not None:
        boundary="recovery"+uuid.uuid4().hex
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="recovery.txt"\r\nContent-Type: text/plain\r\n\r\n'.encode()+file+f'\r\n--{boundary}--\r\n'.encode())
        headers["Content-Type"]="multipart/form-data; boundary="+boundary
    else:
        body=json.dumps(payload).encode() if payload is not None else None
        headers["Content-Type"]="application/json"
    with urllib.request.urlopen(urllib.request.Request(base+path,data=body,headers=headers,method=method),timeout=180) as response:
        data=json.load(response)
    if data.get("code","200")!="200":raise RuntimeError(str(data))
    return data.get("data",data)
def wait(predicate,timeout=180):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        value=predicate()
        if value:return value
        time.sleep(.1)
    raise TimeoutError("Processing did not reach expected state")
def latest(doc):return api("GET",f"/knowledgeDocument/tasks/{doc}")[0]
def complete(doc):
    result=wait(lambda: (task if (task:=latest(doc))["task_status"] in {"Completed","Failed"} else None))
    assert result["task_status"]=="Completed",result
    return result
def start_normal():
    compose("up","-d","--build","--wait","--force-recreate","backend","frontend")
def vectors(kb):return api("GET",f"/vectorize/status/{kb}")["vector_count"]

reports=[]
try:
    start_normal()
    token=api("POST","/login",{"username":"admin","password":"admin"})["token"]
    for stage in ["parse","split","embed"]:
        name="Recovery verification "+stage+" "+uuid.uuid4().hex[:8]
        api("POST","/knowledgeBase/add",{"name":name,"status":"Active"})
        kb=next(k["id"] for k in api("GET","/knowledgeBase/selectAll") if k["name"]==name)
        text="\n\n".join(f"Section {i}. The test gateway maintenance identifier is CHECK{i}. Disconnect power before replacing the unit. Record the inspection date and verify the model before reconnecting." for i in range(300))
        url=api("POST","/files/upload",file=text.encode())
        api("POST","/knowledgeDocument/add",{"kb_id":kb,"name":name,"file_name":"recovery.txt","file_url":url})
        doc=api("GET",f"/knowledgeDocument/selectPage?kb_id={kb}")["list"][0]["id"]
        if stage!="parse":
            api("POST",f"/knowledgeDocument/parse/{doc}");complete(doc)
        if stage=="embed":
            api("POST",f"/knowledgeChunk/split/{doc}");complete(doc)
        compose("up","-d","--wait","--force-recreate","backend","frontend",stage=stage)
        endpoint={"parse":"/knowledgeDocument/parse/","split":"/knowledgeChunk/split/","embed":"/vectorize/document/"}[stage]
        api("POST",endpoint+str(doc))
        if stage=="parse":wait(lambda:latest(doc)["task_status"]=="Processing")
        elif stage=="split":
            wait(lambda:api("GET",f"/knowledgeChunk/selectPage?document_id={doc}")["total"]>=3)
        else:
            wait(lambda:latest(doc)["success_count"]>=10)
            assert vectors(kb)>=10
        before=latest(doc)
        assert before["task_status"]=="Processing"
        compose("kill","-s","SIGKILL","backend",stage=stage)
        start_normal()
        failed=latest(doc)
        assert failed["id"]==before["id"] and failed["task_status"]=="Failed" and "restart" in failed["error_message"],failed
        assert vectors(kb)==0
        if stage!="embed":assert api("GET",f"/knowledgeChunk/selectPage?document_id={doc}")["total"]==0
        api("POST",f"/knowledgeDocument/retry/{doc}")
        succeeded=complete(doc)
        assert succeeded["id"]!=failed["id"]
        if stage=="parse":
            assert api("GET",f"/knowledgeDocument/parsedText/{doc}")["parsed_text"]==text
        else:
            chunks=api("GET",f"/knowledgeChunk/selectPage?document_id={doc}&page_size=1000")["list"]
            assert len({c["chunk_index"] for c in chunks})==len(chunks)
            if stage=="embed":assert vectors(kb)==len([c for c in chunks if c["chunk_type"]!="Parent chunk"])
        reports.append({"stage":stage,"interrupted_task":before["id"],"partial_success_count":before["success_count"],
                        "recovered_status":failed["task_status"],"retry_task":succeeded["id"],"retry_status":succeeded["task_status"]})
        print("PASS",stage,flush=True)
        api("DELETE",f"/knowledgeDocument/delete/{doc}")
        api("DELETE",f"/knowledgeBase/delete/{kb}")
    output=ROOT/"docs/verification";output.mkdir(parents=True,exist_ok=True)
    (output/"recovery.json").write_text(json.dumps(reports,indent=2)+"\n")
finally:
    if not args.keep:
        compose("down","--volumes","--remove-orphans")
