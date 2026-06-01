-- Config for NC=20 coefficient file
-- Primary_Fraction_bounds:   0.0 0.2 0.8 1.0  (3 intervals)
-- Secondary_Fraction_bounds: 0.0 0.2 0.8 1.0  (3 intervals)
-- Nf=3 hardcodes frac_bound = {0.0, 0.2, 0.8, 1.0} in ClassGeneralSection.cxx
-- N_groups=5, Nb=5 size bins => NC=20

-- The number of species.
Number_species = 5

-- Particle density in g/cm3
Particle_density = 1.8

default = {
   Number_monte_carlo = 100000,

   diameter = { min = 0.001, max = 10.0, Nb = 5, Nf = 3},
   -- Nb = 5 size bins (matching scram NBIN=5)
   -- Nf = 3 => fraction bounds auto set to {0.0, 0.2, 0.8, 1.0} => NC=20
}
