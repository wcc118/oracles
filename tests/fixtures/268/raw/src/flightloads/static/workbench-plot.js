// Minimal SVG line plots for the glass-box workbench (no external libraries).
'use strict';
const SVG_NS='http://www.w3.org/2000/svg';
function svgEl(name,attrs,parent){const e=document.createElementNS(SVG_NS,name);for(const [k,v] of Object.entries(attrs||{}))e.setAttribute(k,v);if(parent)parent.appendChild(e);return e;}
function el(tag,attrs,...children){const e=document.createElement(tag);for(const [k,v] of Object.entries(attrs||{})){if(v==null||v===false)continue;if(k==='class')e.className=v;else if(k==='text')e.textContent=v;else if(k.startsWith('on'))e.addEventListener(k.slice(2),v);else e.setAttribute(k,v===true?'':v);}for(const c of children.flat()){if(c==null)continue;e.appendChild(typeof c==='string'?document.createTextNode(c):c);}return e;}
function niceTicks(lo,hi,count){if(!(hi>lo)){hi=lo+1;}const span=hi-lo,step0=span/count,mag=Math.pow(10,Math.floor(Math.log10(step0)));const step=[1,2,5,10].map(m=>m*mag).find(s=>s>=step0);const out=[];for(let v=Math.ceil(lo/step)*step;v<=hi+step*1e-9;v+=step)out.push(Math.abs(v)<step*1e-9?0:v);return out;}
function fmtTick(v){const a=Math.abs(v);return a!==0&&(a>=1e4||a<1e-3)?v.toExponential(1):String(+v.toPrecision(4));}

// ---------------------------------------------------------------- plot series visibility helpers (#268)
// localStorage key for hidden series: 'wb-plot-series:' + container id + ':' + series name
// Returns a Set of hidden series names (reads from localStorage, safe in VM with no localStorage)
function plotHiddenSeries(id){
  const hidden=new Set();
  try{
    if(typeof localStorage!=='undefined' && localStorage){
      const stored=localStorage.getItem('wb-plot-series:'+id);
      if(stored){
        const names=JSON.parse(stored);
        if(Array.isArray(names))names.forEach(n=>hidden.add(n));
      }
    }
  }catch(e){/* no-op: localStorage unavailable or corrupted */}
  return hidden;
}

// Set a series as hidden/shown (updates localStorage, safe in VM)
function plotSetHidden(id,name,hidden){
  try{
    if(typeof localStorage!=='undefined' && localStorage){
      const current=plotHiddenSeries(id);
      if(hidden)current.add(name);else current.delete(name);
      localStorage.setItem('wb-plot-series:'+id,JSON.stringify([...current]));
    }
  }catch(e){/* no-op: localStorage unavailable */}
}

// Filter series by visibility, keeping original color index for stable coloring
function visibleSeries(series,hiddenSet){
  return series.map((s,k)=>({series:s,colorIndex:k})).filter(({series:s})=>!hiddenSet.has(s.name));
}

// spec: {title, xlabel, ylabel, series:[{name,x:[],y:[],dash,scatter,labels,ids,onclick,showLabels}], logx, logy, cursorX, height}
function plotLines(container,spec){
  // Extract container id for persistence (may be undefined for dynamically created plots)
  const containerId=container.id||null;
  const hidden=containerId?plotHiddenSeries(containerId):new Set();
  const visible=visibleSeries(spec.series,hidden);

  container.textContent='';
  const W=560,H=spec.height||260,m={l:62,r:160,t:spec.title?24:10,b:60}; // increased right margin for legend
  const svg=svgEl('svg',{viewBox:`0 0 ${W} ${H}`,class:'wb-plot',role:'img','aria-label':spec.title||spec.ylabel||'plot'},container);

  // Build visible points array for axis scaling
  const tx=v=>spec.logx?Math.log10(v):v,ty=v=>spec.logy?Math.log10(v):v;
  const pts=visible.flatMap(({series:s})=>s.x.map((x,i)=>[x,s.y[i]])).filter(([x,y])=>x!=null&&y!=null&&isFinite(x)&&isFinite(y)&&(!spec.logx||x>0)&&(!spec.logy||y>0));
  if(!pts.length){svgEl('text',{x:W/2,y:H/2,'text-anchor':'middle',class:'wb-axis-label'},svg).textContent='no finite data';return svg;}

  // Scale axes to visible series only
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

  // Draw visible series
  visible.forEach(({series:s,colorIndex:k})=>{
    if(s.scatter){
      s.x.forEach((x,i)=>{
        const y=s.y[i];
        if(x==null||y==null||!isFinite(x)||!isFinite(y))return;
        const c=svgEl('circle',{cx:X(x).toFixed(2),cy:Y(y).toFixed(2),r:4,class:'wb-series wb-dot wb-s'+(k%6),'data-index':s.ids?s.ids[i]:i},svg);
        if(s.onclick)c.addEventListener('click',()=>s.onclick(i));
        if(s.labels)svgEl('title',{},c).textContent=s.labels[i];
        // Optional point labels for scatter series
        if(s.showLabels){
          svgEl('text',{x:X(x)+6,y:Y(y)+4,class:'wb-point-label',fill:'var(--muted)',style:'font-size:9px'},svg).textContent=s.labels[i]||'';
        }
      });
      return;
    }
    let d='',pen=false;
    s.x.forEach((x,i)=>{
      const y=s.y[i];
      const ok=x!=null&&y!=null&&isFinite(x)&&isFinite(y)&&(!spec.logx||x>0)&&(!spec.logy||y>0);
      if(!ok){pen=false;return;}
      d+=(pen?'L':'M')+X(x).toFixed(2)+' '+Y(y).toFixed(2);
      pen=true;
    });
    svgEl('path',{d,class:'wb-series wb-s'+(k%6),'stroke-dasharray':s.dash?'6 4':'none'},svg);
  });

  // Draw cursor line if active
  if(spec.cursorX!=null&&isFinite(spec.cursorX)){
    const px=X(spec.cursorX);
    svgEl('line',{x1:px,x2:px,y1:m.t,y2:H-m.b,class:'wb-cursor'},svg);
  }

  // HTML legend outside the SVG
  if(containerId && visible.length>0){
    const legend=el('div',{class:'wb-legend-list',id:containerId+'-legend'});
    visible.forEach(({series:s,colorIndex:k})=>{
      const label=el('label',{class:'wb-legend-item'});
      const checkbox=el('input',{type:'checkbox',checked:!hidden.has(s.name),onchange:e=>{
        const name=s.name;
        plotSetHidden(containerId,name,!e.target.checked);
        // Re-render the plot by triggering the stored spec
        const parent=container.parentElement;
        if(parent&&parent.dataset&&parent.dataset.spec){
          try{
            const spec=JSON.parse(parent.dataset.spec);
            plotLines(container,spec);
          }catch(err){/* ignore parse error */}
        }
      }});
      const swatch=el('span',{class:'wb-swatch wb-s'+(k%6),'style':'display:inline-block;width:16px;height:10px;margin-right:6px;'});
      if(s.dash)swatch.style.border='3px dashed currentColor';
      const name=el('span',{class:'wb-legend-name'},s.name);
      label.append(checkbox,swatch,name);
      legend.appendChild(label);
    });
    // "Show all" button
    const showAll=el('button',{
      type:'button',
      class:'wb-btn wb-secondary wb-show-all',
      style:'margin-top:6px;font-size:12px;',
      onclick:()=>{
        if(containerId){
          visible.forEach(({series:s})=>plotSetHidden(containerId,s.name,false));
          // Re-render after clearing hidden set
          const parent=container.parentElement;
          if(parent&&parent.dataset&&parent.dataset.spec){
            try{
              const spec=JSON.parse(parent.dataset.spec);
              plotLines(container,spec);
            }catch(err){/* ignore parse error */}
          }
        }
      }
    },'Show all');
    legend.appendChild(showAll);
    container.appendChild(legend);
  }else if(containerId && visible.length===0){
    // All series hidden - show message
    const msg=el('div',{class:'wb-no-series',style:'text-align:center;color:var(--muted);margin-top:20px;'},'No series selected');
    container.appendChild(msg);
  }

  return svg;
}
