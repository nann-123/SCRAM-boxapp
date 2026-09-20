#!/usr/bin/env python
# -*- coding: utf-8 -*-

from mpi4py import MPI

comm = MPI.COMM_WORLD

rank = comm.rank
Nrank = comm.size

import coefficient_repartition_mpi as cr


# Init the module for all ranks. See script.py fo further details.
cr.Init("config.lua")

# Check that MPI is here:
# cr.MPI should exist and
print cr.CoefficientRepartitionBase.GetRank(), cr.CoefficientRepartitionBase.GetNrank()
# should return the current rank and total number of them. 

# Create an object containing the coefficients
# and corresponding indexes to be computed.
coef = cr.RepartitionCoefficient()

# Compute coefficients for all couples:
coef.MPI_ComputeAll(0)
# That is to note each rank will compute its part of couples.
#
# The 0 in arguments means that, at the end of computation,
# all ranks will send their computed coefficients to rank 0.

comm.Barrier()

# Then, first rank can write them:
if cr.CoefficientRepartitionBase.GetRank() == 0:
    print coef.GetAllCoefficient()
    coef.WriteNetCDF("coef_mpi.nc")
