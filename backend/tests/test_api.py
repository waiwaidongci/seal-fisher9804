"""API冒烟：登录、批量录入、建配对分析、读取结果与权限；限流走fakeredis。"""
import fakeredis
import src.middlewares.rate_limit as rate_limit
rate_limit.redis=fakeredis.FakeStrictRedis()
import pytest
from sqlalchemy import select
from fastapi.testclient import TestClient
from src.main import app
from src.config.database import Base,engine,Session
from src.models.user import User
from src.utils.security import hash_password

@pytest.fixture(scope='module')
def client():
    Base.metadata.create_all(engine)
    with Session() as db:
        for role in ('admin','viewer'):
            if not db.scalar(select(User).where(User.email==role+'@demo.local')):
                db.add(User(email=role+'@demo.local',role=role,password_hash=hash_password('Research2026!')))
        db.commit()
    with TestClient(app) as c:
        yield c

def token(client,email):
    r=client.post('/auth/login',json={'email':email,'password':'Research2026!'})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}

def test_stream_flow_end_to_end(client):
    admin=token(client,'admin@demo.local')
    batch={'records':[
        {'line':'L9','stream':'trial','source_key':'T-1','at_ms':1000,'result':'pass'},
        {'line':'L9','stream':'leak','source_key':'K-1','at_ms':1600,'result':'fail'},
        {'line':'L9','stream':'trial','source_key':'T-2','at_ms':9000,'result':'fail'}]}
    r=client.post('/streams/records',json=batch,headers=admin)
    assert r.status_code==200 and len(r.json())==3
    assert client.post('/streams/records',json=batch,headers=admin).status_code==409  # 重名拒绝
    r=client.post('/match-analyses',json={'line':'L9'},headers=admin)
    assert r.status_code==200,r.text
    a=r.json()
    assert a['status']=='completed' and a['result']['pairs']==1
    assert a['result']['trial']=={'pass':1,'fail':0,'unmatched':1}
    assert a['result']['leak']=={'pass':0,'fail':1,'unmatched':0}
    got=client.get(f"/match-analyses/{a['id']}",headers=admin)
    assert got.status_code==200 and got.json()['checksum']==a['checksum']
    assert client.get('/streams/lines',headers=admin).json()==[{'line':'L9','trial':2,'leak':1}]
    assert len(client.get('/streams/records?line=L9',headers=admin).json())==3

def test_invalid_enum_rejected(client):
    admin=token(client,'admin@demo.local')
    bad={'records':[{'line':'L9','stream':'glue','source_key':'X-1','at_ms':0,'result':'pass'}]}
    assert client.post('/streams/records',json=bad,headers=admin).status_code==422

def test_viewer_is_read_only(client):
    viewer=token(client,'viewer@demo.local')
    batch={'records':[{'line':'L9','stream':'trial','source_key':'T-9','at_ms':0,'result':'pass'}]}
    assert client.post('/streams/records',json=batch,headers=viewer).status_code==403
    assert client.post('/match-analyses',json={'line':'L9'},headers=viewer).status_code==403
    assert client.get('/match-analyses',headers=viewer).status_code==200
