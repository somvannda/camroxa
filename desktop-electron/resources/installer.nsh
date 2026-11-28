; Camxora 2.0.0 installer tweaks.
;
; 2.0.0 is the Electron rebuild of the desktop app. 1.7.1 (and older) shipped as
; the Python app built with Inno Setup (AppId {A7C2E8D1-4F19-4B6A-9C31-CAMXORA2026}).
; Installing 2.0.0 must replace that app instead of leaving two Camxora
; installations behind, so remove the legacy install (silently) before the new
; files are written. The old uninstaller is elevated by its own manifest; if the
; user declines that prompt, setup continues and 2.0.0 installs per user.

!macro customInit
  SetRegView 64
  ReadRegStr $0 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{A7C2E8D1-4F19-4B6A-9C31-CAMXORA2026}_is1" "UninstallString"
  StrCmp $0 "" legacy_try_32 legacy_uninstall

legacy_try_32:
  SetRegView 32
  ReadRegStr $0 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{A7C2E8D1-4F19-4B6A-9C31-CAMXORA2026}_is1" "UninstallString"
  SetRegView 64
  StrCmp $0 "" legacy_done legacy_uninstall

legacy_uninstall:
  DetailPrint "Removing the previous Camxora desktop (1.7.1)..."
  ExecWait '$0 /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-' $1
  DetailPrint "Previous Camxora desktop uninstall exited with $1."

legacy_done:
  SetRegView 64
!macroend
