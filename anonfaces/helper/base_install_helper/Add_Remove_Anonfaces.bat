@echo off

:: BatchGotAdmin
:-------------------------------------
REM  --> Check for permissions
    IF "%PROCESSOR_ARCHITECTURE%" EQU "amd64" (
>nul 2>&1 "%SYSTEMROOT%\SysWOW64\cacls.exe" "%SYSTEMROOT%\SysWOW64\config\system"
) ELSE (
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
)

REM --> If error flag set, we do not have admin.
if '%errorlevel%' NEQ '0' (
    echo Requesting administrative privileges...
    goto UACPrompt
) else ( goto gotAdmin )

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    set params= %*
    echo UAC.ShellExecute "cmd.exe", "/c ""%~s0"" %params:"=""%", "", "runas", 1 >> "%temp%\getadmin.vbs"

    "%temp%\getadmin.vbs"
    del "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
    pushd "%CD%"
    CD /D "%~dp0"
:--------------------------------------   

@echo off
cd %~dp0
for /f "delims=:" %%s in ('echo;prompt $h$s$h:^|cmd /d') do set "|=%%s"&set ">>=\..\c nul&set /p s=%%s%%s%%s%%s%%s%%s%%s<nul&popd"
set "<=pushd "%public%"&2>nul findstr /c:\ /a" &set ">=%>>%&echo;" &set "|=%|:~0,1%" &set /p s=\<nul>"%public%\c"
:TOP
CLS
set "M="
set "manualremoval="
set "pythonincorrect="
set "gitincorrect="
ECHO.
%<%:ec "Choose Add or Remove Anonfaces?"%>%
ECHO.
ECHO 1 = Add		2 = Remove	3 = Cleanup Nvidia	4 = Exit
ECHO.
SET /P M=TYPE YOUR CHOICE THEN PRESS ENTER:

set "MM=%M%"
setlocal EnableDelayedExpansion

if "!MM!"==" " (
   cls
   echo INCORRECT INPUT ENTERED!
   echo.
   pause
   cls
   goto :TOP
   )
   
if "%M%"=="" (
   cls
   echo NOTHING ENTERED!
   echo.
   pause
   cls
   goto :TOP
   )
   
IF [%M:~0,1%]==[1] CLS && GOTO 1
IF [%M:~0,1%]==[2] CLS && GOTO 2
IF [%M:~0,1%]==[3] CLS && GOTO 3
IF [%M:~0,1%]==[4] CLS && exit/b
IF [%M:~0,1%]==[ ] (
    cls
    echo INCORRECT INPUT ENTERED!
    echo.
    pause
    goto :TOP
    )

:1
setlocal DisableDelayedExpansion
CLS
echo.
%<%:ec "Installing all required resources for Anonfaces"%>%
echo.
:: Check if winget is available
where winget >nul 2>&1
if %errorlevel%==1 goto GETWGET
if %errorlevel%==0 (
    %<%:ec "Winget is available."%>%
    echo.
	%<%:ec "Installing Required C++ Redist"%>%
	winget install --id Microsoft.VCRedist.2015+.x64 --source winget
	echo.
	ping 127.0.0.1 -n 3 >nul
    :GETGIT
	:: Check if Git is installed
    for /f "tokens=3 delims= " %%a in ('git --version 2^>^&1') do (
        set GIT_VERSION=%%a
		if "%%a"=="not" (
            goto GITWINGET
        ) else if "%%a"=="or" (
            goto GITWINGET
        ) else if "%%a"=="2.46.0.windows.1" (
            goto GITGOOD
        ) else (
            set "gitincorrect=true"
			goto GITINCORRECT
        )
    )

    :GITGOOD
    CLS
	ECHO.
    %<%:ec "GIT %GIT_VERSION% is already installed."%>%
    goto GETPYTHON
	
	:GITWINGET
	CLS
	ECHO.
	%<%:ec "Installing Git via winget..."%>%
	echo.
	winget download --id Git.Git --download-directory .
	for %%f in (Git*.exe) do start "" /b /wait "%%f" /verysilent
	ping 127.0.0.1 -n 3 >nul
	got GETPYTHON

    :GETPYTHON
    :: Check if Python is installed
    for /f "tokens=2 delims= " %%a in ('python --version 2^>^&1') do (
        set PYTHON_VERSION=%%a
		if "%%a"=="is" (
            goto PYTHONWINGET
        ) else if "%%a"=="program" (
            goto PYTHONWINGET
		) else if "%%a"=="was" (
            goto PYTHONWINGET
        ) else if "%%a"=="3.12.6" (
            goto PYTHONGOOD
        ) else (
            set "pythonincorrect=true"
			goto PYTHONINCORRECT
        )
    )

    :PYTHONGOOD
	echo.
    %<%:ec "Python %PYTHON_VERSION% is already installed."%>%
	ping 127.0.0.1 -n 3 >nul
    goto REFRESHENV
	
	:PYTHONWINGET
	CLS
	echo.
	%<%:ec "Installing Python via winget..."%>%
	echo.
	winget download --id Python.Python.3.12 --download-directory .
	for %%f in (python*.exe) do start "" /b /wait "%%f" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_exe=1
	ping 127.0.0.1 -n 3 >nul
	goto REFRESHENV
)

:GETWGET
CLS
echo.
%<%:ec "Winget is not available. Falling back to direct downloads with static versions..."%>%
ping 127.0.0.1 -n 3 >nul
echo.
%<%:ec "Installing Required C++ Redist"%>%
wget "https://aka.ms/vs/17/release/vc_redist.x64.exe" --no-check-certificate -O VC-Installer.exe
start "" /b /wait "VC-Installer.exe" /install /silent
echo.
for /f "tokens=3 delims= " %%a in ('git --version 2^>^&1') do (
    set GIT_VERSION=%%a
	if "%%a"=="not" (
        goto GITWGET
    ) else if "%%a"=="or" (
        goto GITWGET
    ) else if "%%a"=="2.46.0.windows.1" (
        goto GITGOODWGET
    ) else (
        goto GITINCORRECT
    )
)
	
:GITGOODWGET
CLS
ECHO.
%<%:ec "GIT %GIT_VERSION% is already installed."%>%
goto GETPYTHONWGET

:GITWGET
CLS
ECHO.
%<%:ec "Installing Git via wget..."%>%
echo.
wget "https://github.com/git-for-windows/git/releases/download/v2.46.0.windows.1/Git-2.46.0-64-bit.exe" --no-check-certificate -O Git-Installer.exe
start "" /b /wait "Git-Installer.exe" /verysilent
ping 127.0.0.1 -n 3 >nul
got GETPYTHONWGET


:GETPYTHONWGET
for /f "tokens=2 delims= " %%a in ('python --version 2^>^&1') do (
    if "%%a"=="is" (
        goto PYTHONWGET
    ) else if "%%a"=="program" (
        goto PYTHONWGET
	) else if "%%a"=="was" (
            goto PYTHONWINGET
    ) else if "%%a"=="3.12.6" (
        goto PYTHONGOODWGET
    ) else (
        goto PYTHONINCORRECT
    )
)

:PYTHONGOODWGET
echo.
%<%:ec "Python is already installed."%>%
ping 127.0.0.1 -n 3 >nul
goto REFRESHENV

:PYTHONWGET
CLS
echo.
%<%:ec "Installing Python via winget..."%>%
echo.
wget "https://www.python.org/ftp/python/3.12.6/python-3.12.6-amd64.exe" --no-check-certificate -O Python-Installer.exe
start "" /b /wait "Python-Installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_exe=1
ping 127.0.0.1 -n 3 >nul
goto REFRESHENV


:REFRESHENV
setlocal DisableDelayedExpansion
echo.
ping 127.0.0.1 -n 5 >nul
CLS
echo.
%<%:ec "Refreshing Environment!"%>%
echo.
call refresh.bat >nul
python -m pip install --upgrade setuptools pip requests
cls
python bat_branch_selector.py
cls
for /f "delims=" %%i in (selected_branch.txt) do (
    set "selected_branch=%%i"
)

if "%selected_branch%"=="No branch selected." (
    echo Failed to retrieve branches. Exiting...
    pause
	del /f /q selected_branch.txt >nul
    goto REFRESHENV
) else if "%selected_branch%"=="" (
    echo No branch selected. Exiting...
    pause
	del /f /q selected_branch.txt >nul
    goto REFRESHENV
)
cls
python -c "import requests; exec(requests.get('https://raw.githubusercontent.com/StealUrKill/anonfaces/%selected_branch%/anonfaces/helper/add_remove_helper.py').text)"
del /f /q selected_branch.txt >nul
ping 127.0.0.1 -n 3 >nul
cls
echo.
%<%:ec "EXITING"%>%
ping 127.0.0.1 -n 5 >nul
exit









:2
setlocal DisabledDelayedExpansion
CLS
set "M="
set "manualremoval="
set "pythonincorrect="
set "gitincorrect="
ECHO.
%<%:ec "1 = Uninstall All?"%>%
ECHO.
%<%:ec "2 = Remove Anonfaces & pip modules"%>%
ECHO.
SET /P M=TYPE YOUR CHOICE THEN PRESS ENTER:

set "MM=%M%"
setlocal EnableDelayedExpansion

if "!MM!"==" " (
   cls
   echo INCORRECT INPUT ENTERED!
   echo.
   pause
   cls
   goto :TOP
   )
   
if "%M%"=="" (
   cls
   echo NOTHING ENTERED!
   echo.
   pause
   cls
   goto :TOP
   )
   
IF [%M:~0,1%]==[1] CLS && GOTO 1UN
IF [%M:~0,1%]==[2] CLS && GOTO 2UN

IF [%M:~0,1%]==[ ] (
    cls
    echo INCORRECT INPUT ENTERED!
    echo.
    pause
    goto :TOP
    )

:2UN
echo.
echo.
%<%:ec "Uninstalling all required resources for Anonfaces"%>%
echo.
%<%:ec "Choose Uninstall or choose Uninstall Both"%>%
echo.
ping 127.0.0.1 -n 6 >nul
CLS
python bat_branch_selector.py
cls
for /f "delims=" %%i in (selected_branch.txt) do (
    set "selected_branch=%%i"
)

if "%selected_branch%"=="No branch selected." (
    echo Failed to retrieve branches. Exiting...
    pause
	del /f /q selected_branch.txt >nul
    goto REFRESHENV
) else if "%selected_branch%"=="" (
    echo No branch selected. Exiting...
    pause
	del /f /q selected_branch.txt >nul
    goto REFRESHENV
)
cls
python -c "import requests; exec(requests.get('https://raw.githubusercontent.com/StealUrKill/anonfaces/%selected_branch%/anonfaces/helper/add_remove_helper.py').text)"
del /f /q selected_branch.txt >nul
CLS
echo.
%<%:ec "Exiting"%>%
ping 127.0.0.1 -n 4 >nul
exit /b

:1UN
CLS
set "manualremoval=true"
goto REMOVEINVALIDPYTHON

:DELGIT
CLS
set "manualremoval=true"
goto REMOVEINVALIDGIT

:LEFTOVERS
CLS
echo.
%<%:ec "Removing Any Leftover Files Manually"%>%
rd /s /q "%LocalAppData%\pip" >nul 2>&1
rd /s /q "%LocalAppData%\Programs\Python" >nul 2>&1
rd /s /q "C:\Program Files\Git" >nul 2>&1
for /d %%G in ("%appdata%\Microsoft\Windows\Start Menu\Programs\Python*") do rd /s /q "%%~G" >nul 2>&1
for /d %%G in ("%appdata%\Microsoft\Windows\Start Menu\Programs\Git") do rd /s /q "%%~G" >nul 2>&1
for /d %%G in ("C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Git") do rd /s /q "%%~G" >nul 2>&1
rd /s /q "C:\Program Files (x86)\Intel\openvino_2023.3.0" >nul 2>&1
rd /s /q "C:\Program Files (x86)\Intel\openvino_2023" >nul 2>&1
ping 127.0.0.1 -n 2 >nul
CLS
echo.
%<%:ec "Exiting"%>%
ping 127.0.0.1 -n 4 >nul
exit /b










:PYTHONINCORRECT
CLS
set "pversion="
echo.
set tested_version=3.12.6
set "required_major=3"
set "required_minor=10"
for /f "tokens=2 delims= " %%a in ('python --version 2^>^&1') do set "pversion=%%a"
for /f "tokens=1,2 delims=." %%a in ("%pversion%") do (
    set "pversion_major=%%a"
    set "pversion_minor=%%b"
)
if %pversion_major% GTR %required_major% (
    goto ASKKEEPPYTHON
) else if %pversion_major% EQU %required_major% (
    if %pversion_minor% GEQ %required_minor% (
        goto ASKKEEPPYTHON
    ) else (
        goto UNINSTALL_PYTHON_VERSION
    )
) else (
    goto UNINSTALL_PYTHON_VERSION
)
:ASKKEEPPYTHON
%<%:ec "Python %pversion% is installed, which is higher than 3.10."%>%
ECHO.
%<%:ec "The known tested version is %tested_version%"%>%
ECHO.
%<%:ec "Do you want to continue with the untested Python version %pversion%?"%>%
ECHO.
ECHO 1 = Yes		2 = No
ECHO.
SET /P M=TYPE YOUR CHOICE THEN PRESS ENTER:

set "MM=%M%"
setlocal EnableDelayedExpansion

if "!MM!"==" " (
	cls
	echo INCORRECT INPUT ENTERED!
	echo.
	pause
	cls
	goto PYTHONINCORRECT
	)

if "%M%"=="" (
	cls
	echo NOTHING ENTERED!
	echo.
	pause
	cls
	goto PYTHONINCORRECT
	)

IF [%M:~0,1%]==[1] CLS && GOTO REFRESHENV
IF [%M:~0,1%]==[2] CLS && GOTO UNINSTALL_PYTHON_VERSION
IF [%M:~0,1%]==[ ] (
	cls
	echo INCORRECT INPUT ENTERED!
	echo.
	pause
	goto PYTHONINCORRECT
	)

:UNINSTALL_PYTHON_VERSION
setlocal DisableDelayedExpansion	
CLS
ECHO.
%<%:ec "Uninstall Python version %pversion% before continuing."%>%
set "M="
ECHO.
%<%:ec "Would you like to remove it?"%>%
ECHO.
ECHO 1 = Yes		2 = Exit
ECHO.
SET /P M=TYPE YOUR CHOICE THEN PRESS ENTER:

set "MM=%M%"
setlocal EnableDelayedExpansion

if "!MM!"==" " (
   cls
   echo INCORRECT INPUT ENTERED!
   echo.
   pause
   cls
   goto UNINSTALL_PYTHON_VERSION
   )
   
if "%M%"=="" (
   cls
   echo NOTHING ENTERED!
   echo.
   pause
   cls
   goto UNINSTALL_PYTHON_VERSION
   )
   
IF [%M:~0,1%]==[1] CLS && GOTO REMOVEINVALIDPYTHON
IF [%M:~0,1%]==[2] CLS && exit/b
IF [%M:~0,1%]==[ ] (
    cls
    echo INCORRECT INPUT ENTERED!
    echo.
    pause
    goto UNINSTALL_PYTHON_VERSION
    )


:REMOVEINVALIDPYTHON
setlocal DisableDelayedExpansion
setlocal EnableDelayedExpansion
set "string1="
set "string2="
set "string3="
set "string4="
call refresh.bat >nul
ping 127.0.0.1 -n 1 >nul

for /f "tokens=2*" %%a in ('reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" /s /f "Python" ^| find "Quiet"') do set "string1=%%b"
for /f "tokens=2*" %%a in ('reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" /s /f "Python" ^| find "Quiet"') do set "string2=%%b"
for /f "tokens=2*" %%a in ('reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall" /s /f "Python" ^| find "Quiet"') do set "string3=%%b"
for /f "tokens=2*" %%a in ('reg query "HKCU\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall" /s /f "Python" ^| find "Quiet"') do set "string4=%%b"
IF "!string1!"=="" (
    IF "!string2!"=="" (
        IF "!string3!"=="" (
			IF "!string4!"=="" (
				goto PYTHONLAUNCHER
			)
		)
	)
)
set "uninstall_string="
IF NOT "!string1!"=="" (
    set "uninstall_string=!string1!"
) ELSE IF NOT "!string2!"=="" (
    set "uninstall_string=!string2!"
) ELSE IF NOT "!string3!"=="" (
    set "uninstall_string=!string3!"
) ELSE IF NOT "!string4!"=="" (
    set "uninstall_string=!string4!"
)

:UNINSTALLPYTHONAPP
set "pversion="

for /f "tokens=8 delims=\" %%a in ("!uninstall_string!") do (
    for /f "tokens=1,2 delims=- " %%b in ("%%a") do (
        set "pversion=%%b-%%c"
    )
)

IF NOT "!uninstall_string!"=="" (
	ECHO.
	%<%:ec " Now Uninstalling %pversion% "%>%
    !uninstall_string!
	goto PYTHONLAUNCHER
) ELSE (
    goto REMOVEINVALIDPYTHON
)
ECHO.

:PYTHONLAUNCHER
set "string5="
set "string6="
set "string7="
set "string8="

for /f "tokens=*" %%a in ('reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall" /s /f "Python Launcher" ^| findstr /i "{.*}"') do (
    for /f "tokens=2*" %%b in ('reg query "%%a" /v "UninstallString" 2^>nul ^| find "UninstallString"') do (
        set "string5=%%c"
    )
)
for /f "tokens=*" %%a in ('reg query "HKCU\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall" /s /f "Python Launcher" ^| findstr /i "{.*}"') do (
    for /f "tokens=2*" %%b in ('reg query "%%a" /v "UninstallString" 2^>nul ^| find "UninstallString"') do (
        set "string6=%%c"
    )
)
for /f "tokens=*" %%a in ('reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" /s /f "Python Launcher" ^| findstr /i "{.*}"') do (
    for /f "tokens=2*" %%b in ('reg query "%%a" /v "UninstallString" 2^>nul ^| find "UninstallString"') do (
        set "string6=%%c"
    )
)
for /f "tokens=*" %%a in ('reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" /s /f "Python Launcher" ^| findstr /i "{.*}"') do (
    for /f "tokens=2*" %%b in ('reg query "%%a" /v "UninstallString" 2^>nul ^| find "UninstallString"') do (
        set "string7=%%c"
    )
)
IF "!string5!"=="" (
    IF "!string6!"=="" (
        IF "!string7!"=="" (
            IF "!string8!"=="" (
                ::First condition: If manualremoval is empty and pythonincorrect is true
                IF "!manualremoval!"=="" (
                    IF "!pythonincorrect!"=="true" (
                        goto :1
                    )
                )                
                ::Second condition: If manualremoval is true and pythonincorrect is empty
                IF "!manualremoval!"=="true" (
                    IF "!pythonincorrect!"=="" (
                        goto DELGIT
                    )
                )
            )
        )
    )
)
:CONTINUE
set "uninstall_string2="
IF NOT "!string5!"=="" (
    set "uninstall_string2=!string5!"
) ELSE IF NOT "!string6!"=="" (
    set "uninstall_string2=!string6!"
) ELSE IF NOT "!string7!"=="" (
    set "uninstall_string2=!string7!"
) ELSE IF NOT "!string8!"=="" (
    set "uninstall_string2=!string8!"
)
for /f "tokens=2 delims=/X " %%a in ("!uninstall_string2!") do set "uninstall_string2_clean=%%a"

IF NOT "!uninstall_string2_clean!"=="" (
    msiexec /uninstall !uninstall_string2_clean! /passive
) else (
    goto WAITINVALID
)
:WAITINVALID
CLS
set "noinfo=INFO: No tasks are running which match the specified criteria."
for /f "tokens=1  delims=," %%F in ('tasklist /nh /fi "imagename eq Python*" /fo csv') do set uninstall=%%F
ping 127.0.0.1 -n 2 > NUL 2>&1
if "%uninstall%" == "%noinfo%" (
GOTO REMOVEINVALIDPYTHON
) else (
GOTO WAITINVALID
)
GOTO TOP











:GITINCORRECT
CLS
set "pversiongit="
echo.
for /f "tokens=3 delims= " %%a in ('git --version 2^>^&1') do set pversiongit=%%a
set "M="
%<%:ec "GIT %pversiongit% is installed."%>%
echo.
%<%:ec "Uninstall version %pversiongit% before continuing."%>%
ECHO.
%<%:ea "Would you like to remove GIT %pversiongit%?"%>%
ECHO.
%<%:ec "Exit will try to use existing GIT"%>%
ECHO.
ECHO 1 = Yes		2 = Exit
ECHO.
SET /P M=TYPE YOUR CHOICE THEN PRESS ENTER:

set "MM=%M%"
setlocal EnableDelayedExpansion

if "!MM!"==" " (
   cls
   echo INCORRECT INPUT ENTERED!
   echo.
   pause
   cls
   goto GITINCORRECT
   )
   
if "%M%"=="" (
   cls
   echo NOTHING ENTERED!
   echo.
   pause
   cls
   goto GITINCORRECT
   )
   
IF [%M:~0,1%]==[1] CLS && GOTO REMOVEINVALIDGIT
IF [%M:~0,1%]==[2] CLS && GOTO GETPYTHON
IF [%M:~0,1%]==[ ] (
    cls
    echo INCORRECT INPUT ENTERED!
    echo.
    pause
    goto GITINCORRECT
    )

:REMOVEINVALIDGIT
setlocal DisableDelayedExpansion
setlocal EnableDelayedExpansion
set "string1="
set "string2="
set "string3="
set "string4="
call refresh.bat >nul

for /f "tokens=2*" %%a in ('reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" /s /f "GIT" ^| find "Quiet" ^| findstr /r /i "\<Git\>"') do set "string1=%%b"
for /f "tokens=2*" %%a in ('reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" /s /f "GIT" ^| find "Quiet" ^| findstr /r /i "\<Git\>"') do set "string2=%%b"
for /f "tokens=2*" %%a in ('reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall" /s /f "GIT" ^| find "Quiet" ^| findstr /r /i "\<Git\>"') do set "string3=%%b"
for /f "tokens=2*" %%a in ('reg query "HKCU\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall" /s /f "GIT" ^| find "Quiet" ^| findstr /r /i "\<Git\>"') do set "string4=%%b"
IF "!string1!"=="" (
    IF "!string2!"=="" (
        IF "!string3!"=="" (
            IF "!string4!"=="" (
                ::First condition: If manualremoval is empty and gitincorrect is true
                IF "!manualremoval!"=="" (
                    IF "!gitincorrect!"=="true" (
                        goto :1
                    )
                )                
                ::Second condition: If manualremoval is true and gitincorrect is empty
                IF "!manualremoval!"=="true" (
                    IF "!gitincorrect!"=="" (
                        goto LEFTOVERS
                    )
                )
            )
        )
    )
)

set "uninstall_string="
IF NOT "!string1!"=="" (
    set "uninstall_string=!string1!"
) ELSE IF NOT "!string2!"=="" (
    set "uninstall_string=!string2!"
) ELSE IF NOT "!string3!"=="" (
    set "uninstall_string=!string3!"
) ELSE IF NOT "!string4!"=="" (
    set "uninstall_string=!string4!"
)
set "pversiongit="
for /f "tokens=3 delims= " %%a in ('git --version 2^>^&1') do set pversiongit=%%a
IF NOT "!uninstall_string!"=="" (
	ECHO.
	%<%:ec " Now Uninstalling %pversiongit% "%>%
    !uninstall_string!
	goto WAITGIT
) ELSE (
    goto REMOVEINVALIDGIT
)

:WAITGIT
::CLS
set "noinfo=INFO: No tasks are running which match the specified criteria."
for /f "tokens=1  delims=," %%F in ('tasklist /nh /fi "imagename eq GIT*" /fo csv') do set uninstall=%%F
ping 127.0.0.1 -n 3 > NUL 2>&1
if "%uninstall%" == "%noinfo%" (
GOTO REMOVEINVALIDGIT
) else (
GOTO WAITGIT
)
GOTO TOP
PAUSE



















:3
setlocal DisabledDelayedExpansion
CLS
set "M="
ECHO.
%<%:ec "This is to remove any traces of Nvidia"%>%
ECHO.
%<%:ec "Only to be done after manual uninstall"%>%
ECHO.
%<%:ec "Some might not remove due to Windows"%>%
ECHO.
ECHO.
%<%:ec "Has manual uninstall been done?"%>%
ECHO.
ECHO 1 = Yes		2 = No
ECHO.
SET /P M=TYPE YOUR CHOICE THEN PRESS ENTER:

set "MM=%M%"
setlocal EnableDelayedExpansion

if "!MM!"==" " (
   cls
   echo INCORRECT INPUT ENTERED!
   echo.
   pause
   cls
   goto :3
   )
   
if "%M%"=="" (
   cls
   echo NOTHING ENTERED!
   echo.
   pause
   cls
   goto :3
   )
   
IF [%M:~0,1%]==[1] CLS && GOTO UNNVIDIA
IF [%M:~0,1%]==[2] CLS && exit/b

IF [%M:~0,1%]==[ ] (
    cls
    echo INCORRECT INPUT ENTERED!
    echo.
    pause
    goto :3
    )
	
:UNNVIDIA
setlocal DisabledDelayedExpansion
CLS
ECHO.
%<%:ec "Removing Any Leftover Nvidia Files Manually"%>%
rd /s /q "C:\ProgramData\NVIDIA" > NUL 2>&1
rd /s /q "C:\ProgramData\NVIDIA Corporation" > NUL 2>&1
rd /s /q "C:\Program Files\NVIDIA" > NUL 2>&1
rd /s /q "C:\Program Files\NVIDIA Corporation" > NUL 2>&1
rd /s /q "C:\Program Files\NVIDIA GPU Computing Toolkit" > NUL 2>&1
rd /s /q "C:\Program Files (x86)\NVIDIA Corporation" > NUL 2>&1
rd /s /q "%localappdata%\NVIDIA" > NUL 2>&1
rd /s /q "%USERPROFILE%\AppData\LocalLow\NVIDIA" > NUL 2>&1
ping 127.0.0.1 -n 2 >nul
CLS
echo.
%<%:ec "Exiting"%>%
ping 127.0.0.1 -n 4 >nul
exit /b
