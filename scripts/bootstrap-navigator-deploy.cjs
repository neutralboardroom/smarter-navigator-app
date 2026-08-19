'use strict';
const fs=require('fs');
const path=require('path');
const crypto=require('crypto');
const cp=require('child_process');

const root=path.resolve(__dirname,'..');
const target=path.join(root,'.runtime','navigator-live');
const expectedSha256=String(process.env.NAVIGATOR_DEPLOY_CARRIER_SHA256||'').trim().toLowerCase();
const expectedBytes=Number(process.env.NAVIGATOR_DEPLOY_CARRIER_BYTES||0);
const expectedRelease=String(process.env.NAVIGATOR_DEPLOY_RELEASE||'').trim();
const expectedBuilder=String(process.env.NAVIGATOR_DEPLOY_BUILDER||'').trim();
const expectedTree=String(process.env.NAVIGATOR_DEPLOY_SOURCE_TREE_SHA256||'').trim().toLowerCase();

function fail(message){console.error(`[NAVIGATOR DEPLOY] ${message}`);process.exit(1)}
function assert(ok,message){if(!ok)fail(message)}
function sha(file){return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')}
function readJson(rel){const p=path.join(target,rel);assert(fs.existsSync(p),`missing required file: ${rel}`);return JSON.parse(fs.readFileSync(p,'utf8'))}

assert(/^[a-f0-9]{64}$/.test(expectedSha256),'NAVIGATOR_DEPLOY_CARRIER_SHA256 is required');
assert(Number.isInteger(expectedBytes)&&expectedBytes>0,'NAVIGATOR_DEPLOY_CARRIER_BYTES is required');
assert(/^0\.\d+\.\d+$/.test(expectedRelease),'NAVIGATOR_DEPLOY_RELEASE is required');
assert(/^NAV\d+\.\d+$/.test(expectedBuilder),'NAVIGATOR_DEPLOY_BUILDER is required');
assert(/^[a-f0-9]{64}$/.test(expectedTree),'NAVIGATOR_DEPLOY_SOURCE_TREE_SHA256 is required');

const carrierNames=fs.readdirSync(root).filter(n=>/^NAVIGATOR_DEPLOY_RUNTIME(?:\(\d+\))?\.tgz$/.test(n)).sort();
assert(carrierNames.length>0,'Navigator deployment carrier is missing');
const inspected=carrierNames.map(name=>{const file=path.join(root,name);const st=fs.statSync(file);return {name,file,bytes:st.size,sha256:sha(file)}});
const matches=inspected.filter(x=>x.bytes===expectedBytes&&x.sha256===expectedSha256);
assert(matches.length>0,`no carrier matches expected bytes/SHA-256; found ${inspected.map(x=>`${x.name}:${x.bytes}:${x.sha256}`).join(', ')}`);
const carrier=matches[0];

const members=cp.execFileSync('tar',['-tzf',carrier.file],{encoding:'utf8',maxBuffer:128*1024*1024});
let memberCount=0;
for(const raw of members.split(/\r?\n/)){
  const name=raw.trim(); if(!name) continue; memberCount++;
  const normalized=name.replace(/^\.\//,'');
  assert(!path.posix.isAbsolute(normalized),`unsafe absolute archive member: ${name}`);
  assert(!normalized.split('/').includes('..'),`unsafe parent traversal archive member: ${name}`);
}
assert(memberCount>100&&memberCount<5000,`unexpected carrier member count: ${memberCount}`);

fs.rmSync(target,{recursive:true,force:true});
fs.mkdirSync(target,{recursive:true});
cp.execFileSync('tar',['-xzf',carrier.file,'-C',target],{stdio:'inherit'});

const pkg=readJson('package.json');
assert(pkg.name==='smarter-navigator',`unexpected runtime package identity: ${pkg.name}`);
assert(pkg.version===expectedRelease,`runtime version mismatch: ${pkg.version} != ${expectedRelease}`);
const state=readJson('docs/CURRENT_PRODUCT_STATE.json');
assert(state.product==='Smarter Navigator','current product identity mismatch');
assert(state.productVersion===expectedRelease,`current product version mismatch: ${state.productVersion}`);
assert(state.builderVersion===expectedBuilder,`current builder mismatch: ${state.builderVersion}`);
assert(state.scope==='SMARTER_NAVIGATOR_ONLY','product scope mismatch');
assert(state.canonicalPublicOrigin==='https://www.smarternavigator.com','canonical production domain mismatch');

const source=readJson('SOURCE_FILE_MANIFEST.json');
assert(source.product==='SMARTER NAVIGATOR','source manifest product mismatch');
assert(source.productVersion===expectedRelease,'source manifest release mismatch');
assert(source.builderVersion===expectedBuilder,'source manifest builder mismatch');
assert(source.canonicalSourceTreeSha256===expectedTree,`source tree mismatch: ${source.canonicalSourceTreeSha256}`);
const deployId=readJson('DEPLOYMENT_SOURCE_IDENTITY.json');
assert(deployId.product==='SMARTER NAVIGATOR'&&deployId.productVersion===expectedRelease&&deployId.builderVersion===expectedBuilder,'deployment source identity mismatch');
assert(deployId.canonicalSourceTreeSha256===expectedTree,'deployment source tree mismatch');
assert(deployId.sisterProductRepositoryReuse===false,'sister-product repository reuse must be false');

const rules=readJson('governance/CANONICAL_ROGER_RULES_REGISTER.json');
assert(Number(rules.ruleCount)===382&&Number(rules.activeRuleCount)===381,'Roger Rule count mismatch');
const byId=new Map((rules.rules||[]).map(r=>[r.id,r]));
for(const id of ['HOME-RGR-BUILD-VALUE-008','HOME-RGR-NATIONAL-009','HOME-RGR-NATIONAL-010','HOME-RGR-NATIONAL-011','NAV-RGR-BRAND-012']) assert(byId.get(id)?.active===true,`required active Roger Rule missing: ${id}`);

for(const rel of ['server.js','public/home/index.html','public/home/navigator/index.html','public/home/professionals/index.html','public/home/professionals/membership/index.html','public/home/professionals/state-readiness/index.html']) assert(fs.existsSync(path.join(target,rel)),`missing deploy-critical surface: ${rel}`);
cp.execFileSync(process.execPath,['--check',path.join(target,'server.js')],{stdio:'inherit'});
const npm=process.platform==='win32'?'npm.cmd':'npm';
cp.execFileSync(npm,['--prefix',target,'ci','--omit=dev','--no-audit','--no-fund','--ignore-scripts'],{stdio:'inherit',env:{...process.env,NPM_CONFIG_AUDIT:'false',NPM_CONFIG_FUND:'false'}});
cp.execFileSync(npm,['--prefix',target,'run','deployment:validate'],{stdio:'inherit'});
cp.execFileSync(npm,['--prefix',target,'run','predeploy:check'],{stdio:'inherit'});

const marker={
  schemaVersion:'smarter-navigator.render-bootstrap.v1',
  release:expectedRelease,
  builder:expectedBuilder,
  carrier:carrier.name,
  carrierSha256:carrier.sha256,
  carrierBytes:carrier.bytes,
  carrierMembers:memberCount,
  canonicalSourceTreeSha256:expectedTree,
  canonicalDomain:'https://www.smarternavigator.com',
  rogerRuleRecords:rules.ruleCount,
  activeRogerRules:rules.activeRuleCount,
  nationalOwnerRule:'HOME-RGR-NATIONAL-009',
  maximumReasonableOwnerRule:'HOME-RGR-BUILD-VALUE-008',
  brandOwnerRule:'NAV-RGR-BRAND-012',
  preparedAt:new Date().toISOString()
};
fs.writeFileSync(path.join(target,'.navigator-render-bootstrap.json'),JSON.stringify(marker,null,2)+'\n');
console.log(`[NAVIGATOR DEPLOY] verified v${marker.release} / ${marker.builder}; carrier=${marker.carrierSha256}; tree=${marker.canonicalSourceTreeSha256}`);
