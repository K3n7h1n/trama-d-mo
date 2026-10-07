# v3 "Follow the Thread": the red piping (Passepoil) becomes the story's red thread —
# its own explode offset/label (detached from the upholstery) and the Raw Catalog
# Material-265-A red fabric (Diffuse map) from texture-blender/fil-rouge-texture.
# Run after v2.py in the same Blender session:  exec(open(v3.py).read()); stage_v3()
import bpy, os

FIL_SRC = '/Users/kenshin/Desktop/Trama/texture-blender/fil-rouge-texture/Material-265-A_'
FIL_2K = '/Users/kenshin/Desktop/Trama/fauteuil/blender/textures/fil_rouge_2k/fil_rouge_'
FIL_1K = '/Users/kenshin/Desktop/Trama/fauteuil/blender/textures/web1k/filrouge_'
FIL_CH = ('Diffuse', 'Normal', 'Roughness')

# glTF (Y-up) offset: the thread lifts off last and floats clear of the chair on its own
THREAD = dict(explode=[0.95, 1.05, 0.2], order=9, label='Le fil rouge',
              desc='Un seul fil de trame, tissé puis cousu — Material 265')

def make_fil_textures():
    """2K copies for Blender (the 4K originals are ~11 MB each), 1K for the web GLB."""
    import subprocess
    for ch in FIL_CH:
        for dst, px in ((FIL_2K + ch + '.jpg', 2048), (FIL_1K + ch + '.jpg', 1024)):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if not os.path.exists(dst):
                subprocess.run(['/usr/bin/sips', '-Z', str(px), FIL_SRC + ch + '.jpg', '--out', dst],
                               check=True, capture_output=True)

def fil_material():
    m = bpy.data.materials.get('Passepoil') or bpy.data.materials.new('Passepoil')
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (400, 0)
    b = nt.nodes.new('ShaderNodeBsdfPrincipled'); b.location = (100, 0)
    nt.links.new(b.outputs[0], out.inputs[0])
    c = tex_node(nt, FIL_2K + 'Diffuse.jpg', False, (-500, 250))
    nt.links.new(c.outputs['Color'], b.inputs['Base Color'])
    nt.nodes.active = c  # Solid/Texture viewport shows the active image node
    r = tex_node(nt, FIL_2K + 'Roughness.jpg', True, (-500, 0))
    nt.links.new(r.outputs['Color'], b.inputs['Roughness'])
    n = tex_node(nt, FIL_2K + 'Normal.jpg', True, (-500, -250))
    nm = nt.nodes.new('ShaderNodeNormalMap'); nm.location = (-200, -250); nm.inputs['Strength'].default_value = 0.7
    nt.links.new(n.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs[0], b.inputs['Normal'])
    b.inputs['Sheen Weight'].default_value = 0.25; b.inputs['Sheen Roughness'].default_value = 0.5
    m.diffuse_color = (0.42, 0.05, 0.05, 1)
    return m

def stage_v3():
    make_fil_textures()
    o = bpy.data.objects['Passepoil']
    o.data.materials.clear(); o.data.materials.append(fil_material())
    uv_cyl_fabric(o, 0.12)  # finer weave on the thin tube
    for k, v in THREAD.items(): o[k] = v
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)

def swap_fil_images(to_web):
    for im in bpy.data.images:
        for ch in FIL_CH:
            hi, lo = FIL_2K + ch + '.jpg', FIL_1K + ch + '.jpg'
            if to_web and im.filepath == hi: im.filepath = lo; im.reload()
            if not to_web and im.filepath == lo: im.filepath = hi; im.reload()
