"""AI Compass: cited guidance and accountable human review."""
import html
import importlib.metadata
import json
import os
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

from compass.settings import Settings
from compass.repository import Repository
from compass.corpus import Corpus, KNOWLEDGE
from compass.guidance import GuidanceService
from compass.evaluations import evaluate, load_dataset
from compass.schemas import DomainError
from compass.intake import IntakeService
from compass.ui import install_theme, topbar, feature, section, footer

st.set_page_config(page_title="AI Compass", page_icon="🧭", layout="wide")
install_theme()

@st.cache_resource
def resources(settings):
    repo=Repository(settings); corpus=Corpus(settings.data_dir)
    return repo,corpus,GuidanceService(settings,corpus,repo)

try:
    settings=Settings.from_env()
    repo,corpus,service=resources(settings)
except Exception as exc:
    st.error(f"Application initialization failed ({type(exc).__name__}). Check .env and database/model connectivity. Live mode requires OPENAI_API_KEY.")
    st.stop()

if 'pending_navigation' in st.session_state:st.session_state.navigation=st.session_state.pop('pending_navigation')

actors=repo.actors(); actor_map={a['actor_id']:a for a in actors}
with st.sidebar:
    st.title("✦ AI Compass")
    st.markdown('<div class="brand-caption">ENTERPRISE AI GUIDANCE</div><div class="workspace-card"><span class="workspace-avatar">N</span><span>Northstar Enterprises<small>Synthetic organization · Working app</small></span></div>',unsafe_allow_html=True)
    st.markdown('<div class="nav-eyebrow">WORKSPACE</div>',unsafe_allow_html=True)
    page=st.radio("Workspace",["Overview","Ask Compass","Tools & models","Source library","Requests & review","Evidence & release","Audit trail","RAG evaluations","Settings & architecture"],key="navigation",label_visibility="collapsed")
    st.divider()
    st.caption("Local evidence mode" if settings.mode=="local" else "Live model mode")
    st.caption("Fictional Northstar enterprise policies. Guidance does not grant approval.")

with st.container(key="compass_header"):
    breadcrumb_col,persona_col,avatar_col=st.columns([5,3,.55],vertical_alignment="center")
    breadcrumb_col.markdown(f'<div class="header-breadcrumb">Workspace / {html.escape(page)}</div>',unsafe_allow_html=True)
    with persona_col:
        if settings.demo_identities:
            actor_id=st.selectbox("User / Persona",list(actor_map),format_func=lambda x:f"{actor_map[x]['name']} · {actor_map[x]['role']}",key="actor",label_visibility="collapsed",help="Switch fictional users to explore their assigned cases and actions.")
        else:
            if not st.user.is_logged_in:
                if st.button("Sign in"):st.login()
                st.stop()
            matched=[a for a in actors if a.get("email")==st.user.get("email","")]
            if not matched:st.error("No assigned application identity.");st.stop()
            actor_id=matched[0]["actor_id"]
            st.caption(matched[0]['name'])
    principal=repo.principal(actor_id)
    initials=''.join(part[0] for part in principal.name.split()[:2])
    avatar_col.markdown(f'<div class="avatar">{html.escape(initials)}</div>',unsafe_allow_html=True)
if settings.demo_identities:
    st.markdown('<div class="demo-banner">SYNTHETIC DATA · Select a user or persona at the top right. Case access and human action gates follow the selected identity.</div>',unsafe_allow_html=True)
if st.session_state.get("previous_actor")!=actor_id:
    for key in [k for k in st.session_state if k.startswith(("result_","packet_"))]:del st.session_state[key]
    st.session_state.previous_actor=actor_id

if "flash" in st.session_state:st.success(st.session_state.pop("flash"))

def dump(value):return json.dumps(value,indent=2,default=str)
def table(rows):
    if rows:st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
    else:st.info("No records available in your assigned scope.")
def act(fn):
    try:fn();st.session_state.flash="Action recorded with an audit event.";st.rerun()
    except (DomainError,ValueError,KeyError) as exc:st.error(str(exc))
def case_picker(prefix):
    rows=repo.requests(principal)
    if not rows:st.info("No cases are assigned to this persona.");return None
    byid={r['request_id']:r for r in rows}
    rid=st.selectbox("Assigned request",list(byid),format_func=lambda x:f"{x} · {byid[x]['title']}",key=prefix+actor_id)
    return byid[rid]
def case_header(r):
    st.subheader(r['title'])
    cols=st.columns(3)
    for col,key,label in zip(cols,['lifecycle','approval_disposition','release_readiness'],['Workflow','Approval','Release']):col.metric(label,r[key])
    st.caption(f"{r['request_id']} · Version {r['current_version']} · {r['scope']['deployment_id']}")
    st.info(r['next_action'])
def render_result(result):
    g=result['guidance'];st.subheader(g['outcome']);st.write(g['summary'])
    for claim in g.get('claims',[]):
        st.write(claim['text']);st.caption("Sources: "+", ".join(claim['evidence_ids']))
    for title,key in [('Conditions','conditions'),('Next steps','next_steps')]:
        if g.get(key):
            st.markdown(f"**{title}**")
            for item in g[key]:st.write("• "+item)
    st.caption(f"{result['elapsed_seconds']:.2f}s · {result['mode']} · {result['manifest']}")
    with st.expander(f"Inspect evidence ({len(result['evidence'])} references)"):
        for e in result['evidence']:
            st.markdown(f"**{e['citation_id']} · {e['title']}**");st.text(e['text'])
    with st.expander("Retrieval details"):
        st.json(result['retrieval']);st.write(result['steps']);st.caption("Citation ID validation checks references, not semantic faithfulness.")
        if result.get('error_type'):st.error("Service failure: "+result['error_type'])

def navigate(target):
    st.session_state.navigation=target

def scenario(question):
    st.session_state.prefill_question=question
    navigate("Ask Compass")

if page=="Overview":
    with st.container(key="overview_hero"):
        st.markdown('<div class="hero"><div class="compass-art">✦</div><div class="eyebrow">RIGHT TOOL. RIGHT POLICY. RIGHT GUIDANCE.</div><h1>Clarity for every<br>enterprise AI decision.</h1><p>Find permitted tools and models, understand the rules, and move through the right reviews with evidence at every step.</p></div>',unsafe_allow_html=True)
        with st.form('home_ask',border=False):
            prompt_col,submit_col=st.columns([5,1],vertical_alignment='bottom')
            home_question=prompt_col.text_input('What would you like to do with AI?',placeholder='What would you like to do with AI?',label_visibility='collapsed')
            home_submit=submit_col.form_submit_button('Ask AI Compass ↗',type='primary',width='stretch')
        if home_submit:
            if home_question.strip():
                st.session_state.pending_home_question=home_question
                st.session_state.prefill_question=home_question
                # Navigation is applied on the next run, before the sidebar widget is instantiated.
                st.session_state.pending_navigation='Ask Compass'
                st.rerun()
            else:st.info('Describe the task, tool and data you want guidance on.')
        chips=st.columns([1,1,1,2])
        chips[0].button('Use customer notes',on_click=scenario,args=('Can I use customer meeting notes with MeetBrief?',),width='stretch')
        chips[1].button('Choose a RAG model',on_click=scenario,args=('Which approved model and deployment can I use for a RAG application?',),width='stretch')
        chips[2].button('Prepare an approval',on_click=scenario,args=('How do I request approval for a new customer-facing AI assistant?',),width='stretch')
    st.write('')
    for col,icon,title,description,target,label in zip(st.columns(3),['✧','◇','⌘'],['Grounded guidance','Governed approval','Measurable quality'],['Policy evidence with conditions, exact source sections and an honest uncertainty path.','Requests, specialist findings, decisions and independent release gates.','Retrieval, grounding, citations and regression evidence as a core product workflow.'],['Ask Compass','Requests & review','RAG evaluations'],['Ask a question →','Explore your cases →','Open RAG evaluation →']):
        with col:
            with st.container(key='featurecard_'+target.replace(' ','_')):
                feature(icon,title,description)
                st.button(label,on_click=navigate,args=(target,),key='feature_'+target,width='stretch')
    section('One evidence foundation','Published synthetic corpus · v3.0')
    cols=st.columns(4)
    catalog_count=f"{len(repo.catalog('tools'))} / {len(repo.catalog('models'))} / {len(repo.catalog('deployments'))}"
    for col,label,value,caption in zip(cols,['Logical data sources','Governed catalog','Assigned requests','RAG evaluation'],[len(corpus.sources),catalog_count,len(repo.requests(principal)),len(load_dataset(settings))],['8 knowledge and 4 operational sources','Tools / models / deployments','Access follows your case assignments','30 development / 20 holdout cases']):
        col.metric(label,value);col.caption(caption)
    st.markdown('<div class="callout">Tool, model and deployment permissions are separate facts. Guidance does not grant approval. A scope or model-version change requires a fresh assessment.</div>',unsafe_allow_html=True)
    section('Your assigned work','Current workflow, approval and release status')
    table([{k:r[k] for k in ['request_id','title','approval_disposition','release_readiness']} for r in repo.requests(principal)])
    if settings.mode=='local':st.caption('LOCAL EVIDENCE MODE · BM25 and lexical hash vectors retrieve source extracts. No model calls or AI permission decisions are generated in this mode.')

elif page=="Ask Compass":
    st.markdown('<div class="eyebrow">GROUNDED GUIDANCE</div>',unsafe_allow_html=True)
    st.title("Ask AI Compass");st.caption("Given my task, tool and data, what does policy permit, what conditions apply, and what should I do next?")
    if 'prefill_question' in st.session_state:st.session_state.question_text=st.session_state.pop('prefill_question')
    if 'pending_home_question' in st.session_state:
        with st.spinner('Retrieving authorized evidence...'):
            result=service.ask(st.session_state.pop('pending_home_question'),principal)
            repo.save_guidance(principal,result);st.session_state['result_'+actor_id]=result
    with st.form("question_form"):
        question=st.text_area("Your question",placeholder="Can I upload a customer contract to ContractLens?",height=110,key="question_text")
        a,b=st.columns(2)
        deps=repo.catalog('deployments');depmap={d['deployment_id']:d for d in deps}
        dep=a.selectbox("Deployment context (optional)",["Not specified",*depmap])
        data_class=b.selectbox("Data classification",["Not specified","Public","Internal","Confidential","Restricted"])
        submitted=st.form_submit_button("Find policy guidance",type="primary")
    if submitted:
        try:
            with st.spinner("Retrieving authorized evidence..."):
                context={"data_class":data_class}
                if dep!='Not specified':context['deployment_id']=dep
                result=service.ask(question,principal,context);repo.save_guidance(principal,result)
                st.session_state['result_'+actor_id]=result
        except DomainError as exc:st.error(str(exc))
    if 'result_'+actor_id in st.session_state:render_result(st.session_state['result_'+actor_id])
    with st.expander("Your saved guidance"):
        history=repo.saved_guidance(principal)
        if history:
            chosen=st.selectbox("Previous question",range(len(history)),format_func=lambda i:history[i]['result']['question'])
            if st.button("Open saved guidance"):st.session_state['result_'+actor_id]=history[chosen]['result'];st.rerun()
        else:st.caption("No saved questions yet.")

elif page=="Tools & models":
    st.title("Tools, models & deployments");st.caption("Check the exact deployment and permitted data scope before choosing a tool.")
    for tab,kind in zip(st.tabs(["Tools","Models","Deployments"]),['tools','models','deployments']):
        with tab:
            rows=repo.catalog(kind);q=st.text_input("Search catalog",key='search_'+kind)
            rows=[r for r in rows if q.lower() in dump(r).lower()]
            keys={'tools':['tool_id','name','status'],'models':['model_version_id','name','status'],'deployments':['deployment_id','tool_id','status','permitted_data_classes','region']}[kind]
            table([{k:r.get(k) for k in keys} for r in rows])
            if rows:
                idx=st.selectbox("Inspect record",range(len(rows)),format_func=lambda i,records=rows:records[i].get('name',records[i].get('deployment_id','Record')),key='inspect_'+kind)
                st.json(rows[idx])

elif page=="Source library":
    st.title("Source library");st.caption("Knowledge sources #1–7 and #9 feed retrieval. Operational records remain in the case store.")
    browse,upload=st.tabs(["Published corpus","Source upload"])
    with browse:
        table([{k:s[k] for k in ['number','name','route']} for s in corpus.sources])
        sources=[s for s in corpus.sources if s['number'] in KNOWLEDGE]
        selected=st.selectbox("Read knowledge source",sources,format_func=lambda s:s['name'])
        text=Path(selected['path']).read_text()
        with st.expander("Source content"):st.code(text,language='json' if selected['name'].endswith('json') else 'markdown')
        st.download_button("Download source",text,file_name=selected['name'])
        st.caption("Use Requests, Evidence and Audit for authorized operational records. Raw operational files are not exposed here.")
    with upload:
        if actor_id!='ACT-013':st.info("Select Riley, the source administrator, to stage uploads in this synthetic demo.")
        else:
            number=st.selectbox("Source number",sorted(KNOWLEDGE));file=st.file_uploader("Markdown or catalog JSON",type=['md','json'])
            if file and st.button("Validate and stage",type='primary'):
                try:
                    content=file.getvalue();units=corpus.preview(file.name,content,number)
                    with st.spinner('Preparing parallel validation and candidate indexing tracks...'):
                        report=IntakeService(corpus,repo,service.retriever).prepare(principal,file.name,content,number)
                    st.json(report)
                    l,r=st.columns(2)
                    l.write("**Track A: retrieval preparation**");l.write("Section-aware chunks embedded into a separate, unpublished Qdrant candidate collection.")
                    r.write("**Track B: structured validation**");r.write("Source identity, section uniqueness and catalog references validated independently.")
                except (ValueError,DomainError,UnicodeError,KeyError) as exc:st.error(str(exc))
            st.warning("Candidate indexes remain unpublished. This release searches the bundled published snapshot; policy-owner publication and catalog activation are outside this first release.")
            table([{k:r[k] for k in ['upload_id','name','source_number','created_at','status']} for r in repo.uploads(principal)])

elif page=="Requests & review":
    st.title("Requests & human review")
    with st.expander("Create a request"):
        with st.form('create'):
            title=st.text_input('Request title');purpose=st.text_area('Business purpose')
            deployment=st.selectbox('Proposed deployment',[d['deployment_id'] for d in repo.catalog('deployments')])
            audience=st.selectbox('Audience',['Employees','Customers']);personal=st.checkbox('Includes personal data')
            if st.form_submit_button('Create draft'):act(lambda:repo.create_request(principal,title,purpose,deployment,audience,personal))
    r=case_picker('review_case_')
    if r:
        case_header(r);rid=r['request_id'];v=r['current_version']
        with st.expander('Current scope'):st.json(r['scope'])
        with st.expander('Submit and sponsor'):
            if actor_id==r['sponsor_actor_id'] and st.button('Endorse current version'):act(lambda:repo.endorse(principal,rid,v,str(uuid.uuid4())))
            if actor_id==r['requester_actor_id'] and st.button('Submit for review'):act(lambda:repo.submit(principal,rid,v,str(uuid.uuid4())))
            st.caption('The sponsor endorses first. The requester then freezes the submitted scope.')
        st.subheader('Domain reviews');table(list(repo.latest_reviews(principal,rid).values()))
        assigned=[domain for domain,actor in repo.review_assignments(r['required_review_domains']).items() if actor==actor_id]
        if assigned:
            with st.form('review'):
                domain=st.selectbox('Review domain',assigned);finding=st.selectbox('Finding',['Satisfactory','Changes requested','Blocking'])
                rationale=st.text_area('Review rationale')
                if st.form_submit_button('Record finding'):act(lambda:repo.record_review(principal,rid,v,domain,finding,rationale,str(uuid.uuid4())))
        if actor_id==r['decision_owner_actor_id']:
            with st.form('decision'):
                disposition=st.selectbox('Formal decision',['Approved with conditions','Rejected','Return for revision']);rationale=st.text_area('Decision rationale')
                if st.form_submit_button('Record authorized decision'):act(lambda:repo.record_decision(principal,rid,v,disposition,rationale,str(uuid.uuid4())))
        if actor_id==r['requester_actor_id']:
            with st.expander('Prepare a revised version'):
                newdep=st.selectbox('Revised deployment',[d['deployment_id'] for d in repo.catalog('deployments')]);reason=st.text_input('Change reason')
                if st.button('Create new scope version'):act(lambda:repo.revise(principal,rid,v,newdep,reason,str(uuid.uuid4())))
        with st.expander('Decision history'):table(repo.case_records(principal,rid,'decisions'))

elif page=="Evidence & release":
    st.title("Evidence & release")
    r=case_picker('evidence_case_')
    if r:
        case_header(r);rid=r['request_id'];v=r['current_version']
        conditions=[c for c in repo.case_records(principal,rid,'conditions') if c['request_version']==v]
        table(conditions)
        if conditions:
            c=st.selectbox('Condition',conditions,format_func=lambda x:x['condition_id'])
            st.json(c)
            template={'synthetic_fixture':True,'configuration':{'request_id':rid,'request_version':v,'deployment_id':r['scope']['deployment_id'],'model_version_ids':r['scope']['model_version_ids']},'findings':'Replace with actual findings and supporting artifact references.'}
            st.download_button('Download evidence JSON template',dump(template),file_name='evidence-template.json')
            if actor_id==c['owner_actor_id']:
                artifact=st.file_uploader('Evidence JSON',type=['json'])
                if artifact and st.button('Submit evidence'):
                    try:payload=json.loads(artifact.getvalue());act(lambda:repo.submit_evidence(principal,rid,v,c['condition_id'],payload,str(uuid.uuid4())))
                    except ValueError:st.error('Invalid JSON evidence.')
            if actor_id==c['verifier_actor_id']:
                with st.form('verify'):
                    accepted=st.checkbox('Evidence meets the condition');reason=st.text_area('Independent verification rationale')
                    if st.form_submit_button('Record verification'):act(lambda:repo.verify(principal,rid,v,c['condition_id'],accepted,reason,str(uuid.uuid4())))
        with st.expander('Submitted evidence'):table(repo.case_records(principal,rid,'evidence'))
        if actor_id==r['decision_owner_actor_id']:
            reason=st.text_area('Release rationale')
            if st.button('Verify gates and clear release',type='primary'):act(lambda:repo.clear_release(principal,rid,v,reason,str(uuid.uuid4())))
        st.caption('Release requires a current approval, exact approved deployment and models, and independent verification of every pre-release condition.')

elif page=="Audit trail":
    st.title("Audit trail & case export")
    r=case_picker('audit_case_')
    if r:
        rid=r['request_id'];events=repo.audit_events(principal,rid)
        table([{k:e.get(k) for k in ['event_id','occurred_at_utc','actor_id','action','request_version']} for e in events])
        with st.expander('Event details'):st.json(events)
        if st.button('Prepare authorized case export'):
            st.session_state['packet_'+actor_id]=repo.export_case(principal,rid)
        packet=st.session_state.get('packet_'+actor_id)
        if packet and packet['request']['request_id']==rid:st.download_button('Download case evidence packet',dump(packet),file_name=rid+'-audit.json')
        st.caption('Case access is enforced server side. Export preparation is itself an audited action. A hash chain supports tamper detection; this database is not a WORM archive.')

elif page=="RAG evaluations":
    st.title("RAG evaluations");st.caption("Compare retrieval strategies against 50 author-drafted synthetic cases. Results shown below are measured runs, not targets.")
    allowed=actor_id in {'ACT-003','ACT-004','ACT-012','ACT-013','ACT-014','ACT-022'}
    if not allowed:st.info('Switch to a Quality, Governance, Platform or Audit persona to run and inspect experiments.')
    else:
        with st.form('evaluate'):
            a,b,c=st.columns(3);split=a.selectbox('Dataset split',['development','holdout','all']);strategy=b.selectbox('Retrieval strategy',['hybrid','dense','bm25']);limit=c.slider('Maximum cases',1,50,10)
            judge=st.checkbox('Use configured model judge (paid API calls)',disabled=settings.mode!='live')
            if st.form_submit_button('Run evaluation',type='primary'):
                try:
                    with st.spinner('Running real retrieval and guidance checks...'):result=evaluate(settings,repo,service,principal,split,strategy,limit,judge)
                    st.success(f"Recorded {result['run_id']}")
                except DomainError as exc:st.error(str(exc))
        runs=repo.eval_runs(principal)
        if runs:
            run=st.selectbox('Experiment',runs[::-1],format_func=lambda r:f"{r['run_id']} · {r['strategy']} · {r['split']}")
            summary=run['summary'];cols=st.columns(4)
            for col,key,label in zip(cols,['route_accuracy','retrieval_recall_at_5','evidence_coverage','p95_seconds'],['Route accuracy','Recall@5','Evidence coverage','p95 seconds']):
                value=summary.get(key);col.metric(label,'Not scored' if value is None else f'{value:.3f}')
            st.info(summary['note']);table(run['results']);st.download_button('Download measured evaluation',dump(run),file_name=run['run_id']+'.json')
        with st.expander('Dataset and evaluation limits'):
            st.write('30 development and 20 holdout cases. Repeated holdout use turns it into development feedback. Gold labels require independent review.')
            st.write('Reference validity checks IDs. Semantic citation precision, claim faithfulness and cost are not scored by the local evaluator. No judge or human approval is fabricated.')
            table([{k:e[k] for k in ['case_id','split','category','question','expected_route']} for e in load_dataset(settings)])

elif page=="Settings & architecture":
    st.title("Settings & architecture")
    st.write('Streamlit → LangGraph guidance workflow → LangChain retrieval and typed repository tools → Qdrant knowledge index and transactional case store.')
    st.json({'mode':settings.mode,'transactional_database':repo.engine.dialect.name,'vector_database':'Qdrant server' if settings.qdrant_url else 'Qdrant embedded','manifest':corpus.manifest,'chunk_count':len(corpus.chunks),'embedding':service.retriever.embedding_name,'chat_model':settings.chat_model if settings.mode=='live' else 'None: extractive evidence','judge_model_configured':settings.judge_model,'remote_summary_tracing_enabled':settings.remote_tracing,'openai_key_present':bool(os.getenv('OPENAI_API_KEY')),'langsmith_key_present':bool(os.getenv('LANGSMITH_API_KEY'))})
    st.subheader('Installed versions')
    table([{'component':name,'version':importlib.metadata.version(name)} for name in ['streamlit','langchain','langchain-openai','langgraph','qdrant-client','sqlalchemy','psycopg','langsmith']])
    with st.expander('Configuration example'):st.code((settings.root/'.env.example').read_text(),language='bash')
    st.warning('This is a synthetic project workspace. Demo persona switching is not authentication. Enterprise deployment requires configured OIDC, real identity assignments, infrastructure controls and policy-owner publication controls.')

footer()
