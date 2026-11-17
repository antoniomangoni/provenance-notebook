import json, sys, time
import numpy as np
from vote_lib import nested_vote_cv, stab_screen, f_screen, KNN_GRID, KNN_P_GRID

name, seed = sys.argv[1], int(sys.argv[2])
man = len(sys.argv) > 3 and sys.argv[3] == "man"

tab = np.loadtxt("data/pilot.csv", delimiter=",", skiprows=1)
X, y = tab[:, :-1], tab[:, -1]

if name == "top20F":
    fn = lambda Xx, yy: f_screen(Xx, yy, 20)
else:
    thr = float(name[4:])
    fn = lambda Xx, yy: stab_screen(Xx, yy, thr)

t0 = time.time()
aucs, chosen = nested_vote_cv(X, y, fn, seed=seed, knn_grid=KNN_P_GRID if man else KNN_GRID)
res = {
    "screen": name, "seed": seed, "manhattan": man,
    "mean": float(aucs.mean()), "folds": [float(a) for a in aucs],
    "n_feats": [int(c[3]) for c in chosen],
    "weight": [float(c[2]) for c in chosen],
    "time": round(time.time() - t0, 1),
}
suffix = "man" if man else ""
json.dump(res, open(f"out/search/{name}_{seed}{suffix}.json", "w"))
print(json.dumps({k: res[k] for k in ("screen", "seed", "manhattan", "mean", "folds", "n_feats", "time")}))
