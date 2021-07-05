:: copy all files to new folder
xcopy /I /e .\* ..\Ortho4XP_FSX_P3D_copy

:: remove git files
rmdir /s /q ..\Ortho4XP_FSX_P3D_copy\.git

:: create zip file
powershell Compress-Archive ..\Ortho4XP_FSX_P3D_copy\* Ortho4XP_FSX_P3D.zip

:: remove .\Ortho4XP_FSX_P3D temp folder, since we only care about the .zip for release
rmdir /s /q ..\Ortho4XP_FSX_P3D_copy
