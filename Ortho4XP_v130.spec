# -*- mode: python ; coding: utf-8 -*-


from PyInstaller.utils.hooks import collect_dynamic_libs
block_cipher = None


a = Analysis(['Ortho4XP_v130.py'],
             pathex=['src', 'G:\\Ortho4XP_FSX_P3D'],
             binaries=collect_dynamic_libs("rtree"),
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='Ortho4XP_v130',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True )
