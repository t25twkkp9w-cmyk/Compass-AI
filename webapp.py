"""Reference-faithful browser UI with the existing governed Python services."""
import json
import os
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from compass.settings import Settings
from compass.repository import Repository
from compass.corpus import Corpus, KNOWLEDGE
from compass.guidance import GuidanceService
from compass.intake import IntakeService
from compass.evaluations import evaluate,load_dataset
from compass.schemas import DomainError

ROOT=Path(__file__).parent
settings=Settings.from_env()
settings=replace(settings,database_url=settings.db_url,runtime_directory=os.getenv('COMPASS_WEB_RUNTIME',str(ROOT/'.runtime-web')))
repo=None;corpus=None;service=None
@asynccontextmanager
async def lifespan(app):
    global repo,corpus,service
    repo=Repository(settings);corpus=Corpus(settings.data_dir);service=GuidanceService(settings,corpus,repo)
    yield
    service.retriever.close();repo.engine.dispose()
app=FastAPI(title='AI Compass',lifespan=lifespan)
app.mount('/assets',StaticFiles(directory=ROOT/'frontend'),name='assets')
class Action(BaseModel):
    actor_id:str=Field(max_length=60)
    type:str=Field(max_length=50)
    data:dict[str,Any]=Field(default_factory=dict)
    action_id:str=Field(default_factory=lambda:str(uuid.uuid4()),max_length=80)

def principal(actor_id):
    if not settings.demo_identities:raise HTTPException(503,'This local web UI requires synthetic demo identities. Enterprise authentication must be integrated before disabling demo mode.')
    try:return repo.principal(actor_id)
    except DomainError:raise HTTPException(404,'Unknown demo persona.')

def bootstrap(actor_id):
    p=principal(actor_id);requests=repo.requests(p)
    cases={}
    for r in requests:
        rid=r['request_id']
        cases[rid]={'request':r,'reviews':list(repo.latest_reviews(p,rid).values()),'review_assignments':repo.review_assignments(r['required_review_domains'])}
        for kind in ['conditions','evidence','decisions','snapshots','releases']:cases[rid][kind]=repo.case_records(p,rid,kind)
        cases[rid]['events']=repo.audit_events(p,rid)
    return {'actor':p.model_dump(),'actors':repo.actors(),'cases':cases,'tools':repo.catalog('tools'),'models':repo.catalog('models'),'deployments':repo.catalog('deployments'),
        'sources':[{k:s[k] for k in ['number','name','route']} for s in corpus.sources],
        'knowledge':{str(s['number']):Path(s['path']).read_text() for s in corpus.sources if s['number'] in KNOWLEDGE},
        'mode':settings.mode,'manifest':corpus.manifest,'section_count':len(corpus.sections),'eval_cases':[{k:c[k] for k in ['case_id','split','category','question','expected_route']} for c in load_dataset(settings)],
        'eval_runs':repo.eval_runs(p),'uploads':repo.uploads(p),'history':repo.saved_guidance(p),
        'can_evaluate':p.actor_id in {'ACT-003','ACT-004','ACT-012','ACT-013','ACT-014','ACT-022'}}
@app.get('/')
def index():return FileResponse(ROOT/'frontend'/'index.html')
@app.get('/health')
def health():return {'status':'ok','service_ready':service is not None}
@app.get('/api/bootstrap')
def get_bootstrap(actor_id:str='ACT-001'):return bootstrap(actor_id)
@app.post('/api/action')
def action(command:Action):
    p=principal(command.actor_id);d=command.data;t=command.type;result=None
    try:
        if t=='ask':
            result=service.ask(str(d.get('question','')),p,d.get('context',{}));repo.save_guidance(p,result)
        elif t=='create':result={'request_id':repo.create_request(p,d['title'],d['purpose'],d['deployment_id'],d['audience'],bool(d.get('personal_data')))}
        elif t=='upload':
            content=str(d['text']).encode('utf-8')
            if len(content)>5_000_000:raise DomainError('Maximum file size is 5 MB.')
            result=IntakeService(corpus,repo,service.retriever).prepare(p,d['name'],content,int(d['number']))
        elif t=='evaluate':result=evaluate(settings,repo,service,p,d.get('split','development'),d.get('strategy','hybrid'),min(50,max(1,int(d.get('limit',10)))),bool(d.get('judge',False)))
        elif t=='export':result=repo.export_case(p,d['request_id'])
        elif t in {'endorse','submit','review','decide','revise','evidence','verify','release'}:
            args=(p,d['request_id'],int(d['version']));key=command.action_id
            if t=='endorse':repo.endorse(*args,key)
            elif t=='submit':repo.submit(*args,key)
            elif t=='review':repo.record_review(*args,d['domain'],d['finding'],d['rationale'],key)
            elif t=='decide':repo.record_decision(*args,d['disposition'],d['rationale'],key)
            elif t=='revise':repo.revise(*args,d['deployment_id'],d['rationale'],key)
            elif t=='evidence':repo.submit_evidence(*args,d['condition_id'],d['artifact'],key)
            elif t=='verify':repo.verify(*args,d['condition_id'],bool(d['accepted']),d['rationale'],key)
            elif t=='release':repo.clear_release(*args,d['rationale'],key)
        else:raise DomainError('Unknown action.')
        return {'result':result,'workspace':bootstrap(p.actor_id)}
    except (DomainError,ValueError,KeyError,UnicodeError) as exc:raise HTTPException(400,str(exc))
