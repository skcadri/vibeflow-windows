' Windowless launcher — runs VibeFlow.bat hidden so it goes straight to the
' system tray with no console window. Resolves VibeFlow.bat relative to this
' script's own folder, so it's fully portable.
Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
batPath = fso.GetParentFolderName(WScript.ScriptFullName) & "\VibeFlow.bat"
WshShell.Run chr(34) & batPath & chr(34), 0
Set WshShell = Nothing
