# Rebuild the chair from scratch inside Blender:
#   exec(open('/Users/kenshin/Desktop/Trama/fauteuil/blender/scripts/build_all.py').read())
#   stage_geometry(); stage_materials(); stage_studio()
# Textures are (re)generated with textures.py: wood(); boucle()
import bpy, bmesh, math, os
LIBDIR = globals().get('LIBDIR', '/Users/kenshin/Desktop/Trama/fauteuil/blender/scripts')
from mathutils import Matrix
for f in ('chairlib.py', 'parts.py', 'finish.py'):
    exec(open(os.path.join(LIBDIR, f)).read())

BLEND = '/Users/kenshin/Desktop/Trama/fauteuil/blender/fauteuil.blend'

def stage_geometry():
    for n in ('Cube', 'Light', 'Camera'):
        o = bpy.data.objects.get(n)
        if o: bpy.data.objects.remove(o, do_unlink=True)
    # placeholder materials (replaced in stage_materials)
    for n in ('Bois', 'BoisMassif', 'Tissu', 'Passepoil', 'Polypropylene', 'Aluminium'):
        if not bpy.data.materials.get(n): bpy.data.materials.new(n)
    # wooden outer shell
    w = hollow_egg('CoqueBois', 0.0, 0.014, rows=230, cols=224)
    cw = prism('_cut_wood', opening_poly(C_WOOD)); boolean(w, cw); cw.hide_viewport = True
    bm = bmesh.new(); bm.from_mesh(w.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=2e-5); bm.to_mesh(w.data); bm.free()
    ref = egg('_outer_ref', 0.0, rows=230, cols=224); ref.hide_viewport = True; ref.hide_render = True
    rim_piping(w, opening_poly(C_WOOD), ref, 'Passepoil')
    # upholstery body
    g = egg('Garnissage', 0.006)
    cu = prism('_cut_uph', opening_poly(C_UPH)); boolean(g, cu); cu.hide_viewport = True
    cols = 160
    cav = loft('_cavity', cos_space(0.30, 0.97, 90), lambda z: rrect(CA(z), CB(z), -0.9, CR(z), cols), cols)
    boolean(g, cav); cav.hide_viewport = True; cav.hide_render = True
    m = g.modifiers.new('rm', 'REMESH'); m.mode = 'VOXEL'; m.voxel_size = 0.01
    s = g.modifiers.new('sm', 'SMOOTH'); s.factor = 1.0; s.iterations = 65
    d = g.modifiers.new('sub', 'SUBSURF'); d.levels = 1
    apply_mods(g)
    decimate(g, 0.35)
    # inner shell, cushions, base
    build_inner_shell()
    cushion('Assise', (0.535, 0.58, 0.15), (0, -0.105, 0.378), 0, bevel=0.04, crown=(0, 0, 0.018), crown_front=0.012)
    cushion('CoussinLombaire', (0.36, 0.13, 0.14), (0, 0.16, 0.53), -12, bevel=0.05, crown=(0, 0, 0.0), crown_front=0.02)
    cushion('AppuiTete', (0.40, 0.10, 0.27), (0, 0.258, 0.853), -13, bevel=0.045, crown=(0, 0, 0.0), crown_front=0.02)
    build_base()
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)

PARTS = {  # name: (explode offset blender xyz, order, label, desc, material)
    'Pietement': ((0, 0, 0), 0, 'Piètement', 'Bois massif — finition mate', 'BoisMassif'),
    'Visserie': ((0, 0, 0.10), 1, 'Visserie', 'Acier inoxydable', 'Aluminium'),
    'Liaison': ((0, 0, 0.20), 2, 'Éléments de liaison', 'Aluminium usiné — finition satinée', 'Aluminium'),
    'CoqueBois': ((0, 0, 0.42), 3, 'Coque extérieure bois', 'Chêne ou noyer cintré', 'Bois'),
    'CoqueInterieure': ((0, 0, 0.78), 4, 'Coque intérieure', 'Polypropylène renforcé', 'Polypropylene'),
    'Garnissage': ((0, 0, 1.16), 5, 'Housse de revêtement', 'Tissu bouclé, cousu sur mesure', 'Tissu'),
    'Passepoil': ((0, 0, 1.16), 5, 'Surpiqûres', 'Passepoil rouge — coutures premium', 'Passepoil'),
    'Assise': ((0, -0.30, 1.30), 6, 'Coussinage', 'Mousse haute résilience', 'Tissu'),
    'CoussinLombaire': ((0, -0.38, 1.44), 7, 'Coussin lombaire', 'Soutien du bas du dos', 'Tissu'),
    'AppuiTete': ((0, -0.24, 1.62), 8, 'Appui-tête intégré', 'Soutien tout en douceur', 'Tissu'),
}

def stage_materials():
    M = {
        'Bois': pbr('Bois', tex='bois_color', rough=0.42, coat=0.15),
        'BoisMassif': pbr('BoisMassif', tex='bois_color', rough=0.45, coat=0.1),
        'Tissu': pbr('Tissu', tex='tissu_color', normal='tissu_normal', rough=0.92, sheen=0.25, sheen_tint=(0.75, 0.8, 0.7)),
        'Passepoil': pbr('Passepoil', color=(0.30, 0.012, 0.009), normal='tissu_normal', rough=0.8, sheen=0.4, sheen_tint=(1, 0.6, 0.55), nstrength=0.6),
        'Polypropylene': pbr('Polypropylene', color=(0.86, 0.86, 0.84), rough=0.45),
        'Aluminium': pbr('Aluminium', color=(0.8, 0.8, 0.8), rough=0.28, metal=1.0),
    }
    O = bpy.data.objects
    for n, (off, order, label, desc, mat) in PARTS.items():
        o = O[n]; setmat(o, M[mat])
        o['explode'] = [off[0], off[2], -off[1]]  # glTF (Y-up) coordinates
        o['order'] = order; o['label'] = label; o['desc'] = desc; o['part'] = True
    uv_cylindrical(O['CoqueBois']); uv_cylindrical(O['CoqueInterieure']); uv_legs(O['Pietement'])
    for n in ('Garnissage', 'Assise', 'CoussinLombaire', 'AppuiTete'):
        uv_box(O[n], 0.12)
        for p in O[n].data.polygons: p.use_smooth = True
    for p in O['Passepoil'].data.polygons: p.use_smooth = True
    sharp(O['CoqueBois'], 50); sharp(O['CoqueInterieure'], 50); sharp(O['Pietement'], 50)
    sharp(O['Liaison'], 35); sharp(O['Visserie'], 35)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)

def stage_studio():
    sc = bpy.context.scene
    st = bpy.data.collections.get('Studio') or bpy.data.collections.new('Studio')
    if st.name not in [c.name for c in sc.collection.children]: sc.collection.children.link(st)
    def light(name, loc, rot, energy, size, color=(1, 1, 1)):
        o = bpy.data.objects.get(name)
        if o: bpy.data.objects.remove(o)
        ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.color = color; ld.size = size
        o = bpy.data.objects.new(name, ld); st.objects.link(o)
        o.location = loc; o.rotation_euler = [math.radians(a) for a in rot]
    light('Key', (-1.8, -2.2, 2.6), (50, 0, -40), 140, 2.0, (1, 0.97, 0.92))
    light('Fill', (2.5, -1.5, 1.5), (65, 0, 55), 45, 3.0, (0.92, 0.95, 1))
    light('Rim', (0.5, 2.5, 2.2), (-55, 0, 180), 90, 2.0)
    if not bpy.data.objects.get('Sol'):
        bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=6)
        o = bm_to_obj(bm, 'Sol', st)
        m = bpy.data.materials.get('Sol') or bpy.data.materials.new('Sol'); m.use_nodes = True
        b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        b.inputs['Base Color'].default_value = (0.62, 0.61, 0.59, 1); b.inputs['Roughness'].default_value = 0.8
        o.data.materials.append(m)
    w = sc.world or bpy.data.worlds.new('World'); sc.world = w; w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs[0].default_value = (0.55, 0.55, 0.54, 1); bg.inputs[1].default_value = 0.35
    try: sc.render.engine = 'BLENDER_EEVEE'
    except TypeError: pass
    sc.view_settings.view_transform = 'AgX'
    cd = bpy.data.cameras.get('Camera') or bpy.data.cameras.new('Camera')
    cam = bpy.data.objects.get('Camera') or bpy.data.objects.new('Camera', cd)
    if cam.name not in st.objects: st.objects.link(cam)
    cam.location = (-1.55, -2.35, 1.2); cam.rotation_euler = (math.radians(80), 0, math.radians(-33))
    sc.camera = cam
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)

def stage_export(out='/Users/kenshin/Desktop/Trama/fauteuil/web/models/'):
    os.makedirs(out, exist_ok=True)
    parts = [o for o in bpy.data.objects if o.get('part')]
    for o in bpy.data.objects: o.select_set(False)
    for o in parts: o.select_set(True); o.location = (0, 0, 0)
    bpy.context.view_layer.objects.active = parts[0]
    common = dict(use_selection=True, export_extras=True, export_yup=True, export_apply=True,
                  export_image_format='JPEG', export_jpeg_quality=88, export_texcoords=True, export_normals=True,
                  export_materials='EXPORT', export_cameras=False, export_lights=False, export_animations=False)
    bpy.ops.export_scene.gltf(filepath=out+'fauteuil.glb', export_format='GLB',
                              export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
                              export_draco_position_quantization=14, export_draco_normal_quantization=10,
                              export_draco_texcoord_quantization=12, **common)
    bpy.ops.export_scene.gltf(filepath=out+'fauteuil_sans_draco.glb', export_format='GLB',
                              export_draco_mesh_compression_enable=False, **common)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
