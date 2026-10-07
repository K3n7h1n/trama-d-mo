import bpy, bmesh, math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

def cushion(name, size, center, rot_x=0.0, bevel=0.035, crown=(0, 0, 0.015), crown_front=0.0, mat='Tissu'):
    remove(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x*size[0], v.co.y*size[1], v.co.z*size[2]))
    o = bm_to_obj(bm, name)
    b = o.modifiers.new('bev', 'BEVEL'); b.width = bevel; b.segments = 4; b.limit_method = 'NONE'
    s = o.modifiers.new('sub', 'SUBSURF'); s.levels = 3
    apply_mods(o)
    hx, hy, hz = size[0]/2, size[1]/2, size[2]/2
    for v in o.data.vertices:
        x, y, z = v.co
        fx = max(0.0, 1-(x/hx)**2); fy = max(0.0, 1-(y/hy)**2); fz = max(0.0, 1-(z/hz)**2)
        # puff: top (+z) and front (-y) faces
        if z > 0: v.co.z += crown[2]*fx*fy*(z/hz)
        if y < 0 and crown_front: v.co.y -= crown_front*fx*fz*(-y/hy)
        if y > 0 and crown[1]: v.co.y += crown[1]*fx*fz*(y/hy)
    o.data.transform(Matrix.Translation(center) @ Matrix.Rotation(math.radians(rot_x), 4, 'X'))
    for p in o.data.polygons: p.use_smooth = True
    o.data.materials.append(bpy.data.materials[mat])
    return o

def point_seg_dist(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx-ax, by-ay
    L = dx*dx+dy*dy
    t = 0 if L == 0 else max(0, min(1, ((px-ax)*dx+(py-ay)*dy)/L))
    return math.hypot(px-(ax+t*dx), py-(ay+t*dy))

def rim_piping(shell, poly, outer_ref, name, radius=0.0065, push=0.004, mat='Passepoil', smooth_it=6, step=0.006, merge=0.0025):
    """Build a tube following the outer rim of a shell cut by an extruded YZ polygon."""
    me = shell.data
    n = len(poly)
    # bvh for outer surface
    bmo = bmesh.new(); bmo.from_mesh(outer_ref.data)
    bvh = BVHTree.FromBMesh(bmo); bmo.free()
    on_cut = []
    for v in me.vertices:
        p = (v.co.y, v.co.z)
        d = min(point_seg_dist(p, poly[i], poly[(i+1) % n]) for i in range(n))
        on_cut.append(d < 3e-4)
    outer = [False]*len(me.vertices); inner_ids = []
    for v in me.vertices:
        if not on_cut[v.index]: continue
        loc, nor, idx, dist = bvh.find_nearest(v.co)
        if dist is not None and dist < 0.004: outer[v.index] = True
        else: inner_ids.append(v.index)
    kd = KDTree(len(inner_ids))
    for i in inner_ids: kd.insert(me.vertices[i].co, i)
    kd.balance()
    ids = [i for i in range(len(me.vertices)) if outer[i]]
    parent = {i: i for i in ids}
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    kdo = KDTree(len(ids))
    for i in ids: kdo.insert(me.vertices[i].co, i)
    kdo.balance()
    for i in ids:
        for (c, j, d) in kdo.find_range(me.vertices[i].co, merge):
            ri, rj = find(i), find(j)
            if ri != rj: parent[ri] = rj
    cl = {}
    for i in ids: cl.setdefault(find(i), []).append(i)
    cpos = {r: sum((me.vertices[i].co for i in m), Vector())/len(m) for r, m in cl.items()}
    adj = {r: set() for r in cl}
    for e in me.edges:
        a, b = e.vertices
        if outer[a] and outer[b]:
            ra, rb = find(a), find(b)
            if ra != rb: adj[ra].add(rb); adj[rb].add(ra)
    start = next(r for r in adj if len(adj[r]) == 2)
    loop = [start]; seen = {start}; prev = None; cur = start
    while True:
        cand = [x for x in adj[cur] if x not in seen]
        if not cand: break
        if prev is None: nx = cand[0]
        else:
            d0 = (cpos[cur]-cpos[prev]).normalized()
            nx = max(cand, key=lambda x: (cpos[x]-cpos[cur]).normalized().dot(d0))
        prev, cur = cur, nx; seen.add(nx); loop.append(nx)
    loops = [loop, len(cl), (cpos[loop[-1]]-cpos[loop[0]]).length]
    # polygon orientation -> inward (opening side) normal of nearest segment
    area = sum(poly[i][0]*poly[(i+1) % n][1]-poly[(i+1) % n][0]*poly[i][1] for i in range(n))
    sgn = 1 if area > 0 else -1
    def push_dir(c):
        best = None
        for i in range(n):
            d = point_seg_dist((c.y, c.z), poly[i], poly[(i+1) % n])
            if best is None or d < best[0]: best = (d, i)
        a = poly[best[1]]; b = poly[(best[1]+1) % n]
        dy, dz = b[0]-a[0], b[1]-a[1]; l = math.hypot(dy, dz) or 1
        return Vector((0, -dz*sgn/l, dy*sgn/l))
    pts = []
    for r in loop:
        c = cpos[r]
        ico, _, _ = kd.find(c)
        pts.append((c+ico)/2 + push_dir(c)*push)
    # smooth + resample
    N = len(pts)
    for _ in range(smooth_it):
        pts = [(pts[(i-1) % N]+pts[i]*2+pts[(i+1) % N])/4 for i in range(N)]
    L = [0.0]
    for i in range(1, N+1): L.append(L[-1]+(pts[i % N]-pts[i-1]).length)
    total = L[-1]; k = max(8, int(total/step))
    res = []; j = 0
    for q in range(k):
        s = total*q/k
        while L[j+1] < s: j += 1
        t = (s-L[j])/max(1e-9, L[j+1]-L[j])
        res.append(pts[j].lerp(pts[(j+1) % N], t))
    # push outwards from the shell (towards the opening): use offset from the chair centre line in YZ-normal of polygon -> approximate with push along +normal of nearest outer surface projected
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'
    sp = cu.splines.new('POLY'); sp.points.add(len(res)-1)
    for i, p in enumerate(res): sp.points[i].co = (p.x, p.y, p.z, 1)
    sp.use_cyclic_u = True
    cu.bevel_depth = radius; cu.bevel_resolution = 3; cu.use_fill_caps = True
    remove(name)
    o = bpy.data.objects.new(name, cu); coll().objects.link(o)
    me2 = bpy.data.meshes.new_from_object(o.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(o); bpy.data.curves.remove(cu)
    o = bpy.data.objects.new(name, me2); coll().objects.link(o)
    for p in o.data.polygons: p.use_smooth = True
    o.data.materials.append(bpy.data.materials[mat])
    return o, len(loops[0]), loops[1:]


def cyl_between(bm, p0, p1, r0, r1, seg=32):
    p0 = Vector(p0); p1 = Vector(p1); d = p1-p0
    res = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r0, radius2=r1, depth=d.length)
    q = d.to_track_quat('Z', 'Y')
    M = Matrix.Translation((p0+p1)/2) @ q.to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=M, verts=res['verts'])
    return res

def build_base():
    # ---- wooden base (Pietement) ----
    bm = bmesh.new()
    feet = [( 0.305, -0.335), (-0.305, -0.335), ( 0.305, 0.36), (-0.305, 0.36)]
    tops = [( 0.165, -0.165), (-0.165, -0.165), ( 0.165, 0.185), (-0.165, 0.185)]
    for (fx, fy), (tx, ty) in zip(feet, tops):
        cyl_between(bm, (fx, fy, 0.0), (tx, ty, 0.212), 0.0135, 0.023)
    o = bm_to_obj(bm, 'Pietement_pieds')
    b = o.modifiers.new('bev', 'BEVEL'); b.width = 0.004; b.segments = 3; b.limit_method = 'ANGLE'
    apply_mods(o)
    # hub + arms as curves
    objs = [o]
    for (tx, ty) in tops:
        cu = bpy.data.curves.new('arm', 'CURVE'); cu.dimensions = '3D'
        sp = cu.splines.new('BEZIER'); sp.bezier_points.add(1)
        p0 = Vector((0, 0.01, 0.214)); p1 = Vector((tx, ty, 0.21))
        sp.bezier_points[0].co = p0; sp.bezier_points[1].co = p1
        mid = (p0+p1)/2 + Vector((0, 0, 0.012))
        sp.bezier_points[0].handle_left = p0-(mid-p0)*0.5; sp.bezier_points[0].handle_right = mid
        sp.bezier_points[1].handle_left = mid; sp.bezier_points[1].handle_right = p1+(p1-mid)*0.5
        cu.bevel_depth = 0.02; cu.bevel_resolution = 4; cu.use_fill_caps = True; cu.resolution_u = 16
        co = bpy.data.objects.new('arm', cu); coll().objects.link(co)
        co.scale = (1, 1, 1)
        me = bpy.data.meshes.new_from_object(co.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        bpy.data.objects.remove(co); bpy.data.curves.remove(cu)
        ao = bpy.data.objects.new('arm', me); coll().objects.link(ao); objs.append(ao)
    bm = bmesh.new()
    cyl_between(bm, (0, 0.01, 0.196), (0, 0.01, 0.232), 0.055, 0.052, 48)
    ho = bm_to_obj(bm, 'hub')
    b = ho.modifiers.new('bev', 'BEVEL'); b.width = 0.006; b.segments = 3; b.limit_method = 'ANGLE'
    apply_mods(ho); objs.append(ho)
    join(objs, 'Pietement')
    # ---- aluminium connectors (Liaison) ----
    bm = bmesh.new()
    r = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(0.21, 0.21, 0.008), verts=r['verts'])
    bmesh.ops.translate(bm, vec=(0, 0.01, 0.246), verts=r['verts'])
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        tx, ty = (0.165*sx, 0.185 if sy > 0 else -0.165)
        c = Vector((tx/2, (ty+0.01)/2, 0.241)); d = Vector((tx, ty-0.01, 0))
        r = bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(d.length, 0.03, 0.006), verts=r['verts'])
        bmesh.ops.rotate(bm, cent=Vector(), matrix=Matrix.Rotation(math.atan2(d.y, d.x), 3, 'Z'), verts=r['verts'])
        bmesh.ops.translate(bm, vec=c, verts=r['verts'])
        # end tab
        r = bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(0.04, 0.04, 0.012), verts=r['verts'])
        bmesh.ops.rotate(bm, cent=Vector(), matrix=Matrix.Rotation(math.atan2(d.y, d.x), 3, 'Z'), verts=r['verts'])
        bmesh.ops.translate(bm, vec=(tx, ty, 0.236), verts=r['verts'])
    cyl_between(bm, (0, 0.01, 0.228), (0, 0.01, 0.242), 0.045, 0.045, 48)
    lo = bm_to_obj(bm, 'Liaison')
    b = lo.modifiers.new('bev', 'BEVEL'); b.width = 0.0015; b.segments = 2; b.limit_method = 'ANGLE'
    apply_mods(lo)
    # ---- bolts (Visserie) ----
    bm = bmesh.new()
    pos = [(0.08, 0.09), (-0.08, 0.09), (0.08, -0.07), (-0.08, -0.07)]
    for x, y in pos:  # plate -> shell, pointing up
        cyl_between(bm, (x, y, 0.236), (x, y, 0.27), 0.0045, 0.0045, 16)
        cyl_between(bm, (x, y, 0.236), (x, y, 0.2415), 0.009, 0.009, 6)
    for tx, ty in [(0.165, -0.165), (-0.165, -0.165), (0.165, 0.185), (-0.165, 0.185)]:
        cyl_between(bm, (tx, ty, 0.185), (tx, ty, 0.25), 0.0045, 0.0045, 16)
        cyl_between(bm, (tx, ty, 0.244), (tx, ty, 0.2495), 0.009, 0.009, 6)
    vo = bm_to_obj(bm, 'Visserie')
    for m_, ob in (('BoisMassif', bpy.data.objects['Pietement']), ('Aluminium', lo), ('Aluminium', vo)):
        ob.data.materials.clear(); ob.data.materials.append(bpy.data.materials[m_])
        for p in ob.data.polygons: p.use_smooth = True
    for ob in (lo, vo):
        mod = ob.modifiers.new('sba', 'WEIGHTED_NORMAL') if False else None

def join(objs, name):
    bm = bmesh.new()
    for o in objs:
        me = o.data.copy(); me.transform(o.matrix_world)
        bm.from_mesh(me); bpy.data.meshes.remove(me)
    for o in objs:
        me = o.data; bpy.data.objects.remove(o)
        if me.users == 0: bpy.data.meshes.remove(me)
    return bm_to_obj(bm, name)

def build_inner_shell():
    s = hollow_egg('CoqueInterieure', 0.016, 0.024, rows=130, cols=176)
    ctrl = [(-0.30, 0.20), (-0.305, 0.33)]+[(y, z-0.035) for y, z in C_WOOD[3:]]
    cut = prism('_cut_inner', opening_poly(ctrl)); boolean(s, cut); cut.hide_viewport = True
    # screw holes
    bm = bmesh.new()
    for y, z in [(0.30, 0.82), (0.34, 0.62), (0.28, 0.44), (-0.12, 0.40), (0.08, 0.47), (0.2, 0.36)]:
        cyl_between(bm, (-0.6, y, z), (0.6, y, z), 0.007, 0.007, 16)
    for x, z in [(0.13, 0.78), (-0.13, 0.78), (0.15, 0.55), (-0.15, 0.55), (0.0, 0.9)]:
        cyl_between(bm, (x, 0.0, z), (x, 0.7, z), 0.007, 0.007, 16)
    for x, y in [(0.08, 0.09), (-0.08, 0.09), (0.08, -0.07), (-0.08, -0.07), (0.2, 0.2), (-0.2, 0.2), (0.2, -0.25), (-0.2, -0.25)]:
        cyl_between(bm, (x, y, 0.1), (x, y, 0.4), 0.007, 0.007, 16)
    h = bm_to_obj(bm, '_holes')
    m = s.modifiers.new('bool', 'BOOLEAN'); m.operation = 'DIFFERENCE'; m.object = h; m.solver = 'EXACT'; m.use_self = True
    apply_mods(s); h.hide_viewport = True; h.hide_render = True
    s.data.materials.clear(); s.data.materials.append(bpy.data.materials['Polypropylene'])
    for p in s.data.polygons: p.use_smooth = True
    return s
