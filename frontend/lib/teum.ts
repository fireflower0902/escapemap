export type Slot = { time:string; status:"available"|"full"|"closed"|"unknown"; booking_url:string|null };
export type Theme = {id:string;name:string;poster_url?:string|null;difficulty?:number|null;rating?:number|null;duration_min?:number|null;genre?:string|null;min_players?:number|null;max_players?:number|null;slots:Slot[]};
export type Cafe = {id:string;name:string;branch_name?:string|null;address:string;area?:string;website_url?:string|null;crawled:boolean;crawled_at?:string|null;themes:Theme[]};
export type Filters={date:string;area:string;from:string;to:string;difficulty?:string;minRating?:string};
export function seoulToday(){return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());}
export function validDate(value?:string){return typeof value==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value)&&Number.isFinite(Date.parse(value))&&new Date(value).toISOString().slice(0,10)===value;}
export function externalURL(value?:string|null){try{const url=new URL(value||'');return ['http:','https:'].includes(url.protocol)?url.href:null;}catch{return null;}}
export function filterCafes(cafes:Cafe[],query:string,from:string,to:string,onlyAvailable:boolean,difficulty="",minRating=""){
 const q=query.trim().toLocaleLowerCase();
 return cafes.map(cafe=>{
  const cafeMatch=`${cafe.name} ${cafe.branch_name||''} ${cafe.address}`.toLocaleLowerCase().includes(q);
  const themes=cafe.themes.filter(theme=>(cafeMatch||theme.name.toLocaleLowerCase().includes(q))&&(!difficulty||theme.difficulty===Number(difficulty))&&(!minRating||(typeof theme.rating==="number"&&theme.rating>=Number(minRating)))).map(theme=>({...theme,slots:theme.slots.filter(slot=>(!from||slot.time>=from)&&(!to||slot.time<=to))})).filter(theme=>!onlyAvailable||theme.slots.some(slot=>slot.status==='available'));
  return {...cafe,themes,matchedEmpty:!onlyAvailable&&!difficulty&&!minRating&&cafe.themes.length===0&&cafeMatch};
 }).filter(cafe=>cafe.themes.length>0||cafe.matchedEmpty).sort((a,b)=>{
  const available=(c:Cafe)=>c.themes.some(t=>t.slots.some(s=>s.status==='available'));
  return Number(available(b))-Number(available(a))||Number(b.crawled)-Number(a.crawled)||(a.name+(a.branch_name||'')).localeCompare(b.name+(b.branch_name||''),'ko');
 });
}
export function availableCount(cafe:Cafe){return cafe.themes.reduce((n,t)=>n+t.slots.filter(s=>s.status==='available').length,0);}
