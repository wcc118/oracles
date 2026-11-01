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
const code=fs.readFileSync(path.join(process.argv[2],"src/flightloads/static/workbench.js"),'utf8');
new vm.Script(code,{filename:"src/flightloads/static/workbench.js"}).runInContext(context,{timeout:5000});
const read=expression=>JSON.parse(JSON.stringify(vm.runInContext(expression,context,{timeout:1000})));
vm.runInContext(`wb.inputs={sections:{airfoil:'NACA 0012',reynolds:234567,mach:0.12,flap:{enabled:false}},'aero-3d':{definition:{geometry:{wing_chord_in:4,tail_chord_in:2}}}};`, context);
const before=read('wb.inputs.sections');
vm.runInContext('sectionsView()',context);
assert.deepEqual(read('wb.inputs.sections'),before,'render must preserve every input');

emit({ok:true,reason:'Behavioral assertions passed'},0);
} catch(error) {
const behavioral=error.code==='ERR_ASSERTION';
emit({ok:false,reason:behavioral?error.message:'Checker could not complete',...(behavioral?{}:{error:String(error)})},behavioral?1:2);
}
