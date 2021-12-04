#!/usr/bin/env python
# -*- coding: utf-8 -*-

# my_screen.py file from lolly
# maintainer: lolly - lolly.enigma2@gmail.com
#
# Big thanks at Billy2011 and MediaPortal Team for code snipets and the ideas
#
#This plugin for enigma2 settop boxes is free software which entitles you to modify the source code,
#if you clearly identify the original license and developers, but you are not expressly authorized,
#to distribute this software / publish without source code. This applies for the original version,
#but also the version with your changes. That said, you also have the source code of your changes
#distribute / publish to.

from my_globals import *


desktopSize = getDesktop(0).size()

screenList = []

class MyScreen(Screen):

	def __init__(self, session, parent = None, *ret_args):
		Screen.__init__(self, session, parent)
		screenList.append((self, ret_args))

		self["oATV_actions"] = ActionMap(["My_Actions"], {
			"ok": self.ok,
			"cancel": self.keyCancel,
			"up" : self.keyUp,
			"down" : self.keyDown,
			"right" : self.keyRight,
			"left" : self.keyLeft,
			"nextBouquet" : self.keyPageUp,
			"prevBouquet" : self.keyPageDown }, -1)

		self['menuname'] = Label(_("%s")% config.openatv.versiontext.value)
		self['text_header'] = Label (_("Please wait..."))
		self['text_ico_red'] = Label("")
		self['text_ico_green'] = Label("")
		self['text_ico_yellow'] = Label("")
		self['text_ico_blue'] = Label("")
		self['cover'] = Pixmap()
		self['Page'] = Label("")
		self['page'] = Label("")
		self['text'] = ScrollLabel("")

	def showInfos(self):
		exist = self['liste'].getCurrent()
		if self.keyLocked or exist == None:
			return
		title = self['liste'].getCurrent()[0][0]
		if not re.match('.*?----------------------------------------', title):
			self['text_header'].setText(title)
		else:
			self['text_header'].setText('')

	def close(self, *args):
		Screen.close(self, *args)
		if len(screenList):
			screenList.pop()

	def keyPageNumber(self):
		self.session.openWithCallback(self.callbackkeyPageNumber, VirtualKeyBoard, title = (_("Enter page number")), text = str(self.page))

	def callbackkeyPageNumber(self, answer):
		if answer is not None:
			answer = re.findall('\d+', answer)
		else:
			return
		if answer:
			if int(answer[0]) < self.lastpage + 1:
				self.page = int(answer[0])
				self.loadPage()
			else:
				self.page = self.lastpage
				self.loadPage()

	def switchToLast(self):
		if self.keyLocked:
			return
		self.page = self.lastpage
		self.loadPage()

	def switchToFirst(self):
		if self.keyLocked:
			return
		if not self.page < 2:
			self.page = self.firstpage
			self.loadPage()

	def keyPageDown(self):
		if self.keyLocked or self.Noswitch == True:
			return
		if not self.page < 2:
			self.page -= 1
			self.loadPage()

	def keyPageUp(self):
		if self.keyLocked or self.Noswitch == True:
			return
		self.page += 1
		self.loadPage()

	def keyLeft(self):
		if self.keyLocked:
			return
		self['liste'].pageUp()
		self.showInfos()

	def keyRight(self):
		if self.keyLocked:
			return
		self['liste'].pageDown()
		self.showInfos()

	def keyUp(self):
		if self.keyLocked:
			return
		self['liste'].up()
		self.showInfos()

	def keyDown(self):
		if self.keyLocked:
			return
		self['liste'].down()
		self.showInfos()

	def keyTxtPageUp(self):
		self['text'].pageUp()

	def keyTxtPageDown(self):
		self['text'].pageDown()

	def keyCancel(self):
		self.close()

	def dataError(self,error):
		keyLocked=False
		print error

####### build menus
	if desktopSize.width() == 1920:
		def listleft(self, entry):
			self.ml.l.setFont(0, gFont("Regular", 26))
			self.ml.l.setItemHeight(40)
			res = [entry]
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 0, 1545, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[0]))
			return res
		def listgit(self, entry):
			self.ml.l.setFont(0, gFont("Regular", 24))
			self.ml.l.setFont(1, gFont("Regular", 26))
			self.ml.l.setItemHeight(65)
			res = [entry]
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 0, 990, 35, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[0]))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 25, 990, 35, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[1]))
			return res
		def favolist(self, entry):
			self.ml.l.setFont(0, gFont("Regular", 26))
			self.ml.l.setItemHeight(40)
			res = [entry]
			if entry[0] == "Forum:":
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 0, 990, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[0], 0x636363))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 100, 0, 990, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[1]))
			else:
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 0, 990, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[0]))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 100, 0, 990, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[1]))
			return res
		def forenlist(self, entry):
			self.ml.l.setFont(0, gFont("Regular", 24))
			self.ml.l.setFont(1, gFont("Regular", 26))
			self.ml.l.setItemHeight(90)
			ico_name = False
			if entry[2] == "forum_old-48.png":
				ico_name = "forum_old-48.png"
			else:
				ico_name = "forum_new-48.png"
			if ico_name:
				png = "/usr/lib/enigma2/python/Plugins/Extensions/openATVreader/pics/%s" % ico_name
				ico = LoadPixmap(png)
				res = [entry]
				res.append(MultiContentEntryPixmapAlphaBlend(pos=(5,21), size=(48,48), png=ico))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 60, 0, 1380, 40, 1, RT_HALIGN_LEFT | RT_VALIGN_TOP, entry[0], 0xb1b1b1))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 60, 30, 1380, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_BOTTOM, entry[5]+' '+entry[6], 0x636363))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 60, 60, 1380, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_BOTTOM, entry[7], 0x636363))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 600, 30, 1380, 45, 0, RT_HALIGN_LEFT, entry[3], 0x979797))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 600, 60, 1380, 45, 0, RT_HALIGN_LEFT, entry[4], 0x979797))
				return res
			else:
				res = [entry]
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 0, 1000, 90, 1, RT_HALIGN_CENTER | RT_VALIGN_CENTER, entry[0]))
				return res
		def subforenlist(self, entry):
			self.ml.l.setFont(0, gFont("Regular", 24))
			self.ml.l.setFont(1, gFont("Regular", 26))
			self.ml.l.setItemHeight(60)
			ico_name = False
			if entry[2] == "forum_old-48.png":
				ico_name = "forum_old-48.png"
			else:
				ico_name = "forum_new-48.png"
			if ico_name:
				png = "/usr/lib/enigma2/python/Plugins/Extensions/openATVreader/pics/%s" % ico_name
				ico = LoadPixmap(png)
				res = [entry]
				res.append(MultiContentEntryPixmapAlphaBlend(pos=(5,6), size=(48,48), png=ico))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 60, 0, 1380, 60, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[0], 0xb1b1b1))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 600, 30, 1380, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_BOTTOM, entry[3], 0x979797))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 600, 0, 1380, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_TOP, entry[4], 0x979797))
				return res
			else:
				res = [entry]
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 0, 1000, 60, 1, RT_HALIGN_CENTER | RT_VALIGN_CENTER, entry[0]))
				return res
		def threadlist(self, entry):
			self.ml.l.setFont(0, gFont("Regular", 24))
			self.ml.l.setFont(1, gFont("Regular", 26))
			self.ml.l.setItemHeight(60)
			ico_name = False
			if entry[2] == "hot new attachments" or entry[2] == "hot new":
				ico_name = "thread_hot_new-30.png"
			elif entry[2] == "dot hot attachments" or entry[2] == "dot hot":
				ico_name = "thread_dot_hot-30-right.png"
			elif entry[2] == "hot attachments" or entry[2] == "hot":
				ico_name = "thread_hot-30.png"
			elif entry[2] == "new attachments" or entry[2] == "new" or entry[2] == "new attachments":
				ico_name = "thread_new-30.png"
			elif entry[2] == "dot new" or entry[2] == "dot new attachments":
				ico_name = "thread_dot_new-30-right.png"
			elif entry[2] == "new moved" or entry[2] == "moved":
				ico_name = "thread_moved_new-30.png"
			else:
				ico_name = "thread_old-30.png"
			rating_name = False
			if "rating5" in entry[3]:
				rating_name = "rating-trans-15_5.png"
			elif "rating4" in entry[3]:
				rating_name = "rating-trans-15_4.png"
			elif "rating3" in entry[3]:
				rating_name = "rating-trans-15_3.png"
			elif "rating2" in entry[3]:
				rating_name = "rating-trans-15_2.png"
			elif "rating1" in entry[3]:
				rating_name = "rating-trans-15_1.png"
			else:
				rating_name = "rating-trans-15_0.png"
			png = "/usr/lib/enigma2/python/Plugins/Extensions/openATVreader/pics/%s" % ico_name
			png1 = "/usr/lib/enigma2/python/Plugins/Extensions/openATVreader/pics/%s" % rating_name
			ico = LoadPixmap(png)
			rating = LoadPixmap(png1)
			res = [entry]
			if "nonsticky" in entry[3]:
				stick=""
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 60, 0, 1030, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_TOP, stick, 0x117CBD))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 60, 0, 1030, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_TOP, entry[0], 0xb1b1b1))
			else:
				stick="Wichtig: "
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 60, 0, 1030, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_TOP, stick, 0x117CBD))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 150, 0, 1030, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_TOP, entry[0], 0xb1b1b1))
			res.append(MultiContentEntryPixmapAlphaBlend(pos=(5,6), size=(48,48), png=ico))
			res.append(MultiContentEntryPixmapAlphaBlend(pos=(1110,0), size=(75,15), png=rating))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 60, 30, 1030, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_BOTTOM, "Letzter Beitrag: "+entry[7]+' '+entry[8] + ' von '+entry[6], 0x636363))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 1300, 30, 200, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_BOTTOM, entry[4], 0x979797))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 1300, 0, 200, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_TOP, entry[5], 0x979797))
			return res
		def thread_Contentlist(self, entry):
			self.ml.l.setFont(0, gFont("Regular", 24))
			self.ml.l.setFont(1, gFont("Regular", 26))
			self.ml.l.setItemHeight(40)
			res = [entry]
			if entry[4] == "Community Administrator":
				fontcolor = 0xFF0000
			elif entry[4] == "Super-Moderator":
				fontcolor = 0x0066ff
			elif entry[4] == "Moderator":
				fontcolor = 0xFF8031
			elif entry[4] == "VIP-User":
				fontcolor = 0xb10ce4
			elif entry[4] == "Betatester":
				fontcolor = 0xE1B500
			else:
				fontcolor = 0x979797
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 0, 120, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, 'Post: '+entry[2]))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 130, 0, 215, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[3], fontcolor))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 305, 0, 250, 40, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, ' - '+entry[0]+' '+entry[1]))
			return res
		def ranglisten(self, entry):
			self.ml.l.setFont(0, gFont("Regular",26))
			self.ml.l.setItemHeight(40)
			res = [entry]
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 0, 80, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[0]))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 55, 0, 200, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[1]))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 255, 0, 80, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[2]))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 360, 0, 80, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[3], 0xfc1010))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 420, 0, 80, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[4], 0xCC9900))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 470, 0, 80, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[5], 0x99CC00))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 530, 0, 80, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[6], 0x336600))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 580, 0, 80, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[7]))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 630, 0, 80, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[8]))
			return res
		def listPM(self, entry):
			self.ml.l.setFont(0, gFont("Regular", 26))
			self.ml.l.setItemHeight(40)
			res = [entry]
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 0, 990, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[1]+','+entry[2],0x117CBD ))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 220, 0, 990, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[5]))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 480, 0, 1500, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[0]))
			return res
	else:
		def listleft(self, entry):
			self.ml.l.setFont(0, gFont("Regular", 18))
			res = [entry]
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 0, 990, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[0]))
			return res
		def listgit(self, entry):
			self.ml.l.setFont(0, gFont("Regular", 16))
			self.ml.l.setItemHeight(50)
			res = [entry]
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 0, 990, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[0]))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 25, 990, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[1]))
			return res
		def favolist(self, entry):
			self.ml.l.setFont(0, gFont("Regular", 18))
			res = [entry]
			if entry[0] == "Forum:":
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 0, 990, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[0], 0x636363))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 100, 0, 990, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[1]))
			else:
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 0, 990, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[0]))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 100, 0, 990, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[1]))
			return res
		def forenlist(self, entry):
			self.ml.l.setFont(0, gFont("Regular", 16))
			self.ml.l.setFont(1, gFont("Regular", 18))
			self.ml.l.setFont(2, gFont("Regular", 14))
			self.ml.l.setItemHeight(60)
			ico_name = False
			if entry[2] == "forum_old-48.png":
				ico_name = "forum_old-48.png"
			else:
				ico_name = "forum_new-48.png"
			if ico_name:
				png = "/usr/lib/enigma2/python/Plugins/Extensions/openATVreader/pics/%s" % ico_name
				ico = LoadPixmap(png)
				res = [entry]
				res.append(MultiContentEntryPixmapAlphaBlend(pos=(5,6), size=(48,48), png=ico))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 60, 0, 1380, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_TOP, entry[0], 0xb1b1b1))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 60, 20, 1380, 20, 2, RT_HALIGN_LEFT | RT_VALIGN_BOTTOM, entry[5]+' '+entry[6], 0x636363))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 60, 40, 1380, 20, 2, RT_HALIGN_LEFT | RT_VALIGN_BOTTOM, entry[7], 0x636363))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 400, 20, 1380, 20, 0, RT_HALIGN_LEFT, entry[3], 0x979797))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 400, 40, 1380, 20, 0, RT_HALIGN_LEFT, entry[4], 0x979797))
				return res
			else:
				res = [entry]
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 0, 1000, 60, 1, RT_HALIGN_CENTER | RT_VALIGN_CENTER, entry[0]))
				return res
		def subforenlist(self, entry):
			self.ml.l.setFont(0, gFont("Regular", 16))
			self.ml.l.setFont(1, gFont("Regular", 18))
			self.ml.l.setItemHeight(50)
			ico_name = False
			if entry[2] == "forum_old-48.png":
				ico_name = "forum_old-48.png"
			else:
				ico_name = "forum_new-48.png"

			if ico_name:
				png = "/usr/lib/enigma2/python/Plugins/Extensions/openATVreader/pics/%s" % ico_name
				ico = LoadPixmap(png)
				res = [entry]
				res.append(MultiContentEntryPixmapAlphaBlend(pos=(5,2), size=(48,48), png=ico))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 60, 0, 1380, 50, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[0], 0xb1b1b1))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 450, 0, 1380, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_BOTTOM, entry[4], 0x979797))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 450, 20, 1380, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_TOP, entry[3], 0x979797))
				return res
			else:
				res = [entry]
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 0, 1000, 60, 1, RT_HALIGN_CENTER | RT_VALIGN_CENTER, entry[0]))
				return res
		def threadlist(self, entry):
			self.ml.l.setFont(0, gFont("Regular", 16))
			self.ml.l.setFont(1, gFont("Regular", 18))
			self.ml.l.setItemHeight(40)
			ico_name = False
			if entry[2] == "hot new attachments" or entry[2] == "hot new":
				ico_name = "thread_hot_new-30.png"
			elif entry[2] == "dot hot attachments" or entry[2] == "dot hot":
				ico_name = "thread_dot_hot-30-right.png"
			elif entry[2] == "hot attachments" or entry[2] == "hot":
				ico_name = "thread_hot-30.png"
			elif entry[2] == "new attachments" or entry[2] == "new" or entry[2] == "new attachments":
				ico_name = "thread_new-30.png"
			elif entry[2] == "dot new" or entry[2] == "dot new attachments":
				ico_name = "thread_dot_new-30-right.png"
			elif entry[2] == "new moved" or entry[2] == "moved":
				ico_name = "thread_moved_new-30.png"
			else:
				ico_name = "thread_old-30.png"
			rating_name = False
			if "rating5" in entry[3]:
				rating_name = "rating-trans-15_5.png"
			elif "rating4" in entry[3]:
				rating_name = "rating-trans-15_4.png"
			elif "rating3" in entry[3]:
				rating_name = "rating-trans-15_3.png"
			elif "rating2" in entry[3]:
				rating_name = "rating-trans-15_2.png"
			elif "rating1" in entry[3]:
				rating_name = "rating-trans-15_1.png"
			else:
				rating_name = "rating-trans-15_0.png"
			png = "/usr/lib/enigma2/python/Plugins/Extensions/openATVreader/pics/%s" % ico_name
			png1 = "/usr/lib/enigma2/python/Plugins/Extensions/openATVreader/pics/%s" % rating_name
			ico = LoadPixmap(png)
			rating = LoadPixmap(png1)
			res = [entry]
			if "nonsticky" in entry[3]:
				stick=""
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 60, 0, 630, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_TOP, stick, 0x117CBD))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 60, 0, 630, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_TOP, entry[0], 0xb1b1b1))
			else:
				stick="Wichtig: "
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 60, 0, 630, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_TOP, stick, 0x117CBD))
				res.append((eListboxPythonMultiContent.TYPE_TEXT, 125, 0, 570, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_TOP, entry[0], 0xb1b1b1))
			res.append(MultiContentEntryPixmapAlphaBlend(pos=(5,6), size=(48,48), png=ico))
			res.append(MultiContentEntryPixmapAlphaBlend(pos=(900,0), size=(75,15), png=rating))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 60, 20, 630, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_BOTTOM, "Letzter Beitrag: "+entry[7]+' '+entry[8] + ' von '+entry[6], 0x636363))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 700, 20, 200, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_BOTTOM, entry[4], 0x979797))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 700, 0, 200, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_TOP, entry[5], 0x979797))
			return res
		def thread_Contentlist(self, entry):
			self.ml.l.setFont(0, gFont("Regular", 16))
			res = [entry]
			if entry[4] == "Community Administrator":
				fontcolor = 0xFF0000
			elif entry[4] == "Super-Moderator":
				fontcolor = 0x0066ff
			elif entry[4] == "Moderator":
				fontcolor = 0xFF8031
			elif entry[4] == "VIP-User":
				fontcolor = 0xb10ce4
			elif entry[4] == "Betatester":
				fontcolor = 0xE1B500
			else:
				fontcolor = 0x979797
		
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 0, 80, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, 'Post: '+entry[2]))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 95, 0, 155, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[3], fontcolor))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 220, 0, 160, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, ' - '+entry[0]+' '+entry[1]))
			return res
		def ranglisten(self, entry):
			self.ml.l.setFont(0, gFont("Regular", 18))
			res = [entry]
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 0, 80, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[0]))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 45, 0, 180, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[1]))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 245, 0, 80, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[2]))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 310, 0, 80, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[3], 0xfc1010))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 370, 0, 80, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[4], 0xCC9900))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 420, 0, 80, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[5], 0x99CC00))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 480, 0, 80, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[6], 0x336600))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 530, 0, 80, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[7]))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 590, 0, 80, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[8]))
			return res
		def listPM(self, entry):
			self.ml.l.setFont(0, gFont("Regular", 18))
			res = [entry]
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 0, 990, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[1]+','+entry[2],0x117CBD ))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 200, 0, 990, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[5]))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 460, 0, 990, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[0]))
			return res
