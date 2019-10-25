from os import path, sep, makedirs
from os import name as osName
from random import random, randint
from threading import Thread
from time import time, sleep, perf_counter, strftime
import sys
from urllib.error import URLError
from socket import gethostbyname, gaierror
import cv2
from numpy import array, where
import pyautogui
import subprocess
from urllib import parse, request
import version
from PIL import Image
from PIL.ImageQt import ImageQt
from configparser import ConfigParser
from ctypes import windll
import gui
import Screenshot
from PyQt5.QtGui import QPalette, QColor, QBrush, QPixmap, QIcon, QImage, QKeySequence
from PyQt5.QtWidgets import QTableWidgetItem, QAbstractItemView, QApplication, QTableView, QDialog, QLabel, QMessageBox, \
    QFileDialog, QInputDialog, QLineEdit, QHeaderView, QShortcut
from PyQt5.QtCore import Qt, QPoint, QObject, pyqtSignal, QThread, pyqtSlot, QSize, QVariant, QBuffer, \
    QAbstractNativeEventFilter, QAbstractEventDispatcher
from win32gui import FindWindow, GetWindowText, EnumWindows, SetForegroundWindow
import re
import io
import atexit
from pyqtkeybind import keybinder

class WindowMgr:
    """Encapsulates some calls to the winapi for window management"""

    def __init__(self):
        """Constructor"""
        self._handle = None

    def find_window(self, class_name, window_name=None):
        """find a window by its class_name"""
        self._handle = FindWindow(class_name, window_name)

    def _window_enum_callback(self, hwnd, wildcard):
        """Pass to win32gui.EnumWindows() to check all the opened windows"""
        if re.match(wildcard, str(GetWindowText(hwnd))) is not None:
            self._handle = hwnd

    def find_window_wildcard(self, wildcard):
        """find a window whose title matches the wildcard regex"""
        self._handle = None
        EnumWindows(self._window_enum_callback, wildcard)

    def set_foreground(self):
        """put the window in the foreground"""
        SetForegroundWindow(self._handle)


def is_admin():
    try:
        return windll.shell32.IsUserAnAdmin()
    except:
        return False


def GetUUID():
    cmd = 'wmic csproduct get uuid'
    uuid = str(subprocess.check_output(cmd))
    pos1 = uuid.find("\\n") + 2
    uuid = uuid[pos1:-15]
    return uuid


def fetch_thing(url, params, method):
    if method == 'POST':
        params = parse.urlencode(params).encode("utf-8")
        f = request.urlopen(url, params)
    else:
        params = parse.urlencode(params)
        f = request.urlopen(url + '?' + params)

    return f.read().decode('utf-8'), f.code


class ScaledLabel(QLabel):
    def __init__(self, *args, **kwargs):
        QLabel.__init__(self)
        self._pixmap = QPixmap(self.pixmap())

    def resizeEvent(self, event):
        self.setPixmap(self._pixmap.scaled(
            self.width(), self.height(),
            Qt.KeepAspectRatio))


class Main(QObject):
    signalStatus = pyqtSignal(bool)
    signalLog = pyqtSignal(str)
    signalQueue = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super(self.__class__, self).__init__(parent)
        self.app = parent

        # Create a gui object.
        self.dialog = Dialog(parent)

        self.setupConfig()

        # Create a new worker thread.
        self.createWorkerThread()

        # Make any cross object connections.
        self._connectSignals()

        config = ConfigParser(strict=False)
        config.read('config.ini')
        self.keyStart = config.get('macro', 'start')
        self.keyStop = config.get('macro', 'stop')

        keybinder.register_hotkey(self.dialog.winId(), self.keyStart, self.startWorker)
        keybinder.register_hotkey(self.dialog.winId(), self.keyStop, self.forceWorkerReset)

        self.dialog.ui.start.setText(" Start (%s)" % (self.keyStart))
        self.dialog.ui.stop.setText(" Stop (%s)" % (self.keyStop))

        self.dialog.show()

    def startWorker(self):
        self.dialog.ui.start.click()

    def setupConfig(self):
        config = ConfigParser(strict=False)
        config.read('config.ini')

        if not config.has_section("bindings"):
            config.add_section('bindings')

        if not config.has_option("bindings", "map"):
            config.set('bindings', 'map', 'm')

        if not config.has_option("bindings", "attack"):
            config.set('bindings', 'attack', '1')

        if not config.has_option("bindings", "interact"):
            config.set('bindings', 'interact', 'v')

        if not config.has_option("bindings", "journal"):
            config.set('bindings', 'journal', 'l')

        if not config.has_option("bindings", "swap"):
            config.set('bindings', 'swap', 'tab')

        if not config.has_option("bindings", "card"):
            config.set('bindings', 'card', '/')

        if not config.has_option("bindings", "jump"):
            config.set('bindings', 'jump', 'space')

        if not config.has_option("bindings", "item"):
            config.set('bindings', 'use', 'z')

        if not config.has_section("macro"):
            config.add_section('macro')

        if not config.has_option("macro", "start"):
            config.set('macro', 'start', 'Shift+F1')

        if not config.has_option("macro", "stop"):
            config.set('macro', 'stop', 'Shift+F2')

        self.dialog.ui.keyMap.setKeySequence(config.get('bindings', 'map'))
        self.dialog.ui.keyAttack.setKeySequence(config.get('bindings', 'attack'))
        self.dialog.ui.keyInteract.setKeySequence(config.get('bindings', 'interact'))
        self.dialog.ui.keyJournal.setKeySequence(config.get('bindings', 'journal'))
        self.dialog.ui.keySwap.setKeySequence(config.get('bindings', 'swap'))
        self.dialog.ui.keyJump.setKeySequence(config.get('bindings', 'jump'))
        self.dialog.ui.keyUse.setKeySequence(config.get('bindings', 'use'))
        self.dialog.ui.keyCardDuel.setKeySequence(config.get('bindings', 'card'))

        self.dialog.ui.keyStart.setKeySequence(config.get('macro', 'start'))
        self.dialog.ui.keyStop.setKeySequence(config.get('macro', 'stop'))

        self.keyStart = config.get('macro', 'start')
        self.keyStop = config.get('macro', 'stop')

        if not config.has_section("cardduel"):
            config.add_section('cardduel')

        if not config.has_option("cardduel", "standard"):
            config.set('cardduel', 'standard', 'Deck 1')

        if not config.has_option("cardduel", "3starwar"):
            config.set('cardduel', '3starwar', 'Deck 2')

        standardIndex = self.dialog.ui.deckStandard.findText(config.get('cardduel', 'standard'), Qt.MatchFixedString)
        if standardIndex >= 0:
            self.dialog.ui.deckStandard.setCurrentIndex(standardIndex)

        _3starIndex = self.dialog.ui.deck3StarWar.findText(config.get('cardduel', '3starwar'), Qt.MatchFixedString)
        if _3starIndex >= 0:
            self.dialog.ui.deck3StarWar.setCurrentIndex(_3starIndex)

        with open('config.ini', 'w') as f:
            config.write(f)

    def _connectSignals(self):
        self.dialog.ui.stop.clicked.connect(self.forceWorkerReset)
        self.dialog.ui.tableWidget.itemChanged.connect(self.updateQueue)
        self.dialog.ui.paragonTable.itemChanged.connect(self.updateParagonItems)

        self.dialog.ui.keyStart.keySequenceChanged.connect(self.updateControlKey)
        self.dialog.ui.keyStop.keySequenceChanged.connect(self.updateControlKey)

        self.signalStatus.connect(self.dialog.updateStatus)
        self.signalLog.connect(self.dialog.log)
        self.signalQueue.connect(self.dialog.updateQueueStatus)

        self.parent().aboutToQuit.connect(self.forceWorkerQuit)

    def updateControlKey(self, val):
        sender = self.sender()
        key = val.toString().replace(", ", "+")

        print("=======")
        print("Oldkey: " + self.keyStart)
        print("Newkey: " + key)

        if sender.objectName() == "keyStart":
            if not key:
                print("Empty, setting back to: " + self.keyStart)
                return

            keybinder.unregister_hotkey(self.dialog.winId(), self.keyStart)
            ok = keybinder.register_hotkey(self.dialog.winId(), key, self.worker.startWork)
            if not ok:
                print("Unable to set hotkey")
                return
            self.keyStart = key
        elif sender.objectName() == "keyStop":
            if not key:
                print("Empty, setting back to: " + self.keyStop)
                return

            keybinder.unregister_hotkey(self.dialog.winId(), self.keyStop)
            ok = keybinder.register_hotkey(self.dialog.winId(), key, self.forceWorkerReset)
            if not ok:
                print("Unable to set hotkey")
                return
            self.keyStop = key

        config = ConfigParser(strict=False)
        config.read('config.ini')
        config.set('macro', 'start', self.keyStart)
        config.set('macro', 'stop', self.keyStop)
        with open('config.ini', 'w') as f:
            config.write(f)


    def createWorkerThread(self):
        self.worker = WorkerObject()
        self.worker_thread = QThread()
        self.worker.queue = {}
        self.updateParagonItems()
        #self.worker.paragonItems = {}

        self.worker.KMap = self.dialog.ui.keyMap.keySequence().toString()
        self.worker.KAttack = self.dialog.ui.keyAttack.keySequence().toString()
        self.worker.KInteract = self.dialog.ui.keyInteract.keySequence().toString()
        self.worker.KJournal = self.dialog.ui.keyJournal.keySequence().toString()
        self.worker.KSwap = self.dialog.ui.keySwap.keySequence().toString()
        self.worker.KCard = self.dialog.ui.keyCardDuel.keySequence().toString()
        self.worker.KJump = self.dialog.ui.keyJump.keySequence().toString()
        self.worker.KUse = self.dialog.ui.keyUse.keySequence().toString()

        # self.worker.KStart = self.dialog.ui.keyStart.keySequence().toString()
        # self.worker.KStop = self.dialog.ui.keyStop.keySequence().toString()

        self.worker.deckStandard = str(self.dialog.ui.deckStandard.currentText())
        self.worker.deck3StarWar = str(self.dialog.ui.deck3StarWar.currentText())

        # Setup the worker object and the worker_thread.
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.start()

        # Connect any worker signals
        self.worker.signalStatus.connect(self.dialog.updateStatus)
        self.worker.signalLog.connect(self.dialog.log)
        self.worker.signalQueue.connect(self.dialog.updateQueueStatus)

        self.dialog.ui.start.clicked.connect(self.worker.startWork)

        self.dialog.ui.keyMap.keySequenceChanged.connect(self.worker.updateKMap)
        self.dialog.ui.keyAttack.keySequenceChanged.connect(self.worker.updateKAttack)
        self.dialog.ui.keyInteract.keySequenceChanged.connect(self.worker.updateKInteract)
        self.dialog.ui.keyJournal.keySequenceChanged.connect(self.worker.updateKJournal)
        self.dialog.ui.keySwap.keySequenceChanged.connect(self.worker.updateKSwap)
        self.dialog.ui.keyCardDuel.keySequenceChanged.connect(self.worker.updateKCard)

        self.dialog.ui.keyJump.keySequenceChanged.connect(self.worker.updateKJump)
        self.dialog.ui.keyUse.keySequenceChanged.connect(self.worker.updateKUse)

        self.dialog.ui.deckStandard.currentTextChanged.connect(self.worker.updateDeckStandard)
        self.dialog.ui.deck3StarWar.currentTextChanged.connect(self.worker.updateDeck3StarWar)

        self.dialog.ui.deck3StarWar.currentTextChanged.connect(self.worker.updateDeck3StarWar)

    def updateParagonItems(self):
        if not hasattr(self.worker, 'paragonItems'):
            self.worker.paragonItems = {}
        for row in range(self.dialog.ui.paragonTable.rowCount()):
            name = self.dialog.ui.paragonTable.item(row, 0)
            item = self.dialog.ui.paragonTable.cellWidget(row, 1)
            self.worker.paragonItems.update({name.text(): item.pixmap()})

    def updateQueue(self):
        for index, irow in enumerate(range(self.dialog.ui.tableWidget.rowCount())):
            row = []
            for icol in range(self.dialog.ui.tableWidget.columnCount()):
                cell = self.dialog.ui.tableWidget.item(irow, icol)
                if cell is not None:
                    row.append(cell.text())

            self.worker.queue.update({index: row})

    def forceWorkerReset(self):
        if self.worker_thread.isRunning():
            self.worker.stop()

            self.dialog.log('Terminating thread')
            self.worker_thread.terminate()

            self.dialog.log('Waiting for thread termination')
            self.worker_thread.wait()

            self.signalStatus.emit(False)

            self.dialog.log('Building new working object')
            self.createWorkerThread()

            self.dialog.log('Ready')

    def forceWorkerQuit(self):
        if self.worker_thread.isRunning():
            self.worker.stop()
            self.worker_thread.terminate()
            self.worker_thread.wait()


def region_grabber(region):
    x1 = region[0]
    y1 = region[1]
    width = region[2] - x1
    height = region[3] - y1

    return pyautogui.screenshot(region=(x1, y1, width, height))


def imageSearch(image, precision=0.9, screenshot=False):
    im = pyautogui.screenshot()

    img_rgb = array(im)
    img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)

    if screenshot:
        template = cv2.cvtColor(array(image), cv2.COLOR_BGR2GRAY)
    else:
        template = cv2.imread(image, 0)
        template.shape[::-1]

    res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    if max_val < precision:
        # print ("^ Not found")
        return [-1, -1]
    return max_loc


def imageSearchArea(image, x1, y1, x2, y2, precision=0.9, im=None, screenshot=False):
    x = str(round(time()))

    if x1 < 0 or y1 < 0:
        return [-1, -1]

    if im is None:
        im = region_grabber(region=(x1, y1, x2, y2))
        #print("Saving -> " + x)
        # usefull for debugging purposes, this will save the captured region as "testarea.png"

    #if image == 'images/QuestComplete_Indicator.png' or image == 'images/QuestInProgress.png':
        #im.save('testarea_' + x + '.png')

    img_rgb = array(im)
    img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)
    #template = cv2.imread(image, 0)
    if screenshot:
        template = cv2.cvtColor(array(image), cv2.COLOR_BGR2GRAY)
    else:
        template = cv2.imread(image, 0)
        template.shape[::-1]

    res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    if max_val < precision:
        return [-1, -1]
    return max_loc


def imageSearchLoop(image, timesample, precision=0.9, customFunction=None, timeout=0):
    pos = imageSearch(image, precision=precision)
    timer = time()
    while pos[0] == -1:
        curTime = time() - timer
        #if timeout > 0 and curTime > timeout:
        if 0 < timeout < curTime:
            return [-1, -1]

        if customFunction is not None:
            print("Doing " + customFunction.__name__)
            customFunction()

        pos = imageSearch(image, precision)
        if timesample > 0 and pos[0] == -1:
            sleep(timesample)
            print(image + " not found, waiting (" + str(curTime) + "s)")

    return pos


def imageSearchCount(image, precision=0.9, screenshot=False):
    img_rgb = pyautogui.screenshot()
    img_rgb = array(img_rgb)
    img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)

    if screenshot:
        template = cv2.cvtColor(array(image), cv2.COLOR_BGR2GRAY)
    else:
        template = cv2.imread(image, 0)

    w, h = template.shape[::-1]
    res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
    loc = where(res >= precision)
    count = []
    for pt in zip(*loc[::-1]):
        cv2.rectangle(img_rgb, pt, (pt[0] + w, pt[1] + h), (0, 0, 255), 2)
        count.append((pt[0], pt[1]))
    # cv2.imwrite('result.png', img_rgb)
    return count


def imageSearchCountArea(image, x1, y1, x2, y2, precision=0.9, im=None):
    if x1 < 0 or y1 < 0:
        return [-1, -1]

    if im is None:
        im = region_grabber(region=(x1, y1, x2, y2))
        # im.save('testarea.png')
        # usefull for debugging purposes, this will save the captured region as "testarea.png"

    img_rgb = im
    img_rgb = array(img_rgb)
    img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)

    template = cv2.imread(image, 0)
    w, h = template.shape[::-1]

    res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
    loc = where(res >= precision)
    count = []
    for pt in zip(*loc[::-1]):
        cv2.rectangle(img_rgb, pt, (pt[0] + w, pt[1] + h), (0, 0, 255), 2)
        count.append((pt[0], pt[1]))
    # cv2.imwrite('result.png', img_rgb)
    return count


def clickImage(image, pos, action, timestamp, offset=(0, 0), screenshot=False):
    if screenshot:
        img = cv2.cvtColor(array(image), cv2.COLOR_BGR2GRAY)
    else:
        img = cv2.imread(image)
    height, width, channels = img.shape
    #pyautogui.moveTo(pos[0] + (width / 2) + offset[0], pos[1] + (height / 2) + offset[1], timestamp)
    x = pos[0] + (width / 2) + offset[0]
    y = pos[1] + (height / 2) + offset[1]
    click(action=action, x=x, y=y)


def click(action="left", x=None, y=None):
    #pyautogui.click(x=x, y=y)
    pyautogui.mouseDown(x=x, y=y, button=action, pause=0.2);
    pyautogui.mouseUp(x=x, y=y, button=action)


def r(num, rand):
    return num + rand * random()


def press(key):
    if isinstance(key, list):
        for i in key:
            pyautogui.keyDown(i)

        for i in key:
            pyautogui.keyUp(i)
    else:
        pyautogui.keyDown(key)
        pyautogui.keyUp(key)


def searchAndClickImage(image, precision=0.8, offset=(0, 0)):
    pos = imageSearch(image, precision)
    if pos[0] != -1:
        clickImage(image, pos, "left", 0, offset)
        return [pos[0], pos[1]]

    print("Not found: " + image + " [" + str(precision) + "]")
    return [-1, -1]


class WorkerObject(QObject):
    signalStatus = pyqtSignal(bool)
    signalLog = pyqtSignal(str)
    signalQueue = pyqtSignal(int, int)

    # 0 = idle
    # 1 = processing
    # 2 = done

    def __init__(self, parent=None):
        super(self.__class__, self).__init__(parent)
        self.isRunning = False
        self.KMap = None
        self.KAttack = None
        self.KInteract = None
        self.KJournal = None
        self.KSwap = None
        self.KCard = None

        self.deckStandard = None
        self.deck3StarWar = None

    def stop(self):
        self.isRunning = False

    def log(self, text):
        self.signalLog.emit(str(text))

    @pyqtSlot()
    def startWork(self):
        if self.isRunning:
            self.log("Already started")
            return

        self.isRunning = True
        self.signalStatus.emit(True)

        w = WindowMgr()
        w.find_window_wildcard(".*Aura Kingdom Online.*")
        try:
            w.set_foreground()
        except:
            self.log("Could not find Aura Kingdom's window!")
            self.signalStatus.emit(False)
            self.isRunning = False
            return
        sleep(1)

        for key, value in self.queue.items():
            print(key, '->', value)
            if value[2] == "Done" or value[2] == "Aborted":
                continue

            self.signalQueue.emit(key, 1)
            mode = value[0]
            char = value[1]
            self.log("Mode: " + mode)
            self.log("Character: " + char)

            if mode == "Dungeon Leech [3/1] [No Limit]":
                self.doLeeching("dungeon31")
            elif mode == "Dungeon Leech [2/1] [No Limit]":
                self.doLeeching("dungeon21")
            elif mode == "Dungeon Leech [1/1] [No Limit]":
                self.doLeeching("dungeon11")
            elif mode == "Daily Field Quests":
                self.doFieldDailies()
            elif mode == "Card Duels [Standard]":
                self.doCardDuel("standard")
            elif mode == "Card Duels [Standard] [No Limit]":
                self.doCardDuel("standard", True)
            elif mode == "Card Duels [3 Star War]":
                self.doCardDuel("3starwar")
            elif mode == "Card Duels [3 Star War] [No Limit]":
                self.doCardDuel("3starwar", True)
            elif mode == "Paragon Auto Roll":
                self.doParagon()

            self.signalQueue.emit(key, 2)

        self.signalStatus.emit(False)
        self.log("Queue finished")
        self.isRunning = False

    def updateKMap(self, val):
        self.KMap = val.toString()
        self.updateKConfig("map", val.toString())

    def updateKAttack(self, val):
        self.KAttack = val.toString()
        self.updateKConfig("attack", val.toString())

    def updateKInteract(self, val):
        self.KInteract = val.toString()
        self.updateKConfig("interact", val.toString())

    def updateKJournal(self, val):
        self.KJournal = val.toString()
        self.updateKConfig("journal", val.toString())

    def updateKSwap(self, val):
        self.KSwap = val.toString()
        self.updateKConfig("swap", val.toString())

    def updateKCard(self, val):
        self.KCard = val.toString()
        self.updateKConfig("card", val.toString())

    def updateKJump(self, val):
        self.KJump = val.toString()
        self.updateKConfig("jump", val.toString())

    def updateKUse(self, val):
        print(val.toString())
        self.KUse = val.toString()
        self.updateKConfig("use", val.toString())

    def updateDeckStandard(self, val):
        self.deckStandard = val
        self.updateDeckConfig("standard", val)

    def updateDeck3StarWar(self, val):
        self.deck3StarWar = val
        self.updateDeckConfig("3starwar", val)

    def updateDeckConfig(self, name, key):
        config = ConfigParser(strict=False)
        config.read('config.ini')

        if not config.has_section("cardduel"):
            config.add_section('cardduel')

        config.set('cardduel', name, key)

        with open('config.ini', 'w') as f:
            config.write(f)

    def updateKConfig(self, name, key):
        config = ConfigParser(strict=False)
        config.read('config.ini')

        if not config.has_section("bindings"):
            config.add_section('bindings')

        config.set('bindings', name, key)

        with open('config.ini', 'w') as f:
            config.write(f)

    def tigerHeal(self):
        while True:
            press("f2")
            press("num1")
            sleep(1.5)
            press("num3")
            sleep(1)

            pos = imageSearch("images/test.png", 0.95)
            if pos[0] == -1:
                self.log("done")
                break

    def nothing(self):
        self.log("This task is unavailable")

    def addQueue(self, item):
        print(item.data().toString())

    def onCurrentModeChanged(self, i):
        print("Index changed to " + str(i))
        self.mode = i

    def doParagon(self):
        if len(self.paragonItems.items()) < 1:
            self.log("Empty paragon items, please check Settings -> Paragon Items")
            return
        while True:
            searchAndClickImage("images/Paragon_TakeAll.png", 0.98)
            searchAndClickImage("images/Paragon_Ruby.png", 0.98)
            start = searchAndClickImage("images/Paragon_Start.png", 0.95)
            if start[0] != -1:
                sleep(0.7)
                pos = imageSearch("images/Paragon_Confirm.png", 0.9)
                if pos[0] != -1:
                    self.log("Confirm")
                    searchAndClickImage("images/Paragon_OK.png", 0.9)
                    pyautogui.moveTo(start[0], start[1], 0)
                else:
                    self.log("No confirm")

                colorCheck = pyautogui.locateOnScreen("images/Paragon_Receive.png", confidence=0.999)
                if colorCheck is not None:
                    clickImage('images/Paragon_Receive.png', [colorCheck[0], colorCheck[1]], "left", 0)
                    self.log("Top row reached, receiving item and attempting to roll again..")
                    continue

                self.log("Rolling paragon..")
                rec = imageSearchLoop('images/Paragon_Receive.png', 1, 0.95, timeout=10)
                if rec[0] == -1:
                    self.log("Cannot receive any item, stopping (something is wrong)")
                    break

                pos = imageSearch("images/Paragon_ItemPos.png", 0.99)
                self.log("Checking what we got..")
                if pos[0] == -1:
                    self.log("Cannot locate item rewards window, please do not block paragon table view")
                    self.log("Stopping")
                    break

                foundSomething = False
                for name, key in self.paragonItems.items():
                    img = QImage(key)
                    buffer = QBuffer()
                    buffer.open(QBuffer.ReadWrite)
                    img.save(buffer, "PNG")
                    pil_im = Image.open(io.BytesIO(buffer.data()))

                    '''
                    checkItem = imageSearchArea(pil_im,
                                             pos[0], pos[1], pos[0] + 70, pos[1] + 80,
                                             precision=0.99, screenshot=True)
                    if checkItem[0] != -1:
                        self.log("Found: " +  name)
                        foundSomething = True
                        break
                    '''
                    checkItem = pyautogui.locateOnScreen(image=pil_im,
                                                   region=(pos[0], pos[1], 70, 80), confidence=0.85)
                    if checkItem is not None:
                        self.log("Found: " + name)
                        foundSomething = True
                        break

                if foundSomething:
                    clickImage('images/Paragon_Receive.png', rec, "left", 0)
                    click("left")
                    sleep(0.5)
                    check = imageSearch('images/Paragon_Receive.png', 0.95)
                    if check[0] != -1:
                        self.log("Inventory could be full, stopping")
                        break
            else:
                pos = searchAndClickImage("images/Paragon_Receive.png", 0.98)
                if pos[0] != -1:
                    self.log("Cannot advance to next row")
                else:
                    self.log("Unable to find 'Go for it!' button")
                    self.log("Please check if paragon table is visible")
                    break

            sleep(2)

    def doCardDuel(self, mode, nolimit = False):
        while True:
            def openDeck():
                press(self.KCard)
                sleep(1)

            self.log("Waiting for Card Deck UI")
            imageSearchLoop('images/DeckOpened_Indicator.png', 1.5, customFunction=openDeck)
            self.log("Card Deck UI opened")
            sleep(0.5)

            pos = imageSearch("images/CardDuel_NoEntry.png", 0.99)
            if pos[0] != -1:
                if nolimit:
                    press(self.KUse)
                    sleep(3)
                else:
                    self.log("Card Duel finished because no entry left")
                    break

            self.log("Initiating Random Duel")
            searchAndClickImage("images/RandomDuel_Btn.PNG")
            pyautogui.moveTo(1, 1, 0)

            sleep(1)
            pos = imageSearch("images/DuelInfo_Indicator.png")
            if pos[0] == -1:
                self.log("No duel info detected, retrying..")
                press("esc")
                continue

            if mode == "standard":
                deck = self.deckStandard.replace(" ", "_")
                pos = pyautogui.locateOnScreen(image=r'images/Duel' + deck + '.png',
                                               region=(pos[0] - 20, pos[1] + 60, 200, 50),
                                               grayscale=True, confidence=0.95)
                if pos is not None:
                    self.log("Found " + deck)
                    clickImage('images/Duel' + deck + '.png', pos, "left", 0)

            elif mode == "3starwar":
                deck = self.deck3StarWar.replace(" ", "_")
                pos = pyautogui.locateOnScreen(image=r'images/Duel' + deck + '.png',
                                               region=(pos[0] - 20, pos[1] + 60, 200, 50),
                                               grayscale=True, confidence=0.95)
                if pos is not None:
                    self.log("Found " + deck)
                    clickImage('images/Duel' + deck + '.png', pos, "left", 0)

                searchAndClickImage("images/CardDuelType_Standard.PNG")
                sleep(0.5)
                searchAndClickImage("images/CardDuelType_3StarWar.PNG")

            searchAndClickImage("images/CardDuel_OK.PNG")
            sleep(1)

            pos = imageSearch("images/DuelInfo_Indicator.png")
            if pos[0] != -1:
                self.log("Check Card Deck's requirements!")
                break

            self.log("Queueing Card Duel")
            pos = imageSearchLoop('images/CardDuel_Begin.png', 1, timeout=70)
            if pos[0] == -1:
                self.log("Queue timeout, re-queueing..")
                continue

            self.log("Card Battle begins!")
            sleep(1)

            start = perf_counter()
            failSafe = False
            basePos = imageSearchCount("images/CardHPBar.png", 0.95)
            while len(basePos) < 5:
                if basePos == 1:
                    start = perf_counter()

                if (len(basePos) > 0 and round(perf_counter() - start) >= 10) \
                        or (len(basePos) < 1 and round(perf_counter() - start) >= 20):
                    self.log("Card duel Fail-safe trigerred")
                    failSafe = True
                    break

                count = imageSearchCount("images/CardHPBar.png", 0.95)
                basePos = count if len(count) > len(basePos) else basePos
                self.log("Card Count: " + str(len(basePos)))

            def isDuelFinished():
                while True:
                    pos = imageSearch("images/CardDuel_Finished.png", 0.95)
                    if pos[0] != -1:
                        self.log("Card Duel finished!")
                        break
                    sleep(1)

            t1 = Thread(target=isDuelFinished, args=())
            t1.start()

            while t1.isAlive():
                for i, k in enumerate(basePos):
                    #if not t1.isAlive():
                        #break

                    x, y = k[0], k[1]
                    x += 20
                    y += 30

                    for u in (range(2)):
                        self.log("Iterate Card [" + str(i) + "]: Skill " + str(u))
                        buff_x = x - 5
                        buff_y = y + 10

                        pyautogui.moveTo(x, y, 0)
                        pyautogui.mouseDown(button="left");
                        pyautogui.mouseUp(button="left")

                        if pyautogui.locateOnScreen('images/CardAttack_Skill.png',
                                                    region=(buff_x, buff_y, 23, 7)) is not None:
                            pyautogui.moveTo(x, y - 250, 0)
                            pyautogui.mouseDown(button="left");
                            pyautogui.mouseUp(button="left")
                            self.log("Attack from index: " + str(i))
                        elif pyautogui.locateOnScreen('images/CardBuff_Skill.png',
                                                      region=(buff_x, buff_y, 23, 7)) is not None:
                            pyautogui.moveTo(x, y - 100, 0)
                            pyautogui.mouseDown(button="left");
                            pyautogui.mouseUp(button="left")
                            self.log("Attack from index: " + str(i))

                        x += 40
            sleep(1)

    def doFieldDailies(self):
        def checkButterfly(objCount):
            press(self.KInteract)
            sleep(1)
            pos = imageSearch("images/QuestSkip_Btn.png")
            if pos[0] != -1:
                clickImage('images/QuestSkip_Btn.png', pos, "left", 0)
                sleep(1)
                searchAndClickImage('images/dailyquests/lostbutterfly_trigger.png')

        def interactWithNpc(curTime = None):
            '''pos = imageSearch("images/QuestComplete_Indicator.png", 0.99)
            if pos[0] == -1:
                sleep(6)'''
            press("a")
            press(self.KInteract)

        def explore(objCount):
            if objCount == 1:
                obj = pyautogui.position()
                pos = imageSearch("images/dailyquests/explore_unstuck.png", 0.99)
                if pos[0] != -1:
                    self.log("Found the point")
                    click("left", pos[0] - 3, pos[1])
                    sleep(5)
                    click("left", obj[0], obj[1])
                    sleep(5)

        def jump(curTime):
            print("curTime: " + str(round(curTime)))
            if round(curTime) % 5 == 0:
                press(self.KJump)

        questListA = {
            # TODO: add jumps on flying demons after quest
            'otiumcrystal': (1, -1, -1, None, None, None),
            'flyingdemons': (1, 5, 0.6, None, None, jump),
            'friendship': (1, -1, -1, None, None, None),
            'wastedisposal': (1, 5, 0.6, None, None, None),
            'supplynetwork': (1, -1, -1, None, None, None),
            'confirm': (1, -1, -1, None, None, None),
            'public': (1, -1, -1, None, None, None),
            'explore': (1, 15, -1, None, explore, None),
            'annoying': (1, -1, -1, None, None, jump),
            # TODO: Add anti stuck jumps after quest annoying
            #'refusing': (1, 5, 0.6, None, None, None),
            'determine': (1, -1, 0.6, None, None, None),
            'road': (1, 5, 0.6, None, None, None),
            'importance': (1, -1, -1, None, None, None),
            'control': (1, 5, 0.6, None, None, None),
            'waring': (1, -1, -1, None, None, None),
            'sleeping': (1, 5, 0.6, None, None, None), }

        questListB = {
            'frontline': (1, -1, -1, None, None, None),
            'repairammo': (1, 5, 0.6, None, None, None),
            'reservesupplies': (1, 5, 0.6, None, None, None),
            'dogslesson': (1, 5, 0.6, None, None, None),
            'hiddenthreats': (1, -1, -1, None, None, None),
            'soldiersfru': (1, 5, 0.6, None, None, None),
            # 'secretforest': (1.5, 15, 0.6, None, None, None),
            'restlesstree': (1, 5, 0.6, None, None, None),
            'guardaction': (1, -1, -1, None, None, None),
            'difficulties': (1, 5, 0.6, None, None, None),
            'makewound': (1, 5, 0.6, None, None, None),
            'clear': (1, -1, -1, None, None, None),
            'forsakenwaste': (1, -1, -1, interactWithNpc, None, interactWithNpc),
            'Mischiveous': (1, 5, 0.6, None, None, None),
            'lostbutterfly': (1, 5, -1, None, checkButterfly, None),
            'tailoring': (1, 5, 0.6, None, None, None), }

        quests = {**questListA, **questListB}.items()
        skippedQuests = []
        initView = False
        press(['shift', 'r'])
        while True:
            searchAndClickImage("images/QuestClose_UI.png")
            self.log("Waiting for the journal window")
            pos = imageSearch("images/JournalOpened_Indicator.png", 0.99)
            if pos[0] != -1:
                scrollable = list(pos)
                scrollable[0] += 150
                scrollable[1] += 30
                self.log("Journal UI is found")

                pos = imageSearch("images/CategoryField_Icon.png", 0.95)

                if pos[0] != -1:
                    self.log("Found field category")
                    search = imageSearchCountArea("images/FieldQuest_Init.png", pos[0], pos[1], pos[0] + 250,
                                                  pos[1] + 200, 0.95)
                    if len(search) < 2:
                        self.log("Unable to see quests, scrolling down")
                        pyautogui.moveTo(scrollable[0], scrollable[1], 0)
                        pyautogui.scroll(-50)
                        continue

                    initView = True
                    self.log("Scanning field quests")
                    isQuestFound = False
                    self.log("Quest scan begins")

                    for questName, param in quests:
                        if skippedQuests.__contains__(questName):
                            self.log("Skipped: " + questName)
                            continue

                        self.log("Looking for: " + questName)
                        status = self.doQuest(questName, param[0], param[1], param[2], param[3], param[4],
                                              param[5])

                        if status == 0:
                            skippedQuests.append(questName)
                        elif status == 1:
                            skippedQuests.append(questName)
                            isQuestFound = True
                        elif status == 2:
                            isQuestFound = True
                            initView = False

                        if isQuestFound:
                            self.log("Quest finished completely, breaking the loop")
                            break
                    if isQuestFound is False:
                        self.log("No more available quests")
                        return
                else:
                    if initView is False:
                        searchAndClickImage('images/CloseCategory.png', offset=(15, 0))
            else:
                press("esc")
                press(self.KJournal)
            sleep(1)

    def doQuest(self, questName, interval=10, interactStartAt=15, interactOffset=0.6,
                beforeQuestFunction=None, inQuestFunction=None, afterQuestFunction=None):
        label = "images/dailyquests/" + questName + "_label.png"
        npc = "images/dailyquests/" + questName + "_npc.png"
        labelPos = imageSearch(label)

        if labelPos[0] != -1:
            self.log("Found a quest: " + questName)
            clickImage(label, labelPos, "left", 0)
            self.log("Walking to NPC")
            pos = searchAndClickImage(npc)
            if pos[0] != -1:
                while True:
                    sleep(1)
                    '''pos = imageSearch("images/NPC_Icon.png")
                    if pos[0] != -1:
                        press("esc")
                        press(self.KMap)'''

                    if beforeQuestFunction is not None:
                        self.log("Running custom function before quest")
                        beforeQuestFunction()

                    pos = searchAndClickImage("images/QuestSkip_Btn.png")
                    if pos[0] != -1:
                        sleep(1)
                        pos = imageSearch("images/QuestAccept_Btn.png")
                        if pos[0] != -1:
                            clickImage("images/QuestAccept_Btn.png", pos, "left", 0)
                            self.log("Quest accepted")
                            sleep(1.5)

                            self.log("Doing the objectives")
                            self.doObjective(questName, interactStartAt, interactOffset, interval, inQuestFunction)

                            timer = time()
                            mounted = False
                            self.log("Turning it to NPC")
                            while True:
                                curTime = time() - timer
                                if interactOffset > -1 and curTime > 5 and not mounted:
                                    press(['shift', 'r'])
                                    mounted = True

                                pos = imageSearch("images/QuestSkip_Btn.png")
                                if pos[0] != -1:
                                    self.log("NPC Found")
                                    if pos[0] != -1:
                                        clickImage("images/QuestSkip_Btn.png", pos, "left", 0)
                                        sleep(0.8)
                                        pos = searchAndClickImage('images/QuestComplete_Btn.png', 0.95)
                                        if pos[0] != -1:
                                            self.log("Quest completed")
                                            break

                                #press(self.KJump)
                                pos = imageSearch("images/ClickableQuest.png")
                                if pos[0] != -1:
                                    if afterQuestFunction is not None:
                                        self.log("Running custom function after quest")
                                        afterQuestFunction(curTime)
                                    pyautogui.moveTo(pos[0] + 50, pos[1] + 3)
                                    click()
                        break
                    else:
                        def openMap():
                            press("esc")
                            press(self.KJournal)
                            sleep(1)

                        imageSearchLoop('images/JournalOpened_Indicator.png', 1, 0.99, customFunction=openMap)
                        #press(self.KJump)
                        posLabel = searchAndClickImage(label)
                        posNpc = searchAndClickImage(npc)
                        if posLabel[0] == -1 and posNpc[0] == -1:
                            self.log("Unable to find NPC and label")
                            if imageSearch('images/MapLoad_Indicator.png')[0] != -1:
                                self.log("Still loading the map..")
                                sleep(2)
                                continue
                            elif imageSearch("images/QuestSkip_Btn.png")[0] != -1:
                                self.log("Found the skip button!")
                                continue
                            self.log("Retrying to find a new quest..")
                            return 2

            return 1
        return 0

    def doObjective(self, questName, interactStartAt=0, interactOffset=0, interval=1, customFunction=None):
        start = perf_counter()
        objectives = []
        objCount = 0

        pos = imageSearchLoop('images/QuestTracker_Pos.png', 1, precision=0.9, timeout=15)
        if pos[0] == -1:
            self.log("Unable to find quest tracker")
            return

        questTrackerPos = [pos[0], pos[1] - 340, pos[0] + 300, pos[1] + 140]
        questTrackerPos[1] = 0 if questTrackerPos[1] < 0 else questTrackerPos[1]
        while len(objectives) == 0:
            objectives = imageSearchCount("images/ClickableQuest.png")
        totalObjective = len(objectives)

        while self.isRunning:
            im = region_grabber(region=(questTrackerPos[0], questTrackerPos[1], questTrackerPos[2], questTrackerPos[3]))
            check1 = imageSearchArea("images/QuestComplete_Indicator.png", questTrackerPos[0], questTrackerPos[1],
                                     questTrackerPos[2], questTrackerPos[3], 0.9, im=im)
            #check2 = imageSearchArea("images/QuestInProgress.png", questTrackerPos[0], questTrackerPos[1],
            #                         questTrackerPos[2], questTrackerPos[3], 0.9, im=im)
            #if check1[0] != -1 and check2[0] == -1:
            if check1[0] != -1:
                self.log("Objectives completed")
                break

            objectives = imageSearchCount("images/ClickableQuest.png")
            objectivesCompleted = imageSearchCount("images/ObjectiveCompleted_Indicator.png")
            self.log("Quest Complete Check 1: " + str(check1[0] != -1))
            #self.log("Quest Complete Check 2: " + str(check2[0] == -1))
            self.log("Total objective count: " + str(totalObjective))
            self.log("Total objective available: " + str(len(objectives)))
            self.log("Total objective completed: " + str(len(objectivesCompleted)))

            if len(objectives) > 0 and totalObjective == len(objectivesCompleted) + len(objectives):
                objectivesOffset = 0
                for x, y in objectivesCompleted:
                    if y < objectives[0][1]:
                        objectivesOffset += 1

                objectiveIndex = objectivesOffset
                x = objectives[0][0] + 50
                y = objectives[0][1] + 3

                #press(self.KJump)
                click("left", x, y)
                self.log("Clicking objective[" + str(objectiveIndex) + "] on " + str(x) + " and " + str(y))

                end = round(perf_counter() - start)
                # if interactStartAt > -1 and end > interactStartAt:
                if -1 < interactStartAt < end:
                    if customFunction is not None:
                        self.log("Running custom function while in quest")
                        customFunction(objCount)

                    if interactOffset > -1:
                        sleep(interactOffset)
                        press(self.KSwap)
                        img = "images/dailyquests/" + questName + "_target_" + str(objectiveIndex) + ".png"
                        target = imageSearch(img, 0.99)
                        if target[0] != -1:
                            self.log("Target found")
                            count = 0
                            while target[0] != -1 and self.isRunning:
                                #press(self.KJump)
                                press(self.KAttack)
                                sleep(0.7)
                                target = imageSearch(img, 0.99)
                                if target[0] != -1:
                                    self.log("Target is still alive")
                                    count += 1
                                    if count % 5 == 0:
                                        self.log("Retrying to reposition")
                                        click("left", x, y)
                                        sleep(1)

                            self.log("Target is dead")
                        continue

            if len(objectives) > 0:
                self.log("Sleeping, interval: " + str(interval))
                #sleep(interval)
                sleep(0.1)

    def doLeeching(self, set):
        def isPartyMode():
            self.log("Party entry count: " + str(countParty) + ", selected: " + set)

            if set == "dungeon11" and countParty > 0:
                return False

            if set == "dungeon21" and countParty > 1:
                return False

            pos = imageSearch("images/Entry_31.png")
            if pos[0] != -1:
                self.log("3/1 available")
                return True

            pos = imageSearch("images/Entry_21.png")
            if pos[0] != -1:
                self.log("2/1 available")
                return True

            pos = imageSearch("images/Entry_11.png")
            if pos[0] != -1:
                self.log("1/1 available")
                return True

            self.log("No party mode available")
            return False

        countParty = 0
        while True:
            sleep(1)
            searchAndClickImage("images/Revive.PNG")
            self.log("Waiting for the teleportation")
            pos = imageSearch("images/teleport_UI.png")
            if pos[0] != -1:
                pos = searchAndClickImage('images/teleportOK_Btn.png')
                if pos[0] != -1:
                    self.log("Found the OK button")

                    # 30 seconds time out
                    if imageSearchLoop('images/MapLoad_Indicator.png', 1.5, timeout=15)[0] == -1:
                        continue

                    sleep(3)

                    openMap = lambda: press(self.KMap)
                    if imageSearchLoop('images/MapOpened_Indicator.png', 1.5, customFunction=openMap, timeout=15)[
                        0] == -1:
                        continue

                    pos = imageSearch("images/MapNPC_Label.png")
                    if pos[0] != -1:
                        sleep(0.5)
                        click(x=pos[0] + 170, y=pos[1] + 3)

                        # Silent Ancient Castle
                        pos = searchAndClickImage('images/dungeons/SilentAncientCastle_Label.png')
                        if pos[0] != -1:
                            pos = searchAndClickImage('images/Walk_Icon.png')
                            if pos[0] != -1:
                                imageSearchLoop("images/dungeonSelection_UI.png", 1.5)

                                if isPartyMode():
                                    countParty += 1
                                    self.log("Entering party mode")
                                    searchAndClickImage('images/dungeons/SilentAncientCastle_Party.png')
                                    searchAndClickImage('images/DungeonOK_Btn.png')
                                else:
                                    self.log("Entering hell mode")
                                    searchAndClickImage('images/dungeons/SilentAncientCastle_Hell.png')
                                    searchAndClickImage('images/DungeonOK_Btn.png')

                        # Dawn Passage
                        pos = searchAndClickImage('images/dungeons/DownPassage_Label.png')
                        if pos[0] != -1:
                            pos = searchAndClickImage('images/Walk_Icon.png')
                            if pos[0] != -1:
                                imageSearchLoop("images/dungeonSelection_UI.png", 1.5)

                                if isPartyMode():
                                    countParty += 1
                                    self.log("Entering party mode")
                                    searchAndClickImage('images/dungeons/DawnPassage_Party.png')
                                    searchAndClickImage('images/DungeonOK_Btn.png')
                                else:
                                    self.log("Entering hell mode")
                                    searchAndClickImage('images/dungeons/DawnPassage_Hell.png')
                                    searchAndClickImage('images/DungeonOK_Btn.png')

                        # Obscure Temple
                        pos = searchAndClickImage('images/dungeons/ObscureTemple_Label.png')
                        if pos[0] != -1:
                            pos = searchAndClickImage('images/Walk_Icon.png')
                            if pos[0] != -1:
                                imageSearchLoop("images/dungeonSelection_UI.png", 1.5)

                                if isPartyMode():
                                    countParty += 1
                                    self.log("Entering party mode")
                                    searchAndClickImage('images/dungeons/ObscureTemple_Party.png')
                                    searchAndClickImage('images/DungeonOK_Btn.png')
                                else:
                                    self.log("Entering hell mode")
                                    searchAndClickImage('images/dungeons/ObscureTemple_Hell.png')
                                    searchAndClickImage('images/DungeonOK_Btn.png')

                        # Tree Cave
                        pos = searchAndClickImage('images/dungeons/TreeCave_Label.png')
                        if pos[0] != -1:
                            pos = searchAndClickImage('images/Walk_Icon.png')
                            if pos[0] != -1:
                                imageSearchLoop("images/dungeonSelection_UI.png", 1.5)

                                if isPartyMode():
                                    countParty += 1
                                    self.log("Entering party mode")
                                    searchAndClickImage('images/dungeons/TreeCave_Party.png')
                                    searchAndClickImage('images/DungeonOK_Btn.png')
                                else:
                                    self.log("Entering hell mode")
                                    searchAndClickImage('images/dungeons/TreeCave_Hell.png')
                                    searchAndClickImage('images/DungeonOK_Btn.png')

                        # OW Chronowood
                        pos = searchAndClickImage('images/dungeons/OW_Chronowood_Label.png')
                        if pos[0] != -1:
                            pos = searchAndClickImage('images/Walk_Icon.png')
                            if pos[0] != -1:
                                imageSearchLoop("images/dungeonSelection_UI.png", 1.5)

                                pos = imageSearch("images/dungeons/OW_Chronowood_Party.png")
                                if pos[0] != -1:
                                    countParty += 1
                                    self.log("Entering party mode")
                                    searchAndClickImage('images/dungeons/OW_Chronowood_Party.png')
                                    searchAndClickImage('images/DungeonOK_Btn.png')
                                else:
                                    self.log("Entering hell mode")
                                    searchAndClickImage('images/dungeons/OW_Chronowood_Hell.png')
                                    searchAndClickImage('images/DungeonOK_Btn.png')

                        # OW Shattered Netherworld
                        pos = searchAndClickImage('images/dungeons/OW_Shattered_Label.png')
                        if pos[0] != -1:
                            pos = searchAndClickImage('images/Walk_Icon.png')
                            if pos[0] != -1:
                                imageSearchLoop("images/dungeonSelection_UI.png", 1.5)

                                pos = imageSearch("images/dungeons/OW_Shattered_Party.png", 0.9)
                                if pos[0] != -1:
                                    countParty += 1
                                    self.log("Entering party mode")
                                    searchAndClickImage('images/dungeons/OW_Shattered_Party.png')
                                    searchAndClickImage('images/DungeonOK_Btn.png')
                                else:
                                    self.log("Entering hell mode")
                                    searchAndClickImage('images/dungeons/OW_Shattered_Hell.png')
                                    searchAndClickImage('images/DungeonOK_Btn.png')

            if countParty > 3:
                countParty = 0

    def doPrimeFactors(self):
        for ii in range(6):
            number = randint(0, 5000 ** ii)
            self.signalLog.emit('Iteration: {}, Factoring: {}'.format(ii, number))
            i = 2
            factors = []
            while i * i <= number:
                if number % i:
                    i += 1
                else:
                    number //= i
                    factors.append(i)
            if number > 1:
                factors.append(number)

            print('Number: ', number, 'Factors: ', factors)


def checkLicense(code):
    try:
        address = gethostbyname("easyak.mooo.com")
        status, response_code = fetch_thing(
            'http://easyak.mooo.com/verify.php',
            {'uuid': GetUUID(), 'code': code},
            'POST'
        )
    except gaierror:
        status = "Offline"
    except URLError:
        status = "Offline"

    if status == "Valid":
        return 1
    else:
        msg = QMessageBox()
        msg.setWindowIcon(QIcon(scriptDir + path.sep + 'icons/icon.png'))
        if address != "167.71.214.166":
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle(version)
            msg.setText("Invalid DNS Server.")
            msg.setInformativeText("Please check `easyak.mooo.com` for updates.")
            msg.exec()
        elif status == "Pending" or status == "Registered":
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle(version)
            msg.setText("License key is waiting for verification.")
            msg.exec()
            return 2
        elif status == "Offline":
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle(version)
            msg.setText(
                "Please check your internet connection.")
            msg.exec()
        else:
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle(version)
            msg.setText(
                "License key is invalid or has expired")
            msg.exec()

    return 0


class Dialog(QDialog):
    def __init__(self, app):
        super().__init__()

        self.app = app
        self.ui = gui.Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.app.setAttribute(Qt.AA_DisableWindowContextHelpButton)
        self.setWindowIcon(QIcon(scriptDir + path.sep + 'icons/icon.png'))

        self.ui.label_5.setText("%s" % (version))
        self.ui.stop.setDisabled(True)
        self.ui.characters.addItem("None")
        self.ui.addTask.setDefault(True)
        self.ui.addTask.setFocus()
        self.ui.widget.setStyleSheet("background-color:#2e2d2b;")
        self.ui.hide.setStyleSheet("background-color:#2e2d2b;")
        self.ui.close.setStyleSheet("background-color:#2e2d2b;")
        self.ui.hide.setFlat(True)
        self.ui.close.setFlat(True)
        self.ui.tableWidget.setSelectionBehavior(QTableView.SelectRows)
        self.ui.paragonTable.setSelectionBehavior(QTableView.SelectRows)
        self.ui.testParagon.setDisabled(True)

        self.ui.keyStart.setDisabled(True)
        self.ui.keyStop.setDisabled(True)

        self.ui.comboBox.clear()
        self.ui.comboBox.addItem("Dungeon Leech [3/1] [No Limit]")
        self.ui.comboBox.addItem("Dungeon Leech [2/1] [No Limit]")
        self.ui.comboBox.addItem("Dungeon Leech [1/1] [No Limit]")
        self.ui.comboBox.addItem("Daily Field Quests")
        self.ui.comboBox.addItem("Card Duels [Standard]")
        self.ui.comboBox.addItem("Card Duels [Standard] [No Limit]")
        self.ui.comboBox.addItem("Card Duels [3 Star War]")
        self.ui.comboBox.addItem("Card Duels [3 Star War] [No Limit]")
        self.ui.comboBox.addItem("Paragon Auto Roll")

        screen = app.primaryScreen()
        rect = screen.availableGeometry()

        config = ConfigParser(strict=False)
        config.read('config.ini')

        if not config.has_section("main"):
            config.add_section('main')

        if not config.has_option("main", "license"):
            config.set('main', 'license', '')

        licenseCode = config.get('main', 'license')
        if licenseCode == '':
            dialog = QInputDialog(self)
            dialog.resize(QSize(300, 100))
            dialog.setWindowTitle(version)
            dialog.setLabelText("Enter License Code:")
            dialog.setTextEchoMode(QLineEdit.Normal)
            if dialog.exec_() == QDialog.Accepted:
                config.set('main', 'license', dialog.textValue())
                licenseCode = config.get('main', 'license')
            else:
                sys.exit()

        status = checkLicense(licenseCode)
        if status == 0:
            sys.exit()
        else:
            with open('config.ini', 'w') as f:
                config.write(f)
            if status == 2:
                sys.exit()

        self.move(rect.width() - self.width() - 15, rect.height() - self.height() - 15)
        self.ui.close.clicked.connect(self.exitClicked)
        self.ui.hide.clicked.connect(self.hideClicked)
        self.ui.addTask.clicked.connect(self.addTask)
        self.ui.removeTask.clicked.connect(self.removeTask)
        self.ui.screenshot.clicked.connect(self.screenshot)
        self.ui.testscreen.clicked.connect(self.testscreen)
        self.ui.save.clicked.connect(self.savescreen)
        self.ui.load.clicked.connect(self.loadimage)

        selectedItem = self.ui.paragonTable.selectionModel()
        selectedItem.selectionChanged.connect(self.updateParagonPreview)
        self.ui.addParagonItem.clicked.connect(self.addParagonItem)
        self.ui.removeParagonItem.clicked.connect(self.removeParagonItem)
        self.ui.testParagon.clicked.connect(self.testParagonItem)

    def test(self):
        print("YAY")

    def updateStatus(self, status):
        if status:
            self.ui.start.setDisabled(True)
            self.ui.addTask.setDisabled(True)
            self.ui.removeTask.setDisabled(True)
            self.ui.stop.setDisabled(False)
            self.ui.addParagonItem.setDisabled(True)
            self.ui.removeParagonItem.setDisabled(True)
        else:
            self.ui.start.setDisabled(False)
            self.ui.addTask.setDisabled(False)
            self.ui.removeTask.setDisabled(False)
            self.ui.stop.setDisabled(True)

            self.ui.addParagonItem.setDisabled(False)
            self.ui.removeParagonItem.setDisabled(False)

            for index in range(self.ui.tableWidget.rowCount()):
                status = self.ui.tableWidget.item(index, 2)
                if status.text() == "In Queue" or status.text() == "Processing":
                    stat = QTableWidgetItem('Aborted')
                    stat.setTextAlignment(Qt.AlignCenter)
                    stat.setForeground(QBrush(QColor(252, 3, 32)))
                    self.ui.tableWidget.setItem(index, 2, stat)

            # self.ui.tableWidget.setRowCount(0);
            # self.ui.tableWidget.setColumnCount(0);

    def updateQueueStatus(self, index, status):
        if status is 1:
            stat = QTableWidgetItem('Processing')
            stat.setTextAlignment(Qt.AlignCenter)
            stat.setForeground(QBrush(QColor(242, 255, 0)))
            self.ui.tableWidget.setItem(index, 2, stat)

        if status is 2:
            stat = QTableWidgetItem('Done')
            stat.setTextAlignment(Qt.AlignCenter)
            stat.setForeground(QBrush(QColor(0, 255, 0)))
            self.ui.tableWidget.setItem(index, 2, stat)

    def log(self, text):
        if text is str(text):
            print(text)
        self.ui.label_5.setText("%s >> %s" % (version, text))
        self.ui.listWidget.addItem(str(text))
        self.ui.listWidget.scrollToBottom()

    def goodbye(self):
        name = str(round(time()))
        makedirs("logs/", exist_ok=True)
        with open("logs/" + name + ".log", "w") as outfile:
            for i in range(self.ui.listWidget.count()):
                outfile.write("%s\n" % str(self.ui.listWidget.item(i).text()))

    def screenshot(self):
        self.ui.testscreen.setDisabled(False)
        self.ui.save.setDisabled(False)
        ScreenApp = Screenshot.SelectableApp()
        ScreenApp.MainLoop()
        region = ScreenApp.getRegion()
        del ScreenApp.frame
        del ScreenApp
        if region is not None:
            self.img = pyautogui.screenshot(region=region)

            qim = ImageQt(self.img)
            pix = QPixmap.fromImage(qim)
            pix.detach()
            self.ui.label_6.setPixmap(pix)
        self.app.processEvents()

    def loadimage(self):
        self.ui.testscreen.setDisabled(False)
        self.ui.save.setDisabled(False)

        fname = QFileDialog.getOpenFileName(self, 'Open file', 'images/', "Image files (*.jpg *.png *.bmp)")
        self.ui.label_6.setPixmap(QPixmap(fname[0]))
        self.img = Image.open(fname[0])

    def savescreen(self):
        file = "images/saves/" + strftime("%Y%m%d-%H%M%S") + ".png"
        self.img.save(file)
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Info")
        msg.setText("Screenshot saved to:")
        msg.setInformativeText(file)
        msg.exec()

    def testscreen(self):
        self.ui.label_6.setText("Loading")
        self.app.processEvents()

        '''checkItem = pyautogui.locateOnScreen(image=self.img, confidence=self.ui.doubleSpinBox.value())
        qim = ImageQt(self.img)
        pix = QPixmap.fromImage(qim)
        pix.detach()
        self.ui.label_6.setPixmap(pix)
        if checkItem is not None:
            pyautogui.moveTo(checkItem[0], checkItem[1], 0)
            print(True)
        else:
            print(False)

        return'''

        test = imageSearch(self.img, self.ui.doubleSpinBox.value(), screenshot=True)
        x = imageSearchCount(self.img, self.ui.doubleSpinBox.value(), screenshot=True)
        count = len(x)

        msg = QMessageBox()
        if test[0] > -1:
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Info")
            msg.setText("Image located on " + str(test))
            msg.setInformativeText("Count: " + str(count))

            img = cv2.cvtColor(array(self.img), cv2.COLOR_BGR2GRAY)
            height, width = img.shape
            pyautogui.moveTo(test[0], test[1], 0)
        else:
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Error")
            msg.setText("Could not locate the image on the screen")

        qim = ImageQt(self.img)
        pix = QPixmap.fromImage(qim)
        pix.detach()
        self.ui.label_6.setPixmap(pix)
        msg.exec()

    def mousePressEvent(self, event):
        self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        if hasattr(self, 'oldPos'):
            delta = QPoint(event.globalPos() - self.oldPos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPos()

    def hideClicked(self):
        self.showMinimized()

    def exitClicked(self):
        sys.exit(-1)

    def addParagonItem(self):
        itemName = self.ui.paragonItem.text()
        rowPosition = self.ui.paragonTable.rowCount()
        count = rowPosition + 1
        if not itemName:
            def itemExists(table, item):
                for row in range(table.rowCount()):
                    name = table.item(row, 0).text()
                    if item == name:
                        return True

                return False

            itemName = "Item " + str(count)
            check = itemExists(self.ui.paragonTable, itemName)
            while check:
                count += 1
                itemName = "Item " + str(count)
                check = itemExists(self.ui.paragonTable, itemName)

        ScreenApp = Screenshot.SelectableApp()
        ScreenApp.MainLoop()
        region = ScreenApp.getRegion()
        pix = None

        del ScreenApp.frame
        del ScreenApp
        if region is not None:
            self.img = pyautogui.screenshot(region=region)
            qim = ImageQt(self.img)
            pix = QPixmap.fromImage(qim)
            pix.detach()
            self.ui.label_12.setPixmap(pix)
        self.app.processEvents()

        if pix == None:
            return

        self.ui.testParagon.setDisabled(False)
        self.ui.paragonTable.setColumnCount(2)
        self.ui.paragonTable.setHorizontalHeaderLabels(("Item Name;").split(";"))
        self.ui.paragonTable.horizontalHeader().hide()
        self.ui.paragonTable.verticalHeader().hide()
        self.ui.paragonTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ui.paragonTable.setEditTriggers(QAbstractItemView.NoEditTriggers);
        self.ui.paragonTable.insertRow(rowPosition)

        paragonItem = QTableWidgetItem(itemName)
        paragonIcon = QLabel()
        paragonIcon.setPixmap(pix)
        paragonIcon.setAlignment(Qt.AlignCenter)

        self.ui.paragonTable.setCellWidget(rowPosition, 1, paragonIcon)
        self.ui.paragonTable.setItem(rowPosition, 0, paragonItem)
        self.ui.paragonTable.scrollToBottom()
        self.ui.paragonItem.setText("")

    def updateParagonPreview(self, item):
        for index in item.indexes():
            if index.column() == 0:
                pix = self.ui.paragonTable.cellWidget(index.row(), 1).pixmap()
                self.ui.label_12.setPixmap(pix)
                break

    def removeParagonItem(self):
        self.ui.paragonTable.removeRow(self.ui.paragonTable.currentRow())

    def testParagonItem(self):
        pixmap = self.ui.label_12.pixmap().copy()
        qImg = QImage(pixmap)
        buffer = QBuffer()
        buffer.open(QBuffer.ReadWrite)
        qImg.save(buffer, "PNG")
        img = Image.open(io.BytesIO(buffer.data()))

        self.ui.label_12.setText("Loading")
        self.ui.paragonTable.setColumnHidden(1, True)
        for i in range(3):
            self.app.processEvents()

        test = imageSearch(img, 0.99, screenshot=True)
        x = imageSearchCount(img, 0.99, screenshot=True)
        count = len(x)

        msg = QMessageBox()
        if test[0] > -1:
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Info")
            msg.setText("Image located on " + str(test))
            msg.setInformativeText("Count: " + str(count))

            img = cv2.cvtColor(array(img), cv2. COLOR_BGR2GRAY)
            height, width = img.shape
            pyautogui.moveTo(test[0] + (width / 2), test[1] + (height / 2), 0.5)
        else:
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Error")
            msg.setText("Could not locate the image on the screen")

        self.ui.paragonTable.setColumnHidden(1, False)
        self.ui.label_12.setPixmap(pixmap)
        msg.exec()

    def addTask(self):
        rowPosition = self.ui.tableWidget.rowCount()
        if rowPosition > 0:
            last = self.ui.tableWidget.item(self.ui.tableWidget.rowCount() - 1, 0)
            stat = self.ui.tableWidget.item(self.ui.tableWidget.rowCount() - 1, 2)
            if "No Limit" in last.text() and "In Queue" in stat.text():
                msg = QMessageBox()
                msg.setWindowIcon(QIcon(scriptDir + path.sep + 'icons/icon.png'))
                msg.setIcon(QMessageBox.Information)
                msg.setWindowTitle("Info")
                msg.setText("The previous item contains [No Limit] tag!")
                msg.setInformativeText("This means it will run that task forever and the macro will never get to do the next one")
                msg.exec()

        self.ui.tableWidget.setColumnCount(3)
        self.ui.tableWidget.setHorizontalHeaderLabels(("Task;Name;Status").split(";"))
        self.ui.tableWidget.verticalHeader().hide()
        #self.ui.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        item = QTableWidgetItem('text')
        item.setForeground(QBrush(QColor(0, 255, 0)))

        self.ui.tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers);
        self.ui.tableWidget.insertRow(rowPosition)

        task = QTableWidgetItem(self.ui.comboBox.currentText())
        name = QTableWidgetItem(self.ui.characters.currentText())
        name.setTextAlignment(Qt.AlignCenter)
        stat = QTableWidgetItem('In Queue')
        stat.setTextAlignment(Qt.AlignCenter)
        stat.setForeground(QBrush(QColor(252, 186, 3)))

        self.ui.tableWidget.setItem(rowPosition, 0, task)
        self.ui.tableWidget.setItem(rowPosition, 1, name)
        self.ui.tableWidget.setItem(rowPosition, 2, stat)

        self.ui.tableWidget.scrollToBottom()

    def removeTask(self):
        self.ui.tableWidget.removeRow(self.ui.tableWidget.currentRow())


class WinEventFilter(QAbstractNativeEventFilter):
    def __init__(self, keybinder):
        self.keybinder = keybinder
        super().__init__()

    def nativeEventFilter(self, eventType, message):
        ret = self.keybinder.handler(eventType, message)
        return ret, 0


if __name__ == '__main__' and is_admin():
    version = "EasyAK " + version.build
    app = QApplication(sys.argv)
    pyautogui.FAILSAFE = False

    if getattr(sys, 'frozen', False):
        # frozen
        scriptDir = path.dirname(sys.executable)
    else:
        # unfrozen
        scriptDir = path.dirname(path.realpath(__file__))

    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.Disabled, QPalette.Button, QColor(30, 30, 30))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, Qt.black)

    app.setStyle('Fusion')
    app.setPalette(dark_palette)
    app.setStyleSheet("QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }")


    def on_exception_triggered(type_except, value, tb):
        import traceback
        trace = "".join(traceback.format_exception(type_except, value, tb))
        sys.__excepthook__(type_except, value, tb)


    sys.excepthook = on_exception_triggered

    keybinder.init()
    example = Main(app)

    # Install a native event filter to receive events from the OS
    win_event_filter = WinEventFilter(keybinder)
    event_dispatcher = QAbstractEventDispatcher.instance()
    event_dispatcher.installNativeEventFilter(win_event_filter)

    atexit.register(example.dialog.goodbye)
    sys.exit(app.exec_())
else:
    current_os_name = osName

    # If a freezer is used (PyInstaller, cx_freeze, py2exe)
    if getattr(sys, "frozen", False):
        runner = sys.executable
        arguments = ''
    # If script is Nuitka compiled (sloppy detection that must happen after frozen detection).
    # Nuitka does not set the frozen attribute on sys
    # elif sys.argv[0].endswith('.exe') or not sys.argv[0].endswith('.py'):
    elif globals().get("__compiled__", False):
        # On nuitka, sys.executable is the python binary, even if it does not exist in standalone,
        # so we need to fill runner with sys.argv[0] plus absolute path
        runner = sys.argv[0]
        arguments = ''
    # If standard interpretet CPython is used
    else:
        runner = sys.executable
        arguments = sys.argv[0]

    print(runner)
    print(arguments)
    windll.shell32.ShellExecuteW(None, "runas", runner, arguments, None, 1)
