# MIPI RAW10 (RGGB) -> PNG, 2x2 binned debayer, gray-world WB, auto exposure stretch, gamma
import sys, numpy as np
from PIL import Image
f, w, h, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
order = sys.argv[5] if len(sys.argv) > 5 else 'RGGB'
d = np.fromfile(f, np.uint8)
stride = len(d) // h
d = d[:stride*h].reshape(h, stride)[:, :w*5//4].reshape(h, w//4, 5).astype(np.uint16)
p = np.empty((h, w//4, 4), np.uint16)
for i in range(4): p[:, :, i] = (d[:, :, i] << 2) | ((d[:, :, 4] >> (2*i)) & 3)
p = p.reshape(h, w).astype(np.float32) - 64
print('raw mean %.1f max %d' % (p.mean(), p.max()))
q = {k: p[y::2, x::2] for k, (y, x) in zip(order, [(0,0),(0,1),(1,0),(1,1)]) if True}
c = {'R': p[order.index('R')//2::2, order.index('R')%2::2]}
idx = [i for i, k in enumerate(order) if k == 'G']
g = (p[idx[0]//2::2, idx[0]%2::2] + p[idx[1]//2::2, idx[1]%2::2]) / 2
b = p[order.index('B')//2::2, order.index('B')%2::2]
img = np.stack([c['R'], g, b], -1).clip(0, None)
m = img.reshape(-1, 3).mean(0); img *= m[1] / np.maximum(m, 1e-3)
img /= max(np.percentile(img, 99.5), 1e-3)
img = (img.clip(0, 1) ** (1/2.2) * 255).astype(np.uint8)
Image.fromarray(img).save(out); print(out, img.shape)
