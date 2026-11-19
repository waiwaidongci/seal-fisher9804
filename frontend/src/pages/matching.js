import {streams,matchAnalyses} from '../api/matching.js';
import {table} from '../components/common/table.js';
import {status} from '../components/common/status.js';
import {esc,fmt} from '../utils/format.js';
import {bindForm} from '../hooks/forms.js';
const state={line:'',lines:[],records:[],analyses:[]};
const STREAMS={trial:'试封登记',leak:'漏封仪读数'};
const RESULTS={pass:'合格',fail:'失败'};
function counts(a){
 if(a.status!=='completed'||!a.result)return {html:`<span class="error">拒绝出数：${esc(a.error)}</span>`};
 const r=a.result;
 return {html:`配对 ${r.pairs} 件 · 总时差 ${fmt(r.total_diff_ms)} 毫秒<br>试封登记 合格${r.trial.pass} 失败${r.trial.fail}（未配对${r.trial.unmatched}）<br>漏封仪读数 合格${r.leak.pass} 失败${r.leak.fail}（未配对${r.leak.unmatched}）`};
}
export async function render(){
 const writable=localStorage.getItem('research-role')!=='viewer';
 [state.lines,state.analyses]=await Promise.all([streams.lines(),matchAnalyses.list()]);
 if(!state.line||!state.lines.some(x=>x.line===state.line))state.line=state.lines[0]?.line||'';
 state.records=state.line?await streams.records(state.line):[];
 const lineOptions=state.lines.map(x=>`<option value="${esc(x.line)}" ${x.line===state.line?'selected':''}>${esc(x.line)} · 试封${x.trial}条/漏封${x.leak}条</option>`).join('');
 return `<div class="eyebrow">02 / STREAM MATCHING</div><h1>产线双流水配对</h1><p class="lead">试封登记与漏封仪读数没有共同编号，按产线各录一份流水。同一条产线、时刻相差不超过三秒的记录一对一配对：先配最多件，再让总时差最小。</p><div class="method-note">若同样最优的配法会改变任一工艺的合格或失败数，则拒绝出数并说明歧义。建分析时两份流水按同一截点冻结，迟到的源记录只进新分析；每线最多一万条，计算超过5秒即拒绝。出数的两组合格/失败计数可录入「来源录入」页供原检验使用。</div><div class="toolbar"><label>产线<select id="line-select">${lineOptions}</select></label></div>
 ${writable?`<h2>录入流水记录</h2><form id="record-form" class="inline-form"><label>产线<input name="line" value="${esc(state.line)}" required maxlength="60"></label><label>流水<select name="stream"><option value="trial">试封登记</option><option value="leak">漏封仪读数</option></select></label><label>源记录编号<input name="source_key" placeholder="如 REG-0001" required maxlength="100"></label><label>时刻（毫秒）<input name="at_ms" type="number" min="0" step="1" value="0" required></label><label>结果<select name="result"><option value="pass">合格</option><option value="fail">失败</option></select></label><button type="submit">保存记录</button></form>`:'<p class="method-note">观察员仅可读取；分析师与负责人可录入记录并建分析。</p>'}
 <h2>流水明细 <small>${esc(state.line)||'未选择产线'} · 最近${state.records.length}条</small></h2>${table(['编号','流水','源记录编号','时刻（毫秒）','结果',...(writable?['操作']:[])],state.records.map(r=>[r.id,STREAMS[r.stream]||r.stream,r.source_key,r.at_ms,RESULTS[r.result]||r.result,...(writable?[{html:`<button class="text" data-delete="${r.id}">移除</button>`}]:[])]))}
 <h2>配对分析 <small>同一截点冻结两份流水</small></h2>${writable&&state.line?`<form id="analyze-form" class="toolbar"><button type="submit">对 ${esc(state.line)} 新建配对分析 →</button></form>`:''}${table(['分析','产线','状态','两组计数与未配对数 / 拒绝原因','冻结'],state.analyses.map(a=>[{html:`#${a.id}`},a.line,{html:status(a.status)},counts(a),`截点${a.cutoff} · ${a.snapshot.length}条 · ${a.checksum.slice(0,12)}`]))}`;
}
export function bind(refresh){
 const sel=document.getElementById('line-select');
 if(sel)sel.onchange=()=>{state.line=sel.value;refresh();};
 bindForm('record-form',async data=>{await streams.add([{line:data.line,stream:data.stream,source_key:data.source_key,at_ms:+data.at_ms,result:data.result}]);state.line=data.line;refresh();});
 bindForm('analyze-form',async()=>{await matchAnalyses.create(state.line);refresh();});
 document.querySelectorAll('[data-delete]').forEach(el=>el.onclick=async()=>{try{await streams.remove(+el.dataset.delete);refresh();}catch(e){document.getElementById('notice').textContent=e.message;}});
}
