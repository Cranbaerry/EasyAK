pyinstaller ^
    --nowindow ^
	--hiddenimport cv2 ^
	--hiddenimport PyQt5.QtGui ^
	--hiddenimport PyQt5.QtWidgets ^
	--hiddenimport PyQt5.QtCore ^
	--hiddenimport numpy.random.common ^
	--hiddenimport numpy.random.bounded_integers ^
	--hiddenimport numpy.random.entropy ^
	--hiddenimport numpy.core.multiarray ^
	--paths=D:\Documents\EasyAK_R3\venv\Lib\site-packages ^
    easyAK.py 
pause