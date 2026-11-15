// Local .env files must never be compiled into the Worker by OpenNext.
const fs=require('node:fs');
const {spawnSync}=require('node:child_process');
const {parseEnv:parse}=require('node:util');
const files=['.env.production.local','.env.local','.env.production','.env'];
const moved=[];const env={...process.env,CLOUDFLARE_DEPLOYMENT:'true'};
try{
 for(const file of files){
  if(!fs.existsSync(file))continue;
  const values=parse(fs.readFileSync(file,'utf8'));
  for(const [key,value] of Object.entries(values)){
   if(key.startsWith('NEXT_PUBLIC_'))env[key]??=value;
   else delete env[key];
  }
  const backup=file+'.cloudflare-backup';
  if(fs.existsSync(backup))throw new Error('A previous build backup needs recovery: '+backup);
  fs.renameSync(file,backup);moved.push([file,backup]);
 }
 env.CLOUDFLARE_DEPLOYMENT='true';
 const result=spawnSync(process.execPath,['node_modules/@opennextjs/cloudflare/dist/cli/index.js','build'],{stdio:'inherit',env});
 process.exitCode=result.status??1;
}finally{for(const [file,backup]of moved.reverse())fs.renameSync(backup,file);}
