# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['easyAK.py'],
             pathex=['D:\\Documents\\EasyAK_R3\\venv\\Lib\\site-packages', 'D:\\Documents\\EasyAK_R3'],
             binaries=[],
             datas=[],
             hiddenimports=['cv2', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5.QtCore', 'numpy.random.common', 'numpy.random.bounded_integers', 'numpy.random.entropy', 'numpy.core.multiarray'],
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
          [],
          exclude_binaries=True,
          name='easyAK',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='easyAK')
