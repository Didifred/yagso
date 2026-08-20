@echo off
setlocal

set "repositoryRoot=%~dp0.."
pushd "%~dp0"
cd  %repositoryRoot%
if errorlevel 1 exit /b 1

pip install build
python -m build
if errorlevel 1 (
    popd
    exit /b 1
)

set "wheelName="
for /f "delims=" %%W in ('dir /b /a-d /o-d "%repositoryRoot%\dist\*.whl" 2^>nul') 
    do if not defined wheelName set "wheelName=%%W"

if not defined wheelName (
    echo No wheel was generated in %repositoryRoot%\dist
    popd
    exit /b 1
)

echo Installing %wheelName%
pip install --force-reinstall "%repositoryRoot%\dist\%wheelName%"
set "exitCode=%errorlevel%"

popd
exit /b %exitCode%
