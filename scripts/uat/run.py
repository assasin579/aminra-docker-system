#!/usr/bin/env python3
"""Run browser UAT in disposable, labelled Docker containers. Live schema reads only."""
import argparse, hashlib, json, os, secrets, signal, subprocess, sys, tempfile, time, urllib.request
import fcntl, shutil
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[2]
LABEL='io.aminra.uat.run'

def sh(argv,data=None,out=None):
 r=subprocess.run(argv,input=data,stdout=out or subprocess.PIPE,stderr=subprocess.PIPE,timeout=240)
 if r.returncode:raise RuntimeError(Path(argv[0]).name+' failed: '+r.stderr.decode(errors='replace')[-1000:])
 return r.stdout.decode() if out is None else ''
def js(argv):return json.loads(sh(argv))
def wait(url):
 deadline=time.monotonic()+150
 while time.monotonic()<deadline:
  try:
   with urllib.request.urlopen(url,timeout=3) as r:
    if r.status==200:return
  except Exception:pass
  time.sleep(1)
 raise RuntimeError('Service readiness timeout: '+url)
def realm_fixture(run):
 actors={}
 for name,role,parent in [('bizA','business',None),('bizB','business',None),('cbX','cb_admin',None),('cbY','cb_admin',None),('admin','platform_admin',None),('member','business','bizA'),('assigned','auditor','cbX'),('unassigned','auditor','cbX')]:
  uid=str(uuid4());actors[name]={'id':uid,'email':run+'-'+name.lower()+'@example.invalid','password':secrets.token_urlsafe(24)+'Aa1!','role':role,'tenant_id':actors[parent]['id'] if parent else uid,'is_owner':not bool(parent)}
 mappers=[{'name':key,'protocol':'openid-connect','protocolMapper':'oidc-usermodel-attribute-mapper','config':{'user.attribute':key,'claim.name':key,'jsonType.label':kind,'access.token.claim':'true','id.token.claim':'true'}} for key,kind in [('tenant_id','String'),('is_owner','boolean'),('status','String')]]
 mappers+=[{'name':'subject-explicit','protocol':'openid-connect','protocolMapper':'oidc-usermodel-property-mapper','config':{'user.attribute':'id','claim.name':'sub','jsonType.label':'String','access.token.claim':'true','id.token.claim':'true'}},{'name':'email-explicit','protocol':'openid-connect','protocolMapper':'oidc-usermodel-property-mapper','config':{'user.attribute':'email','claim.name':'email','jsonType.label':'String','access.token.claim':'true','id.token.claim':'true'}},{'name':'backend-audience','protocol':'openid-connect','protocolMapper':'oidc-audience-mapper','config':{'included.custom.audience':'aminra-backend','access.token.claim':'true'}},{'name':'realm-roles','protocol':'openid-connect','protocolMapper':'oidc-usermodel-realm-role-mapper','config':{'claim.name':'realm_access.roles','jsonType.label':'String','multivalued':'true','access.token.claim':'true'}}]
 realm={'realm':'aminra','enabled':True,'sslRequired':'none','registrationAllowed':False,'roles':{'realm':[{'name':r} for r in ['business','cb_admin','auditor','platform_admin']]},'clients':[{'clientId':'aminra-frontend','publicClient':True,'enabled':True,'directAccessGrantsEnabled':True,'standardFlowEnabled':True,'redirectUris':['http://127.0.0.1/*'],'defaultClientScopes':['profile','email'],'protocolMappers':mappers}],'users':[{'id':a['id'],'username':a['email'],'email':a['email'],'enabled':True,'emailVerified':True,'firstName':name,'lastName':'UAT','requiredActions':[],'realmRoles':[a['role']],'credentials':[{'type':'password','value':a['password'],'temporary':False}],'attributes':{'tenant_id':[a['tenant_id']],'is_owner':[str(a['is_owner']).lower()],'status':['active']}} for name,a in actors.items()]}
 return actors,realm
class Run:
 def __init__(self,args):
  self.args=args;self.id='uat-'+time.strftime('%Y%m%d')+'-'+secrets.token_hex(4)
  self.output=Path(args.output or ROOT/'.uat-runs'/self.id).resolve();self.output.mkdir(parents=True,mode=0o700);os.chmod(self.output,0o700)
  self.private=tempfile.TemporaryDirectory(prefix='aminra-uat-');self.tmp=Path(self.private.name);self.names=[]
  self.protected={x['Name']:{'id':x['Id'],'image':x['Image'],'started':x['State']['StartedAt']} for x in js(['docker','inspect',*sh(['docker','ps','-q']).split()]) if not x['Config'].get('Labels',{}).get(LABEL)}
  suite={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in [ROOT/'scripts/uat',ROOT/'frontend/aminra-web/uat'] for p in sorted(folder.glob('*')) if p.is_file() and p.suffix in ('.py','.ts')}
  self.state={'suite_manifest':suite,'run_id':self.id,'suite':args.suite,'project':args.project,'source':sh(['git','rev-parse','HEAD']).strip(),'test_source_dirty':bool(sh(['git','status','--porcelain'])),'phase':'preflight','cleanup':False};self.save()
 def save(self):
  (self.output/'run.json').write_text(json.dumps(self.state,indent=2));(self.output/'resources.json').write_text(json.dumps({'run_id':self.id,'containers':self.names,'network':self.id},indent=2))
 def start(self,service,image,env=None,port=None,mounts=None,extra=None,cmd=None):
  name=self.id+'-'+service;self.names.append(name);self.save();print('UAT_START',service,flush=True)
  argv=['docker','run','-d','--name',name,'--label',LABEL+'='+self.id,'--network',self.id,'--network-alias','uat-'+service]
  if env:
   f=self.tmp/(service+'.env');f.write_text('\n'.join(k+'='+v for k,v in env.items())+'\n');os.chmod(f,0o600);argv+=['--env-file',str(f)]
  if port:argv+=['-p',f'127.0.0.1::{port}']
  for src,dst in mounts or []:argv+=['-v',str(src)+':'+dst]
  sh(argv+(extra or [])+[image]+(cmd or []))
  if port:return 'http://127.0.0.1:'+js(['docker','inspect',name])[0]['NetworkSettings']['Ports'][str(port)+'/tcp'][0]['HostPort']
  return name
 def setup(self):
  sh(['docker','network','create','--label',LABEL+'='+self.id,self.id]);a,realm=realm_fixture(self.id)
  f=self.tmp/'realm.json';f.write_text(json.dumps(realm));os.chmod(f,0o644)
  self.pg=self.start('postgres',self.args.postgres_image,env={'POSTGRES_PASSWORD':secrets.token_urlsafe(24),'POSTGRES_DB':'uat','POSTGRES_USER':'uat_owner'})
  for _ in range(90):
   if subprocess.run(['docker','exec',self.pg,'pg_isready','-h','127.0.0.1','-U','uat_owner','-d','uat'],capture_output=True).returncode==0:break
   time.sleep(1)
  else:raise RuntimeError('PostgreSQL readiness timeout')
  schema=self.tmp/'schema.sql'
  if self.args.schema_file:
   schema.write_bytes(Path(self.args.schema_file).read_bytes());head=self.args.schema_head
  else:
   source=self.args.schema_source_container
   head=sh(['docker','exec',source,'psql','-U',self.args.schema_source_user,'-d',self.args.schema_source_db,'-Atc','SELECT version_num FROM alembic_version']).strip()
   with schema.open('wb') as out:sh(['docker','exec',source,'pg_dump','-U',self.args.schema_source_user,'-d',self.args.schema_source_db,'--schema-only','--no-owner','--no-acl'],out=out)
  if not head or not all(c.isalnum() or c=='_' for c in head):raise RuntimeError('Expected one explicit schema head')
  sh(['docker','exec','-i',self.pg,'psql','-U','uat_owner','-d','uat','-v','ON_ERROR_STOP=1'],schema.read_bytes())
  pw=secrets.token_urlsafe(24)
  sql=f"CREATE ROLE aminra_app LOGIN PASSWORD '{pw}'; GRANT CONNECT ON DATABASE uat TO aminra_app; GRANT USAGE ON SCHEMA public TO aminra_app; GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO aminra_app; GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO aminra_app; REVOKE ALL ON alembic_version FROM aminra_app; GRANT SELECT ON alembic_version TO aminra_app; REVOKE UPDATE,DELETE ON dossier_document_attachments FROM aminra_app; INSERT INTO alembic_version VALUES ('{head}');"
  sh(['docker','exec','-i',self.pg,'psql','-U','uat_owner','-d','uat','-v','ON_ERROR_STOP=1'],sql.encode())
  master_password=secrets.token_urlsafe(32)
  kc=self.start('keycloak',self.args.keycloak_image,env={'KC_DB':'dev-file','KC_HTTP_ENABLED':'true','KC_HOSTNAME_STRICT':'false','KEYCLOAK_ADMIN':'uat-admin','KEYCLOAK_ADMIN_PASSWORD':master_password},mounts=[(f,'/opt/keycloak/data/import/aminra-realm.json:ro')],port=8080,cmd=['start-dev','--import-realm','--http-port=8080'])
  wait(kc+'/realms/aminra/.well-known/openid-configuration')
  # Imported custom identity attributes must be visible to the real token mappers.
  # This config affects only our disposable realm, never production Keycloak.
  from urllib.parse import urlencode
  token_request=urllib.request.Request(kc+'/realms/master/protocol/openid-connect/token',data=urlencode({'grant_type':'password','client_id':'admin-cli','username':'uat-admin','password':master_password}).encode())
  with urllib.request.urlopen(token_request,timeout=15) as response:master_token=json.load(response)['access_token']
  profile_url=kc+'/admin/realms/aminra/users/profile';headers={'Authorization':'Bearer '+master_token,'Content-Type':'application/json'}
  with urllib.request.urlopen(urllib.request.Request(profile_url,headers=headers),timeout=15) as response:profile=json.load(response)
  profile['unmanagedAttributePolicy']='ENABLED'
  with urllib.request.urlopen(urllib.request.Request(profile_url,data=json.dumps(profile).encode(),headers=headers,method='PUT'),timeout=15) as response:response.read()

  # Runtime identity verification gets a read-only service account, never the
  # fixture administrator credential. Exercise least privilege in the real KC.
  reader_secret=secrets.token_urlsafe(32)
  def kc_api(method,path,payload=None):
   request=urllib.request.Request(kc+'/admin/realms/aminra'+path,method=method,headers=headers,data=None if payload is None else json.dumps(payload).encode())
   with urllib.request.urlopen(request,timeout=15) as response:
    body=response.read();return json.loads(body) if body else None
  kc_api('POST','/clients',{'clientId':'aminra-uat-authz-reader','secret':reader_secret,'publicClient':False,'serviceAccountsEnabled':True,'standardFlowEnabled':False,'directAccessGrantsEnabled':False,'enabled':True,'protocol':'openid-connect'})
  reader_id=kc_api('GET','/clients?clientId=aminra-uat-authz-reader')[0]['id']
  service_user=kc_api('GET','/clients/'+reader_id+'/service-account-user')['id']
  management=kc_api('GET','/clients?clientId=realm-management')[0]['id']
  view_users=kc_api('GET','/clients/'+management+'/roles/view-users')
  kc_api('POST','/users/'+service_user+'/role-mappings/clients/'+management,[view_users])
  self.start('redis','redis:7-alpine')
  self.backend=self.id+'-backend'
  be=self.start('backend',self.args.backend_image,port=8000,extra=['--entrypoint','sh'],cmd=['-c','exec uvicorn app:app --host 0.0.0.0 --port 8000'],env={'DATABASE_URL':f'postgresql://aminra_app:{pw}@uat-postgres:5432/uat','KEYCLOAK_URL':'http://uat-keycloak:8080','KEYCLOAK_INTERNAL_URL':'http://uat-keycloak:8080','KEYCLOAK_REALM':'aminra','KEYCLOAK_AUDIENCE':'aminra-backend','KEYCLOAK_AUTHZ_CLIENT_ID':'aminra-uat-authz-reader','KEYCLOAK_AUTHZ_CLIENT_SECRET':reader_secret,'KEYCLOAK_AUTHZ_TTL_SECONDS':'2','ENVIRONMENT':'uat','UPLOAD_DIR':'/app/docs','OPENROUTER_API_KEY':'','DEEPSEEK_API_KEY':'','REDIS_URL':'redis://uat-redis:6379/0','JWT_SECRET':secrets.token_urlsafe(32)})
  wait(be+'/openapi.json')
  seed='''import asyncio,asyncpg,json,sys,os
m=json.load(sys.stdin)
async def main():
 c=await asyncpg.connect(os.environ['DATABASE_URL'])
 for name,a in m.items():
  await c.execute("INSERT INTO users (id,email,keycloak_sub,role,company_name,status,tenant_id,is_owner) VALUES ($1,$2,$1,$3::user_role,$4,'active',$5,$6)",a['id'],a['email'],'provider' if a['role'] in ('cb_admin','auditor','platform_admin') else 'business',a['email'].split('@')[0],a['tenant_id'],a['is_owner'])
 role=await c.fetchrow("SELECT current_user AS name,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
 assert role['name']=='aminra_app' and not role['rolsuper'] and not role['rolbypassrls']
 assert await c.fetchval('SELECT count(*) FROM documents')==0
 print('IDENTITY_SEED_OK');await c.close()
asyncio.run(main())'''
  sh(['docker','exec','-i',self.backend,'python','-c',seed],json.dumps(a).encode())
  frontend_env={'BACKEND_URL':'http://uat-backend:8000','KEYCLOAK_URL':'http://uat-keycloak:8080','KEYCLOAK_REALM':'aminra','KEYCLOAK_CLIENT_ID':'aminra-frontend','PORT':'3000','HOSTNAME':'0.0.0.0'}
  if self.args.frontend_source:
   snapshot=self.tmp/'frontend-source';snapshot.mkdir()
   prefix='frontend/aminra-web/';paths=set(sh(['git','ls-files',prefix]).splitlines()+sh(['git','ls-files','--others','--exclude-standard',prefix]).splitlines())
   manifest={}
   for path in sorted(paths):
    rel=Path(path.removeprefix(prefix));source=ROOT/path
    if not source.is_file() or source.is_symlink() or any(part in ('node_modules','.next','uat','e2e','__tests__') for part in rel.parts) or '.test.' in rel.name or rel.name.startswith('.env'):continue
    target=snapshot/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);manifest[str(rel)]=hashlib.sha256(target.read_bytes()).hexdigest()
   (snapshot/'node_modules').symlink_to('/app/node_modules',target_is_directory=True)
   self.state['frontend_runtime_kind']='development_snapshot';self.state['frontend_source_manifest']=manifest
   fe=self.start('frontend',self.args.frontend_image,port=3000,env=frontend_env,mounts=[(snapshot,'/workspace')],extra=['--user',str(os.getuid())+':'+str(os.getgid()),'--workdir','/workspace','--entrypoint','node'],cmd=['/app/node_modules/next/dist/bin/next','dev','--webpack','--hostname','0.0.0.0'])
  else:
   self.state['frontend_runtime_kind']='production_image'
   fe=self.start('frontend',self.args.frontend_image,port=3000,env=frontend_env)
  wait(fe+'/business/login')
  diagnose="""import httpx,json,sys,jwt
m=json.load(sys.stdin);a=m['bizA'];r=httpx.post('http://uat-keycloak:8080/realms/aminra/protocol/openid-connect/token',data={'client_id':'aminra-frontend','grant_type':'password','username':a['email'],'password':a['password']});r.raise_for_status();t=r.json()['access_token'];claims=jwt.decode(t,options={'verify_signature':False});me=httpx.get('http://127.0.0.1:8000/auth/me',headers={'Authorization':'Bearer '+t});print(json.dumps({'issuer':claims.get('iss'),'audience':claims.get('aud'),'has_email':bool(claims.get('email')),'has_tenant':bool(claims.get('tenant_id')),'roles':claims.get('realm_access'),'profile_status':me.status_code,'profile_error':me.json().get('detail')}))
if me.status_code!=200:raise RuntimeError('Profile preflight: '+me.text+' issuer='+str(claims.get('iss'))+' aud='+str(claims.get('aud'))+' email_present='+str(bool(claims.get('email'))))"""
  sh(['docker','exec','-i',self.backend,'python','-c',diagnose],json.dumps(a).encode())
  self.config=self.tmp/'config.json';self.config.write_text(json.dumps({'run_id':self.id,'base_url':fe,'api_url':be,'actors':a,'output':str(self.output),'keycloak_admin_password':master_password}));os.chmod(self.config,0o600)
  self.state.update({'phase':'browser','base_url':fe,'api_url':be,'schema_head':head,'schema_sha256':hashlib.sha256(schema.read_bytes()).hexdigest(),'schema_source':'schema only; zero customer rows','images':{s:js(['docker','image','inspect',i])[0]['Id'] for s,i in [('backend',self.args.backend_image),('frontend',self.args.frontend_image),('keycloak',self.args.keycloak_image)]}});self.save()
 def j1j2_database(self):
  tests=['tests/test_submission_j1_j2_disposable.py']
  result=subprocess.run(['docker','exec','-e','J1J2_APP_ROLE=aminra_app',self.backend,'python','-m','pytest',*tests,'-q','-p','no:cacheprovider','--junitxml=/tmp/uat-j1j2.xml'],capture_output=True,timeout=180)
  (self.output/'database.log').write_bytes(result.stdout+result.stderr)
  sh(['docker','cp',self.backend+':/tmp/uat-j1j2.xml',str(self.output/'database.xml')])
  self.state['database_exit']=result.returncode
  checks={}
  for target,expected in [('055_dossier_document_attachments:054_requirements_versions','Cannot downgrade after durable dossier'),('057_document_current_versions:056_j1j2_lineage_merge','recover forward')]:
   generated=subprocess.run(['docker','exec',self.backend,'alembic','downgrade',target,'--sql'],capture_output=True)
   if generated.returncode:raise RuntimeError('Could not generate guarded downgrade proof: '+generated.stderr.decode()[-300:])
   attempt=subprocess.run(['docker','exec','-i',self.pg,'psql','-U','uat_owner','-d','uat','-v','ON_ERROR_STOP=1'],input=generated.stdout,capture_output=True)
   key='guard_'+target[:3];checks[key]=attempt.returncode!=0 and expected in attempt.stderr.decode()
   (self.output/(key+'.log')).write_bytes(attempt.stdout+attempt.stderr)
  head=sh(['docker','exec',self.pg,'psql','-U','uat_owner','-d','uat','-Atc','SELECT version_num FROM alembic_version']).strip();checks['schema_head_preserved']=head==self.state['schema_head']
  role_code='''import asyncio,os,json,asyncpg
async def main():
 c=await asyncpg.connect(os.environ['DATABASE_URL']);r=dict(await c.fetchrow("SELECT current_user AS name,rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,rolreplication FROM pg_roles WHERE rolname=current_user"))
 checks={'runtime_role':r['name']=='aminra_app' and not any(v for k,v in r.items() if k!='name'),'owns_no_tables':await c.fetchval("SELECT count(*)=0 FROM pg_class WHERE relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)"),'no_ddl':not await c.fetchval("SELECT has_schema_privilege(current_user,'public','CREATE')"),'no_migration_write':not await c.fetchval("SELECT has_table_privilege(current_user,'alembic_version','UPDATE')"),'no_document_truncate':not await c.fetchval("SELECT has_table_privilege(current_user,'documents','TRUNCATE')")}
 print(json.dumps({'role':r,'checks':checks}));await c.close()
asyncio.run(main())'''
  role=json.loads(sh(['docker','exec',self.backend,'python','-c',role_code]));(self.output/'db-role.json').write_text(json.dumps(role,indent=2));checks['app_role_least_privilege']=all(role['checks'].values())
  checks['images_match_source_revision']=all(js(['docker','image','inspect',self.state['images'][service]])[0]['Config'].get('Labels',{}).get('org.opencontainers.image.revision')==self.state['source'] for service in ['backend','frontend'])
  (self.output/'runtime-checks.json').write_text(json.dumps(checks,indent=2));self.save()
 def recovery(self):
  started=time.monotonic();dump=self.output/'synthetic-recovery.dump'
  with dump.open('wb') as out:sh(['docker','exec',self.pg,'pg_dump','-U','uat_owner','-d','uat','-Fc'],out=out)
  os.chmod(dump,0o600)
  # Only the freshly created run-labelled database/container is eligible.
  assert js(['docker','inspect',self.pg])[0]['Config']['Labels'][LABEL]==self.id
  assert js(['docker','inspect',self.backend])[0]['Config']['Labels'][LABEL]==self.id
  sh(['docker','stop','-t','10',self.backend])
  sh(['docker','exec',self.pg,'dropdb','-U','uat_owner','--force','uat'])
  sh(['docker','exec',self.pg,'createdb','-U','uat_owner','uat'])
  sh(['docker','cp',str(dump),self.pg+':/tmp/recovery.dump'])
  sh(['docker','exec',self.pg,'pg_restore','-U','uat_owner','-d','uat','--exit-on-error','/tmp/recovery.dump'])
  sh(['docker','start',self.backend])
  info=js(['docker','inspect',self.backend])[0]
  self.state['api_url']='http://127.0.0.1:'+info['NetworkSettings']['Ports']['8000/tcp'][0]['HostPort']
  wait(self.state['api_url']+'/openapi.json')
  self.state['recovery']={'restore_seconds':round(time.monotonic()-started,3),'dump_sha256':hashlib.sha256(dump.read_bytes()).hexdigest(),'scope':'synthetic PostgreSQL recovery; existing Keycloak and document storage retained; not full disaster recovery'};self.save()
 def cleanup(self):
  errors=[]
  for name in reversed(self.names):
   r=subprocess.run(['docker','inspect',name],capture_output=True)
   if r.returncode:
    if b'No such object' not in r.stderr and b'No such container' not in r.stderr:errors.append('Cannot verify container removal '+name)
    continue
   if json.loads(r.stdout)[0]['Config'].get('Labels',{}).get(LABEL)!=self.id:errors.append('ownership mismatch '+name);continue
   if subprocess.run(['docker','rm','-fv',name],capture_output=True).returncode:errors.append(name)
  r=subprocess.run(['docker','network','inspect',self.id],capture_output=True)
  if r.returncode and b'not found' not in r.stderr and b'No such network' not in r.stderr:errors.append('Cannot verify network removal')
  if r.returncode==0:
   if json.loads(r.stdout)[0].get('Labels',{}).get(LABEL)==self.id:
    if subprocess.run(['docker','network','rm',self.id],capture_output=True).returncode:errors.append(self.id)
   else:errors.append('network ownership mismatch')
  for name,before in self.protected.items():
   r=subprocess.run(['docker','inspect',name],capture_output=True)
   if r.returncode:errors.append('pre-existing runtime missing '+name);continue
   x=json.loads(r.stdout)[0]
   if {'id':x['Id'],'image':x['Image'],'started':x['State']['StartedAt']}!=before:errors.append('pre-existing runtime changed '+name)
  self.state['pre_existing_runtimes_unchanged']=not errors
  try:self.private.cleanup()
  except OSError as exc:errors.append('private temporary cleanup: '+str(exc))
  self.state['cleanup']=not errors;self.state['cleanup_errors']=errors;self.save()
@contextmanager
def execution_lock(path):
 # Docker bridge changes can interrupt Chromium navigation in another run.
 fd=os.open(path,os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'a') as lock:
  try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX | fcntl.LOCK_NB)
  except BlockingIOError:raise RuntimeError('Another isolated UAT run is active; run suites sequentially') from None
  try:yield
  finally:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for flag,value in [('backend-image','aminra-backend:document-domain-5457cf8'),('frontend-image','aminra-frontend:document-domain-5457cf8'),('keycloak-image','aminra-docker-system-keycloak:latest'),('postgres-image','postgres:16-alpine'),('schema-source-container','aminra-docker-system-postgres-db-1'),('schema-source-user','aminra_user'),('schema-source-db','aminra'),('baseline','/home/user/Documents/all-docs/02-Projects/aminra/testing/uat-execution-register.csv')]:p.add_argument('--'+flag,default=value)
 p.add_argument('--frontend-source',action='store_true',help='Frozen disposable source snapshot on a deps-stage image; never production-build acceptance')
 p.add_argument('--browser-cache',default=str(Path.home()/'.cache/aminra-uat-browsers'));p.add_argument('--suite',choices=['full','core','j1j2'],default='full');p.add_argument('--grep');p.add_argument('--schema-file');p.add_argument('--schema-head');p.add_argument('--output');p.add_argument('--project',choices=['desktop','mobile','firefox','webkit'],default='desktop')
 args=p.parse_args();os.chdir(ROOT)
 lock_path=Path.home()/'.cache'/'aminra-uat-runner.lock';lock_path.parent.mkdir(parents=True,exist_ok=True)
 try:
  with execution_lock(lock_path):return execute(args)
 except (RuntimeError,OSError) as exc:
  print('UAT_STOP:',str(exc),file=sys.stderr);return 1

def execute(args):
 from report import generate
 run=Run(args);code=1
 def stop(signum,frame):raise KeyboardInterrupt('UAT interrupted')
 signal.signal(signal.SIGTERM,stop)
 try:
  browser_env={**os.environ,'PLAYWRIGHT_BROWSERS_PATH':args.browser_cache}
  browser_module=ROOT/'frontend/aminra-web/node_modules/playwright'
  browser_name={'desktop':'chromium','mobile':'chromium','firefox':'firefox','webkit':'webkit'}[args.project]
  probe=subprocess.run(['node','-e',"const fs=require('fs'),p=require(process.argv[1]);if(!fs.existsSync(p[process.argv[2]].executablePath()))process.exit(1)",str(browser_module),browser_name],env=browser_env,capture_output=True)
  if probe.returncode:raise RuntimeError('Required Playwright browser missing; install the locked browser into --browser-cache before UAT')
  run.setup();env={**os.environ,'UAT_CONFIG':str(run.config),'UAT_OUTPUT':str(run.output),'UAT_SUITE':args.suite,'PLAYWRIGHT_BROWSERS_PATH':args.browser_cache}
  cli=ROOT/'frontend/aminra-web/node_modules/@playwright/test/cli.js'
  if not cli.exists():raise RuntimeError('Run npm ci in frontend/aminra-web first')
  with (run.output/'browser.log').open('w') as log:result=subprocess.run(['node',str(cli),'test','-c',str(ROOT/'frontend/aminra-web/uat/playwright.config.ts'),'--project='+args.project]+(['--grep',args.grep] if args.grep else []),env=env,stdout=log,stderr=subprocess.STDOUT)
  code=result.returncode;run.state['browser_exit']=code
  if args.suite=='j1j2':run.j1j2_database();code=code or run.state['database_exit']
  if (run.output/'recovery-fixture.json').exists():
   run.recovery();recovery=run.output/'recovery';recovery.mkdir(mode=0o700)
   recovery_env={**env,'UAT_RECOVERY':'1','UAT_OUTPUT':str(recovery)}
   with (recovery/'browser.log').open('w') as log:
    rr=subprocess.run(['node',str(cli),'test','-c',str(ROOT/'frontend/aminra-web/uat/playwright.config.ts'),'--project='+args.project],env=recovery_env,stdout=log,stderr=subprocess.STDOUT)
   code=code or rr.returncode;run.state['recovery_browser_exit']=rr.returncode
   report_path=run.output/'playwright.json';original=json.loads(report_path.read_text());additional=json.loads((recovery/'playwright.json').read_text());original['suites']+=additional['suites'];report_path.write_text(json.dumps(original))
 except (Exception,KeyboardInterrupt) as exc:
  import traceback
  run.state['error']=str(exc);(run.output/'runner-error.txt').write_text(traceback.format_exc());print('UAT_STOP:',str(exc),flush=True)
 finally:
  for name in run.names:
   r=subprocess.run(['docker','logs','--tail','100',name],capture_output=True)
   if r.returncode==0:(run.output/(name.rsplit('-',1)[-1]+'.log')).write_bytes(r.stdout+r.stderr)
  current_suite={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in [ROOT/'scripts/uat',ROOT/'frontend/aminra-web/uat'] for p in sorted(folder.glob('*')) if p.is_file() and p.suffix in ('.py','.ts')}
  run.state['test_source_unchanged']=current_suite==run.state['suite_manifest']
  if not run.state['test_source_unchanged']:run.state['error']='UAT test source changed during execution; freeze source and rerun'
  run.cleanup();report=generate(Path(args.baseline),run.output,run.state)
  if args.suite=='j1j2':
   from j1j2 import generate as generate_j1j2
   acceptance=generate_j1j2(report,run.output);run.state['j1j2_gate']=acceptance['gate'];run.save()
  print(json.dumps({'run_id':run.id,'report':str(run.output/'report.html'),'cases':report['case_counts'],'gate':report['gate'],'cleanup':run.state['cleanup']},ensure_ascii=False),flush=True)
 if code!=0 or report['execution_gate']!='PASS':return 1
 return 0 if args.suite=='j1j2' and run.state.get('j1j2_gate')=='PASS' or report['gate']=='PASS' else 2
if __name__=='__main__':sys.exit(main())
