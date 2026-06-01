# Windows Report Dependency Notes

SCRAM BoxApp has two PDF report paths:

1. **Built-in offline PDF backend**
   - Always available in the packaged app.
   - Does not require LaTeX, Python, internet access, or administrator permission.
   - Used automatically when `xelatex` or `tectonic` is not available, or when LaTeX compilation fails.

2. **Optional LaTeX backend**
   - Used when `xelatex` or `tectonic` is installed and working.
   - Produces the editable `.tex` workflow.
   - Optional for ordinary users.

## Dependency Package

The Windows release provides:

- `dist/windows/dependencies/basic-miktex-25.12-x64.exe`
- `dist/windows/dependencies/README_REPORT_DEPENDENCIES_zh.md`

Official MiKTeX package metadata:

- SHA-256: `14B42DD9F4B4A7813A8BFD69C8F99316C2888CC4EE26F631F397E163D85D6C62`
- Source: <https://miktex.org/download>

To refresh the local copy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\fetch_report_dependencies_windows.ps1
```

## User Repair Flow

1. First try “Generate Report” again. The app should create a PDF through the built-in backend even without LaTeX.
2. If the user specifically needs LaTeX compilation, close SCRAM BoxApp.
3. Run `basic-miktex-25.12-x64.exe` from the dependency folder.
4. Allow MiKTeX to install missing packages automatically.
5. Reopen SCRAM BoxApp and generate the report again.
