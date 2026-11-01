// Minimal SVG line plots for the glass-box workbench (no external libraries).
'use strict';
const SVG_NS='http://www.w3.org/2000/svg';
function svgEl(name,attrs,parent){const e=document.createElementNS(SVG_NS,name);for(const [k,v] of Object.entries(attrs||{}))e.setAttribute(k,v);if(parent)parent.appendChild(e);return e;}
function niceTicks(lo,hi,count){if(!(hi>lo)){hi=lo+1;}const span=hi-lo,step0=span/count,mag=Math.pow(10,Math.floor(Math.log10(step0)));const step=[1,2,5,10].map(m=>m*mag).find(s=>s>=step0);const out=[];for(let v=Math.ceil(lo/step)*step;v<=hi+step*1e-9;v+=step)out.push(Math.abs(v)<step*1e-9?0:v);return out;}
function fmtTick(v){const a=Math.abs(v);return a!==0&&(a>=1e4||a<1e-3)?v.toExponential(1):String(+v.toPrecision(4));}
// ---------------------------------------------------------------- series visibility (#268)
// Hidden series are remembered per plot container id: in memory always, and in
// localStorage when the browser allows it (key 'wb-plot-series:' + id + ':' + name).
const PLOT_HIDDEN=new Map();
function plotStorage(){try{return typeof localStorage!=='undefined'&&localStorage?localStorage:null;}catch{return null;}}
function plotHiddenSeries(id){
  if(!id)return new Set();
  if(!PLOT_HIDDEN.has(id)){const hidden=new Set(),store=plotStorage(),prefix='wb-plot-series:'+id+':';
    try{if(store)for(let i=0;i<store.length;i++){const k=store.key(i);if(k&&k.startsWith(prefix)&&store.getItem(k)==='hidden')hidden.add(k.slice(prefix.length));}}catch{}
    PLOT_HIDDEN.set(id,hidden);}
  return new Set(PLOT_HIDDEN.get(id));
}
function plotSetHidden(id,name,hidden){
  if(!id)return;const set=new Set(plotHiddenSeries(id));if(hidden)set.add(name);else set.delete(name);PLOT_HIDDEN.set(id,set);
  const store=plotStorage(),key='wb-plot-series:'+id+':'+name;try{if(store){if(hidden)store.setItem(key,'hidden');else store.removeItem(key);}}catch{}
}
function visibleSeries(series,hiddenSet){return series.map((series,colorIndex)=>({series,colorIndex})).filter(v=>!hiddenSet.has(v.series.name));}
function plotLegend(container,spec,hidden){
  const node=(tag,attrs,text)=>{const e=document.createElement(tag);for(const [k,v] of Object.entries(attrs||{}))e.setAttribute(k,v);if(text!=null)e.textContent=text;return e;};
  const id=container.id||null,box=node('div',{class:'wb-legend-list'});if(id)box.id=id+'-legend';
  const rerender=()=>plotLines(container,spec);
  spec.series.forEach((s,k)=>{
    const item=node('label',{class:'wb-legend-item'}),check=node('input',{type:'checkbox'});check.checked=!hidden.has(s.name);
    check.addEventListener('change',()=>{if(id)plotSetHidden(id,s.name,!check.checked);else{container._plotHidden??=new Set();if(check.checked)container._plotHidden.delete(s.name);else container._plotHidden.add(s.name);}rerender();});
    const swatch=node('span',{class:'wb-swatch wb-s'+(k%6)+(s.dash?' wb-swatch-dash':'')+(s.scatter?' wb-swatch-dot':'')});
    item.append(check,swatch,node('span',{class:'wb-legend-name'},s.name));box.appendChild(item);});
  const all=node('button',{type:'button',class:'wb-btn wb-secondary wb-show-all'},'Show all');
  all.addEventListener('click',()=>{for(const s of spec.series){if(id)plotSetHidden(id,s.name,false);}container._plotHidden=new Set();rerender();});
  box.appendChild(all);container.appendChild(box);
}
// spec: {title, xlabel, ylabel, series:[{name,x,y,dash,scatter,labels,ids,onclick,showLabels}], logx, logy, cursorX, height}
// The legend below the plot toggles series; axes scale to the visible series only.
function plotLines(container,spec){
  container.textContent='';
  const hidden=container.id?plotHiddenSeries(container.id):new Set(container._plotHidden||[]);
  const shown=visibleSeries(spec.series,hidden);
  const W=560,H=spec.height||260,m={l:62,r:12,t:spec.title?24:10,b:40};
  const svg=svgEl('svg',{viewBox:`0 0 ${W} ${H}`,class:'wb-plot',role:'img','aria-label':spec.title||spec.ylabel||'plot'},container);
  const tx=v=>spec.logx?Math.log10(v):v,ty=v=>spec.logy?Math.log10(v):v;
  const pts=shown.map(v=>v.series).flatMap(s=>s.x.map((x,i)=>[x,s.y[i]])).filter(([x,y])=>x!=null&&y!=null&&isFinite(x)&&isFinite(y)&&(!spec.logx||x>0)&&(!spec.logy||y>0));
  if(!pts.length){svgEl('text',{x:W/2,y:H/2,'text-anchor':'middle',class:'wb-axis-label'},svg).textContent=shown.length?'no finite data':'no series selected';plotLegend(container,spec,hidden);return svg;}
  let [x0,x1]=[Math.min(...pts.map(p=>tx(p[0]))),Math.max(...pts.map(p=>tx(p[0])))];
  let [y0,y1]=[Math.min(...pts.map(p=>ty(p[1]))),Math.max(...pts.map(p=>ty(p[1])))];
  if(x1===x0)x1=x0+1;if(y1===y0){y0-=1;y1+=1;}const pad=(y1-y0)*0.06;y0-=pad;y1+=pad;
  const X=v=>m.l+(tx(v)-x0)/(x1-x0)*(W-m.l-m.r),Y=v=>H-m.b-(ty(v)-y0)/(y1-y0)*(H-m.t-m.b);
  const g=svgEl('g',{class:'wb-grid'},svg);
  const xt=spec.logx?niceTicks(Math.floor(x0),Math.ceil(x1),6).filter(Number.isInteger):niceTicks(x0,x1,6);
  const yt=spec.logy?niceTicks(Math.floor(y0),Math.ceil(y1),5).filter(Number.isInteger):niceTicks(y0,y1,5);
  for(const t of xt){if(t<x0-1e-9||t>x1+1e-9)continue;const v=spec.logx?Math.pow(10,t):t,px=X(v);svgEl('line',{x1:px,x2:px,y1:m.t,y2:H-m.b},g);svgEl('text',{x:px,y:H-m.b+14,'text-anchor':'middle',class:'wb-tick'},svg).textContent=fmtTick(v);}
  for(const t of yt){if(t<y0-1e-9||t>y1+1e-9)continue;const v=spec.logy?Math.pow(10,t):t,py=Y(v);svgEl('line',{x1:m.l,x2:W-m.r,y1:py,y2:py},g);svgEl('text',{x:m.l-5,y:py+4,'text-anchor':'end',class:'wb-tick'},svg).textContent=fmtTick(v);}
  svgEl('rect',{x:m.l,y:m.t,width:W-m.l-m.r,height:H-m.t-m.b,class:'wb-frame'},svg);
  if(spec.title)svgEl('text',{x:m.l,y:15,class:'wb-plot-title'},svg).textContent=spec.title;
  if(spec.xlabel)svgEl('text',{x:(W+m.l)/2,y:H-6,'text-anchor':'middle',class:'wb-axis-label'},svg).textContent=spec.xlabel;
  if(spec.ylabel)svgEl('text',{x:12,y:(H-m.b+m.t)/2,'text-anchor':'middle',transform:`rotate(-90 12 ${(H-m.b+m.t)/2})`,class:'wb-axis-label'},svg).textContent=spec.ylabel;
  shown.forEach(({series:s,colorIndex:k})=>{if(s.scatter){s.x.forEach((x,i)=>{const y=s.y[i];if(x==null||y==null||!isFinite(x)||!isFinite(y))return;const c=svgEl('circle',{cx:X(x).toFixed(2),cy:Y(y).toFixed(2),r:4,class:'wb-series wb-dot wb-s'+(k%6),'data-index':s.ids?s.ids[i]:i},svg);if(s.onclick)c.addEventListener('click',()=>s.onclick(i));if(s.labels)svgEl('title',{},c).textContent=s.labels[i];if(s.showLabels&&s.labels?.[i])svgEl('text',{x:(X(x)+6).toFixed(2),y:(Y(y)-6).toFixed(2),class:'wb-point-label'},svg).textContent=s.labels[i];});return;}
    let d='',pen=false;s.x.forEach((x,i)=>{const y=s.y[i];const ok=x!=null&&y!=null&&isFinite(x)&&isFinite(y)&&(!spec.logx||x>0)&&(!spec.logy||y>0);if(!ok){pen=false;return;}d+=(pen?'L':'M')+X(x).toFixed(2)+' '+Y(y).toFixed(2);pen=true;});
    svgEl('path',{d,class:'wb-series wb-s'+(k%6),'stroke-dasharray':s.dash?'6 4':'none'},svg);});
  if(spec.cursorX!=null&&isFinite(spec.cursorX)){const px=X(spec.cursorX);svgEl('line',{x1:px,x2:px,y1:m.t,y2:H-m.b,class:'wb-cursor'},svg);}
  plotLegend(container,spec,hidden);
  return svg;
}
