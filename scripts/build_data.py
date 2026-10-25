import csv, json, math, collections, sys
import numpy as np
from scipy.spatial import cKDTree

# usage: python scripts/build_data.py <folder with unzipped GTFS> <output json>
D = sys.argv[1].rstrip('/') + '/' if len(sys.argv) > 1 else 'gtfs/'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'data/curitiba_data.json'

LAT0, LON0 = -25.45, -49.27
KX = 111320 * math.cos(math.radians(LAT0))
KY = 110574.0


def xy(lat, lon):
    return ((lon - LON0) * KX, (lat - LAT0) * KY)


def rd(name):
    return csv.DictReader(open(D + name, encoding='utf-8-sig'))


def sec(t):
    h, m, s = map(int, t.split(':'))
    return h * 3600 + m * 60 + s


# groups supplied by the user. 0 = regular bus, 1 = Expresso/BRT (incl. Ligeirao), 2 = Ligeirinho
BRT_ROUTES = {'203', '302', '303', '500', '502', '503', '602', '603', 'X11', 'X12', 'X20', '250', '350', '550'}
LIG_ROUTES = {'022', '023', '024', '206', '220', '305', '307', '469', '505', '506', '507', '508', '601', '700', '702'}
SPEED = {0: 18 / 3.6, 1: 24 / 3.6, 2: 21 / 3.6}  # m/s, estimated commercial speeds


def mode_of(rid):
    return 1 if rid in BRT_ROUTES else 2 if rid in LIG_ROUTES else 0

NAMES = {r['route_id']: ' '.join(r['route_long_name'].split()) for r in rd('routes.txt')}

# stops
stops ={r['stop_id']: xy(float(r['stop_lat']), float(r['stop_lon'])) for r in rd('stops.txt')}

# shapes
shp = collections.defaultdict(list)
for r in rd('shapes.txt'):
    shp[r['shape_id']].append((int(r['shape_pt_sequence']), float(r['shape_pt_lat']), float(r['shape_pt_lon'])))
P = {}
for sid, pts in shp.items():
    pts.sort()
    P[sid] = np.array([xy(a, b) for _, a, b in pts])
sids = list(P)
allp = np.vstack([P[s] for s in sids])
lab = np.concatenate([[i] * len(P[s]) for i, s in enumerate(sids)])
tree = cKDTree(allp)
print('shapes', len(P), 'points', len(allp))

# trips
trips = {r['trip_id']: r for r in rd('trips.txt')}
seq = collections.defaultdict(list)
first_t = {}
for r in rd('stop_times.txt'):
    tid = r['trip_id']
    seq[tid].append((int(r['stop_sequence']), r['stop_id']))
    if r['arrival_time'] and tid not in first_t:
        first_t[tid] = sec(r['departure_time'] or r['arrival_time'])
print('trips with stops', len(seq))

# patterns
pat = {}
pat_list = []
trip_pat = {}
for tid, lst in seq.items():
    lst.sort()
    ids = tuple(s for _, s in lst if s in stops)
    if len(ids) < 2:
        continue
    key = (trips[tid]['route_id'], ids)
    if key not in pat:
        pat[key] = len(pat_list)
        pat_list.append(key)
    trip_pat[tid] = pat[key]
print('patterns', len(pat_list))


def dp(pts, tol):
    n = len(pts)
    if n < 3:
        return list(range(n))
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        p = pts[a + 1:b]
        d = pts[b] - pts[a]
        L = math.hypot(*d)
        if L == 0:
            dist = np.hypot(p[:, 0] - pts[a][0], p[:, 1] - pts[a][1])
        else:
            dist = np.abs(d[0] * (p[:, 1] - pts[a][1]) - d[1] * (p[:, 0] - pts[a][0])) / L
        i = int(np.argmax(dist))
        if dist[i] > tol:
            k = a + 1 + i
            keep[k] = True
            stack.append((a, k))
            stack.append((k, b))
    return list(np.nonzero(keep)[0])


paths = []
fallback = 0
for key in pat_list:
    rid, ids = key
    sp = np.array([stops[s] for s in ids])
    m = len(sp)
    sample = sp[np.unique(np.linspace(0, m - 1, min(m, 30)).astype(int))]
    cand = set(lab[i] for i in tree.query_ball_point(sample[0], 60))
    best = None
    for ci in cand:
        S = P[sids[ci]]
        prev = 0
        ds = []
        idx = []
        for x, y in sample:
            dd = np.hypot(S[prev:, 0] - x, S[prev:, 1] - y)
            j = int(np.argmin(dd))
            ds.append(dd[j])
            prev += j
            idx.append(prev)
        ds = np.array(ds)
        frac = float((ds < 60).mean())
        if frac >= 0.85 and idx[-1] > idx[0]:
            score = (frac, -float(ds.mean()))
            if best is None or score > best[0]:
                best = (score, ci, idx[0], idx[-1])
    if best:
        _, ci, i0, i1 = best
        seg = P[sids[ci]][i0:i1 + 1]
    else:
        seg = sp
        fallback += 1
    keep = dp(seg, 12.0)
    seg = seg[keep]
    L = float(np.hypot(*np.diff(seg, axis=0).T).sum())
    paths.append((seg, L, mode_of(rid), rid))
print('fallback patterns', fallback, 'of', len(pat_list))

# per-trip tables
days = {1: 'wk', 2: 'sat', 3: 'sun'}
T = {d: {'p': [], 's': [], 'e': []} for d in days.values()}
npat = [[0, 0, 0] for _ in paths]
zero = 0

# Each timetable row is the time a bus passes ONE timing stop (the id in the trip_id).
# The same bus is listed once per timing stop, so keep a single timing stop per
# (route, day type, stop pattern): the one with the most trips, ties -> earliest in the pattern.
# Loop lines are listed once per timing stop with a rotated stop list, so also merge
# groups of the same route/day that serve the same set of stops (Jaccard >= 0.95).
grp = collections.Counter()
for tid, pi in trip_pat.items():
    if tid in first_t:
        pp = tid.split('_')
        grp[(pi, pp[1], pp[2])] += 1
byrd = collections.defaultdict(list)
for (pi, dd, a), n in grp.items():
    byrd[(pat_list[pi][0], dd)].append((pi, a, n))
stopsets = {}


def sset(pi):
    if pi not in stopsets:
        stopsets[pi] = set(pat_list[pi][1])
    return stopsets[pi]


def grank(g, mx):
    pi, a, n = g
    ids = pat_list[pi][1]
    i = ids.index(a) if a in ids else 10 ** 9
    # prefer the timing stop at the start of the pattern (no offset needed) when it is nearly as complete
    return (0 if (i == 0 and n >= 0.9 * mx) else 1, -n, i)


keep_groups = set()
for (rid_, dd), lst in byrd.items():
    chosen = []
    mxn = max(g[2] for g in lst)
    for g in sorted(lst, key=lambda x: grank(x, mxn)):
        s = sset(g[0])
        if any(len(s & sset(h[0])) / max(1, len(s | sset(h[0]))) >= 0.95 for h in chosen):
            continue
        chosen.append(g)
        keep_groups.add((g[0], dd, g[1]))


def frac_along(seg, L, pt, hint):
    if L <= 0:
        return 0.0
    dseg = np.hypot(*np.diff(seg, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(dseg)])
    best = None
    for i in range(len(seg) - 1):
        a = seg[i]
        v = seg[i + 1] - a
        vv = float(v @ v)
        u = 0.0 if vv == 0 else max(0.0, min(1.0, float((pt - a) @ v) / vv))
        q = a + u * v
        if math.hypot(*(pt - q)) < 50:
            f = (cum[i] + u * dseg[i]) / L
            cand = (abs(f - hint), f)
            if best is None or cand < best:
                best = cand
    return best[1] if best else hint


fcache = {}
dropped = 0
for tid, pi in trip_pat.items():
    if tid not in first_t:
        continue
    parts = tid.split('_')
    if (pi, parts[1], parts[2]) not in keep_groups:
        dropped += 1
        continue
    d = int(parts[1])
    t0 = first_t[tid]
    if t0 < 4 * 3600:
        t0 += 86400
    if t0 == 86400:
        zero += 1
    seg, L, mode, _rid = paths[pi]
    dur = max(L / SPEED[mode], 420)
    ids = pat_list[pi][1]
    ck = (pi, parts[2])
    if ck not in fcache:
        a = parts[2]
        if a in ids and len(ids) > 1:
            hint = ids.index(a) / (len(ids) - 1)
            fcache[ck] = frac_along(seg, L, np.array(stops[a]), hint) if a in stops else hint
        else:
            fcache[ck] = 0.0
    start = t0 - fcache[ck] * dur
    T[days[d]]['p'].append(pi)
    T[days[d]]['s'].append(int(start))
    T[days[d]]['e'].append(int(start + dur))
    npat[pi][d - 1] += 1
print('duplicate timing-stop rows dropped', dropped)
print('trips at 00:00 exactly', zero)

# per-minute counts, axis starts at 04:00, 1441 points
counts = {}
for dname, t in T.items():
    out = {}
    for mode in (0, 1, 2):
        diff = np.zeros(1442, int)
        for p, s, e in zip(t['p'], t['s'], t['e']):
            if paths[p][2] != mode:
                continue
            a = max(0, (s - 4 * 3600) // 60)
            b = min(1441, (e - 4 * 3600 + 59) // 60)
            if b > a:
                diff[a] += 1
                diff[b] -= 1
        out[('bus', 'brt', 'lig')[mode]] = np.cumsum(diff)[:1441].tolist()
    counts[dname] = out
    print(dname, 'trips', len(t['p']), 'peak bus', max(out['bus']), 'peak brt', max(out['brt']), 'peak lig', max(out['lig']))

# encode
LO = 1e5
enc_paths = []
minx = miny = 1e18
maxx = maxy = -1e18
for (seg, L, mode, rid), n in zip(paths, npat):
    flat = []
    px = py = 0
    for k, (x, y) in enumerate(seg):
        lon = LON0 + x / KX
        lat = LAT0 + y / KY
        ix, iy = int(round((lon - LON0) * LO)), int(round((lat - LAT0) * LO))
        flat += [ix - px, iy - py]
        px, py = ix, iy
        minx, maxx = min(minx, lon), max(maxx, lon)
        miny, maxy = min(miny, lat), max(maxy, lat)
    enc_paths.append({'m': mode, 'L': round(L), 'n': n, 'r': rid, 'nm': NAMES.get(rid, ''), 'q': flat})
data = {'origin': [LON0, LAT0], 'scale': LO, 'bbox': [minx, miny, maxx, maxy],
        'paths': enc_paths,
        'trips': T, 'counts': counts}
json.dump(data, open(OUT, 'w'), separators=(',', ':'))
import os
print('bbox', data['bbox'], 'size MB', os.path.getsize(OUT) / 1e6)
