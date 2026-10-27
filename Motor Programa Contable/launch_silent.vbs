Dim fso, scriptDir, WshShell, pyExe, localAppData

Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = scriptDir
localAppData = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%")

' Locate python or pythonw executable (prefer .venv, then local Python311, fallback to python)
pyExe = scriptDir & "\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(pyExe) Then
    pyExe = scriptDir & "\.venv\Scripts\python.exe"
End If
If Not fso.FileExists(pyExe) And localAppData <> "%LOCALAPPDATA%" Then
    pyExe = localAppData & "\Programs\Python\Python311\pythonw.exe"
End If
If Not fso.FileExists(pyExe) And localAppData <> "%LOCALAPPDATA%" Then
    pyExe = localAppData & "\Programs\Python\Python311\python.exe"
End If
If Not fso.FileExists(pyExe) Then
    pyExe = "pythonw"
End If

' Run start_system.py completely hidden (0 = Hide Window, False = don't wait)
WshShell.Run """" & pyExe & """ """ & scriptDir & "\start_system.py""", 0, False

Set WshShell = Nothing
Set fso = Nothing
