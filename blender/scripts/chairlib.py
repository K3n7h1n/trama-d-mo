import bpy, bmesh, math
from mathutils import Vector

# ---------- interpolation ----------
def pchip(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    n = len(xs)
    if n == 1:
        return lambda x: ys[0]
    h = [xs[i+1]-xs[i] for i in range(n-1)]
    d = [(ys[i+1]-ys[i])/h[i] for i in range(n-1)]
    m = [0.0]*n
    m[0] = d[0]; m[-1] = d[-1]
    for i in range(1, n-1):
        if d[i-1]*d[i] <= 0:
            m[i] = 0.0
        else:
            w1 = 2*h[i]+h[i-1]; w2 = h[i]+2*h[i-1]
            m[i] = (w1+w2)/(w1/d[i-1]+w2/d[i])
    def f(x):
        if x <= xs[0]: return ys[0]
        if x >= xs[-1]: return ys[-1]
        i = 0
        while xs[i+1] < x: i += 1
        t = (x-xs[i])/h[i]
        h00 = 2*t**3-3*t**2+1; h10 = t**3-2*t**2+t
        h01 = -2*t**3+3*t**2; h11 = t**3-t**2
        return h00*ys[i]+h10*h[i]*m[i]+h01*ys[i+1]+h11*h[i]*m[i+1]
    return f

def catmull(ctrl, per=10):
    P = [ctrl[0]] + list(ctrl) + [ctrl[-1]]
    out = []
    for i in range(1, len(P)-2):
        p0, p1, p2, p3 = P[i-1], P[i], P[i+1], P[i+2]
        for k in range(per):
            t = k/per
            out.append(tuple(0.5*((2*p1[j]) + (-p0[j]+p2[j])*t + (2*p0[j]-5*p1[j]+4*p2[j]-p3[j])*t*t + (-p0[j]+3*p1[j]-3*p2[j]+p3[j])*t**3) for j in range(2)))
    out.append(tuple(ctrl[-1]))
    return out

# ---------- 2D sections ----------
def resample_closed(pts, k):
    N = len(pts)
    L = [0.0]
    for i in range(1, N+1):
        a = pts[i-1]; b = pts[i % N]
        L.append(L[-1]+math.hypot(b[0]-a[0], b[1]-a[1]))
    total = L[-1]
    out = []; j = 0
    for q in range(k):
        s = total*q/k
        while L[j+1] < s: j += 1
        seg = L[j+1]-L[j]
        t = 0 if seg == 0 else (s-L[j])/seg
        p0 = pts[j]; p1 = pts[(j+1) % N]
        out.append((p0[0]+(p1[0]-p0[0])*t, p0[1]+(p1[1]-p0[1])*t))
    return out

def superellipse(a, b, cy, n, k, dense=1440):
    pts = []
    for i in range(dense):
        t = 2*math.pi*i/dense
        s = math.sin(t); c = math.cos(t)
        x = a*math.copysign(abs(s)**(2/n), s)
        y = cy+b*math.copysign(abs(c)**(2/n), c)
        pts.append((x, y))
    return resample_closed(pts, k)

def rrect(a, yb, yf, r, k, dense=1440):
    r = min(r, a-1e-4, (yb-yf)/2-1e-4)
    pts = []
    def arc(cx, cy, a0, a1, m=60):
        for i in range(m):
            t = a0+(a1-a0)*i/m
            pts.append((cx+r*math.cos(t), cy+r*math.sin(t)))
    def line(p, q, m=60):
        for i in range(m):
            t = i/m
            pts.append((p[0]+(q[0]-p[0])*t, p[1]+(q[1]-p[1])*t))
    line((0, yb), (a-r, yb))
    arc(a-r, yb-r, math.pi/2, 0)
    line((a, yb-r), (a, yf+r))
    arc(a-r, yf+r, 0, -math.pi/2)
    line((a-r, yf), (-(a-r), yf))
    arc(-(a-r), yf+r, -math.pi/2, -math.pi)
    line((-a, yf+r), (-a, yb-r))
    arc(-(a-r), yb-r, math.pi, math.pi/2)
    line((-(a-r), yb), (0, yb))
    return resample_closed(pts, k)

# ---------- scene helpers ----------
def coll(name="Fauteuil"):
    c = bpy.data.collections.get(name)
    if not c:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c

def remove(name):
    o = bpy.data.objects.get(name)
    if o:
        me = o.data if o.type == 'MESH' else None
        bpy.data.objects.remove(o, do_unlink=True)
        if me and me.users == 0:
            bpy.data.meshes.remove(me)

def bm_to_obj(bm, name, collection=None):
    remove(name)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    (collection or coll()).objects.link(o)
    return o

def loft(name, zs, section_fn, cols, cap_bottom=True, cap_top=True, collection=None):
    bm = bmesh.new()
    rows = []
    for z in zs:
        pts = section_fn(z)
        rows.append([bm.verts.new((x, y, z)) for x, y in pts])
    for i in range(len(rows)-1):
        r0, r1 = rows[i], rows[i+1]
        for j in range(cols):
            bm.faces.new((r0[j], r0[(j+1) % cols], r1[(j+1) % cols], r1[j]))
    for ring, flag in ((rows[0], cap_bottom), (rows[-1], cap_top)):
        if not flag: continue
        c = Vector((0, 0, 0))
        for v in ring: c += v.co
        c /= len(ring)
        cv = bm.verts.new(c)
        for j in range(cols):
            bm.faces.new((ring[j], ring[(j+1) % cols], cv))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    return bm_to_obj(bm, name, collection)

def cos_space(z0, z1, n):
    return [z0+(z1-z0)*(1-math.cos(math.pi*i/(n-1)))/2 for i in range(n)]

def prism(name, poly, xw=1.2):
    bm = bmesh.new()
    L = [bm.verts.new((-xw, y, z)) for y, z in poly]
    R = [bm.verts.new((xw, y, z)) for y, z in poly]
    n = len(poly)
    for i in range(n):
        bm.faces.new((L[i], L[(i+1) % n], R[(i+1) % n], R[i]))
    bm.faces.new(L); bm.faces.new(R[::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    o = bm_to_obj(bm, name)
    o.display_type = 'WIRE'; o.hide_render = True
    return o

def apply_mods(o):
    dg = bpy.context.evaluated_depsgraph_get()
    oe = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(oe)
    old = o.data
    o.modifiers.clear()
    o.data = me
    if old.users == 0: bpy.data.meshes.remove(old)
    me.name = o.name

def boolean(o, cutter, op='DIFFERENCE'):
    m = o.modifiers.new('bool', 'BOOLEAN')
    m.operation = op; m.object = cutter
    try: m.solver = 'EXACT'
    except Exception: pass
    apply_mods(o)

def solidify(o, t, offset=-1.0):
    m = o.modifiers.new('solid', 'SOLIDIFY')
    m.thickness = t; m.offset = offset; m.use_even_offset = True
    apply_mods(o)

# ---------- chair shape tables (metres, front = -Y, up = Z) ----------
Z0, ZT = 0.25, 1.025
A = pchip([(0.25,0.20),(0.255,0.25),(0.265,0.30),(0.28,0.335),(0.30,0.36),(0.33,0.378),(0.38,0.388),(0.45,0.39),(0.55,0.39),(0.60,0.382),(0.65,0.36),(0.70,0.33),(0.75,0.315),(0.80,0.322),(0.87,0.35),(0.93,0.365),(0.97,0.36),(0.995,0.345),(1.01,0.32),(1.02,0.28),(1.025,0.23)])
BACK = pchip([(0.25,0.08),(0.255,0.15),(0.265,0.22),(0.28,0.27),(0.31,0.31),(0.36,0.345),(0.43,0.37),(0.52,0.39),(0.62,0.405),(0.72,0.415),(0.82,0.42),(0.90,0.418),(0.96,0.405),(0.995,0.385),(1.015,0.36),(1.025,0.32)])
FRONT = pchip([(0.25,-0.28),(0.255,-0.33),(0.265,-0.37),(0.28,-0.39),(0.31,-0.40),(0.40,-0.405),(0.55,-0.405),(0.65,-0.40),(0.75,-0.37),(0.85,-0.30),(0.95,-0.20),(1.025,-0.10)])
NEXP = pchip([(0.25,3.0),(0.6,3.2),(0.8,2.6),(1.025,2.4)])

def egg_section(d, cols):
    def f(z):
        a = A(z)-d; back = BACK(z)-d; front = FRONT(z)+d
        return superellipse(a, (back-front)/2, (back+front)/2, NEXP(z), cols)
    return f

def egg(name, d=0.0, rows=150, cols=192):
    zs = cos_space(Z0+d, ZT-d, rows)
    return loft(name, zs, egg_section(d, cols), cols)

C_WOOD = [(-0.37,0.29),(-0.355,0.34),(-0.325,0.40),(-0.27,0.465),(-0.19,0.515),(-0.08,0.548),(0.03,0.578),(0.105,0.615),(0.16,0.67),(0.19,0.74),(0.205,0.82),(0.217,0.89),(0.228,0.945),(0.245,0.99),(0.255,1.10)]
C_UPH = [(-0.5,0.64),(-0.3,0.648),(-0.12,0.653),(0.0,0.66),(0.07,0.675),(0.115,0.71),(0.14,0.76),(0.155,0.82),(0.165,0.88),(0.175,0.93),(0.19,0.975),(0.21,1.01),(0.22,1.10)]

def opening_poly(ctrl, dz=0.0, dy=0.0):
    c = [(y+dy, z+dz) for y, z in ctrl]
    curve = catmull(c, 12)
    return [(-1.2, curve[0][1])] + curve + [(curve[-1][0], 1.6), (-1.2, 1.6)]

# cavity (inside of the upholstery)
CA = pchip([(0.30,0.262),(0.33,0.278),(0.45,0.282),(0.60,0.282),(0.66,0.27),(0.72,0.24),(0.78,0.215),(0.85,0.21),(0.92,0.21),(0.945,0.2),(0.96,0.175),(0.97,0.14)])
CB = pchip([(0.30,0.20),(0.40,0.215),(0.50,0.23),(0.60,0.25),(0.70,0.27),(0.80,0.29),(0.90,0.31),(0.95,0.315),(0.97,0.305)])
CR = pchip([(0.30,0.07),(0.60,0.09),(0.75,0.13),(0.97,0.12)])

def hollow_egg(name, d_out, d_in, rows=150, cols=192):
    """Closed hollow solid between egg offsets d_out (outer) and d_in (inner)."""
    a = egg('_tmp_a', d_out, rows, cols); b = egg('_tmp_b', d_in, rows, cols)
    bm = bmesh.new(); bm.from_mesh(a.data)
    bm2 = bmesh.new(); bm2.from_mesh(b.data)
    bmesh.ops.reverse_faces(bm2, faces=bm2.faces[:])
    me_tmp = bpy.data.meshes.new('_tmp'); bm2.to_mesh(me_tmp); bm2.free()
    bm.from_mesh(me_tmp); bpy.data.meshes.remove(me_tmp)
    remove('_tmp_a'); remove('_tmp_b')
    return bm_to_obj(bm, name)
