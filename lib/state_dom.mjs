// Minimal state-test DOM, not a browser renderer. Detached IDs are addressable;
// layout, mounting, accessibility and actual SVG rendering are outside these cases.
export function stateDOM() {
  const ids = new Map(), plots = [];
  const matches = (node, selector) => selector.startsWith('#') ? node.id === selector.slice(1)
    : selector.startsWith('.') ? String(node.className||'').split(' ').includes(selector.slice(1)) : node.tagName === selector;
  function element(tag) {
    const node = {tagName: tag, children: [], listeners: {}, attrs: {}, style: {}, dataset: {},
      value: '', id: '', className: '', textContent: '', checked: false, parentElement: null,
      setAttribute(key, value) {this.attrs[key] = String(value); if (key === 'id') {this.id=String(value);ids.set(this.id,this);} if(key==='value')this.value=String(value); if(key==='class')this.className=String(value);},
      getAttribute(key) {return this.attrs[key] ?? null;}, removeAttribute(key) {delete this.attrs[key];},
      appendChild(child) {this.children.push(child);child.parentElement=this;if(this.tagName==='select' && this.children.length===1)this.value=child.value;return child;},
      append(...children) {children.forEach(child=>this.appendChild(child !== null && typeof child === 'object' ? child : {textContent:String(child),children:[]}));},
      addEventListener(name, fn) {(this.listeners[name]??=[]).push(fn);},
      querySelectorAll(selector) {const found=[];const visit=n=>{for(const child of n.children||[]){if(matches(child,selector))found.push(child);visit(child);}};visit(this);return found;},
      querySelector(selector) {return this.querySelectorAll(selector)[0] ?? null;},
      closest(selector) {let n=this;while(n){if(matches(n,selector))return n;n=n.parentElement;}return null;},
      insertBefore(child) {return this.appendChild(child);}, remove() {}, focus() {},
      classList: {add() {}, remove() {}, toggle() {}, contains() {return false;}},
    };
    return node;
  }
  const document = {createElement:element,createElementNS:(_,tag)=>element(tag),
    createTextNode:text=>({textContent:text,children:[]}),getElementById:id=>ids.get(id)||null,
    querySelector:selector=>selector.startsWith('#')?ids.get(selector.slice(1))||null:null,
    querySelectorAll:()=>[],addEventListener() {},body:element('body')};
  const context = {document,console:{log(){},warn(){},error(){}},
    window:{addEventListener(){},matchMedia:()=>({matches:false})},
    fetch:()=>new Promise(()=>{}), localStorage:{getItem:()=>null,setItem(){},removeItem(){}},
    setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,clearInterval(){},
    requestAnimationFrame:()=>0, cancelAnimationFrame(){},
    plotLines:(box,spec)=>{plots.push({id:box.id,spec});},
  };
  return {context,ids,plots,fire(id,event,value) {const node=ids.get(id);if(!node)throw Error('fixture control absent: '+id);node.value=String(value);for(const fn of node.listeners[event]||[])fn({target:node});}};
}
