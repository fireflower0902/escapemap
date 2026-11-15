"use client";
import Link from 'next/link';
import {useEffect,useRef,useState} from 'react';
import {ArrowRight,Clock3,Volume2,VolumeX} from 'lucide-react';
import {DAILY_PROBLEM_KEY,PROBLEM_DURATION,advanceProblem,problemDay,questions,readyProblem,remainingSeconds,restoreDailyProblem,startProblem,timerText,type ProblemSession} from '@/lib/problem-room';

export default function ProblemRoom(){
 const [session,setSession]=useState<ProblemSession>(()=>readyProblem());
 const [loaded,setLoaded]=useState(false),[day,setDay]=useState('');
 const [soundOn,setSoundOn]=useState(false),[audioError,setAudioError]=useState('');
 const answerRef=useRef<HTMLInputElement>(null),audioRef=useRef<HTMLAudioElement|null>(null),dayRef=useRef('');
 useEffect(()=>{
  const load=()=>{const today=problemDay();let restored:ProblemSession|null=null;try{restored=restoreDailyProblem(JSON.parse(localStorage.getItem(DAILY_PROBLEM_KEY)||'null'));}catch{}dayRef.current=today;setDay(today);setSession(restored||readyProblem());setLoaded(true);};
  load();const storage=(event:StorageEvent)=>{if(event.key===DAILY_PROBLEM_KEY)load();};
  const interval=setInterval(()=>{if(dayRef.current!==problemDay()){setSoundOn(false);load();}},1000);
  window.addEventListener('storage',storage);return()=>{clearInterval(interval);window.removeEventListener('storage',storage);};
 },[]);
 useEffect(()=>{if(loaded&&day===problemDay())try{localStorage.setItem(DAILY_PROBLEM_KEY,JSON.stringify({day,session}));}catch{}},[loaded,day,session]);
 useEffect(()=>{
  if(session.status!=='active')return;
  const tick=()=>setSession(old=>{if(old.status!=='active')return old;const remaining=remainingSeconds(old);return remaining===old.remaining?old:{...old,remaining,status:remaining===0?'overtime':'active'};});
  tick();const id=setInterval(tick,250);return()=>clearInterval(id);
 },[session.status,session.deadline]);
 useEffect(()=>{if(session.status==='active')answerRef.current?.focus({preventScroll:true});else audioRef.current?.pause();},[session.deadline,session.status]);
 useEffect(()=>()=>{audioRef.current?.pause();},[]);
 function playAudio(active:ProblemSession){
  if(active.status!=='active')return;
  const audio=audioRef.current??(audioRef.current=new Audio('/audio/problem-room-180-v1.m4a'));
  audio.preload='none';audio.volume=.35;
  const seek=()=>{audio.currentTime=Math.max(0,Math.min(179.9,PROBLEM_DURATION-(active.deadline-Date.now())/1000));};
  if(audio.readyState>=1)seek();else audio.onloadedmetadata=seek;
  setAudioError('');void audio.play().catch(()=>{setSoundOn(false);setAudioError('소리를 재생하지 못했어요. 다시 켜 주세요.');});
 }
 function begin(){const next=startProblem(session);setSession(next);if(soundOn)playAudio(next);}
 function advance(){audioRef.current?.pause();setSession(old=>advanceProblem(old));}
 function toggleSound(){const next=!soundOn;setSoundOn(next);if(next)playAudio(session);else audioRef.current?.pause();}
 const q=questions[session.index];
 if(!loaded)return <div className="teum-state" role="status">문제방을 준비하고 있어요.</div>;
 if(!q)return <section className="teum-complete"><img src="/teum/mascot.svg" alt="문 사이에서 인사하는 고양이"/><div className="eyebrow">TODAY’S PROBLEM ROOM COMPLETE</div><h1>오늘의 문제방 완료!</h1><h2>오늘의 3문제를 모두 마쳤어요.</h2><p className="muted">포기한 문제를 포함해 하루 3문제까지 풀 수 있어요.<br/>한국 시간 자정이 지나면 다시 시작할 수 있어요.</p><Link className="primary" href="/search">방탈출 찾아보기 <ArrowRight size={16}/></Link><Link href="/">홈으로 가기</Link></section>;
 return <>
  <div className="teum-intro"><div className="eyebrow">PICK A PUZZLE</div><h1>문제방에서,<br/>3분만 집중해볼까요?</h1><p className="muted">문제마다 3분, 하루 3문제까지 도전해요.</p></div>
  <div className="quiz-wrap">
   <div className="quiz-progress"><span>오늘의 숫자 추리 · 샘플 문제</span><strong>{session.index+1} / {questions.length}</strong></div>
   <div className="quiz-track"><i style={{width:`${session.index/questions.length*100}%`}}/></div>
   <div className="problem-audio-toolbar"><button type="button" className="sound-toggle" aria-label={soundOn?'배경음 끄기':'배경음 켜기'} aria-pressed={soundOn} onClick={toggleSound}>{soundOn?<Volume2 size={17}/>:<VolumeX size={17}/>}사운드 {soundOn?'ON':'OFF'}</button><span>기본 음소거 · 문제당 3분</span></div>
   {audioError&&<p className="problem-audio-error" role="status">{audioError}</p>}
   {session.status==='ready'?<section className="problem-start"><span className="pill">{q.category}</span><img className="start-mascot" src="/teum/logo.svg" alt=""/><h2>준비됐다면, 문을 열어볼까요?</h2><p>시작 버튼을 누르면 문제가 나타나고<br/>3분 카운트다운이 시작돼요.</p><div className="start-rules"><span>◷ 문제당 3분</span><span>♡ 힌트 사용 가능</span></div><button className="primary start-problem-button" onClick={begin}><span>문제방 시작하기</span><span className="start-duration">3:00 <ArrowRight size={16}/></span></button><small>다른 메뉴를 봐도 시간은 계속 흘러요.<br/>진행 기록은 이 브라우저에 저장돼요.</small></section>:<section className="puzzle">
    <div className="problem-meta"><span className="pill">{q.category}</span><span className="timer-pill" aria-label="남은 시간"><Clock3 size={14}/><strong role="timer" aria-live="off" className={session.remaining<=30&&session.status==='active'?'urgent':''}>{timerText(session.remaining)}</strong></span></div>
    {session.status==='overtime'&&<p className="problem-timeout" role="status">3분이 지났어요. 시간 제한 없이 계속 풀어도 좋아요.</p>}
    <h2>{q.title}</h2><p className="muted">{q.description}</p><div className="numbers">{q.lines}</div>
    {session.status==='solved'?<><div className="solution"><h3>정답이에요! ✨</h3><p>{q.solution}</p></div><button className="primary" onClick={advance}>{session.index===questions.length-1?'오늘 문제방 마치기':'다음 문제로 가기'} <ArrowRight size={16}/></button></>:<>
     <form onSubmit={event=>{event.preventDefault();setSession(old=>old.answer.trim()===q.answer?{...old,status:'solved',remaining:remainingSeconds(old),feedback:''}:{...old,feedback:'한 번 더 생각해 볼까요?'});}}><label className="sr-only" htmlFor="problem-answer">문제 정답</label><input ref={answerRef} id="problem-answer" className="answer" inputMode="numeric" autoComplete="off" placeholder="정답을 입력해 주세요" value={session.answer} onChange={event=>setSession(old=>({...old,answer:event.target.value}))}/><button className="primary" type="submit">정답 입력 <ArrowRight size={16}/></button></form>
     <div className="quiz-feedback" role="status">{session.feedback}</div><button className="quiz-hint" onClick={()=>setSession(old=>({...old,feedback:q.hint}))}>♡ 힌트가 필요해요</button>
     <div className="problem-skip"><button type="button" onClick={advance}>{session.index===questions.length-1?'포기하고 오늘 문제방 마치기':'포기하고 다음 문제로'} <ArrowRight size={15}/></button><p>포기한 문제도 오늘의 3문제에 포함돼요.</p></div>
    </>}
   </section>}
  </div>
 </>;
}
