import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {stateDOM} from '../../../lib/state_dom.mjs';
const emit=(value,code)=>{console.log(JSON.stringify(value));process.exit(code);};
try {
if(createHash('sha256').update(fs.readFileSync(new URL('../../../lib/state_dom.mjs',import.meta.url))).digest('hex')!=="90ce06d3b15e2f9143ae5c0e6506f951bab73c83cfef282adf290f32ebce3349")throw Error('Support file hash mismatch');
const env=stateDOM(), context=vm.createContext(env.context);
const code=fs.readFileSync(path.join(process.argv[2],"src/flightloads/static/workbench-plot.js"),'utf8');
new vm.Script(code,{filename:"src/flightloads/static/workbench-plot.js"}).runInContext(context,{timeout:5000});
const read=expression=>JSON.parse(JSON.stringify(vm.runInContext(expression,context,{timeout:1000})));
Object.defineProperty(context,'localStorage',{get(){throw Error('storage denied');},configurable:true});
vm.runInContext("plotSetHidden('one','lift',true)",context);
assert.deepEqual(read("Array.from(plotHiddenSeries('one'))"),['lift'],'hide survives denied storage');
assert.deepEqual(read("Array.from(plotHiddenSeries('two'))"),[],'plots are independent');
vm.runInContext("plotSetHidden('one','lift',false)",context);
assert.deepEqual(read("Array.from(plotHiddenSeries('one'))"),[],'show reverses hide');

emit({ok:true,reason:'Behavioral assertions passed'},0);
} catch(error) {
const behavioral=error.code==='ERR_ASSERTION';
emit({ok:false,reason:behavioral?error.message:'Checker could not complete',...(behavioral?{}:{error:String(error)})},behavioral?1:2);
}
