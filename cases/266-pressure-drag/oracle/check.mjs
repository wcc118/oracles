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
vm.runInContext(`const P={requested_alpha_deg:[-5,0,5],converged_alpha_deg:[-5,0,5],nonconverged_alpha_deg:[],CL:[-.4,0,.5],CD:[.04,.015,.045],CDp:[.02,.01,.025],CM:[-.05,-.05,-.05],Top_Xtr:[.5,.5,.5],Bot_Xtr:[.6,.6,.6]};wb.results.sections={polar:P,characteristics:null,reference:null,warnings:[],evidence_level:'fixture',provenance:{engine_manifest:{engine:'fixture',version:'1',binary_sha256:'fixture'},input_script_sha256:'fixture',polar_file_sha256:'fixture'},frame:'fixture'};sectionsView();`,context);
const series=env.plots.find(p=>p.id==='wb-plot-cd')?.spec.series;
assert.ok(series,'drag plot must exist');
for(const expected of [[.04,.015,.045],[.02,.01,.025]])assert.ok(series.some(s=>JSON.stringify(s.x)===JSON.stringify([-.4,0,.5])&&JSON.stringify(s.y)===JSON.stringify(expected)),'preserve each supplied drag component');

emit({ok:true,reason:'Behavioral assertions passed'},0);
} catch(error) {
const behavioral=error.code==='ERR_ASSERTION';
emit({ok:false,reason:behavioral?error.message:'Checker could not complete',...(behavioral?{}:{error:String(error)})},behavioral?1:2);
}
