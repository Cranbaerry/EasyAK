import sys
import version
from cx_Freeze import setup, Executable

print("Hi")
# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {"packages": ["numpy", "uu", "socket", "win32gui", "re"],
                     "excludes": ["tkinter", "setuptools", "pymsgbox", "pydoc_data"],
                     "include_files": ["images/", "icons/"],
                     "include_msvcr": True,
                     "add_to_path": True}

# GUI applications require a different base on Windows (the default is for a
# console application).
base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(name="EasyAK",
      version=version.build,
      description="Preconfigured set of macros for your Aura Kingdom's needs",
      options={"build_exe": build_exe_options},
      executables=[Executable("easyak.py", icon = "icons/icon.ico", base=base)])

print("done")
