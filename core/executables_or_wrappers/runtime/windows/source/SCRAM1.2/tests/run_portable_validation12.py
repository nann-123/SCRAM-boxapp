#!/usr/bin/env python3
"""Independent box-model validation: no CESM profile or runtime required."""
from pathlib import Path
import subprocess,shlex,json
root=Path(__file__).resolve().parents[1]
objs=[str(p.relative_to(root)) for p in sorted((root/'SRC').rglob('*.o')) if p.name!='ProgramSCRAM.o']
libs=shlex.split(subprocess.check_output(['nf-config','--flibs'],text=True))
(root/'validation').mkdir(exist_ok=True)
results=[]
for test,refs in [('test_portable_reference12',['tests/cesm_r2_reference/Aerosol_reference.f','tests/cesm_r2_reference/Remap_reference.f90']),('test_portable_sulfate12',[])]:
 cmd=['gfortran','-O0','-g','-fcheck=all','-ffree-line-length-none','-ffixed-line-length-none','-I','SRC','-I','tests/cesm_r2_reference']+refs+[f'tests/{test}.f90']+objs+libs+['-o',f'tests/{test}']
 subprocess.run(cmd,cwd=root,check=True)
 r=subprocess.run([str(root/'tests'/test)],cwd=root,capture_output=True,text=True,check=True)
 print(r.stdout.strip(),flush=True);results.append({'test':test,'status':'PASS','output':r.stdout.strip()})
(root/'validation/PORTABLE_CORE_SUMMARY.json').write_text(json.dumps(results,indent=2)+'\n')
