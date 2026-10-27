Dim fso, scriptDir, WshShell, pyExe, workerScript, localAppData

Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = scriptDir
localAppData = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%")

' Locate python or pythonw executable (prefer venv if present, fallback to local pythonw/python)
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

workerScript = scriptDir & "\webapp\backend\workers\auto_sync_worker.py"

' Run auto_sync_worker.py completely hidden (0 = Hide Window, True = wait for completion)
WshShell.Run """" & pyExe & """ """ & workerScript & """", 0, True

Set WshShell = Nothing
Set fso = Nothing
