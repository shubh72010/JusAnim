"""Deterministic synthesized score -> audio.wav (39.5s mono 44100Hz).
The committed wav is the reference: any rewrite must stay byte-identical
(`cmp` against it). Keep every float expression verbatim — 0.02+0.1 is NOT
0.12 in floating point, and envelope boundaries depend on it.
Usage: python3 audio.py
"""
import math, wave, sys
from array import array
SR=44100; D=39.5; N=int(SR*D)
buf=[0.0]*N
_sin=math.sin; _pi2=2*math.pi
def tone(f0,t0,dur,vol=0.2,f1=None,type='sine'):
    t0SR=t0*SR; ratio=(f1/f0) if f1 else None
    lo,hi=int(t0SR),min(N,int((t0+dur)*SR))
    tri=type!='sine'
    for i in range(lo,hi):
        t=(i-t0SR)/SR
        f=f0*ratio**(t/dur) if ratio else f0
        ph=_pi2*f*t
        v=(1 if _sin(ph)>0 else -1)*0.5 if tri else _sin(ph)
        if t<0.02: e=t/0.02
        elif t<0.02+0.1: e=1-(1-0.7)*(t-0.02)/0.1
        elif t<dur-0.2: e=0.7
        else: e=max(0,0.7*(1-(t-(dur-0.2))/0.2))
        buf[i]+=vol*v*e
def noise(t0,dur,vol=0.05,fc=0.9):
    st=0
    for i in range(int(t0*SR), min(N,int((t0+dur)*SR))):
        st=st*fc+0.1*(2*((i*2654435761)%1000)/1000-1)
        buf[i]+=vol*st
# S1 intro: quiet drone + blinks
tone(110,0.5,3.0,0.05); tone(165,0.5,3.0,0.03)
tone(880,1.2,0.15,0.08); tone(880,2.2,0.15,0.08)
# S2 explore: pentatonic plucks rising
notes=[261,294,330,392,440,523,587,659]
for k,f in enumerate(notes):
    tone(f,5+k*0.5,0.4,0.12)
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
A=32767*0.8
tail=int((D-1)*SR)
vals=[int(A*v/mx) for v in buf[:tail]]+[int(A*v/mx*min(1,(D-i/SR)/1.0)) for i,v in enumerate(buf[tail:],tail)]
out=array('h',vals)
if sys.byteorder!='little': out.byteswap()
w=wave.open('audio.wav','wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes()); w.close()
print('audio.wav done')
