import struct, zlib, math, os
W,H,FPS=480,270,10
CW,CH=16,9
CX,CY=W//2,H//2
CELL=27
GX,GY=(W-CW*CELL)//2,(H-CH*CELL)//2
OUT='i%04d.png'

# cell states
NEVER=0; COLOR=1; GONE=2
grid=[[NEVER]*CW for _ in range(CH)]
col=[[None]*CW for _ in range(CH)]

palette=[(255,90,90),(90,200,255),(255,220,90),(140,255,140),(220,140,255),(255,160,80)]

def circle_cells():
    return [(x,y) for y in range(CH) for x in range(CW)]

def set_cell(x,y,c):
    if 0<=x<CW and 0<=y<CH: grid[y][x]=COLOR; col[y][x]=c

def consume(x,y):
    if 0<=x<CW and 0<=y<CH: grid[y][x]=GONE; col[y][x]=None

FC=[0]
def render_frame(path,px,py,void_x,void_y,void_r,brightness,flash,fade_black,ox=0,oy=0):
    FC[0]+=1
    brightness=brightness*(0.92+0.08*math.sin(FC[0]*0.18))
    img=bytearray(W*H*3)
    for y in range(H):
        for x in range(W):
            pass
    # fill black
    # draw cells
    for cy in range(CH):
        for cx in range(CW):
            if grid[cy][cx]==COLOR and col[cy][cx]:
                r,g,b=col[cy][cx]
                r=min(255,int(r*brightness)); g=min(255,int(g*brightness)); b=min(255,int(b*brightness))
                for yy in range(GY+cy*CELL+1-oy, GY+(cy+1)*CELL-1-oy):
                    if yy<0 or yy>=H: continue
                    for xx in range(CELL-2):
                        xpx=GX+cx*CELL+1-ox+xx
                        if 0<=xpx<W:
                            off=(yy*W+xpx)*3; img[off]=r; img[off+1]=g; img[off+2]=b
    def disc(cx,cy,r,rgb):
        r2=r*r
        x0=max(0,int(cx-r)); x1=min(W,max(0,int(cx+r)+1))
        y0=max(0,int(cy-r)); y1=min(H,max(0,int(cy+r)+1))
        for yy in range(y0,y1):
            for xx in range(x0,x1):
                if (xx-cx)**2+(yy-cy)**2<=r2:
                    o=(yy*W+xx)*3; img[o],img[o+1],img[o+2]=rgb
    if void_r>0:
        disc(void_x-ox,void_y-oy,void_r,(0,0,0))
    if px is not None:
        disc(px-ox,py-oy,CELL*0.45,(255,255,255))
    if flash:
        for i in range(len(img)): img[i]=255
    if fade_black>0:
        img=bytearray(int(v*(1-fade_black)) for v in img) if False else img
        for i in range(0,len(img),3):
            img[i]=int(img[i]*(1-fade_black)); img[i+1]=int(img[i+1]*(1-fade_black)); img[i+2]=int(img[i+2]*(1-fade_black))
    rows=[]
    for y in range(H):
        rows.append(b'\x00'+bytes(img[y*W*3:(y+1)*W*3]))
    raw=b''.join(rows)
    def chunk(tag,data):
        c=struct.pack('>I',len(data))+tag+data
        return c+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',W,H,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw,3))+chunk(b'IEND',b'')
    open(path,'wb').write(png)

def gp(cx,cy): return (GX+cx*CELL+CELL//2, GY+cy*CELL+CELL//2)

frames=[]
def emit(n, px,py, vx,vy,vr, br=1.0, flash=False, fade=0.0, ox=0,oy=0):
    for _ in range(n):
        f=OUT%len(frames); frames.append(f)
        render_frame(f,px,py,vx,vy,vr,br,flash,fade,ox,oy)

# S1 0-6s: blink, grid fade-in
wx,wy=CW//2,CH//2
set_cell(wx,wy,palette[5])
emit(8, *gp(wx,wy), 0,0,0, br=0.0)
emit(4, *gp(wx,wy), 0,0,0, br=1.0)
emit(4, None, 0, 0,0,0, br=0.0)
emit(6, *gp(wx,wy), 0,0,0, br=1.0)
for i in range(10):
    br=i/10
    for dy in range(-1,2):
        for dx in range(-1,2):
            if grid[wy+dy][wx+dx]==NEVER: set_cell(wx+dx,wy+dy,palette[i%6])
    emit(1, *gp(wx,wy), 0,0,0, br=br)
emit(8, *gp(wx,wy), 0,0,0, br=1.0)
wx+=1; set_cell(wx,wy,palette[2]); emit(10, *gp(wx,wy), 0,0,0)

# S2 6-14: tour
path=[(0,0),(2,0),(2,0),(0,2),(-3,0),(-3,0),(0,-1),(-1,-1)]
for i,(dx,dy) in enumerate(path):
    nx,ny=wx+dx,wy+dy
    ax,ay=gp(wx,wy); bx,by=gp(nx,ny)
    for tt in (0.3,0.65,1.0):
        tt=tt*tt*(3-2*tt)
        mx,my=ax+(bx-ax)*tt, ay+(by-ay)*tt
        emit(1, mx,my, 0,0,0)
    set_cell(nx,ny,palette[i%6])
    emit(2, bx,by, 0,0,0)
    wx,wy=nx,ny

# S3 14-23: void appears
vx_,vy_=GX+3*CELL, GY+3*CELL
emit(8, *gp(wx,wy), vx_,vy_,6)
for r in range(6, 90, 4):
    # consume cells overlapping
    cx_v=(vx_-GX)/CELL; cy_v=(vy_-GY)/CELL
    for cy in range(CH):
        for cx in range(CW):
            d=math.hypot(cx-cx_v, cy-cy_v)*CELL
            if d<r: consume(cx,cy)
    emit(2, *gp(wx,wy), vx_,vy_,r)

# S4 23-32: run, void wins
run=[(wx+k,wy+((k)%3)-1) for k in range(1,9)]
for i,(nx,ny) in enumerate(run):
    ax,ay=gp(wx,wy); bx,by=gp(nx,ny)
    for tt in (0.4,1.0):
        tt=tt*tt*(3-2*tt)
        mx,my=ax+(bx-ax)*tt, ay+(by-ay)*tt
        camox=int(max(-40,min(40, mx-W//2))*(1-i/len(run)))
        cx_v=(vx_-GX)/CELL; cy_v=(vy_-GY)/CELL
        r=90+i*14
        for cy in range(CH):
            for cx in range(CW):
                if math.hypot(cx-cx_v,cy-cy_v)*CELL<r: consume(cx,cy)
        set_cell(nx,ny,palette[(i+2)%6])
        emit(1, mx,my, vx_,vy_,r, ox=camox)
    wx,wy=nx,ny
for cy in range(CH):
    for cx in range(CW): grid[cy][cx]=COLOR; col[cy][cx]=palette[(cx+cy)%6]
emit(6, *gp(wx,wy), vx_,vy_,0, br=1.5)
for cy in range(CH):
    for cx in range(CW): consume(cx,cy)
emit(14, None, 0, vx_,vy_,2000)

# S5 32-42: last pixel
emit(24, None, 0, 0,0,0)
wx,wy=CW//2-3,CH//2
set_cell(wx,wy,palette[0]); emit(10, *gp(wx,wy), GX+3*CELL, GY+3*CELL, 40)
for dx,dy in [(1,0),(1,1),(0,1),(-1,1),(-1,0),(0,-1)]:
    set_cell(wx+dx,wy+dy,palette[2]); emit(4, *gp(wx+dx,wy+dy), GX+3*CELL, GY+3*CELL, 40)

# S6 42-55: rebuild
for r in range(0, 260, 6):
    cx_v=(GX+3*CELL-GX)/CELL; cy_v=(GY+3*CELL-GY)/CELL
    vr=max(0,40-r*0.35)
    for cy in range(CH):
        for cx in range(CW):
            if grid[cy][cx]!=COLOR and math.hypot(cx-(CW//2-3),cy-(CH//2))*CELL<r:
                set_cell(cx,cy,palette[(cx*3+cy)%6])
    emit(1, *gp(wx,wy), GX+3*CELL, GY+3*CELL, vr)
emit(4, *gp(wx,wy), GX+3*CELL, GY+3*CELL, 0, flash=True)
img=[1]*1
# flash frame white
for cy in range(CH):
    for cx in range(CW): set_cell(cx,cy,palette[(cx+cy)%6])
set_cell(CW//2, CH//2, (255,255,255))
emit(30, *gp(CW//2,CH//2), 0,0,0)
# black cell beside
set_cell(CW//2+1, CH//2, (5,5,8)); grid[CH//2][CW//2+1]=COLOR; col[CH//2][CW//2+1]=(5,5,8)
emit(30, *gp(CW//2,CH//2), 0,0,0)
# fade to black
for i in range(20):
    emit(1, *gp(CW//2,CH//2), 0,0,0, fade=i/20)
print('frames:',len(frames))
