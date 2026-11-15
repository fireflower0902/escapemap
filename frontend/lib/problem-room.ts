export const PROBLEM_DURATION=180;
export type ProblemSession={index:number;status:'ready'|'active'|'overtime'|'solved';deadline:number;remaining:number;answer:string;feedback:string};
export function readyProblem(index=0):ProblemSession{return {index,status:'ready',deadline:0,remaining:PROBLEM_DURATION,answer:'',feedback:''};}
export function remainingSeconds(session:ProblemSession,now=Date.now()){return session.status==='active'?Math.max(0,Math.ceil((session.deadline-now)/1000)):session.remaining;}
export function timerText(seconds:number){return `${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;}
export function restoreProblem(value:unknown,now=Date.now()):ProblemSession|null{
 if(!value||typeof value!=='object')return null;const s=value as ProblemSession;
 if(!Number.isInteger(s.index)||s.index<0||s.index>3||!['ready','active','overtime','solved'].includes(s.status)||!Number.isFinite(s.deadline)||!Number.isFinite(s.remaining)||s.remaining<0||s.remaining>180||typeof s.answer!=='string'||typeof s.feedback!=='string')return null;
 return {...s,status:s.status==='active'&&remainingSeconds(s,now)===0?'overtime':s.status,remaining:remainingSeconds(s,now)};
}
export const questions=[
 {category:'숫자 · 자릿수 연산',title:'물음표에 들어갈 숫자는?',description:'곱셈에 숨겨진 규칙을 찾아보세요.',lines:'11 × 11 = 4\n22 × 22 = 16\n33 × 33 = 18\n44 × 44 = ??',answer:'19',hint:'먼저 평소처럼 곱해보세요. 계산 결과의 각 자릿수에 주목해 보세요.',solution:'각 곱셈을 계산한 뒤, 결과의 각 자릿수를 더해요. 121 → 1+2+1 = 4, 484 → 4+8+4 = 16, 1089 → 1+0+8+9 = 18. 따라서 44 × 44 = 1936, 1+9+3+6 = 19예요.'},
 {category:'숫자 · 수열 추리',title:'다음 숫자를 찾아주세요.',description:'숫자 사이의 간격을 살펴보세요.',lines:'2, 6, 12\n20, 30, ?',answer:'42',hint:'숫자의 차이가 4, 6, 8, 10…으로 커지고 있어요.',solution:'숫자 사이의 차이는 4, 6, 8, 10, 12로 2씩 커져요. 30에 12를 더하면 42! n × (n + 1)의 규칙으로도 풀 수 있어요.'},
 {category:'숫자 · 규칙 찾기',title:'빈칸 속 숫자는 무엇일까요?',description:'앞의 숫자와 뒤의 숫자를 비교해 보세요.',lines:'3 → 7\n5 → 11\n8 → 17\n12 → ?',answer:'25',hint:'왼쪽 숫자를 두 배로 만든 다음, 1을 더해보세요.',solution:'왼쪽 숫자에 2를 곱하고 1을 더하는 규칙이에요. 따라서 12 × 2 + 1 = 25예요.'},
];

export const DAILY_PROBLEM_KEY='bangpick-problem-day-v2';
export function problemDay(now=Date.now()){return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(now));}
export function restoreDailyProblem(value:unknown,now=Date.now()):ProblemSession|null{
 if(!value||typeof value!=='object')return null;
 const saved=value as {day?:string;session?:unknown};
 return saved.day===problemDay(now)?restoreProblem(saved.session,now):null;
}
export function startProblem(session:ProblemSession,now=Date.now()):ProblemSession{
 return session.status==='ready'&&session.index<questions.length?{...session,status:'active',deadline:now+PROBLEM_DURATION*1000}:session;
}
export function advanceProblem(session:ProblemSession):ProblemSession{
 return session.status==='ready'?session:readyProblem(Math.min(questions.length,session.index+1));
}
