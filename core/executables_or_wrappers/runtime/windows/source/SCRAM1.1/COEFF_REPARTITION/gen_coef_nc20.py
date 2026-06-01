#!/usr/bin/env python3
"""
Generate coagulation repartition coefficient file for SCRAM external mixing.

Configuration:
  N_species = 5        (aerosol groups: BC, BC+OC, OC+OA, SOA, dust)
  Nb = 5               (size bins, matching CESM scram_cesm.cfg Bin_bounds_um)
  Nf = 3               (fraction discretisation)
  frac_bound = [0.0, 0.2, 0.8, 1.0]  (same as Nf=3 hardcoded in ClassGeneralSection.cxx)
  NC = 20              (composition bins)
  Nmc = 100000         (Monte Carlo samples per pair)

Output: coef_s5_f3_b5_nc20.nc  -- matches scram_cesm.cfg Primary/Secondary bounds
"""

import numpy as np
import netCDF4 as nc
import sys, os, time

# ── configuration ──────────────────────────────────────────────────────────────
Ns        = 5          # number of aerosol groups/species
Nb        = 5          # number of size bins
Nf        = 3          # fraction intervals (=> bounds 0.0 0.2 0.8 1.0)
Nmc       = 100_000    # Monte Carlo draws per pair
density   = 1.8e-12    # g/μm³  (1.8 g/cm³)
PI_6      = np.pi / 6.0

# Size bin diameter bounds [μm] — matches scram_cesm.cfg Bin_bounds_um
diam_bounds = np.array([0.01, 0.0398, 0.1585, 0.6310, 2.5119, 10.0])
assert len(diam_bounds) == Nb + 1

# Mass bounds [g]
mass_bounds = density * PI_6 * diam_bounds**3

# Fraction bounds for Nf=3 (hardcoded in ClassGeneralSection.cxx)
frac_bounds = np.array([0.0, 0.2, 0.8, 1.0])
assert len(frac_bounds) == Nf + 1

# ── enumerate composition bins ─────────────────────────────────────────────────
# For N_groups=5, N_species=5, Nf=3:
#   groups 0..3 get fraction in [frac_bounds[idx], frac_bounds[idx+1])
#   group 4 gets remainder [0,1)
# Valid: (i0,i1,i2,i3) with frac_bounds[i0]+frac_bounds[i1]+frac_bounds[i2]+frac_bounds[i3] < 1.0

composition_bins = []   # list of [(lo0,hi0),(lo1,hi1),(lo2,hi2),(lo3,hi3)]

for i0 in range(Nf):
    for i1 in range(Nf):
        for i2 in range(Nf):
            for i3 in range(Nf):
                s = frac_bounds[i0] + frac_bounds[i1] + frac_bounds[i2] + frac_bounds[i3]
                if s < 1.0:
                    composition_bins.append([
                        (frac_bounds[i0], frac_bounds[i0+1]),
                        (frac_bounds[i1], frac_bounds[i1+1]),
                        (frac_bounds[i2], frac_bounds[i2+1]),
                        (frac_bounds[i3], frac_bounds[i3+1]),
                    ])

NC = len(composition_bins)
print(f"NC = {NC}  (expected 20)")
assert NC == 20, f"NC={NC} != 20; check fraction bounds"

Nsize = Nb * NC
Ncouple = Nsize * (Nsize + 1) // 2
print(f"Nb={Nb}, NC={NC}, Nsize={Nsize}, Ncouple={Ncouple}")

# Pre-compute composition bound matrices for fast lookup
# comp_lo[c, s], comp_hi[c, s]  for s in 0..Ns-2  (first Ns-1 species)
comp_lo = np.array([[cb[s][0] for s in range(Ns-1)] for cb in composition_bins])  # (NC, Ns-1)
comp_hi = np.array([[cb[s][1] for s in range(Ns-1)] for cb in composition_bins])  # (NC, Ns-1)

rng = np.random.default_rng(42)   # fixed seed for reproducibility

# ── vectorized sample: draw Nmc particles from general section gs ──────────────
def sample_section_vectorized(gs):
    b = gs // NC
    c = gs %  NC
    m = mass_bounds[b] + rng.random(Nmc) * (mass_bounds[b+1] - mass_bounds[b])
    frac = np.zeros((Nmc, Ns))
    frac_sum = np.zeros(Nmc)
    cb = composition_bins[c]
    frac_limit = sum(lo for (lo, _) in cb)
    avail = np.full(Nmc, 1.0 - frac_limit)
    for s in range(Ns - 1):
        lo, hi = cb[s]
        real_av = np.minimum(hi - lo, avail)
        f = lo + rng.random(Nmc) * real_av
        avail -= (f - lo)
        frac[:, s] = f
        frac_sum += f
    frac[:, Ns-1] = 1.0 - frac_sum
    return m, frac

# ── vectorized find_sections: classify all Nmc coagulated particles ────────────
def find_sections_vec(m12, frac12):
    """Return (gs_array, valid_mask) of shape (Nmc,)."""
    # Size bin: index of upper boundary that m12 first exceeds
    # mass_bounds = [mb0, mb1, ..., mbNb], len = Nb+1
    # For bin b: mass_bounds[b] <= m < mass_bounds[b+1]
    # last bin: mass_bounds[Nb-1] <= m  (no upper limit)
    b = np.searchsorted(mass_bounds[1:], m12, side='right')   # 0..Nb (Nb+1 values)
    b = np.clip(b, 0, Nb - 1)                                  # clamp overflow to last bin

    # Composition bin (vectorized over NC):
    # frac12[:, :Ns-1] — (Nmc, Ns-1)
    f = frac12[:, :Ns-1][:, np.newaxis, :]    # (Nmc, 1, Ns-1)
    lo = comp_lo[np.newaxis, :, :]             # (1, NC, Ns-1)
    hi = comp_hi[np.newaxis, :, :]             # (1, NC, Ns-1)
    in_c = np.all((f >= lo) & (f < hi), axis=2)  # (Nmc, NC) bool

    c = np.argmax(in_c, axis=1)                # (Nmc,) — first True (or 0 if none)
    valid = in_c[np.arange(Nmc), c]            # (Nmc,) — True if match found

    return b * NC + c, valid

# ── Monte Carlo computation ────────────────────────────────────────────────────
print(f"Computing {Ncouple} couples × {Nmc} MC trials …")

index1   = [[] for _ in range(Nsize)]
index2   = [[] for _ in range(Nsize)]
coeffs   = [[] for _ in range(Nsize)]

Ncompute  = 0
err_count = 0
t0 = time.time()

for i1 in range(Nsize):
    m1, frac1 = sample_section_vectorized(i1)
    for i2 in range(i1 + 1):
        m2, frac2 = sample_section_vectorized(i2)

        # Coagulate
        m12   = m1 + m2
        frac12 = (frac1 * m1[:, None] + frac2 * m2[:, None]) / m12[:, None]

        gs, valid = find_sections_vec(m12, frac12)
        err_count += int((~valid).sum())

        count = np.bincount(gs[valid], minlength=Nsize)

        for k in range(Nsize):
            if count[k] > 0:
                index1[k].append(i1)
                index2[k].append(i2)
                coeffs[k].append(float(count[k]) / float(Nmc))

        Ncompute += 1

    elapsed = time.time() - t0
    pct = 100.0 * (i1 + 1) * (i1 + 2) // 2 / Ncouple
    sys.stdout.write(f"\r  {Ncompute}/{Ncouple} ({pct:.1f}%)  elapsed={elapsed:.0f}s  err={err_count}  ")
    sys.stdout.flush()

print(f"\nDone. Ncompute={Ncompute}, err_count={err_count}")

# Fill any section with no contributions with a dummy self-entry (k, k, 0.0)
for k in range(Nsize):
    if len(coeffs[k]) == 0:
        index1[k].append(k)
        index2[k].append(k)
        coeffs[k].append(0.0)

# ── write NetCDF ───────────────────────────────────────────────────────────────
outfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'coef_s5_f3_b5_nc20.nc')
print(f"\nWriting {outfile} …")

with nc.Dataset(outfile, 'w', format='NETCDF3_CLASSIC') as ds:
    ds.createDimension('Nmc',      Nmc)
    ds.createDimension('Ns',       Ns)
    ds.createDimension('Nsize',    Nsize)
    ds.createDimension('Nb',       Nb)
    ds.createDimension('Nc',       NC)
    ds.createDimension('Ncompute', Ncompute)

    for k in range(Nsize):
        nk = len(coeffs[k])
        ds.createDimension(f'Ncoef_{k}', nk)
        v1 = ds.createVariable(f'index1_{k}', 'i4', (f'Ncoef_{k}',))
        v2 = ds.createVariable(f'index2_{k}', 'i4', (f'Ncoef_{k}',))
        vc = ds.createVariable(f'coef_{k}',   'f8', (f'Ncoef_{k}',))
        v1[:] = np.array(index1[k], dtype=np.int32)
        v2[:] = np.array(index2[k], dtype=np.int32)
        vc[:] = np.array(coeffs[k], dtype=np.float64)

print("Done.")
