"""配对算法纯函数测试：最近项抢配、目标优先级、同样最优改变计数拒绝、窗口与护栏。"""
import random
import pytest
from src.services.matching import match_line,MatchRefusal,WINDOW_MS,MAX_PER_STREAM

P,F=True,False  # 合格 / 失败

def test_nearest_record_grabs_the_match():
    # 最近项抢配：T1先登记但离漏封读数1900毫秒，T2只差100毫秒，最近者配走唯一读数
    trials=[(0,P),(2000,F)]
    leaks=[(1900,P)]
    r=match_line(trials,leaks)
    assert r['pairs']==1 and r['total_diff_ms']==100
    assert r['trial']=={'pass':0,'fail':1,'unmatched':1}
    assert r['leak']=={'pass':1,'fail':0,'unmatched':0}

def test_max_pairs_beats_total_diff():
    # 先配最多件：两件配法总时差4800，优于只配一件、时差100的配法
    trials=[(0,P),(2000,P)]
    leaks=[(1900,P),(4900,F)]
    r=match_line(trials,leaks)
    assert r['pairs']==2 and r['total_diff_ms']==4800
    assert r['trial']['pass']==2 and r['leak']=={'pass':1,'fail':1,'unmatched':0}

def test_window_boundary_inclusive_three_seconds():
    # 同线三秒内：恰好3000毫秒可配，3001毫秒不可配
    r=match_line([(0,P)],[(3000,P)])
    assert r['pairs']==1 and r['total_diff_ms']==3000
    r=match_line([(0,P)],[(3001,P)])
    assert r['pairs']==0 and r['trial']['unmatched']==1 and r['leak']['unmatched']==1

def test_unmatched_counts_when_sizes_differ():
    trials=[(0,P),(10,F),(20,F)]
    leaks=[(15,P)]
    r=match_line(trials,leaks)
    assert r['pairs']==1 and r['trial']['unmatched']==2 and r['leak']['unmatched']==0
    assert r['trial']['pass']+r['trial']['fail']==1

def test_empty_stream_gives_zero_pairs():
    r=match_line([(0,P),(1000,F)],[])
    assert r['pairs']==0 and r['trial']=={'pass':0,'fail':0,'unmatched':2}
    assert r['leak']=={'pass':0,'fail':0,'unmatched':0}

def test_equal_optimal_changing_trial_counts_is_refused():
    # 同分配法改变计数：两条试封登记同一时刻、距同一读数都是1000毫秒，
    # 一合格一失败，两种同样最优配法使试封合格数在0和1间变动
    trials=[(0,P),(0,F)]
    leaks=[(1000,P)]
    with pytest.raises(MatchRefusal) as e:
        match_line(trials,leaks)
    assert '试封登记合格数可在0到1之间变动' in str(e.value)
    assert '配对1件、总时差1000毫秒' in str(e.value)

def test_equal_optimal_changing_leak_counts_is_refused():
    # 漏封仪侧同样最优却改变计数，同样拒绝
    trials=[(1000,P)]
    leaks=[(0,P),(0,F)]
    with pytest.raises(MatchRefusal) as e:
        match_line(trials,leaks)
    assert '漏封仪读数合格数可在0到1之间变动' in str(e.value)

def test_equal_optimal_without_count_change_is_accepted():
    # 同样最优的配法存在，但两条候选登记都是合格，计数不变，应当出数
    trials=[(0,P),(0,P)]
    leaks=[(1000,F)]
    r=match_line(trials,leaks)
    assert r['pairs']==1 and r['trial']=={'pass':1,'fail':0,'unmatched':1}
    assert r['leak']=={'pass':0,'fail':1,'unmatched':0}

def test_over_ten_thousand_records_is_refused():
    too_many=[(i,P) for i in range(MAX_PER_STREAM+1)]
    with pytest.raises(MatchRefusal) as e:
        match_line(too_many,[(0,P)])
    assert '一万条' in str(e.value)
    with pytest.raises(MatchRefusal):
        match_line([(0,P)],too_many)

def test_timeout_is_refused():
    with pytest.raises(MatchRefusal) as e:
        match_line([(0,P)],[(1000,P)],time_limit_s=-1.0)
    assert '超过5秒时限' in str(e.value)

def test_deterministic_for_same_input():
    trials=[(500,P),(1200,F),(2400,P)]
    leaks=[(900,F),(2000,P),(2600,P)]
    assert match_line(trials,leaks)==match_line(list(reversed(trials)),list(reversed(leaks)))

def brute_force(trials,leaks,window=WINDOW_MS):
    """独立oracle：枚举全部配法，返回(最多件数,最小总时差,试封合格数集合,漏封合格数集合)。"""
    n,m=len(trials),len(leaks);solutions=[]
    def rec(a,used,pairs,total,tp,lp):
        if a==n: solutions.append((pairs,total,tp,lp));return
        rec(a+1,used,pairs,total,tp,lp)
        for b in range(m):
            if not used[b] and abs(trials[a][0]-leaks[b][0])<=window:
                used[b]=True
                rec(a+1,used,pairs+1,total+abs(trials[a][0]-leaks[b][0]),tp+trials[a][1],lp+leaks[b][1])
                used[b]=False
    rec(0,[False]*m,0,0,0,0)
    key=max((p,-t) for p,t,_,_ in solutions)
    optimal=[s for s in solutions if (s[0],-s[1])==key]
    return key[0],-key[1],{s[2] for s in optimal},{s[3] for s in optimal}

def check_against_oracle(trials,leaks):
    pairs,total,trial_passes,leak_passes=brute_force(trials,leaks)
    if len(trial_passes)>1 or len(leak_passes)>1:
        with pytest.raises(MatchRefusal):
            match_line(trials,leaks)
    else:
        r=match_line(trials,leaks)
        assert r['pairs']==pairs and r['total_diff_ms']==total
        assert r['trial']['pass']==trial_passes.pop() and r['leak']['pass']==leak_passes.pop()
        assert r['trial']['fail']==pairs-r['trial']['pass'] and r['leak']['fail']==pairs-r['leak']['pass']
        assert r['trial']['unmatched']==len(trials)-pairs and r['leak']['unmatched']==len(leaks)-pairs

@pytest.mark.parametrize('seed',range(300))
def test_against_brute_force_oracle(seed):
    rng=random.Random(seed)
    n,m=rng.randint(0,4),rng.randint(0,4)
    # 时刻取自密集小集合，刻意制造同时刻并列与同样最优配法
    trials=[(rng.choice([0,500,1000,1500,2000,3000,4500]),rng.random()<.5) for _ in range(n)]
    leaks=[(rng.choice([0,500,1000,1500,2000,3000,4500]),rng.random()<.5) for _ in range(m)]
    check_against_oracle(trials,leaks)

def test_large_dense_line_within_time_limit():
    # 上限规模冒烟：10000+10000条密集候选也应在5秒时限内出数或按规则拒绝
    rng=random.Random(8)
    trials=[(i*1000,rng.random()<.5) for i in range(10000)]
    leaks=[(i*1000+rng.randrange(-2500,2501,100),rng.random()<.5) for i in range(10000)]
    r=match_line(trials,leaks)
    assert r['pairs']==10000
    assert r['trial']['pass']+r['trial']['fail']==10000 and r['leak']['pass']+r['leak']['fail']==10000
