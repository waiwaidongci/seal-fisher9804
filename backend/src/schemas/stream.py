from pydantic import BaseModel,Field
from typing import Literal
class StreamRecordInput(BaseModel):
    line:str=Field(min_length=1,max_length=60)
    stream:Literal['trial','leak']
    source_key:str=Field(min_length=1,max_length=100)
    at_ms:int=Field(ge=0,le=10**15)
    result:Literal['pass','fail']
class StreamBatchInput(BaseModel):
    records:list[StreamRecordInput]=Field(min_length=1,max_length=2000)
class MatchAnalysisInput(BaseModel):
    line:str=Field(min_length=1,max_length=60)
