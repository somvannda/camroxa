; Camxora 2.0.0 installer tweaks.
;
; 2.0.0 is the Electron rebuild. 1.7.1 and older shipped as the Python app built
; with Inno Setup. Its AppId in camxora_python/installer/Camxora.iss is
;   AppId={{A7C2E8D1-4F19-4B6A-9C31-CAMXORA2026}
; Inno only unescapes the opening "{{", so the uninstall key that actually
; lands in the registry keeps the doubled closing braces:
;   {A7C2E8D1-4F19-4B6A-9C31-CAMXORA2026}}_is1
; Installing 2.0.0 must replace that app, not sit beside it, so remove the
; legacy install (silently) before the new files are written. The old
; uninstaller elevates itself; if the user declines that prompt, setup
; continues and 2.0.0 installs per user.

!macro customInit
  SetRegView 64
  ReadRegStr $0 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{A7C2E8D1-4F19-4B6A-9C31-CAMXORA2026}}_is1" "QuietUninstallString"
  StrCmp $0 "" 0 legacy_run
  ReadRegStr $0 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{A7C2E8D1-4F19-4B6A-9C31-CAMXORA2026}}_is1" "UninstallString"
  StrCmp $0 "" 0 legacy_run

  SetRegView 32
  ReadRegStr $0 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{A7C2E8D1-4F19-4B6A-9C31-CAMXORA2026}}_is1" "QuietUninstallString"
  StrCmp $0 "" 0 legacy_run
  ReadRegStr $0 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{A7C2E8D1-4F19-4B6A-9C31-CAMXORA2026}}_is1" "UninstallString"
  StrCmp $0 "" 0 legacy_run
  SetRegView 64

  ReadRegStr $0 HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\{A7C2E8D1-4F19-4B6A-9C31-CAMXORA2026}}_is1" "QuietUninstallString"
  StrCmp $0 "" 0 legacy_run
  ReadRegStr $0 HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\{A7C2E8D1-4F19-4B6A-9C31-CAMXORA2026}}_is1" "UninstallString"
  StrCmp $0 "" 0 legacy_run

  ; Last resort: the default 1.7.1 install location.
  IfFileExists "$PROGRAMFILES64\Camxora\unins000.exe" 0 legacy_done
  StrCpy $0 '"$PROGRAMFILES64\Camxora\unins000.exe"'
  Goto legacy_run

legacy_run:
  DetailPrint "Removing the previous Camxora desktop (1.7.1)..."
  ExecWait '$0 /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-' $1
  DetailPrint "Previous Camxora desktop uninstall exited with $1."

legacy_done:
  SetRegView 64
!macroend
