import wx

class SelectableFrame(wx.Frame):
    c1 = None
    c2 = None
    pos = None

    def __init__(self, parent=None, id=-1, title=""):
        wx.Frame.__init__(self, parent, id, title, pos=(0, 0), size=wx.DisplaySize(), style=wx.FRAME_NO_TASKBAR | wx.NO_BORDER | wx.STAY_ON_TOP)

        self.panel = wx.Panel(self, size=self.GetSize())

        self.panel.Bind(wx.EVT_MOTION, self.OnMouseMove)
        self.panel.Bind(wx.EVT_LEFT_DOWN, self.OnMouseSelect)
        self.panel.Bind(wx.EVT_RIGHT_DOWN, self.OnReset)
        self.panel.Bind(wx.EVT_LEFT_UP, self.OnMouseUp)
        self.panel.Bind(wx.EVT_PAINT, self.OnPaint)
        self.panel.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

        self.Bind(wx.EVT_CLOSE, self.OnClose)

        self.SetCursor(wx.Cursor(wx.CURSOR_CROSS))

        self.panel.SetBackgroundColour(wx.Colour(0, 0, 0))
        self.panel.SetBackgroundStyle(wx.BG_STYLE_COLOUR)

        self.SetTransparent(150)

    def OnClose(self, event):
        self.Destroy()

    def OnMouseMove(self, event):
        if event.Dragging() and event.LeftIsDown():
            self.c2 = event.GetPosition()
            self.Refresh()

    def OnMouseSelect(self, event):
        self.SetCursor(wx.Cursor(wx.CURSOR_CROSS))
        self.c1 = event.GetPosition()

    def OnMouseUp(self, event):
        self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        self.TakeScreenshot()

    def OnKeyDown(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_ESCAPE:
            self.Close()

        event.Skip()

    def OnReset(self, event=None):
        self.Destroy()
        #wx.PaintDC(self.panel).Clear()
        #self.SetCursor(wx.StockCursor(wx.CURSOR_CROSS))

    def OnPaint(self, event):
        if not self.RegionSelected():
            #wx.PaintDC(self.panel).Clear()
            return
        dc = wx.PaintDC(self.panel)
        dc.SetPen(wx.Pen("white", 1, wx.LONG_DASH))
        dc.SetBrush(wx.Brush(wx.Colour(100, 100, 100), wx.SOLID))

        dc.DrawRectangle(self.c1.x, self.c1.y, self.c2.x - self.c1.x, self.c2.y - self.c1.y)

    def RegionSelected(self):
        if self.c1 is None or self.c2 is None:
            return False
        else:
            return True

    def TakeScreenshot(self):
        if not self.RegionSelected():
            return
        self.Refresh()

        reverseC1 = False if self.c2.x - self.c1.x > 0 else True
        reverseC2 = False if self.c2.y - self.c1.y > 0 else True

        a = self.c2.x - self.c1.x if self.c2.x - self.c1.x > 0 else self.c1.x - self.c2.x
        b = self.c2.y - self.c1.y if self.c2.y - self.c1.y > 0 else self.c1.y - self.c2.y

        self.pos = (self.c2.x if reverseC1 else self.c1.x, self.c2.y if reverseC2 else self.c1.y, a, b)
        self.Close()

#--------------------------------------------------------------------------------------------------------

class SelectableApp(wx.App):
    def OnInit(self):
        self.frame = SelectableFrame(None)
        self.frame.Show(True)
        self.SetTopWindow(self.frame)
        return True

    def getRegion(self):
        return self.frame.pos

#--------------------------------------------------------------------------------------------------------#


#app = SelectableApp(False)
#app.MainLoop()