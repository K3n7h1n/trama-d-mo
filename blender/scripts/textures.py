import bpy, numpy as np, os
TEX = '/Users/kenshin/Desktop/Trama/fauteuil/blender/textures/'
os.makedirs(TEX, exist_ok=True)

def pnoise(n, scale_px, seed, ax=1.0, ay=1.0):
    rng = np.random.default_rng(seed)
    F = np.fft.fft2(rng.standard_normal((n, n)))
    fy = np.fft.fftfreq(n)[:, None]; fx = np.fft.fftfreq(n)[None, :]
    G = np.exp(-(((fx*scale_px*ax)**2)+((fy*scale_px*ay)**2))*2*np.pi**2)
    r = np.real(np.fft.ifft2(F*G)); r = (r-r.mean())/(r.std()+1e-9)
    return r

def save(name, rgb, noncolor=False):
    n = rgb.shape[0]
    img = bpy.data.images.get(name)
    if img and tuple(img.size) != (n, n):
        bpy.data.images.remove(img); img = None
    if not img:
        img = bpy.data.images.new(name, n, n, alpha=False)
    if noncolor: img.colorspace_settings.name = 'Non-Color'
    rgba = np.ones((n, n, 4), dtype=np.float32); rgba[..., :3] = np.clip(rgb, 0, 1)
    img.pixels.foreach_set(rgba[::-1].ravel())  # image rows bottom->top
    img.filepath_raw = TEX+name+'.png'; img.file_format = 'PNG'; img.save()
    img.filepath = TEX+name+'.png'
    return img

def wood(n=1024, lines=26, seed=3):
    y, x = np.mgrid[0:n, 0:n]/n
    d = pnoise(n, n/5, seed, ax=1.0, ay=5.0)*1.1 + pnoise(n, n/25, seed+1, ax=1, ay=8)*0.12
    t = (x*lines + d) % 1.0
    ring = np.clip((t-0.55)/0.45, 0, 1)**1.5
    fib = pnoise(n, 1.2, seed+2, ax=1.0, ay=60.0)
    blot = pnoise(n, n/5, seed+4, ax=1, ay=3)
    v = 0.5*ring + 0.07*fib + 0.10*blot + 0.25
    v = np.clip(v, 0, 1)
    light = np.array([0.68, 0.45, 0.27]); dark = np.array([0.40, 0.22, 0.11])
    col = light[None, None, :]*(1-v[..., None]) + dark[None, None, :]*v[..., None]
    return save('bois_color', col)

def boucle(n=1024, R=10.0, count=11000, seed=7):
    rng = np.random.default_rng(seed)
    imp = np.zeros((n, n))
    xs = rng.integers(0, n, count); ys = rng.integers(0, n, count)
    np.add.at(imp, (ys, xs), rng.uniform(0.6, 1.0, count))
    yy, xx = np.mgrid[0:n, 0:n]; yy = np.minimum(yy, n-yy); xx = np.minimum(xx, n-xx)
    r = np.sqrt(xx**2+yy**2)
    k = np.exp(-((r-R*0.55)/(R*0.22))**2)
    h = np.real(np.fft.ifft2(np.fft.fft2(imp)*np.fft.fft2(k)))
    h = np.tanh(h/np.percentile(h, 85))
    h += 0.25*pnoise(n, 3, seed+1)*0.3 + 0.15*pnoise(n, 40, seed+2)*0.3
    h = (h-h.min())/(h.max()-h.min())
    gx = (np.roll(h, -1, 1)-np.roll(h, 1, 1))/2; gy = (np.roll(h, -1, 0)-np.roll(h, 1, 0))/2
    s = 9.0
    nx, ny, nz = -gx*s, gy*s, np.ones_like(h)
    L = np.sqrt(nx**2+ny**2+nz**2)
    nrm = np.stack([nx/L, ny/L, nz/L], -1)*0.5+0.5
    save('tissu_normal', nrm, noncolor=True)
    light = np.array([0.42, 0.46, 0.35]); dark = np.array([0.15, 0.18, 0.12])
    v = h**0.8
    col = dark*(1-v[..., None]) + light*v[..., None]
    col *= (1+0.025*pnoise(n, 60, seed+3))[..., None]
    save('tissu_color', col)
    return h
