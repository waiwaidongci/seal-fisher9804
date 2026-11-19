"""冻结与补录：两份流水按同一截点冻结，迟到的源记录只进新分析。"""
import threading,time
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from src.config.database import Base
from src.models.stream import StreamRecord
from src.services import streams
from src.services.matching import match_line
from src.schemas.stream import StreamBatchInput,MatchAnalysisInput

USER=SimpleNamespace(email='analyst@demo.local',role='admin')

@pytest.fixture()
def factory(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'t.db'),connect_args={'timeout':30})
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine,expire_on_commit=False)

def put(db,line,stream,key,at,result):
    batch=StreamBatchInput(records=[{'line':line,'stream':stream,'source_key':key,'at_ms':at,'result':result}])
    return streams.add_records(db,batch,USER)

def test_backfill_only_enters_new_analysis(factory):
    with factory() as db:
        put(db,'L1','trial','T-1',1000,'pass');put(db,'L1','leak','K-1',1500,'pass')
        a=streams.create_analysis(db,MatchAnalysisInput(line='L1'),USER)
        assert a['status']=='completed' and a['result']['pairs']==1
        assert a['result']['trial']=={'pass':1,'fail':0,'unmatched':0}
        # 补录撞冻结：迟到的记录id超过截点，不进已冻结的分析
        late=put(db,'L1','trial','T-2',9000,'fail')[0]
        assert late['id']>a['cutoff']
        again=streams.get_analysis(db,a['id'])
        assert again['result']==a['result']
        assert all(x['id']<=a['cutoff'] for x in again['snapshot'])
        # 冻结快照可复算：从快照重算得到同一结果
        snap=again['snapshot']
        trials=[(x['at_ms'],x['result']=='pass') for x in snap if x['stream']=='trial']
        leaks=[(x['at_ms'],x['result']=='pass') for x in snap if x['stream']=='leak']
        assert match_line(trials,leaks)==again['result']
        # 迟到的记录只进新分析
        b=streams.create_analysis(db,MatchAnalysisInput(line='L1'),USER)
        assert b['cutoff']>=late['id'] and any(x['id']==late['id'] for x in b['snapshot'])
        assert b['result']['trial']=={'pass':1,'fail':0,'unmatched':1}

def test_both_streams_share_one_cutoff(factory):
    with factory() as db:
        put(db,'L3','trial','T-1',0,'pass');put(db,'L3','leak','K-1',500,'fail')
        a=streams.create_analysis(db,MatchAnalysisInput(line='L3'),USER)
        put(db,'L3','leak','K-2',90000,'pass')   # 只补一条漏封流水
        b=streams.create_analysis(db,MatchAnalysisInput(line='L3'),USER)
        # 两份流水共用同一截点：新分析截点同时覆盖两侧迟到的记录
        assert {x['stream'] for x in b['snapshot'] if x['id']>a['cutoff']}=={'leak'}
        assert all(x['id']<=b['cutoff'] for x in b['snapshot'])
        assert b['result']['leak']['unmatched']==1

def test_duplicate_source_key_rejected(factory):
    from fastapi import HTTPException
    with factory() as db:
        put(db,'L4','trial','T-1',0,'pass')
        with pytest.raises(HTTPException) as e:
            put(db,'L4','trial','T-1',100,'fail')
        assert e.value.status_code==409

def test_empty_line_rejected(factory):
    from fastapi import HTTPException
    with factory() as db:
        with pytest.raises(HTTPException) as e:
            streams.create_analysis(db,MatchAnalysisInput(line='L-none'),USER)
        assert e.value.status_code==422

def test_concurrent_backfill_freeze(factory):
    # 一个线程持续补录、两个线程同时建分析：每份分析的两份流水必须齐平落在同一截点
    with factory() as db:
        for i in range(5):
            put(db,'L2','trial',f'T-{i}',i*10000,'pass');put(db,'L2','leak',f'K-{i}',i*10000+400,'fail')
    errors=[];analyses=[];stop=threading.Event()
    def writer():
        try:
            for i in range(5,40):
                with factory() as db:
                    put(db,'L2','trial',f'T-{i}',i*10000,'pass');put(db,'L2','leak',f'K-{i}',i*10000+400,'fail')
        except Exception as e: errors.append(e)
        finally: stop.set()
    def analyzer():
        try:
            while not stop.is_set():
                with factory() as db:
                    analyses.append(streams.create_analysis(db,MatchAnalysisInput(line='L2'),USER))
                time.sleep(0.005)
        except Exception as e: errors.append(e)
    threads=[threading.Thread(target=writer)]+[threading.Thread(target=analyzer) for _ in range(2)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert not errors and analyses
    with factory() as db:
        rows=list(db.scalars(select(StreamRecord).where(StreamRecord.line=='L2').order_by(StreamRecord.id)))
        for a in analyses:
            frozen=[r for r in rows if r.id<=a['cutoff']]
            assert sorted(x['id'] for x in a['snapshot'])==[r.id for r in frozen]
            assert {x['id'] for x in a['snapshot'] if x['stream']=='trial'}=={r.id for r in frozen if r.stream=='trial'}
            assert {x['id'] for x in a['snapshot'] if x['stream']=='leak'}=={r.id for r in frozen if r.stream=='leak'}
