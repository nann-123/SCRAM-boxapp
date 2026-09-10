#!/usr/bin/env python
# -*- coding: utf-8 -*-

import coefficient_repartition as cr

# Init the module with config file "config.lua" and the default section of config file.
cr.Init("config.lua", "default")

# The default section of config file can be omitted.
#cr.Init("config.lua")

# Issue:
cr.GeneralSection.GetCompositionDiscretization()
cr.GeneralSection.GetDiameterDiscretization()
# to see if the config file has been correctly loaded.

# Create an object containing the coefficients
# and corresponding indexes to be computed.
coef = cr.RepartitionCoefficient()

# location of the General Section
coef.GetGeneralSection(0).GetSizeBin()
coef.GetGeneralSection(0).GetCompositionBin()
coef.GetGeneralSection(34).GetSizeBin()
coef.GetGeneralSection(34).GetCompositionBin()

# You can overwrite the number of Monte Carlo of config file:
#coef = cr.RepartitionCoefficient(1000000)
# The default can be found in ClassCoefficientRepartition.hxx.

# Compute the coagulation coefficients of general sections 1 and 2:
coef.Compute(1, 2)

# See the result:
coef.GetAllIndexFirst()
coef.GetAllIndexSecond()
coef.GetAllCoefficient()

# There should have only few values, located in the first sections.
# The algorith ensures that the sum of coefficients be unity (unless to low Monte Carlo number),
# which is one of the properties of the repartition coefficients.

# To compute all couples at at time:
coef.ComputeAll()

# You do not need to clear previous values,
# the algorithm skips couples (here 1,2) already computed.
# But in case you want to restart from scratch, issue:
#coef.Clear()

# At last write coefficients in a NEtCDF file:
coef.WriteNetCDF("coef.nc")
