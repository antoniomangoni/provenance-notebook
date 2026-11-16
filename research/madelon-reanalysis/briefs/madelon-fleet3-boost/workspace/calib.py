import time
import numpy as np
from vote_lib import nested_vote_cv, f_screen

tab = np.loadtxt("data/pilot.csv", delimiter=",", skiprows=1)
X, y = tab[:, :-1], tab[:, -1]
t0 = time.time()
aucs, chosen = nested_vote_cv(X, y, lambda Xx, yy: f_screen(Xx, yy, 20))
print(f"top20F seed0: cv_auc={aucs.mean():.4f} folds={np.round(aucs,3)} time={time.time()-t0:.1f}s")
print("picks:", [(c[0], c[1], c[2], c[3]) for c in chosen])
