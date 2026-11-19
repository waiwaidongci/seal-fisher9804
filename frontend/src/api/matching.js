import {request,post} from './client.js';
export const streams={
 lines:()=>request('/streams/lines'),
 records:line=>request('/streams/records?line='+encodeURIComponent(line)),
 add:records=>post('/streams/records',{records}),
 remove:id=>request(`/streams/records/${id}`,{method:'DELETE'})
};
export const matchAnalyses={
 list:()=>request('/match-analyses'),
 create:line=>post('/match-analyses',{line})
};
