#!/usr/bin/env python3
"""SCRAM1.2 standalone regressions; isolated outputs, original INIT untouched."""
from pathlib import Path
import argparse, subprocess, os, shutil, csv, math, json
p=argparse.ArgumentParser();p.add_argument('--seconds',type=float,default=600);args=p.parse_args()
if args.seconds<=0:raise SystemExit('seconds must be positive')
root=Path(__file__).resolve().parents[1]
results=[]
for source,objlist in [('test_remap12',['ModuleConservativeRemap12']),('test_nearest12',['ModuleInitialization','ModuleCoagulationNearest12'])]:
 cmd=['gfortran','-O0','-g','-fcheck=all','-ffree-line-length-none','-I','SRC',f'tests/{source}.f90']+[f'SRC/{o}.o' for o in objlist]+['-o',f'tests/{source}']
 subprocess.run(cmd,cwd=root,check=True)
 r=subprocess.run([str(root/'tests'/source)],cwd=root,check=True,text=True,capture_output=True)
 results.append({'test':source,'status':'PASS','output':r.stdout.strip()});print(r.stdout.strip(),flush=True)
for name,cfg in [('external','cfg_megapole_01072009.cfg'),('internal','cfg_megapole_01072009_i.cfg'),('cond_only','cfg_cond_only.cfg')]:
 run=root/'validation'/f'{name}_{args.seconds:g}s';run.mkdir(parents=True,exist_ok=True)
 (run/'RESULT').mkdir(exist_ok=True);shutil.copytree(root/'INIT',run/'INIT',dirs_exist_ok=True)
 lines=(root/'INIT'/cfg).read_text().splitlines();lines[13]=f'{args.seconds/3600:.17g} ## SCRAM1.2 regression duration (hours)'
 (run/'case.cfg').write_text('\n'.join(lines)+'\n')
 env=dict(os.environ,SCRAM_RESULTS_DIR=str(run/'audit'),SCRAM_COEFF_REPARTITION_MODE='nearest',SCRAM_REDISTRIBUTION_MODE='moving_center_dualpivot')
 with (run/'run.log').open('w') as f:
  r=subprocess.run([str(root/'ProgramSCRAM'),str(run/'case.cfg')],cwd=run,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180)
 if r.returncode:raise RuntimeError(f'{name} failed; see {run}/run.log')
 table=list(csv.DictReader((run/'audit/csv/timestep_summary.csv').open()))
 if not table or float(table[-1]['time_seconds']) < args.seconds*(1-1e-10):raise RuntimeError(f'{name}: did not reach requested duration')
 for path in (run/'audit/csv').glob('*.csv'):
  for row in csv.DictReader(path.open()):
   for k,v in row.items():
    if v is None:continue
    try:x=float(v)
    except (ValueError,TypeError):continue
    if not math.isfinite(x):raise RuntimeError(f'nonfinite {path}: {k}')
 for row in table:
  if float(row['total_mass'])<0 or float(row['total_number'])<0:raise RuntimeError('negative total')
 results.append({'test':name,'status':'PASS','seconds':args.seconds,'steps':len(table),'last_time_seconds':float(table[-1]['time_seconds'])})
 print(name,results[-1],flush=True)
(root/'validation').mkdir(exist_ok=True)
(root/'validation'/f'SUMMARY_{args.seconds:g}s.json').write_text(json.dumps(results,indent=2)+'\n')
