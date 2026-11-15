"""Original 180-second procedural puzzle ambience; no third-party recordings.
Usage: python3 scripts/generate-problem-audio.py /tmp/problem-room.wav
Then: afconvert -f m4af -d aac@44100 /tmp/problem-room.wav public/audio/problem-room-180-v1.m4a
"""
import array,math,sys,wave
RATE=22050;SECONDS=180
CHORDS=[(196,233.082,293.665),(174.614,220,261.626),(155.563,196,233.082),(146.832,184.997,220),(174.614,220,293.665),(196,233.082,293.665)]
def pad(chord,t):
 return sum(math.sin(math.tau*f*t+0.15*math.sin(math.tau*.08*t))/(i+2) for i,f in enumerate(chord))
with wave.open(sys.argv[1],'wb') as out:
 out.setnchannels(1);out.setsampwidth(2);out.setframerate(RATE)
 for second in range(SECONDS):
  chunk=array.array('h')
  for j in range(RATE):
   t=second+j/RATE;part=int(t//30);blend=min(1,(t%30)/3)
   sound=.19*(pad(CHORDS[part],t)*blend+pad(CHORDS[max(0,part-1)],t)*(1-blend))
   bell=t%12;f=CHORDS[part][2]*2
   sound+=.05*math.exp(-bell*1.8)*(math.sin(math.tau*f*t)+.25*math.sin(math.tau*f*2*t))
   tick=t%(1 if t<150 else .5)
   sound+=.014*math.exp(-tick*65)*math.sin(math.tau*660*tick)
   fade=min(1,t/4,(SECONDS-t)/4);chunk.append(round(max(-.9,min(.9,sound*fade))*32767))
  if sys.byteorder!='little':chunk.byteswap()
  out.writeframes(chunk.tobytes())
print('Generated',SECONDS,'seconds',RATE,'Hz mono')
