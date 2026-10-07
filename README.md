# TRAMA — Follow the Thread (modèle 3D + page web)

## Contenu
- `blender/fauteuil.blend` — scène Blender (collection **Fauteuil** = pièces exportées, collection **Studio** = lumières/sol/caméra de rendu).
- `blender/scripts/` — scripts qui régénèrent tout le modèle depuis zéro (formes, découpes, passepoil, textures, export).
- Textures : celles de `../texture-blender/` (Wood048, Fabric028, Plastic013B, 2K) sont utilisées directement par le .blend.
  `blender/textures/passepoil_color.png` = le tissu Fabric028 teinté rouge pour le passepoil ;
  `blender/textures/web1k/` = copies 1K en JPEG utilisées uniquement pour l'export web.
- `web/models/fauteuil.glb` — modèle compressé Draco (~3,5 Mo, textures 1K) utilisé par la page.
- `web/models/fauteuil_sans_draco.glb` — même modèle sans compression (~11 Mo) pour Spline, three.js editor, Webflow, etc.
- `web/index.html`, `web/main.js`, `web/style.css` — page démo avec l'éclatement au scroll (three.js via CDN).

## Lancer la page en local
Le GLB doit être servi en HTTP (pas en `file://`) :

```bash
cd fauteuil/web && python3 -m http.server 5173
```
puis ouvrir http://localhost:5173

## Pièces du GLB (noms des nodes)
| Node | Pièce | Ordre |
|---|---|---|
| `Pietement` | Piètement bois massif | 0 |
| `Visserie` | Vis / boulons | 1 |
| `Liaison` | Platine + bras alu | 2 |
| `CoqueBois` | Coque extérieure bois cintré | 3 |
| `CoqueInterieure` | Coque intérieure polypropylène (percée) | 4 |
| `Garnissage` | Housse / rembourrage | 5 |
| `Passepoil` | **Le fil rouge** — se détache seul, texture Material-265-A (Diffuse) | 9 |
| `Assise` | Coussin d'assise | 6 |
| `CoussinLombaire` | Coussin lombaire | 7 |
| `AppuiTete` | Appui-tête | 8 |

Chaque node porte dans `userData` (extras glTF) :
- `explode` : décalage `[x, y, z]` en mètres (repère glTF, Y vers le haut) pour la vue éclatée,
- `order` : ordre de décollage,
- `label` / `desc` : textes des étiquettes.

Toutes les pièces ont leur origine en (0,0,0) : position éclatée = `position + explode * t` avec `t` ∈ [0,1].

## La page (récit « Follow the Thread »)
Intro → **Passé** (le fil trace les icônes Vitra) → **Présent** (atelier : le fauteuil s'ouvre, puis le fil rouge se détache seul avec sa flèche rouge) → **Futur** (espace sombre : les fils convergent, la couture s'allume, la lumière révèle TRAMA) → le rendez-vous du 26.11.2026.

- Un seul fil rouge SVG traverse toute la page (`#thread`) : il passe par chaque élément `[data-thread]` et se dessine au scroll. Dans la scène 3D, il entre par le haut, s'attache à la couture du fauteuil et ressort par le bas.
- Charte : noir, blanc, un seul rouge (`--red`), toujours en ligne ; Inter Tight / Inter.

## Régler l'animation
Dans `web/main.js` : l'objet `T` fixe les seuils du scroll (éclatement, départ du fil, solo, noir, rayons, révélation) et le tableau `K` les images-clés caméra. La hauteur de défilement de la scène se règle avec `.scrolly { height: 1100vh }` dans `style.css`.

## Régénérer depuis Blender
Dans la console Python de Blender :
```python
exec(open('/Users/kenshin/Desktop/Trama/fauteuil/blender/scripts/build_all.py').read())
stage_geometry(); stage_materials(); stage_studio()
exec(open('/Users/kenshin/Desktop/Trama/fauteuil/blender/scripts/v2.py').read())
# puis les corrections v2 (voir v2.py) : shaped_cushion('Assise', …), pillow('CoussinLombaire'),
# clean_shell_normals(…), build_base(); fuse_base(), stage_v2_materials()
exec(open('/Users/kenshin/Desktop/Trama/fauteuil/blender/scripts/v3.py').read()); stage_v3()   # fil rouge
swap_images(True); swap_fil_images(True); stage_export(); swap_images(False); swap_fil_images(False)   # export web 1K
```
Les proportions sont pilotées par les tables en fin de `chairlib.py` (`A`, `BACK`, `FRONT` = silhouette de la coque ; `C_WOOD` = ligne de découpe bois ; `C_UPH` = hauteur des accoudoirs et oreilles ; `CA/CB/CR` = creux d'assise).
