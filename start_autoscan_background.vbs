' Silent Background Launcher for Paper Renamer Watcher
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
ScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Run python in background without showing console window (0 = hidden)
WshShell.CurrentDirectory = ScriptDir
WshShell.Run "python rename_papers.py --watch", 0, False
