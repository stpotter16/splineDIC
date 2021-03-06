'''
.. script:: mesh_znssd_eval
    :platform: Unix, Windows
    :synopsis: Compute a NURBS DIC analysis between two images in single step

.. scriptauthor:: Sam Potter <spotter1642@gmail.com>
'''

# Path extensions (probably not necessary, but whatever)
# bootstrap $PATH
import sys
from splineDIC import numerics
from splineDIC import analysis
from splineDIC import spline
from splineDIC import knots
import cv2
import numpy as np

# Debugging
import cProfile as profile
import pdb

pr = profile.Profile()
pr.disable()

# Parse input
try:
    system = sys.argv[1]
    data = sys.argv[2]
    dx = float(sys.argv[3])
    dy = float(sys.argv[4])
    F11 = float(sys.argv[5])
    F12 = float(sys.argv[6])
    F21 = float(sys.argv[7])
    F22 = float(sys.argv[8])
except IndexError:
    print('Invalid command line arguments')
    sys.exit(1)

# Read image data
# Hard code absolute paths for now. Fix later'
if system == 'windows':
    dic_name = 'C:\\Users\\potterst1\\Desktop\\Repositories\\BitBucket\\dic\\data\\DIC_S_cropped_gray_pad_0.tiff'
    psfdi_name = 'C:\\Users\\potterst1\\Desktop\\Repositories\\BitBucket\\dic\\data\\DOA_cropped_gray_pad_0.tiff'
elif system == 'unix':
    dic_name = '/workspace/stpotter/git/bitbucket/dic/data/DIC_S_cropped_gray_pad_0.tiff'
    psfdi_name = '/workspace/stpotter/git/bitbucket/dic/data/DOA_cropped_gray_pad_0.tiff'
else:
    print('Unclear system specification')
    sys.exit(1)

if data == 'dic':
    def_image = cv2.imread(dic_name, -1)  # Read in image 'as is'
elif data == 'psfdi':
    def_image = cv2.imread(psfdi_name, -1)  # Read in image 'as is'
else:
    print('Unclear image data type')
    sys.exit(1)

# Translate image
F = np.array([[F11, F12],
              [F21, F22]])
Finv = np.linalg.inv(F)
F11i = Finv[0, 0]
F12i = Finv[0, 1]
F21i = Finv[1, 0]
F22i = Finv[1, 1]
warp = np.array([[F11i, F12i, -dx],
                 [F21i, F22i, -dy]])

# get def image interp coefficients
def_coeff = numerics.image_interp_bicubic(def_image)

# Create sub images (def)
def_sub_image = def_image[:450, :450]

# Create ref sub image
ref_sub_image = np.zeros(def_sub_image.shape)
i = 0
j = 0
for row in range(0, 450):
    for col in range(0, 450):
        # New pt (x, y)
        pt = F @ np.array([col, row]) + np.array([dx, dy])
        val = numerics.eval_interp_bicubic(def_coeff, pt[0], pt[1], def_image.shape)
        ref_sub_image[i, j] = val
        j += 1
    j = 0
    i += 1

# Specify region of interest
# Format: [column index for start of X, column index for end of X, row index for start of Y, row index for end of Y]
subregion_indices = np.array([150, 350, 150, 350])

# Control Points
rowmin_index = subregion_indices[-2:].min()
rowmax_index = subregion_indices[-2:].max()
colmin_index = subregion_indices[:2].min()
colmax_index = subregion_indices[:2].max()
x = np.linspace(colmin_index, colmax_index, 4)
y = np.linspace(rowmin_index, rowmax_index, 4)
coords = np.zeros((len(x) * len(y), 2))
k = 0
for i in range(0, len(x)):
    for j in range(0, len(y)):
        coords[k, :] = np.array([x[i], y[j]])
        k += 1

coords3d = np.column_stack((coords, np.zeros(len(coords))))

# Surface
ref_surf = spline.Surface()

ref_surf.degree_u = 2
ref_surf.degree_v = 2

num_ctrlpts = np.sqrt(len(coords)).astype('int')
ref_surf.num_ctrlpts_u = num_ctrlpts
ref_surf.num_ctrlpts_v = num_ctrlpts

ref_surf.control_points = coords3d

ref_surf.knot_vector_u = knots.generate_uniform(ref_surf.degree_u, num_ctrlpts)
ref_surf.knot_vector_v = knots.generate_uniform(ref_surf.degree_v, num_ctrlpts)


#TODO: MAKE THIS A FUNCTION
# Compute ROI and ROI uv values
# Get min and max column values from min/max reference ctrlpt node x values
min_col_index = np.min(coords[:, 0]).astype('int')
max_col_index = np.max(coords[:, 0]).astype('int')

# Get maximum column number for sub image array from ref ctrlpt node x values
colmax = (np.max(coords[:, 0]) - np.min(coords[:, 0])).astype('int')

# Get min and max column values from min/max reference ctrlpt node x values
min_row_index = np.min(coords[:, 1]).astype('int')
max_row_index = np.max(coords[:, 1]).astype('int')

# Get min and max row values from min/max reference ctrlpt node y values
rowmax = (np.max(coords[:, 1]) - np.min(coords[:, 1])).astype('int')

# Set reference image mesh over image
roi = ref_sub_image[min_row_index:max_row_index, min_col_index:max_col_index]

u = np.linspace(0, (rowmax - 1) / rowmax, rowmax)  # weird indexing hack
v = np.linspace(0, (colmax - 1) / colmax, colmax)

uu, vv = np.meshgrid(u, v)

uv_vals = np.column_stack((uu.ravel(), vv.ravel()))

#TODO: Up to here

# Get interpolation coefficients
ref_sub_coeff = numerics.image_interp_bicubic(ref_sub_image)
def_sub_coeff = numerics.image_interp_bicubic(def_sub_image)

foo = ref_surf.points(uv_vals)

# Compute reference mesh quantities of interest (array, mean, standard deviation)
f_mesh, f_mean, f_stddev = analysis.ref_mesh_qoi(ref_surf, uv_vals, ref_sub_coeff, ref_sub_image.shape)

# Test synthetically deformed control points
synth_coords = np.zeros((len(coords), 2))
for i in range(len(synth_coords)):
    synth_coords[i, :] = np.matmul(F, coords[i, :]) + np.array([dx, dy])

# Compute synthetic control point displacements
synth_coords_disp = synth_coords - coords
synth_coords_disp3d = np.column_stack((synth_coords_disp, np.zeros(len(synth_coords_disp))))

# Compute znssd between synthetic and ref coordinates
pr.enable()
# Compute znssd between synthetic and ref coordinates
synth_znssd = analysis.mesh_znssd(f_mesh, f_mean, f_stddev, def_sub_image.shape, ref_surf, uv_vals, def_sub_coeff,
                                  synth_coords_disp3d)

pr.disable()
pr.dump_stats('mesh_eval_znssd.pstat')

print('ZNSSD: {}'.format(synth_znssd))
print('Execution time:')
