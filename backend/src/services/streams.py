from sqlalchemy import select,func
from fastapi import HTTPException
from src.models.stream import StreamRecord,MatchAnalysis
from src.services.matching import match_line,MatchRefusal,WINDOW_MS
from src.services.audits import log
from src.utils.serializers import record,now,checksum

def list_lines(db):
    rows=db.execute(select(StreamRecord.line,StreamRecord.stream,func.count()).group_by(StreamRecord.line,StreamRecord.stream)).all()
    lines={}
    for line,stream,n in rows: lines.setdefault(line,{'line':line,'trial':0,'leak':0})[stream]=n
    return sorted(lines.values(),key=lambda x:x['line'])

def list_records(db,line):
    return [record(x) for x in db.scalars(select(StreamRecord).where(StreamRecord.line==line).order_by(StreamRecord.id.desc()).limit(500))]

def add_records(db,data,user):
    saved=[];seen=set()
    for item in data.records:
        key=(item.line,item.stream,item.source_key)
        if key in seen: raise HTTPException(409,f'本次提交内源记录编号重复：{item.line}/{item.stream}/{item.source_key}')
        seen.add(key)
        if db.scalar(select(StreamRecord).where(StreamRecord.line==item.line,StreamRecord.stream==item.stream,StreamRecord.source_key==item.source_key)):
            raise HTTPException(409,f'源记录编号重复：{item.line}/{item.stream}/{item.source_key}')
        row=StreamRecord(**item.model_dump(),created_at=now());db.add(row);saved.append(row)
    db.flush();log(db,user,'stream.save',f'{len(saved)}条');db.commit()
    return [record(x) for x in saved]

def remove_record(db,id,user):
    row=db.get(StreamRecord,id)
    if not row: raise HTTPException(404,'流水记录不存在')
    db.delete(row);log(db,user,'stream.delete',id);db.commit();return {'deleted':True}

def create_analysis(db,data,user):
    # 同一截点冻结两份流水：截点取全表当前最大id，两份流水共用；
    # 之后补录的记录id更大，被排除在本次分析之外，只进新分析。
    cutoff=db.scalar(select(func.coalesce(func.max(StreamRecord.id),0)))
    rows=list(db.scalars(select(StreamRecord).where(StreamRecord.line==data.line,StreamRecord.id<=cutoff).order_by(StreamRecord.id)))
    if not rows: raise HTTPException(422,'该产线在冻结截点前没有流水记录，请先录入')
    snapshot=[{'id':r.id,'stream':r.stream,'at_ms':r.at_ms,'result':r.result} for r in rows]
    trials=[(r.at_ms,r.result=='pass') for r in rows if r.stream=='trial']
    leaks=[(r.at_ms,r.result=='pass') for r in rows if r.stream=='leak']
    analysis=MatchAnalysis(line=data.line,status='completed',cutoff=cutoff,window_ms=WINDOW_MS,
                           snapshot=snapshot,checksum=checksum(snapshot),created_at=now())
    try:
        analysis.result=match_line(trials,leaks)
    except MatchRefusal as e:
        analysis.status='refused';analysis.error=str(e);analysis.result=None
    db.add(analysis);db.flush();log(db,user,'match.create',f'{data.line}#{analysis.id}:{analysis.status}');db.commit()
    return get_analysis(db,analysis.id)

def get_analysis(db,id):
    a=db.get(MatchAnalysis,id)
    if not a: raise HTTPException(404,'配对分析不存在')
    return record(a)

def list_analyses(db):
    return [record(x) for x in db.scalars(select(MatchAnalysis).order_by(MatchAnalysis.id.desc()).limit(100))]
