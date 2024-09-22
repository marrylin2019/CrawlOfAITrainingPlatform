@echo off

@REM change dir to the parent dir
cd /d %~dp0/..
@REM check python env
if not exist ".\venv\Scripts\python.exe" (
    echo python execute was missing, please try again after checing the integrality of the venv folder!
    exit /b
)
set "python=.\venv\Scripts\python.exe"
@REM check parameters
set "shutdown=false"
set "requirements=false"
set "default_all=false"
set "default_user=false"
set "default_task=false"
for %%i in (%*) do (
    if "%%i"=="-s" set "shutdown=true"
    if "%%i"=="--shutdown" set "shutdown=true"

    if "%%i"=="-r" set "requirements=true"
    if "%%i"=="--requirements" set "requirements=true"

    if "%%i"=="-d" set "default_all=true"
    if "%%i"=="--default_all" set "default_all=true"

    if "%%i"=="-du" set "default_user=true"
    if "%%i"=="--default_user" set "default_user=true"

    if "%%i"=="-dt" set "default_task=true"
    if "%%i"=="--default_task" set "default_task=true"
)

if "%requirements%"=="true" (
    @REM check requirements file
    if not exist ".\requirements.txt" (
        echo requirements.txt was missing, please try again after checing the integrality of the folder!
        exit /b
    )

    @REM check pip env
    if not exist ".\venv\Scripts\pip.exe" (
        echo python execute was missing, please try again after checing the integrality of the venv folder!
        exit /b
    )
    %python% -m pip install -r requirements.txt
    cls
)

@REM run based on parameters
if "%shutdown%"=="true" (
    echo Executing SHUTDOWN...
) else (
    echo Executing SETINGUP...
)
%python% -m src.main -s %shutdown% -d %default_all% -dt %default_task% -du %default_user%