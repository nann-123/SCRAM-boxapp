#!/usr/bin/python
# Filename : Mcnubtest_v1.py
import os, sys
import array

import coefficient_repartition as cr
name='coef_s5_f3_b7.nc'
#cr.Init("config2.lua", "default")

#cr.Init("config3f_i.lua", "default")
cr.Init("configauto.lua", "default")
cr.GeneralSection.GetCompositionDiscretization()
cr.GeneralSection.GetDiameterDiscretization()

coef = cr.RepartitionCoefficient()

# To compute all couples at at time:
coef.ComputeAll()

# At last write coefficients in a NEtCDF file:
#os.remove(name)
coef.WriteNetCDF(name)
#coef.WriteBIN(name)
#coef.WriteTXT(name)
