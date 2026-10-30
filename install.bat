@echo off
setlocal DisableDelayedExpansion
rem Vivarc: install, update and repair for Windows.
set "REPO=KASOGIT/vivarc"
set "DEST=%USERPROFILE%\.vivarc\app"
set "PYTHON=python"
where py.exe >nul 2>&1 && set "PYTHON=py -3"
if defined VIVARC_PYTHON set PYTHON="%VIVARC_PYTHON%"
%PYTHON% --version >nul 2>&1 || (
  echo Install Python 3 from python.org, then run this command again.
  exit /b 1
)

rem Work from a temporary copy: an update may replace this batch file.
if defined VIVARC_INSTALL_RUNNING goto install
set "RUNNER=%TEMP%\vivarc-install-%RANDOM%-%RANDOM%.bat"
copy /y "%~f0" "%RUNNER%" >nul || exit /b 1
set "VIVARC_INSTALL_RUNNING=1"
call "%RUNNER%" %*
set "STATUS=%errorlevel%"
del /q "%RUNNER%"
exit /b %STATUS%

:install
for %%D in ("%TEMP%") do set "TEMP_ROOT=%%~fD"
set "WORK=%TEMP_ROOT%\vivarc-%RANDOM%-%RANDOM%"
if exist "%WORK%" exit /b 1
mkdir "%WORK%\src" || exit /b 1
set "URL=%VIVARC_ZIP_URL%"
if defined URL goto download

echo Looking for the latest Vivarc release...
curl.exe -fsSL -o NUL -w "%%{url_effective}" "https://github.com/%REPO%/releases/latest" > "%WORK%\release.txt" || goto failed
set /p RELEASE=<"%WORK%\release.txt"
set "TAG="
for /f "tokens=7 delims=/" %%T in ("%RELEASE%") do set "TAG=%%T"
if not "%TAG:~0,1%"=="v" goto failed
set "URL=https://github.com/%REPO%/archive/refs/tags/%TAG%.zip"

:download
echo Downloading Vivarc...
curl.exe -fsSL "%URL%" -o "%WORK%\vivarc.zip" || goto failed
tar.exe -xf "%WORK%\vivarc.zip" -C "%WORK%\src" --strip-components=1 || goto failed
if not exist "%WORK%\src\vivarc.py" goto failed
if not exist "%WORK%\src\windows_support.py" goto failed
if not exist "%DEST%" mkdir "%DEST%"
xcopy "%WORK%\src\*" "%DEST%\" /E /I /Y /Q >nul || goto failed
%PYTHON% "%DEST%\vivarc.py" install %*
set "STATUS=%errorlevel%"
goto cleanup

:failed
echo Installation failed. Check your connection and that the release supports Windows.
set "STATUS=1"
:cleanup
rem Only remove our generated folder directly inside the resolved temp directory.
for %%D in ("%WORK%") do if /i not "%%~dpD"=="%TEMP_ROOT%\" exit /b 1
rmdir /s /q "%WORK%"
exit /b %STATUS%
