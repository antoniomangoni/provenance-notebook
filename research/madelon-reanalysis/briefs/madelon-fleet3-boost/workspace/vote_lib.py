"""Shared pilot-only screen + vote procedure. Every choice fits on pilot data only."""
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import f_classif
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def stab_screen(X, y, thr=0.3, B=200, seed=0, K=30, cap=50):
    """Features stable among the K best by F statistic across B half-resamples."""
    r = np.random.default_rng(seed)
    counts = np.zeros(X.shape[1])
    for b in range(B):
        idx = r.choice(len(y), size=len(y) // 2, replace=False)
        Fb, _ = f_classif(X[idx], y[idx])
        counts[np.argsort(-Fb)[:K]] += 1
    feats = np.where(counts / B >= thr)[0]
    if len(feats) > cap:  # safety valve; the threshold alone stays well under 50
        Ft, _ = f_classif(X, y)
        feats = feats[np.argsort(-Ft[feats])[:cap]]
    return feats


def f_screen(X, y, k=20):
    F, _ = f_classif(X, y)
    return np.argsort(-F)[:k]


RF_GRID = [
    {"max_features": "sqrt", "min_samples_leaf": 1},
    {"max_features": "sqrt", "min_samples_leaf": 5},
    {"max_features": 0.35, "min_samples_leaf": 1},
    {"max_features": 0.35, "min_samples_leaf": 5},
    {"max_features": 0.5, "min_samples_leaf": 1},
    {"max_features": 0.5, "min_samples_leaf": 5},
]
KNN_GRID = [
    {"n_neighbors": k, "weights": w}
    for k in (5, 9, 13, 17, 21, 25, 31)
    for w in ("uniform", "distance")
]
KNN_P_GRID = [dict(p, **{"metric": "manhattan"}) for p in KNN_GRID]
WS = (0.2, 0.35, 0.5, 0.65, 0.8)  # weight on RF (KNN gets 1-w)


def make_rf(p):
    return RandomForestClassifier(
        n_estimators=500, random_state=0, n_jobs=1, **p)


def make_knn(p):
    return make_pipeline(StandardScaler(), KNeighborsClassifier(**p))


def nested_vote_cv(X, y, screen_fn, n_out=5, n_in=4, seed=0, knn_grid=KNN_GRID):
    """Honest nested CV: screen, grids and vote weight chosen inside every outer fold."""
    skf = StratifiedKFold(n_out, shuffle=True, random_state=seed)
    outer, chosen = [], []
    for tr, te in skf.split(X, y):
        feats = screen_fn(X[tr], y[tr])
        Xu, yu = X[tr][:, feats], y[tr]
        inner = StratifiedKFold(n_in, shuffle=True, random_state=seed)
        best = {}
        for name, grid, mk in (("rf", RF_GRID, make_rf), ("knn", knn_grid, make_knn)):
            scores = []
            for p in grid:
                auc = []
                for itr, ite in inner.split(Xu, yu):
                    m = mk(p).fit(Xu[itr], yu[itr])
                    auc.append(roc_auc_score(yu[ite], m.predict_proba(Xu[ite])[:, 1]))
                scores.append((np.mean(auc), p))
            w_, p_ = max(scores, key=lambda t: t[0])
            best[name] = (w_, p_, mk)
        # OOF probas of the two tuned components, then pick the vote weight
        oof = {}
        for name in ("rf", "knn"):
            proba = np.zeros(len(yu))
            for itr, ite in inner.split(Xu, yu):
                m = best[name][2](best[name][1]).fit(Xu[itr], yu[itr])
                proba[ite] = m.predict_proba(Xu[ite])[:, 1]
            oof[name] = proba
        ws = {}
        for w in WS:
            blend = w * oof["rf"] + (1 - w) * oof["knn"]
            ws[w] = roc_auc_score(yu, blend)
        w = max(ws, key=ws.get)
        m_rf = best["rf"][2](best["rf"][1]).fit(Xu, yu)
        m_knn = best["knn"][2](best["knn"][1]).fit(Xu, yu)
        pe = w * m_rf.predict_proba(X[te][:, feats])[:, 1] + (1 - w) * m_knn.predict_proba(X[te][:, feats])[:, 1]
        outer.append(roc_auc_score(y[te], pe))
        chosen.append((best["rf"][1], best["knn"][1], w, len(feats)))
    return np.array(outer), chosen
