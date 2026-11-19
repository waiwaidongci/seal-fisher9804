import os,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
_tmp=tempfile.mkdtemp(prefix='seal-stream-test-')
os.environ['DATABASE_URL']='sqlite:///'+_tmp+'/api.db'
os.environ['REDIS_URL']='redis://127.0.0.1:6399/15'
os.environ['JWT_SECRET']='stream-test-secret'
os.environ['SEED_DEMO']='false'
