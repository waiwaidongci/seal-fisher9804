"""同线双流水一对一配对。

试封登记与漏封仪读数没有共同编号，按产线各录一份流水。配对规则：
同一条产线、时刻相差不超过三秒的记录一对一配对；在所有配法中先取
配对件数最多，再取总时差最小。若存在同样最优（件数与总时差都相同）
却使任一工艺的合格/失败数发生变化的配法，则拒绝出数并说明歧义。

算法：记录按时刻排序后，费用|Δt|是Monge阵列，必存在非交叉的最优配法
（交叉配法交换端点不增费用、不越窗，且不改变两侧被配记录的集合），
故对齐递推 cur[j]=max(prev[j],cur[j-1],prev[j-1]+边值) 给出全局最优；
前两项构成对候选数组的前缀最大，整行用numpy向量化，O(n×m)。

歧义判定用字典序组合费用：组合费用 = 时差*(配对数+1) + 次级权重，
不牺牲前两级目标即可求出每侧合格/失败记录被配上件数的上下界；
上下界不同即存在改变计数的同样最优配法。
"""
import bisect,time
import numpy as np

WINDOW_MS=3000          # 同线三秒内
MAX_PER_STREAM=10000    # 每线每份流水最多一万条
TIME_LIMIT_S=5.0        # 超时即拒绝出数
_PAIR=10**12            # 件数权重，大于任何组合费用总和
_NEG=-(1<<60)           # 不可行格

class MatchRefusal(Exception):
    """拒绝出数：输入超限、计算超时，或同样最优的配法会改变计数。"""

def _dp_solve(trials,leaks,window_ms,k,mode,deadline):
    """对齐递推：先最多件，再使 时差*k+次级权重 最小。返回(件数,组合费用)。"""
    n,m=len(trials),len(leaks)
    times=np.array([t for t,_ in leaks],dtype=np.int64)
    wcol=None
    if mode and mode[0]=='leak':
        wcol=np.array([1 if p==mode[1] else 0 for _,p in leaks],dtype=np.int64)
    lt=times.tolist()
    prev=np.zeros(m+1,dtype=np.int64);match=np.empty(m+1,dtype=np.int64)
    for i in range(1,n+1):
        if i%256==1 and time.monotonic()>deadline:
            raise MatchRefusal('配对计算超过5秒时限，拒绝出数')
        t,pa=trials[i-1]
        wrow=1 if mode and mode[0]=='trial' and pa==mode[1] else 0
        lo=bisect.bisect_left(lt,t-window_ms);hi=bisect.bisect_right(lt,t+window_ms)
        match.fill(_NEG)
        if lo<hi:
            v=prev[lo:hi]+(_PAIR-wrow)-np.abs(t-times[lo:hi])*k
            if wcol is not None: v-=wcol[lo:hi]
            match[lo+1:hi+1]=v
        prev=np.maximum.accumulate(np.maximum(prev,match))
    value=int(prev[m])
    pairs=-(-value//_PAIR)
    return pairs,pairs*_PAIR-value

def match_line(trials,leaks,window_ms=WINDOW_MS,time_limit_s=TIME_LIMIT_S):
    """trials/leaks：[(at_ms, passed), ...]，同一产线冻结后的两份流水。
    返回两组确定计数与未配对数；无法给出确定结果时抛 MatchRefusal。"""
    deadline=time.monotonic()+time_limit_s
    if len(trials)>MAX_PER_STREAM or len(leaks)>MAX_PER_STREAM:
        raise MatchRefusal(f'单份流水超过每线一万条上限（试封登记{len(trials)}条、漏封仪读数{len(leaks)}条），拒绝出数')
    trials=sorted(trials);leaks=sorted(leaks)
    zero={'pairs':0,'total_diff_ms':0,
          'trial':{'pass':0,'fail':0,'unmatched':len(trials)},
          'leak':{'pass':0,'fail':0,'unmatched':len(leaks)}}
    if not trials or not leaks: return zero
    pairs,total=_dp_solve(trials,leaks,window_ms,1,None,deadline)
    if not pairs: return zero
    k=pairs+1  # 次级权重总和不超过pairs，乘k后字典序严格：先总时差、再次级目标
    def bound(passed,side):
        # 所有“件数最多且总时差最小”的配法中，某侧合格(或失败)记录被配上的最少件数
        return _dp_solve(trials,leaks,window_ms,k,(side,passed),deadline)[1]-total*k
    min_trial=bound(True,'trial');max_trial=pairs-bound(False,'trial')
    min_leak=bound(True,'leak');max_leak=pairs-bound(False,'leak')
    if min_trial!=max_trial or min_leak!=max_leak:
        parts=[]
        if min_trial!=max_trial: parts.append(f'试封登记合格数可在{min_trial}到{max_trial}之间变动')
        if min_leak!=max_leak: parts.append(f'漏封仪读数合格数可在{min_leak}到{max_leak}之间变动')
        raise MatchRefusal(f'存在同样最优的配法（配对{pairs}件、总时差{total}毫秒），但{"，".join(parts)}，两组计数不确定，拒绝出数')
    return {'pairs':pairs,'total_diff_ms':total,
            'trial':{'pass':min_trial,'fail':pairs-min_trial,'unmatched':len(trials)-pairs},
            'leak':{'pass':min_leak,'fail':pairs-min_leak,'unmatched':len(leaks)-pairs}}
