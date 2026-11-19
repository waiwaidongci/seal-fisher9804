import math
import numpy as np
from scipy import stats

def finite_rows(snapshot,keys):
    if not snapshot: raise ValueError('空批次无法分析')
    result=[]
    for row in snapshot:
        values=row['values']
        if any(k not in values for k in keys): raise ValueError('观测字段不完整')
        x=[float(values[k]) for k in keys]
        if not all(math.isfinite(v) for v in x): raise ValueError('观测必须为有限数值')
        result.append(x)
    return np.asarray(result,dtype=float)

def fisher_two_sided(a,b,c,d):
    if any(isinstance(x,bool) or int(x)!=x or x<0 for x in (a,b,c,d)): raise ValueError('计数须为非负整数')
    a,b,c,d=map(int,(a,b,c,d));n1=a+b;n2=c+d;success=a+c;N=n1+n2
    if not n1 or not n2: raise ValueError('两组各需至少1份试件')
    lo=max(0,success-n2);hi=min(n1,success)
    grid=np.arange(lo,hi+1)
    logs=stats.hypergeom.logpmf(grid,N,success,n1)
    observed=float(stats.hypergeom.logpmf(a,N,success,n1))
    return float(min(1,np.exp(logs[logs<=observed+1e-12]).sum()))

def wilson(success,total,alpha=.05):
    if total<=0: raise ValueError('总数须为正')
    z=float(stats.norm.ppf(1-alpha/2));p=success/total;den=1+z*z/total
    center=(p+z*z/(2*total))/den;half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return [center-half,center+half]

def calculate(snapshot,params):
    groups={}
    for row in snapshot:
        v=row['values'];g=v.get('group')
        if g not in ('A','B'): raise ValueError('仅允许预定义工艺组A/B')
        if g in groups: raise ValueError('每组仅允许一条汇总计数，避免重复计数；请编辑该组原记录')
        groups[g]=v
    if set(groups)!=set(('A','B')): raise ValueError('必须同时提供A与B两组')
    a,b=groups['A']['success'],groups['A']['failure'];c,d=groups['B']['success'],groups['B']['failure']
    if max(a,b,c,d)>100000: raise ValueError('单格计数不超过100000')
    p=fisher_two_sided(a,b,c,d);alpha=float(params.get('alpha',.05))
    if not .001<=alpha<=.2: raise ValueError('alpha超出范围')
    pA=a/(a+b);pB=c/(c+d)
    return {'metrics':{'A组合格率':pA,'B组合格率':pB,'B减A率差':pB-pA,'Fisher双侧p':p,'显著性阈值':alpha,'A组Wilson区间':wilson(a,a+b,alpha),'B组Wilson区间':wilson(c,c+d,alpha),'固定边际总数':a+b+c+d},'interpretation':f"B工艺合格率比A工艺{'高' if pB>=pA else '低'}{abs(pB-pA)*100:.2f}个百分点。双侧Fisher p={p:.6g}，在预设α={alpha:g}下{'拒绝两组独立性原假设' if p<alpha else '未拒绝独立性原假设'}。",'caveat':'独立试件、固定比较方案；单组Wilson区间不是率差区间，未拒绝不代表等效。结论须结合业务成本和复试风险。','columns':['工艺','合格','失败','合格率','Wilson下限','Wilson上限'],'rows':[[g,v['success'],v['failure'],v['success']/(v['success']+v['failure']),*wilson(v['success'],v['success']+v['failure'],alpha)] for g,v in groups.items()],'table_title':'预定义工艺2×2计数与单组不确定性'}
