from sqlalchemy import Column,Integer,BigInteger,String,JSON,Text,UniqueConstraint
from src.config.database import Base
class StreamRecord(Base):
    """产线流水记录。id 全表同一序列、两份流水共用，作为配对分析的冻结截点。"""
    __tablename__='stream_records'
    __table_args__=(UniqueConstraint('line','stream','source_key'),)
    id=Column(Integer,primary_key=True)
    line=Column(String(60),nullable=False,index=True)
    stream=Column(String(10),nullable=False)   # trial 试封登记 / leak 漏封仪读数
    source_key=Column(String(100),nullable=False)
    at_ms=Column(BigInteger,nullable=False)
    result=Column(String(10),nullable=False)   # pass 合格 / fail 失败
    created_at=Column(String(40),nullable=False)
class MatchAnalysis(Base):
    """一次配对分析：同一截点冻结两份流水，迟到的源记录只进新分析。"""
    __tablename__='match_analyses'
    id=Column(Integer,primary_key=True)
    line=Column(String(60),nullable=False)
    status=Column(String(20),nullable=False)   # completed 出数 / refused 拒绝出数
    cutoff=Column(Integer,nullable=False)
    window_ms=Column(Integer,nullable=False)
    snapshot=Column(JSON,nullable=False)
    checksum=Column(String(64),nullable=False)
    result=Column(JSON,nullable=True)
    error=Column(Text,default='')
    created_at=Column(String(40),nullable=False)
