"""Read-only installation check; uses only the Python standard library."""
import argparse, json, urllib.request, urllib.parse
p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8080');p.add_argument('--models',action='store_true');args=p.parse_args()
base=args.url.rstrip('/')+'/api';token=''
def call(path,body=None):
    request=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json','token':token})
    with urllib.request.urlopen(request,timeout=180) as response:result=json.load(response)
    if 'code' in result:
        if result['code']!='200':raise RuntimeError(f'{path}: {result.get("msg")}')
        return result.get('data')
    return result
assert call('/health/ready')['status']=='ready'
token=call('/login',{'username':'admin','password':'admin'})['token']
bases=call('/knowledgeBase/selectAll')
docs=call('/knowledgeDocument/selectPage?page_size=100')['list']
assert bases and docs
for sample in docs:
    url=urllib.parse.urljoin(args.url,sample['file_url'])
    with urllib.request.urlopen(urllib.request.Request(url,headers={'token':token})) as response:
        content=response.read()
        assert response.headers.get_content_type()!="application/json", sample['file_name']
        assert len(content)>0
        if sample.get('file_size'):
            assert len(content)==sample['file_size'], (sample['file_name'],len(content),sample['file_size'])
call('/vectorize/health')
print(f'PASS: readiness, admin login, {len(bases)} knowledge bases, {len(docs)} documents, authenticated source download, pgvector.')
if args.models:
    for model in call('/aiModelConfig/selectAll'):
        if model['enabled']=='Yes':
            call('/aiModelConfig/test/'+str(model['id']),{})
            print('PASS:',model['model_type'],model['model_name'])
