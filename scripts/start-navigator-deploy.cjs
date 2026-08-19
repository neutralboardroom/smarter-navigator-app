'use strict';
const fs=require('fs');
const path=require('path');
const http=require('http');
const {spawn}=require('child_process');

const root=path.resolve(__dirname,'..');
const target=path.join(root,'.runtime','navigator-live');
const markerPath=path.join(target,'.navigator-render-bootstrap.json');
const port=Number(process.env.PORT||10000);

function fail(message,child){console.error(`[NAVIGATOR START] ${message}`);if(child&&!child.killed)child.kill('SIGTERM');process.exit(1)}
function request(pathname){return new Promise((resolve,reject)=>{const req=http.get({hostname:'127.0.0.1',port,path:pathname,timeout:15000,headers:{'user-agent':'smarter-navigator-render-selftest/1'}},res=>{const chunks=[];res.on('data',c=>chunks.push(c));res.on('end',()=>resolve({status:res.statusCode,headers:res.headers,body:Buffer.concat(chunks).toString('utf8')}))});req.on('timeout',()=>req.destroy(new Error(`timeout ${pathname}`)));req.on('error',reject)})}
async function waitForServer(){let last;for(let i=0;i<180;i++){try{const r=await request('/healthz');if(r.status===200)return;last=new Error(`health ${r.status}`)}catch(e){last=e}await new Promise(r=>setTimeout(r,500))}throw last||new Error('server did not become healthy')}
async function selfTest(){
  const matrix=[
    ['/',200,'html'],['/healthz',200,'json'],['/readyz',200,'json'],['/reviewz',200,'json'],['/review-manifest.json',200,'json'],
    ['/home/',200,'html'],['/home/united-states/',200,'html'],['/home/help/',200,'html'],['/home/navigator/',200,'html'],['/home/community/',200,'html'],
    ['/home/professionals/',200,'html'],['/home/professionals/state-readiness/',200,'html'],['/home/professionals/membership/',200,'html'],['/home/professionals/quick-start/',200,'html'],
    ['/home/professionals/revenue-command-center/',404,'status'],['/home/api/profiles?q=test&limit=1',404,'status']
  ];
  const results=[];
  for(const [pathname,expected,kind] of matrix){
    const r=await request(pathname);
    if(r.status!==expected)throw new Error(`${pathname} status ${r.status}; expected ${expected}`);
    if(kind==='html'){
      if(!/text\/html/i.test(String(r.headers['content-type']||''))||r.body.length<500)throw new Error(`${pathname} did not return substantive HTML`);
      if(!/noindex/i.test(String(r.headers['x-robots-tag']||'')))throw new Error(`${pathname} missing noindex`);
      if(!/default-src 'self'/.test(String(r.headers['content-security-policy']||'')))throw new Error(`${pathname} missing CSP`);
    }
    if(kind==='json'){
      let parsed; try{parsed=JSON.parse(r.body)}catch{throw new Error(`${pathname} did not return JSON`)}
      if(pathname==='/healthz'&&(parsed.product!=='smarter-navigator'||parsed.version!=='0.44.0'||parsed.builder!=='NAV5.8'))throw new Error('health identity mismatch');
      if(pathname==='/readyz'&&(parsed.ok!==true||parsed.noindex!==true))throw new Error(`readyz not fail-closed review ready: ${r.body}`);
      if(pathname==='/reviewz'&&(parsed.product!=='smarter-navigator'||parsed.version!=='0.44.0'||parsed.noindex!==true))throw new Error('reviewz identity mismatch');
      if(pathname==='/review-manifest.json'&&(parsed.product!=='SMARTER NAVIGATOR'||parsed.productVersion!=='0.44.0'||parsed.builderVersion!=='NAV5.8'))throw new Error('review manifest identity mismatch');
    }
    results.push({path:pathname,status:r.status,bytes:Buffer.byteLength(r.body)});
  }
  console.log(`[NAVIGATOR LIVE SELFTEST] PASS routes=${results.length} release=0.44.0 builder=NAV5.8`);
  console.log(`[NAVIGATOR LIVE SELFTEST] ${JSON.stringify(results)}`);
}

if(!fs.existsSync(markerPath))fail('verified Navigator bootstrap marker missing');
const marker=JSON.parse(fs.readFileSync(markerPath,'utf8'));
const expectedSha=String(process.env.NAVIGATOR_DEPLOY_CARRIER_SHA256||'').trim().toLowerCase();
const expectedTree=String(process.env.NAVIGATOR_DEPLOY_SOURCE_TREE_SHA256||'').trim().toLowerCase();
if(marker.release!=='0.44.0'||marker.builder!=='NAV5.8'||marker.carrierSha256!==expectedSha||marker.canonicalSourceTreeSha256!==expectedTree)fail('deployment marker identity mismatch');

const server=path.join(target,'server.js');
const env={
  ...process.env,
  SMARTER_NAVIGATOR_PRODUCTION_MODE:'1',
  SMARTER_NAVIGATOR_TEMPORARY_REVIEW_MODE:'1',
  TEMPORARY_PROFILE_REVIEW_ENABLED:'NO',
  PUBLIC_INDEXING_ENABLED:'NO',
  PUBLIC_PROFILE_INDEXING_ENABLED:'NO',
  LIVE_PROFILE_PUBLICATION_ENABLED:'NO',
  LIVE_COMMERCE_ENABLED:'NO',
  LIVE_OUTREACH_ENABLED:'NO',
  PRODUCTION_MEMBER_CARE_EMAIL_ENABLED:'NO',
  EXTERNAL_AI_ENABLED:'NO',
  MLS_LISTINGS_ENABLED:'NO',
  SMARTER_NAVIGATOR_DEPLOYMENT_RELEASE:'0.44.0',
  SMARTER_NAVIGATOR_DEPLOYMENT_CARRIER_SHA256:marker.carrierSha256
};
console.log(`[NAVIGATOR START] launching v${marker.release} / ${marker.builder} in temporary noindex review mode`);
const child=spawn(process.execPath,['--max-old-space-size=384',server],{cwd:target,env,stdio:'inherit'});
child.on('error',e=>fail(`server failed to start: ${e.message}`,child));
child.on('exit',(code,signal)=>{if(signal){console.error(`[NAVIGATOR START] server exited via ${signal}`);process.exit(1)}process.exit(code==null?1:code)});
(async()=>{try{await waitForServer();await selfTest()}catch(e){fail(`live self-test failed: ${e.message}`,child)}})();
