# v2 fixes: shell-shaped seat, "Fatboy"-style lumbar pillow with welt, clean shell normals,
# fused wooden base, user textures (texture-blender, 2K) + 1K copies for the web export.
import bpy, bmesh, math, os
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc

UTEX = '/Users/kenshin/Desktop/Trama/texture-blender/'
WEBTEX = '/Users/kenshin/Desktop/Trama/fauteuil/blender/textures/web1k/'
TEXSETS = {
    'wood': 'Wood048_2K-PNG/Wood048_2K-PNG_',
    'fabric': 'Fabric028_2K-PNG/Fabric028_2K-PNG_',
    'plastic': 'Plastic013B_2K-PNG/Plastic013B_2K-PNG_',
}

# ---------------------------------------------------------------- geometry helpers
def ray_hit(poly, c, d):
    """Distance along ray c + t*d to the first crossing of closed 2D polygon."""
    best = None
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]; bx, by = poly[(i+1) % n]
        ex, ey = bx-ax, by-ay
        den = d[0]*ey - d[1]*ex
        if abs(den) < 1e-12: continue
        t = ((ax-c[0])*ey - (ay-c[1])*ex)/den
        u = ((ax-c[0])*d[1] - (ay-c[1])*d[0])/den
        if t > 0 and 0 <= u <= 1 and (best is None or t < best): best = t
    return best

def shaped_cushion(name, polys, c, z0, z1, R=0.035, crown=0.015, bulge=0.008, cols=160, mat='Tissu'):
    """Cushion whose footprint is the intersection of star-shaped polygons (seen from c)."""
    radii = []
    for j in range(cols):
        th = 2*math.pi*j/cols
        d = (math.sin(th), math.cos(th))  # starts at the back (+y) like the shell sections
        radii.append((d, min(ray_hit(p, c, d) for p in polys)))
    rows = []  # (inset, z, scale)
    for i in range(1, 7): rows.append((R, z0, i/6))
    for i in range(1, 9):
        ph = -math.pi/2 + (math.pi/2)*i/8
        rows.append((R*(1-math.cos(ph)), z0+R+R*math.sin(ph), 1.0))
    wall = z1-z0-2*R
    for i in range(1, 6):
        t = i/6
        rows.append((-bulge*math.sin(math.pi*t), z0+R+wall*t, 1.0))
    for i in range(0, 9):
        ph = (math.pi/2)*i/8
        rows.append((R*(1-math.cos(ph)), z1-R+R*math.sin(ph), 1.0))
    for i in range(5, 0, -1):
        s = i/6
        rows.append((R, z1+crown*(1-s*s), s))
    bm = bmesh.new()
    bot = bm.verts.new((c[0], c[1], z0)); top = bm.verts.new((c[0], c[1], z1+crown))
    ring_v = []
    for inset, z, s in rows:
        ring_v.append([bm.verts.new((c[0]+d[0]*(r-inset)*s, c[1]+d[1]*(r-inset)*s, z)) for d, r in radii])
    for a, b in zip(ring_v[:-1], ring_v[1:]):
        for j in range(cols):
            bm.faces.new((a[j], a[(j+1) % cols], b[(j+1) % cols], b[j]))
    for j in range(cols):
        bm.faces.new((ring_v[0][(j+1) % cols], ring_v[0][j], bot))
        bm.faces.new((ring_v[-1][j], ring_v[-1][(j+1) % cols], top))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if bm.calc_volume(signed=True) < 0: bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    o = bm_to_obj(bm, name)
    for p in o.data.polygons: p.use_smooth = True
    o.data.materials.append(bpy.data.materials[mat])
    return o

def pillow(name, W=0.42, H=0.25, T=0.06, kx=0.07, ky=0.12, expo=0.38, nu=64, nv=40,
           center=(0, 0.19, 0.585), tilt=-12, welt=0.0065, mat='Tissu'):
    """Rectangular throw pillow with pinched (concave) edges and a welt seam, like a Fatboy cushion."""
    def sp(n): return [math.sin(math.pi/2*(2*i/n-1)) for i in range(n+1)]
    us, vs = sp(nu), sp(nv)
    def P(u, v, side):
        x = W/2*u*(1-kx*(1-v*v)); y = H/2*v*(1-ky*(1-u*u))
        t = T*max(0.0, (1-u*u)*(1-v*v))**expo
        return Vector((x, y, side*t))
    bm = bmesh.new()
    for side in (1, -1):
        grid = [[bm.verts.new(P(u, v, side)) for u in us] for v in vs]
        for j in range(nv):
            for i in range(nu):
                q = (grid[j][i], grid[j][i+1], grid[j+1][i+1], grid[j+1][i])
                bm.faces.new(q if side > 0 else q[::-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # welt along the seam (boundary where both halves meet)
    loop = [P(u, -1, 0) for u in us[:-1]] + [P(1, v, 0) for v in vs[:-1]] + \
           [P(u, 1, 0) for u in us[::-1][:-1]] + [P(-1, v, 0) for v in vs[::-1][:-1]]
    cu = bpy.data.curves.new('_welt', 'CURVE'); cu.dimensions = '3D'
    spl = cu.splines.new('POLY'); spl.points.add(len(loop)-1)
    for i, p in enumerate(loop): spl.points[i].co = (p.x, p.y, p.z, 1)
    spl.use_cyclic_u = True; cu.bevel_depth = welt; cu.bevel_resolution = 3
    co = bpy.data.objects.new('_welt', cu); coll().objects.link(co)
    wm = bpy.data.meshes.new_from_object(co.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(co); bpy.data.curves.remove(cu)
    bm.from_mesh(wm); bpy.data.meshes.remove(wm)
    # pillow space (x, height, thickness) -> chair space, lean back, place
    M = Matrix.Translation(center) @ Matrix.Rotation(math.radians(tilt), 4, 'X') @ \
        Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts[:])
    o = bm_to_obj(bm, name)
    for p in o.data.polygons: p.use_smooth = True
    o.data.materials.append(bpy.data.materials[mat])
    return o

def clean_shell_normals(o, d_out, d_in, rows, cols, tol=1.5e-3):
    """Replace boolean shading artefacts by normals interpolated from the analytic (uncut) surfaces."""
    refs = []
    for d, sgn in ((d_out, 1), (d_in, -1)):
        r = egg('_nref', d, rows, cols)
        bm = bmesh.new(); bm.from_mesh(r.data); bm.faces.ensure_lookup_table(); bm.normal_update()
        refs.append((BVHTree.FromBMesh(bm), bm, sgn))
        remove('_nref')
    me = o.data
    for p in me.polygons: p.use_smooth = True
    if 'sharp_edge' in me.attributes: me.attributes.remove(me.attributes['sharp_edge'])
    if 'sharp_face' in me.attributes: me.attributes.remove(me.attributes['sharp_face'])
    cache = {}
    normals = [None]*len(me.loops)
    for p in me.polygons:
        c = p.center; which = None
        for k, (bvh, bm, sgn) in enumerate(refs):
            hit = bvh.find_nearest(c)
            if hit[0] is not None and hit[3] < tol and p.normal.dot(hit[1])*sgn > 0.5:
                which = k; break
        for li in p.loop_indices:
            if which is None:
                normals[li] = p.normal.copy(); continue
            vi = me.loops[li].vertex_index
            key = (vi, which)
            if key not in cache:
                bvh, bm, sgn = refs[which]
                loc, nor, fi, dist = bvh.find_nearest(me.vertices[vi].co)
                f = bm.faces[fi]
                w = poly_3d_calc([v.co for v in f.verts], loc)
                n = Vector()
                for wi, v in zip(w, f.verts): n += v.normal*wi
                cache[key] = n.normalized()*sgn
            normals[li] = cache[key]
    me.normals_split_custom_set(normals)
    for _, bm, _ in refs: bm.free()

def fuse_base():
    o = bpy.data.objects['Pietement']
    m = o.modifiers.new('rm', 'REMESH'); m.mode = 'VOXEL'; m.voxel_size = 0.0022
    s = o.modifiers.new('sm', 'SMOOTH'); s.factor = 0.8; s.iterations = 6
    apply_mods(o)
    decimate(o, 0.3)
    for p in o.data.polygons: p.use_smooth = True

# ---------------------------------------------------------------- UVs
def uv_cyl_vertical_grain(o, tile=0.5, R=0.38):
    """Cylindrical UV with u along the height so a horizontally-grained texture runs vertically."""
    me = o.data; uv = uv_layer(me)
    for p in me.polygons:
        side = 1 if p.center.x >= 0 else -1
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            ang = math.atan2(abs(co.x), -(co.y-0.02))
            uv.data[li].uv = (co.z/tile, side*ang*R/tile + 0.5)

def uv_cyl_fabric(o, tile=0.3):
    """u = arc length around the vertical axis (seam at the hidden front-centre), v = height.
    Keeps the fabric's horizontal ribs horizontal everywhere without box-projection seams."""
    me = o.data; uv = uv_layer(me)
    for p in me.polygons:
        side = 1 if p.center.x >= 0 else -1
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            r = math.hypot(co.x, co.y-0.05)
            ang = math.atan2(abs(co.x), co.y-0.05)
            uv.data[li].uv = (side*ang*r/tile + 0.5, co.z/tile)

def uv_legs_along(o, tile=0.35):
    uv_legs(o, tile)
    uv = o.data.uv_layers.active
    for d in uv.data: d.uv = (d.uv.y, d.uv.x)

# ---------------------------------------------------------------- materials
def tex_node(nt, path, noncolor, loc):
    t = nt.nodes.new('ShaderNodeTexImage'); t.location = loc
    im = bpy.data.images.load(path, check_existing=True)
    if noncolor: im.colorspace_settings.name = 'Non-Color'
    t.image = im
    return t

PIPING_TEX = '/Users/kenshin/Desktop/Trama/fauteuil/blender/textures/passepoil_color.png'

def pbr_set(name, key, rough_mult=None, color=None, nstrength=1.0, sheen=0.0, coat=0.0, color_tex=None):
    base = UTEX + TEXSETS[key]
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (400, 0)
    b = nt.nodes.new('ShaderNodeBsdfPrincipled'); b.location = (100, 0)
    nt.links.new(b.outputs[0], out.inputs[0])
    if color is None:
        c = tex_node(nt, color_tex or base+'Color.png', False, (-500, 250)); nt.links.new(c.outputs['Color'], b.inputs['Base Color'])
        nt.nodes.active = c  # Solid/Texture viewport shows the active image node
    else:
        b.inputs['Base Color'].default_value = (*color, 1)
    r = tex_node(nt, base+'Roughness.png', True, (-500, 0)); nt.links.new(r.outputs['Color'], b.inputs['Roughness'])
    n = tex_node(nt, base+'NormalGL.png', True, (-500, -250))
    nm = nt.nodes.new('ShaderNodeNormalMap'); nm.location = (-200, -250); nm.inputs['Strength'].default_value = nstrength
    nt.links.new(n.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs[0], b.inputs['Normal'])
    if sheen:
        b.inputs['Sheen Weight'].default_value = sheen; b.inputs['Sheen Roughness'].default_value = 0.5
    if coat:
        b.inputs['Coat Weight'].default_value = coat; b.inputs['Coat Roughness'].default_value = 0.3
    return m

def stage_v2_materials():
    M = {
        'Bois': pbr_set('Bois', 'wood', coat=0.1),
        'BoisMassif': pbr_set('BoisMassif', 'wood'),
        'Tissu': pbr_set('Tissu', 'fabric', sheen=0.3),
        'Passepoil': pbr_set('Passepoil', 'fabric', color_tex=PIPING_TEX, nstrength=0.6, sheen=0.3),
        'Polypropylene': pbr_set('Polypropylene', 'plastic'),
    }
    solid = {'Bois': (0.62, 0.45, 0.28), 'BoisMassif': (0.6, 0.43, 0.26), 'Tissu': (0.36, 0.38, 0.31),
             'Passepoil': (0.45, 0.03, 0.02), 'Polypropylene': (0.92, 0.91, 0.9), 'Aluminium': (0.75, 0.75, 0.75)}
    for k, c in solid.items(): bpy.data.materials[k].diffuse_color = (*c, 1)
    O = bpy.data.objects
    uv_cyl_vertical_grain(O['CoqueBois'], 0.55)
    uv_cylindrical(O['CoqueInterieure'], 0.8)
    uv_legs_along(O['Pietement'], 0.4)
    for n in ('Garnissage', 'CoussinLombaire', 'AppuiTete', 'Passepoil'):
        uv_cyl_fabric(O[n], 0.3)
    uv_box(O['Assise'], 0.3)
    return M

def make_web_textures():
    """1K JPEG copies of the 2K PNG sets for a light GLB (Blender keeps using the 2K files)."""
    import subprocess
    os.makedirs(WEBTEX, exist_ok=True)
    for key, pre in TEXSETS.items():
        for ch in ('Color', 'Roughness', 'NormalGL'):
            src = UTEX + pre + ch + '.png'; dst = WEBTEX + f'{key}_{ch}.jpg'
            if not os.path.exists(dst):
                subprocess.run(['/opt/homebrew/bin/ffmpeg', '-loglevel', 'error', '-y', '-i', src,
                                '-vf', 'scale=1024:1024', '-q:v', '3', dst], check=True)

def swap_images(to_web):
    lo_pp = WEBTEX + 'passepoil_Color.jpg'
    for im in bpy.data.images:
        fp = im.filepath
        if to_web and fp == PIPING_TEX: im.filepath = lo_pp; im.reload()
        if not to_web and fp == lo_pp: im.filepath = PIPING_TEX; im.reload()
        for key, pre in TEXSETS.items():
            for ch in ('Color', 'Roughness', 'NormalGL'):
                hi = UTEX + pre + ch + '.png'; lo = WEBTEX + f'{key}_{ch}.jpg'
                if to_web and fp == hi: im.filepath = lo; im.reload()
                if not to_web and fp == lo: im.filepath = hi; im.reload()
