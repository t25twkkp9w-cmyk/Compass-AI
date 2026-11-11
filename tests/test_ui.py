from streamlit.testing.v1 import AppTest
import pytest

@pytest.fixture(autouse=True)
def isolated_ui_runtime(tmp_path,monkeypatch):
    monkeypatch.setenv("COMPASS_RUNTIME_DIR",str(tmp_path/"runtime"))
    monkeypatch.setenv("COMPASS_MODE","local")
    monkeypatch.setenv("DATABASE_URL","")
    monkeypatch.setenv("QDRANT_URL","")
    monkeypatch.setenv("COMPASS_REMOTE_TRACING","false")


def test_all_screens_and_cited_question():
    app=AppTest.from_file(str(__import__('pathlib').Path(__file__).resolve().parents[1]/'app.py')).run(timeout=90)
    assert not app.exception
    assert not app.error
    for name in ['Ask Compass','Tools & models','Source library','Requests & review','Evidence & release','Audit trail','RAG evaluations','Settings & architecture']:
        app.sidebar.radio[0].set_value(name).run(timeout=30)
        assert not app.exception, (name,[e.message for e in app.exception])
    app.sidebar.radio[0].set_value('Ask Compass').run()
    app.text_area[0].set_value('Which tool can I use for coding?')
    app.button[0].click().run(timeout=30)
    assert not app.exception
    assert any('Sources:' in c.value for c in app.caption)
    app.selectbox(key='actor').set_value('ACT-013').run()
    app.sidebar.radio[0].set_value('Source library').run()
    assert not app.exception
    assert app.file_uploader if hasattr(app,'file_uploader') else True
    app.sidebar.radio[0].set_value('RAG evaluations').run()
    assert not app.exception

def test_prototype_home_actions_use_real_guidance():
    app=AppTest.from_file(str(__import__('pathlib').Path(__file__).resolve().parents[1]/'app.py')).run(timeout=90)
    buttons={b.label:b for b in app.button}
    buttons['Use customer notes'].click().run(timeout=30)
    assert not app.exception
    assert app.sidebar.radio[0].value=='Ask Compass'
    assert 'customer meeting notes' in app.text_area[0].value
    app.sidebar.radio[0].set_value('Overview').run()
    app.text_input[0].set_value('Which tool can I use for coding?')
    next(b for b in app.button if b.label=='Ask AI Compass ↗').click().run(timeout=30)
    assert not app.exception
    assert app.sidebar.radio[0].value=='Ask Compass'
    assert any('Sources:' in caption.value for caption in app.caption)


def test_persona_dropdown_is_in_main_header_and_switches_scope():
    app=AppTest.from_file(str(__import__('pathlib').Path(__file__).resolve().parents[1]/'app.py')).run(timeout=90)
    assert not app.exception and not app.error
    assert len(app.sidebar.selectbox)==0
    assert app.selectbox(key='actor').label=='User / Persona'
    app.selectbox(key='actor').set_value('ACT-013').run()
    assert not app.exception and not app.error
    assert app.selectbox(key='actor').value=='ACT-013'
    app.sidebar.radio[0].set_value('Source library').run()
    assert not app.exception
    assert not any('Select Riley' in item.value for item in app.info)
