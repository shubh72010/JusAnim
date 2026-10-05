import math, wave, struct
SR=44100; D=39.5; N=int(SR*D)
buf=[0.0]*N
def env(t,a,d,s,r,dur):
    if t<a: return t/a
    if t<a+d: return 1-(1-s)*(t-a)/d
    if t<dur-r: return s
    return max(0,s*(1-(t-(dur-r))/r))
def tone(f0,t0,dur,vol=0.2,f1=None,type='sine'):
    for i in range(int(t0*SR), min(N,int((t0+dur)*SR))):
        t=(i-t0*SR)/SR
        f=f0*(f1/f0)**(t/dur) if f1 else f0
        v=math.sin(2*math.pi*f*t) if type=='sine' else (1 if math.sin(2*math.pi*f*t)>0 else -1)*0.5
        buf[i]+=vol*v*env(t,0.02,0.1,0.7,0.2,dur)
def noise(t0,dur,vol=0.05,fc=0.9):
    st=0
    for i in range(int(t0*SR), min(N,int((t0+dur)*SR))):
        st=st*fc+0.1*(2*((i*2654435761)%1000)/1000-1)
        buf[i]+=vol*st
# S1 intro: quiet drone + blinks
tone(110,0.5,3.0,0.05); tone(165,0.5,3.0,0.03)
tone(880,1.2,0.15,0.08,type='sine'); tone(880,2.2,0.15,0.08)
# S2 explore: pentatonic plucks rising
notes=[261,294,330,392,440,523,587,659]
for k,f in enumerate(notes):
    tone(f,5+k*0.5,0.4,0.12,type='triangle' if (f:=f) else None) if False else tone(f,5+k*0.5,0.4,0.12)
# S3 void: dissonant swell + heartbeat
tone(65,9.5,6.0,0.12,f1=55); tone(92,9.5,6.0,0.08,f1=98)
for hb in (10.5,11.2,12.6,13.3): tone(60,hb,0.2,0.25)
noise(12,3,0.03)
# S4 run: fast arpeggio
for k in range(16): tone([523,659,784,1046][k%4],14.5+k*0.25,0.15,0.09)
tone(40,17.8,0.8,0.3)  # impact
# S5 dark: near silence, one high shimmer
tone(1568,20.5,2.5,0.04)
# S6 rebuild: bright major arpeggio + final chord
maj=[523,659,784,1046,1318]
for k in range(24): tone(maj[k%5],24+k*0.35,0.35,0.1)
tone(523,33,5,0.15); tone(659,33,5,0.12); tone(784,33,5,0.12); tone(1046,33,5,0.08)
# master: normalize + fade last sec
mx=max(abs(v) for v in buf) or 1
out=bytearray()
for i,v in enumerate(buf):
    t=i/SR
    fade=min(1,(D-t)/1.0) if t>D-1 else 1
    out+=struct.pack('<h',int(32767*0.8*v/mx*fade))
w=wave.open('audio.wav','wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(bytes(out)); w.close()
print('audio.wav done')
