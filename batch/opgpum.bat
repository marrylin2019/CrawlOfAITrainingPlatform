@echo off

@REM change dir to the parent dir
cd /d %~dp0/..
set "requirements=.\requirements.txt"
set "python=.\venv\Scripts\python.exe"
set "pip=.\venv\Scripts\pip.exe"

@REM check python env
if not exist "%python%" (
    echo python execute was missing, please try again after checing the integrality of the venv folder!
    exit /b
)
%python% -m src.main %* --python_path %python% --pip_path %pip% --requirements_path %requirements%