import bpy, bmesh, math
from mathutils import Vector

TEXD = '/Users/kenshin/Desktop/Trama/fauteuil/blender/textures/'

def img(name, noncolor=False):
    im = bpy.data.images.get(name)
    if not im:
        im = bpy.data.images.load(TEXD+name+'.png')
    im.name = name
    if noncolor: im.colorspace_settings.name = 'Non-Color'
    return im

def pbr(name, color=None, tex=None, normal=None, rough=0.5, metal=0.0, sheen=0.0, sheen_tint=(1, 1, 1), coat=0.0, nstrength=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (400, 0)
    b = nt.nodes.new('ShaderNodeBsdfPrincipled'); b.location = (100, 0)
    nt.links.new(b.outputs[0], out.inputs[0])
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if color: b.inputs['Base Color'].default_value = (*color, 1); m.diffuse_color = (*color, 1)
    if tex:
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(tex); t.location = (-400, 150)
        nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    if normal:
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(normal, True); t.location = (-400, -200)
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.location = (-150, -200); nm.inputs['Strength'].default_value = nstrength
        nt.links.new(t.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs[0], b.inputs['Normal'])
    if sheen:
        b.inputs['Sheen Weight'].default_value = sheen
        b.inputs['Sheen Tint'].default_value = (*sheen_tint, 1)
        b.inputs['Sheen Roughness'].default_value = 0.5
    if coat:
        b.inputs['Coat Weight'].default_value = coat; b.inputs['Coat Roughness'].default_value = 0.25
    return m

def setmat(o, m):
    o.data.materials.clear(); o.data.materials.append(m)

def uv_layer(me):
    while me.uv_layers: me.uv_layers.remove(me.uv_layers[0])
    return me.uv_layers.new(name='UVMap')

def uv_cylindrical(o, tile=0.5, R=0.38):
    me = o.data; uv = uv_layer(me)
    for p in me.polygons:
        side = 1 if p.center.x >= 0 else -1
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            ang = math.atan2(abs(co.x), -(co.y-0.02))
            uv.data[li].uv = (side*ang*R/tile + 0.5, co.z/tile)

def uv_legs(o, tile=0.35):
    me = o.data; uv = uv_layer(me)
    feet = [(0.305, -0.335), (-0.305, -0.335), (0.305, 0.36), (-0.305, 0.36)]
    tops = [(0.165, -0.165), (-0.165, -0.165), (0.165, 0.185), (-0.165, 0.185)]
    axes = []
    for (fx, fy), (tx, ty) in zip(feet, tops):
        a = Vector((fx, fy, 0.004)); b = Vector((tx, ty, 0.222)); axes.append((a, b))
    for p in me.polygons:
        c = p.center
        best = None
        for i, (a, b) in enumerate(axes):
            d = b-a; t = max(0, min(1, (c-a).dot(d)/d.length_squared))
            dist = (c-(a+d*t)).length
            if best is None or dist < best[0]: best = (dist, i, t)
        dist, i, _ = best
        a, b = axes[i]; d = (b-a).normalized()
        ref = d.orthogonal().normalized(); ref2 = d.cross(ref)
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if dist < 0.035 and c.z < 0.2:
                r = co-a; along = r.dot(d)
                rr = r-d*along
                ang = math.atan2(rr.dot(ref2), rr.dot(ref))
                if p.center.x < 0 and abs(ang) > 2.8: pass
                uv.data[li].uv = (ang*0.022/tile + i*0.3, along/tile)
            else:
                uv.data[li].uv = (co.x/tile, co.y/tile)

def smart_uv(o, tile):
    ctx = bpy.context
    for ob in bpy.data.objects: ob.select_set(False)
    o.select_set(True); ctx.view_layer.objects.active = o
    uv_layer(o.data)
    area = next(a for a in ctx.screen.areas if a.type == 'VIEW_3D')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    with ctx.temp_override(area=area, region=region, active_object=o, object=o, selected_objects=[o], selected_editable_objects=[o]):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.003, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode='OBJECT')
    rescale_uv(o, tile)

def rescale_uv(o, tile):
    me = o.data; uv = me.uv_layers.active
    A3 = sum(p.area for p in me.polygons); A2 = 0.0
    for p in me.polygons:
        pts = [uv.data[li].uv for li in p.loop_indices]
        s = 0.0
        for i in range(len(pts)):
            a = pts[i]; b = pts[(i+1) % len(pts)]
            s += a.x*b.y-b.x*a.y
        A2 += abs(s)/2
    k = math.sqrt(A3/A2)/tile
    for d in uv.data: d.uv = d.uv*k

def decimate(o, ratio):
    m = o.modifiers.new('dec', 'DECIMATE'); m.ratio = ratio
    apply_mods(o)

def sharp(o, deg):
    me = o.data
    for p in me.polygons: p.use_smooth = True
    try:
        me.set_sharp_from_angle(angle=math.radians(deg))
    except Exception as e:
        print('sharp fail', e)

def uv_box(o, tile):
    me = o.data; uv = uv_layer(me)
    for p in me.polygons:
        n = p.normal; ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            c = me.vertices[me.loops[li].vertex_index].co
            if ax == 0: u, v = c.y*(1 if n.x > 0 else -1), c.z
            elif ax == 1: u, v = c.x*(-1 if n.y > 0 else 1), c.z
            else: u, v = c.x, c.y*(1 if n.z > 0 else -1)
            uv.data[li].uv = (u/tile, v/tile)
