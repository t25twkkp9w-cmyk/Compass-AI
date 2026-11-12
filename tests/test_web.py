from dataclasses import replace
import re
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import webapp

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(webapp,'settings',replace(webapp.settings,mode='local',remote_tracing=False,auth_mode='demo',database_url=f"sqlite:///{tmp_path/'web.db'}",runtime_directory=str(tmp_path/'vectors')))
    with TestClient(webapp.app) as client:yield client

def test_reference_shell_has_exact_css_and_top_right_persona(client):
    response=client.get('/')
    assert response.status_code==200
    html=response.text
    original=(webapp.ROOT/'frontend'/'shell.html').read_text()
    assert re.search(r'<style>(.*?)</style>',html,re.S)[1]==re.search(r'<style>(.*?)</style>',original,re.S)[1]
    assert 'id="persona"' not in re.search(r'<aside>(.*?)</aside>',html,re.S)[1]
    header=re.search(r'<header>(.*?)</header>',html,re.S)[1]
    assert 'headerRight' in header and 'id="persona"' in header
    assert '/assets/app.js' in html

def test_web_guidance_scope_and_no_streamlit_dependency_in_ui(client):
    data=client.get('/api/bootstrap?actor_id=ACT-001').json()
    assert len(data['actors'])==30 and len(data['tools'])==10
    assert 'REQ-001' in data['cases']
    admin=client.get('/api/bootstrap?actor_id=ACT-013').json()
    assert 'REQ-001' not in admin['cases']
    response=client.post('/api/action',json={'actor_id':'ACT-001','type':'ask','data':{'question':'Which tool can I use for coding?'}})
    assert response.status_code==200
    result=response.json()['result']
    assert result['error_type'] is None and result['evidence']
    assert all(c['evidence_ids'] for c in result['guidance']['claims'])
    forbidden=client.post('/api/action',json={'actor_id':'ACT-013','type':'export','data':{'request_id':'REQ-001'}})
    assert forbidden.status_code==400
    assert 'not assigned' in forbidden.json()['detail']

def test_web_request_creation_and_evaluation_permissions(client):
    created=client.post('/api/action',json={'actor_id':'ACT-001','type':'create','data':{'title':'Browser-created request','purpose':'Internal policy assistance with citations','deployment_id':'DEP-010','audience':'Employees'}})
    assert created.status_code==200
    rid=created.json()['result']['request_id']
    assert created.json()['workspace']['cases'][rid]['request']['lifecycle']=='Draft'
    denied=client.post('/api/action',json={'actor_id':'ACT-001','type':'evaluate','data':{'limit':1}})
    assert denied.status_code==400
    run=client.post('/api/action',json={'actor_id':'ACT-014','type':'evaluate','data':{'limit':2}})
    assert run.status_code==200
    assert run.json()['result']['summary']['cases']==2
