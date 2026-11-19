from fastapi import APIRouter,Depends
from src.config.database import get_db
from src.middlewares.auth import current_user,writer
from src.schemas.stream import StreamBatchInput,MatchAnalysisInput
from src.services import streams
router=APIRouter()
@router.get('/streams/lines')
def lines(db=Depends(get_db),user=Depends(current_user)): return streams.list_lines(db)
@router.get('/streams/records')
def records(line:str,db=Depends(get_db),user=Depends(current_user)): return streams.list_records(db,line)
@router.post('/streams/records')
def add(data:StreamBatchInput,db=Depends(get_db),user=Depends(writer)): return streams.add_records(db,data,user)
@router.delete('/streams/records/{id}')
def remove(id:int,db=Depends(get_db),user=Depends(writer)): return streams.remove_record(db,id,user)
@router.get('/match-analyses')
def analyses(db=Depends(get_db),user=Depends(current_user)): return streams.list_analyses(db)
@router.post('/match-analyses')
def create(data:MatchAnalysisInput,db=Depends(get_db),user=Depends(writer)): return streams.create_analysis(db,data,user)
@router.get('/match-analyses/{id}')
def analysis(id:int,db=Depends(get_db),user=Depends(current_user)): return streams.get_analysis(db,id)
