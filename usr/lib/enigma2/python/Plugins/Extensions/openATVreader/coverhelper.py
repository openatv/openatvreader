#!/usr/bin/env python
# -*- coding: utf-8 -*-

# coverhelper.py file from lolly for Plugins
#
# Big thanks at Billy2011 for this file
#
# This plugin is free software, you are allowed to modify it
# (if you keep the license and original maintainer),
# but you are not allowed to distribute/publish it without source code
# (this version and your modifications).
# This means you also have to distribute source code of your modifications

from Components.AVSwitch import AVSwitch
from Components.Pixmap import Pixmap
from Components.config import config
from Tools.Directories import fileExists
from enigma import gPixmapPtr, ePicLoad, eTimer
from twisted.web.client import downloadPage


glob_icon_num = 0
glob_last_cover = [None, None]

class CoverHelper:

	COVER_PIC_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/openATVreader/.Icon%d.jpg"
	NO_COVER_PIC_PATH = "/pics/no_cover.png"

	def __init__(self, cover, callback=None, nc_callback=None):
		self._cover = cover
		self.picload = ePicLoad()
		self._no_picPath = "/usr/lib/enigma2/python/Plugins/Extensions/openATVreader"
		self._callback = callback
		self._nc_callback = nc_callback
		self.downloadPath = None
		self.coverTimerStart = eTimer()

	def getCoverTimerStart(self):
		self.coverTimerStart.startLongTimer(20)

	def getCover(self, url, download_cb=None):
		global glob_icon_num
		global glob_last_cover

		self.getCoverTimerStart()
		if url:
			if url.startswith('http'):
				if glob_last_cover[0] == url and glob_last_cover[1]:
					self.showCoverFile(glob_last_cover[1])
					if download_cb:
						download_cb(glob_last_cover[1])
				else:
					glob_icon_num = (glob_icon_num + 1) % 2
					glob_last_cover[0] = url
					glob_last_cover[1] = None
					self.downloadPath = self.COVER_PIC_PATH % glob_icon_num
					d = downloadPage(url, self.downloadPath)
					d.addCallback(self.showCover)
					if download_cb:
						d.addCallback(self.cb_getCover, download_cb)
					d.addErrback(self.dataErrorP)
			elif url.startswith('file://'):
				self.showCoverFile(url[7:])
			else:
				self.showCoverNone()
		else:
			self.showCoverNone()

	def cb_getCover(self, result, download_cb):
		download_cb(result)

	def dataErrorP(self, error):
		print error
		self.showCoverNone()

	def showCover(self, picData):
		self.showCoverFile(self.downloadPath)
		glob_last_cover[1] = self.downloadPath
		return self.downloadPath

	def showCoverNone(self):
		if self._nc_callback:
			self._cover.hide()
			self._nc_callback()
		else:
			self.showCoverFile(self._no_picPath)

		return(self._no_picPath)

	def showCoverFile(self, picPath, showNoCoverart=True):
		if fileExists(picPath):
			self._cover.instance.setPixmap(gPixmapPtr())
			scale = AVSwitch().getFramebufferScale()
			size = self._cover.instance.size()
			self.picload.setPara((size.width(), size.height(), scale[0], scale[1], False, 1, "#20000000"))
			self.updateCover(picPath)
		else:
			printl("Coverfile not found: %s" % picPath, self, "E")
			if showNoCoverart and picPath != self._no_picPath:
				self.showCoverFile(self._no_picPath)

		if self._callback:
			self._callback()

	def updateCover(self, picPath):
		res = self.picload.startDecode(picPath, 0, 0, False)

		if not res:
			ptr = self.picload.getData()
			if ptr != None:
				w = ptr.size().width()
				h = ptr.size().height()
				ratio = float(w) / float(h)
				if self._nc_callback and ratio > 1.05:
					self.showCoverNone()
				else:
					self._cover.instance.setPixmap(ptr)
					self._cover.show()