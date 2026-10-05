#########################################################################################################
#  OpenATVreader, coded by Mr.Servo @ openATV 2024                                                      #
#  -----------------------------------------------------------------------------------------------------#
#  This plugin is licensed under the GNU version 3.0 <https://www.gnu.org/licenses/gpl-3.0.en.html>.    #
#  This plugin is NOT free software. It is open source, you are allowed to modify it (if you keep       #
#  the license), but it may not be commercially distributed. Advertise with this tool is not allowed.   #
#  For other uses, permission from the authors is necessary.                                            #
#########################################################################################################
from glob import glob
from hashlib import md5
from os import linesep, makedirs, rename
from os.path import exists, join
from re import compile, split, sub
from shutil import copy2, rmtree, which
from struct import unpack
from threading import Lock
from urllib.parse import parse_qs, urlparse

from Components.ActionMap import ActionMap, NumberActionMap
from Components.ConditionalWidget import BlinkingWidget
from Components.Console import Console
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from enigma import (
	BT_KEEP_ASPECT_RATIO,
	BT_SCALE,
	detectImageType,
	ePicLoad,
	ePoint,
	eServiceReference,
	eSize,
	eTimer,
	getDesktop,
)
from Plugins.Plugin import PluginDescriptor
from Screens.InfoBar import MoviePlayer
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Tools.BoundFunction import boundFunction
from Tools.Directories import SCOPE_CONFIG, SCOPE_PLUGINS, resolveFilename
from Tools.LoadPixmap import LoadPixmap
from twisted.internet.reactor import callFromThread, callInThread

from . import __version__
from .forumparser import fparser, fpglobals

PLUGIN_NAME = "OpenATV Reader"
PLUGIN_DESCRIPTION = "Das opena.tv Forum bequem auf dem TV mitlesen"


class ATVglobals:
	VERSION = f"v{__version__}"
	AVATARPATH = "/tmp/avatare"
	IMAGEPATH = "/tmp/avatare/postimages"  # images of posts, removed together with the avatars
	PLUGINPATH = resolveFilename(SCOPE_PLUGINS, "Extensions/OpenATVreader/")
	FAVORITEN = resolveFilename(SCOPE_CONFIG, "openatvreader_fav.dat")
	RESOLUTION = "fHD" if getDesktop(0).size().width() > 1300 else "HD"
	POSTSPERMAIN = 5  # quantity of post in view 'latest posts'
	POSTSPERTHREAD = 20  # quantity of post in view 'thread'
	MODULE_NAME = __name__.split(".")[-2]


class ATVhelper(Screen, ATVglobals):
	def handleAvatar(self, widget, pixUrl, callback=None):
		avatarPix, urlFileName, filePath = None, "", join(self.AVATARPATH, "unknown.png")
		if pixUrl:
			if pixUrl.startswith("./"):  # in case it's an plugin avatar ('unknown.png' and 'user_stat.png')
				filePath = join(self.AVATARPATH, pixUrl.replace("./", ""))
			else:
				urlFileName = f"{pixUrl[pixUrl.rfind('?avatar=') + 8:]}"
				if urlFileName:  # possibly the file name had to be renamed according to the correct image type
					picsList = glob(join(self.AVATARPATH, f"{urlFileName.split('.')[0]}.*"))
					filePath = picsList[0] if picsList else ""  # use first hit found
		if filePath and exists(filePath):
			try:
				avatarPix = LoadPixmap(cached=True, path=filePath)
			except Exception as error:  # noqa: BLE001 - a broken avatar file must not stop the plugin
				print(f"[{self.MODULE_NAME}] ERROR in module 'handleAvatar': {error}!")
			if pixUrl in self.avatarDLlist:
				self.avatarDLlist.remove(pixUrl)
		elif pixUrl not in self.avatarDLlist:  # avoid multiple threaded downloads of equal avatars
			self.avatarDLlist.append(pixUrl)
			if callback and urlFileName:
				callInThread(callback, widget, pixUrl, join(self.AVATARPATH, urlFileName))
		return avatarPix, filePath

	def downloadAvatar(self, url, filePath):  # file extensions in url could be wrong
		errMsg, binaryData = fparser.getBinaryData(url)
		if errMsg:
			print(f"[{self.MODULE_NAME}] ERROR in module downloadAvatar': {errMsg}!")
			errText = f"Der OpenA.TV Server ist zur Zeit nicht erreichbar.\n{errMsg}"
			self.session.open(MessageBox, errText, MessageBox.TYPE_INFO, timeout=30, close_on_any_key=True)
			return
		if binaryData:
			try:
				with open(filePath, "wb") as f:
					f.write(binaryData)
			except OSError as errMsg:
				print(f"[{self.MODULE_NAME}] ERROR in module 'downloadAvatar': {errMsg}!")
				self.session.open(MessageBox, errMsg, MessageBox.TYPE_INFO, timeout=30, close_on_any_key=True)
			fileParts = filePath.split(".")
			extension = {0: "png", 1: "jpg", 3: "gif", 4: "svg", 5: "webp"}.get(detectImageType(filePath), fileParts[1])
			if extension != fileParts[1]:  # Some avatars could be incorrectly listed in 'url' as .GIF although they are .JPG or .PNG
				newFname = f"{fileParts[0]}.{extension}"
				rename(filePath, newFname)  # rename with correct extension

	def findPostImage(self, url):
		picsList = glob(join(self.IMAGEPATH, f"{md5(url.encode()).hexdigest()}.*"))
		picsList = [pic for pic in picsList if not pic.endswith(".tmp")]
		return picsList[0] if picsList else ""

	def findVideoThumb(self, url):
		filePath = join(self.IMAGEPATH, f"{md5(url.encode()).hexdigest()}_video.jpg")
		return filePath if exists(filePath) else ""

	def createVideoThumb(self, url, callback, seek="3"):  # grabs a frame of the video with ffmpeg (fetches only the needed parts), calls callback(errMsg, filePath)
		ffmpeg = which("ffmpeg")
		if not ffmpeg:
			callback("ffmpeg ist nicht installiert", "")
			return
		filePath = join(self.IMAGEPATH, f"{md5(url.encode()).hexdigest()}_video.jpg")
		try:
			makedirs(self.IMAGEPATH, exist_ok=True)
		except OSError as error:
			callback(str(error), "")
			return
		if not hasattr(self, "thumbConsole"):
			self.thumbConsole = Console()
		cmd = [ffmpeg, ffmpeg, "-nostdin", "-loglevel", "error", "-y", "-rw_timeout", "20000000", "-ss", seek, "-i", url, "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "3", filePath]
		self.thumbConsole.ePopen(cmd, self.videoThumbFinished, (url, callback, seek, filePath))

	def videoThumbFinished(self, data, retVal, extraArgs):
		url, callback, seek, filePath = extraArgs
		if getattr(self, "closed", False):  # screen was closed meanwhile (ffmpeg got killed)
			return
		if retVal == 0 and exists(filePath):
			callback("", filePath)
		elif seek != "0":  # e.g. a video shorter than 3 seconds: take the first frame
			self.createVideoThumb(url, callback, "0")
		else:
			callback(data.strip() or f"ffmpeg returncode {retVal}", "")

	def downloadPostImage(self, url):  # returns (errMsg, filePath)
		errMsg, binaryData = "", b""
		for _ in range(2):  # external image hosts are sometimes slow, so try twice with a longer timeout
			errMsg, binaryData = fparser.getBinaryData(url, timeout=(10, 20), checkStatus=True)
			if not errMsg:
				break
		if errMsg or not binaryData:
			return errMsg or "keine Daten erhalten", ""
		tempPath = join(self.IMAGEPATH, f"{md5(url.encode()).hexdigest()}.tmp")
		try:
			makedirs(self.IMAGEPATH, exist_ok=True)
			with open(tempPath, "wb") as f:
				f.write(binaryData)
			extension = {0: "png", 1: "jpg", 3: "gif", 4: "svg", 5: "webp"}.get(detectImageType(tempPath))
			if not extension:
				return "unbekanntes Bildformat", ""
			filePath = tempPath.replace(".tmp", f".{extension}")
			rename(tempPath, filePath)
			return "", filePath
		except OSError as error:
			return str(error), ""

	def getImageSize(self, filePath):  # reads (width, height) from the image header, (0, 0) if unknown
		if not filePath:
			return 0, 0
		try:
			with open(filePath, "rb") as f:
				data = f.read()
			if data[:8] == b"\x89PNG\r\n\x1a\n":
				return unpack(">II", data[16:24])
			if data[:6] in (b"GIF87a", b"GIF89a"):
				return unpack("<HH", data[6:10])
			if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
				if data[12:16] == b"VP8X":
					return int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1
				if data[12:16] == b"VP8 ":
					width, height = unpack("<HH", data[26:30])
					return width & 0x3FFF, height & 0x3FFF
				if data[12:16] == b"VP8L":
					bits = int.from_bytes(data[21:25], "little")
					return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
			if data[:2] == b"\xff\xd8":
				pos = 2
				while pos + 9 < len(data):
					if data[pos] != 0xFF:
						pos += 1
						continue
					marker = data[pos + 1]
					if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):  # start of frame
						height, width = unpack(">HH", data[pos + 5:pos + 9])
						return width, height
					if marker == 0xFF or 0xD0 <= marker <= 0xD9 or marker == 0x01:  # fill byte or marker without length
						pos += 1 if marker == 0xFF else 2
						continue
					pos += 2 + unpack(">H", data[pos + 2:pos + 4])[0]
		except (OSError, IndexError, ValueError) as error:
			print(f"[{self.MODULE_NAME}] ERROR in module 'getImageSize': {error}!")
		return 0, 0

	def loadScaledPixmap(self, filePath, width, height):  # decodes the image directly in the needed size (saves memory)
		if not filePath:
			return None
		picLoad = ePicLoad()
		picLoad.setPara((width, height, 1, 1, False, 1, "#00000000"))
		return picLoad.getData() if picLoad.startDecode(filePath, 0, 0, False) == 0 else None

	def playVideo(self, url, videotitle, description):
		sref = eServiceReference(4097, 0, url)
		sref.setName(f"{videotitle} - {description}" if len(f"{videotitle} - {description}") < 30 else videotitle)
		try:
			self.session.open(MoviePlayer, sref, fromMovieSelection=False)
		except TypeError:  # in case the image doesn't support 'fromMovieSelection'
			self.session.open(MoviePlayer, sref)

	def showPic(self, widget, filePath, show=True, scale=True):
		if scale:
			widget.instance.setPixmapScaleFlags(BT_SCALE | BT_KEEP_ASPECT_RATIO)
		widget.instance.setPixmapFromFile(filePath, True)
		if show:
			widget.show()

	def favoriteExists(self, session, favname, favlink):
		self.session = session
		favfound = False
		if favname and favlink and exists(self.FAVORITEN):
			try:
				with open(self.FAVORITEN) as f:
					for line in f.read().split("\n"):
						if favlink in line:
							favfound = True
							break
			except OSError as errMsg:
				self.session.open(MessageBox, f"Favoriten konnten nicht gelesen werden:\n'{errMsg}'", type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
		return favfound

	def writeFavorite(self, session, favname, favlink):
		self.session = session
		if favname and favlink and exists(self.FAVORITEN):
			try:
				with open(self.FAVORITEN, "a") as f:
					f.write(f"{favname}\t{favlink}{linesep}")
			except OSError as errMsg:
				self.session.open(MessageBox, f"Favoriten konnten nicht geschrieben werden:\n'{errMsg}'", type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)


class BlinkingLabel(Label, BlinkingWidget):
	def __init__(self, text=''):
		Label.__init__(self, text=text)
		BlinkingWidget.__init__(self)


class getNumber(ATVhelper):
	skin = """
	<screen name="getNumber" position="center,center" size="150,100" backgroundColor="#1A0F0F0F" flags="wfNoBorder" resolution="1280,720" title=" ">
		<widget source="number" render="Label" position="center,center" size="150,100" font="Regular;44" halign="center" valign="center" transparent="1" zPosition="1" />
		<ePixmap position="113,73" size="35,25" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/keypad_HD.png" alphatest="blend" zPosition="1" />
	</screen>"""

	def __init__(self, session, number):
		if self.RESOLUTION == "fHD":
			self.skin = self.skin.replace("_HD.png", "_fHD.png")
		Screen.__init__(self, session, self.skin)
		self.field = str(number)
		self["version"] = StaticText(self.VERSION)
		self["headline"] = StaticText()
		self["number"] = StaticText(self.field)
		self['actions'] = NumberActionMap(['NumberActions', 'OkCancelActions'], {
			"ok": self.keyOK,
			"cancel": self.quit,
			"1": self.keyNumber,
			"2": self.keyNumber,
			"3": self.keyNumber,
			"4": self.keyNumber,
			"5": self.keyNumber,
			"6": self.keyNumber,
			"7": self.keyNumber,
			"8": self.keyNumber,
			"9": self.keyNumber,
			"0": self.keyNumber
		})
		self.Timer = eTimer()
		self.Timer.callback.append(self.keyOK)
		self.Timer.start(2000, True)

	def keyNumber(self, number):
		self.Timer.start(2000, True)
		self.field = f"{self.field}{number}"
		self["number"].setText(self.field)
		if len(self.field) >= 4:
			self.keyOK()

	def keyOK(self):
		self.Timer.stop()
		self.close(int(self["number"].getText()))

	def quit(self):
		self.Timer.stop()
		self.close(0)


class openATVFav(ATVhelper):
	skin = """
	<screen name="openATVFav" position="center,center" size="966,546" backgroundColor="#1A0F0F0F" resolution="1280,720" title=" ">
		<ePixmap position="10,10" size="300,50" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/openATV_HD.png" alphatest="blend" zPosition="1" />
		<widget source="version" render="Label" position="290,36" size="43,21" font="Regular;16" halign="left" valign="center" foregroundColor="grey" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget source="headline" render="Label" position="330,28" size="630,30" font="Regular;24" halign="left" valign="center" wrap="ellipsis" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<ePixmap position="13,66" size="940,1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/line_HD.png" zPosition="1" />
		<widget source="favMenu" render="Listbox" position="13,73" size="940,420" scrollbarMode="showOnDemand" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1">
			<convert type="TemplatedMultiContent">
				{"template": [
				MultiContentEntryText(pos=(0,0), size=(1200,30), font=0, color="grey" , color_sel="white" , flags=RT_HALIGN_LEFT, text=0)# favorite
				],
				"fonts": [gFont("Regular",22)],
				"itemHeight":30
				}
			</convert>
		</widget>
		<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_red_HD.png" position="14,502" size="26,38" alphatest="blend" />
		<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_blue_HD.png" position="644,502" size="26,38" alphatest="blend" />
		<widget source="key_red" render="Label" position="36,502" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
		<widget source="key_blue" render="Label" position="666,502" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
	</screen>"""

	def __init__(self, session, threadLinks):
		self.threadLinks = threadLinks
		if self.RESOLUTION == "fHD":
			self.skin = self.skin.replace("_HD.png", "_fHD.png")
		Screen.__init__(self, session, self.skin)
		self.count = 0
		self.favlist = []
		self.ready = False
		self["version"] = StaticText(self.VERSION)
		self["headline"] = StaticText("Favoriten")
		self["key_red"] = StaticText("Favorit entfernen")
		self["key_blue"] = StaticText("Startseite")
		self["favMenu"] = List([])
		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "ColorActions"], {
			"ok": self.keyOk,
			"cancel": self.keyExit,
			"down": self.keyPageDown,
			"up": self.keyPageUp,
			"red": self.keyRed,
			"blue": self.keyBlue
		}, -1)
		self.onLayoutFinish.append(self.makeFav)

	def makeFav(self):
		self.ready = False
		self.count = 0
		menutexts = []
		if exists(self.FAVORITEN):
			try:
				with open(self.FAVORITEN) as f:
					for line in f.read().split(linesep):
						if "\t" in line:
							self.count += 1
							favline = line.split("\t")
							favname = favline[0].strip()
							url = favline[1].strip()
							self.favlist.append((favname, url))
							menutexts.append(favname)
			except OSError as errMsg:
				self.session.open(MessageBox, f"Favoriten konnten nicht gelesen werden:\n'{errMsg}'", type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
			if not self.count:
				title = "{keine Einträge vorhanden}"
				self.favlist.append((title, "", ""))
				menutexts.append(title)
			self["favMenu"].updateList(menutexts)
		self.ready = True

	def keyOk(self):
		curridx = self["favMenu"].getCurrentIndex()
		if self.favlist:
			favlink = self.favlist[curridx][1]
			if favlink:
					self.session.openWithCallback(self.keyOkCB, openATVMain, threadLinks=self.threadLinks, favlink=favlink, favMenu=True)

	def keyOkCB(self, home=False):
		if home:
			self.close(True)

	def keyRed(self):
		if exists(self.FAVORITEN):
			curridx = self["favMenu"].getCurrentIndex()
			favname = self.favlist[curridx][0]
			favlink = self.favlist[curridx][1]
			if favname and favlink:
				self.session.openWithCallback(boundFunction(self.keyRedCB, favname, favlink), MessageBox, f"'{favname}'\n\naus den Favoriten entfernen?\n", MessageBox.TYPE_YESNO, timeout=30, default=False)

	def keyRedCB(self, favname, favlink, answer):
		if answer is True:
			data = ""
			try:
				with open(self.FAVORITEN) as f:
					for line in f.read().split("\n"):
						if favlink not in line and line != "\n" and line != "":
							data += f"{line}{linesep}"
			except OSError as errMsg:
				self.session.open(MessageBox, f"Favoriten konnten nicht gelesen werden:\n'{errMsg}'", type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
			try:
				with open(f"{self.FAVORITEN}.new", "w") as f:
					f.write(data)
				rename(f"{self.FAVORITEN}.new", self.FAVORITEN)
			except OSError as errMsg:
				self.session.open(MessageBox, f"Favoriten konnten nicht gelesen werden:\n'{errMsg}'", type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
			self.favlist = []
			self.makeFav()

	def keyBlue(self):
		if self.ready:  # wait on thread was finished
			self.close(True)

	def keyPageDown(self):
		self["favMenu"].down()

	def keyPageUp(self):
		self["favMenu"].up()

	def keyExit(self):
		if self.ready:  # wait on thread was finished
			self.close()


class openATVPost(ATVhelper):
	skin = """
	<screen name="openATVPost" position="center,center" size="1233,680" backgroundColor="#1A0F0F0F" resolution="1280,720" title=" ">
		<ePixmap position="10,10" size="300,50" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/openATV_HD.png" alphatest="blend" zPosition="1" />
		<widget source="version" render="Label" position="290,36" size="43,21" font="Regular;16" halign="left" valign="center" foregroundColor="grey" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget source="headline" render="Label" position="330,28" size="630,30" font="Regular;24" halign="left" valign="center" wrap="ellipsis" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget name="waiting" position="340,29" size="750,30" font="Regular;20" halign="left" valign="bottom" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget source="global.CurrentTime" render="Label" position="1080,6" size="130,40" font="Regular;30" noWrap="1" halign="right" valign="top" foregroundColor="#00FFFFFF" backgroundColor="#1A0F0F0F" transparent="1">
			<convert type="ClockToText">Default</convert>
		</widget>
		<widget source="global.CurrentTime" render="Label" position="940,10" size="140,26" font="Regular;20" noWrap="1" halign="right" valign="bottom" foregroundColor="#00FFFFFF" backgroundColor="#1A0F0F0F" transparent="1">
			<convert type="ClockToText">Format:%A</convert>
		</widget>
		<widget source="global.CurrentTime" render="Label" position="940,34" size="140,26" font="Regular;20" noWrap="1" halign="right" valign="bottom" foregroundColor="#00FFFFFF" backgroundColor="#1A0F0F0F" transparent="1">
			<convert type="ClockToText">Format:%e. %B</convert>
		</widget>
		<widget source="postid" render="Label" position="1080,36" size="130,26" font="Regular;16" halign="right" valign="center" foregroundColor="grey" transparent="1" zPosition="1" />
		<ePixmap position="13,66" size="1200,1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/line_HD.png" zPosition="1" />
		<widget name="avatar" position="21,72" size="69,69" alphatest="blend" transparent="1" zPosition="1" />
		<widget name="online" position="24,144" size="64,16" alphatest="blend" transparent="1" zPosition="1" />
		<widget source="username" render="Label" position="113,76" size="266,30" font="Regular;24" halign="center" valign="center" transparent="1" zPosition="1" foregroundColor="#0092cbdf" />
		<widget source="usertitle" render="Label" position="113,133" size="266,28" font="Regular;21" halign="center" valign="center" foregroundColor="grey" transparent="1" zPosition="1" />
		<widget name="userrank" position="173,106" size="150,26" alphatest="blend" transparent="1" zPosition="1" />
		<widget source="postcnt" render="Label" position="426,80" size="200,28" font="Regular;21" halign="left" valign="center" foregroundColor="#0092cbdf" transparent="1" zPosition="1" />
		<widget source="thxgiven" render="Label" position="426,106" size="266,28" font="Regular;21" halign="left" valign="center" foregroundColor="#00b2b300" transparent="1" zPosition="1" />
		<widget source="thxreceived" render="Label" position="426,133" size="266,28" font="Regular;21" halign="left" valign="center" foregroundColor="#005fb300" transparent="1" zPosition="1" />
		<widget source="residence" render="Label" position="866,80" size="333,28" font="Regular;21" halign="right" valign="center" foregroundColor="#0092cbdf" transparent="1" zPosition="1" />
		<widget source="registered" render="Label" position="866,106" size="333,28" font="Regular;21" halign="right" valign="center" foregroundColor="#00b2b300" transparent="1" zPosition="1" />
		<widget source="datum" render="Label" position="866,133" size="333,28" font="Regular;21" halign="right" valign="center" foregroundColor="#005fb300" transparent="1" zPosition="1" />
		<ePixmap position="13,166" size="1200,1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/line_HD.png" zPosition="1" />
		<widget name="textarea" position="26,186" size="1160,433" font="Regular;24" halign="left" foregroundColor="white" transparent="1" zPosition="0" />
		<widget name="scrollbar" position="1196,186" size="2,433" backgroundColor="#00505050" zPosition="1" />
		<widget name="scrollthumb" position="1194,186" size="6,40" backgroundColor="#00b3b3b3" zPosition="2" />
		<widget name="picframe" position="26,186" size="10,10" backgroundColor="#00ffcc00" zPosition="0" />
		<widget name="codebg0" position="26,186" size="10,10" backgroundColor="#00283038" zPosition="0" />
		<widget name="codebg1" position="26,186" size="10,10" backgroundColor="#00283038" zPosition="0" />
		<widget name="codebg2" position="26,186" size="10,10" backgroundColor="#00283038" zPosition="0" />
		<widget name="codebg3" position="26,186" size="10,10" backgroundColor="#00283038" zPosition="0" />
"""
	# pool of widgets for the visible text blocks and images, positioned at runtime
	skin += "".join(f'<widget name="text{no}" position="26,186" size="1160,30" font="Regular;24" halign="left" foregroundColor="white" transparent="1" zPosition="1" />\n' for no in range(12))
	skin += "".join(f'<widget name="pic{no}" position="26,186" size="10,10" alphatest="blend" transparent="1" zPosition="1" />\n' for no in range(6))
	skin += "".join(f'<widget name="vidlabel{no}" position="26,186" size="170,34" font="Regular;20" halign="center" valign="center" foregroundColor="white" backgroundColor="#00000000" zPosition="2" />\n' for no in range(6))
	skin += """		<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_red_HD.png" position="14,636" size="26,38" alphatest="blend" />
		<widget name="button_green" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_green_HD.png" position="224,636" size="26,38" alphatest="blend" />
		<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_yellow_HD.png" position="434,636" size="26,38" alphatest="blend" />
		<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_blue_HD.png" position="644,636" size="26,38" alphatest="blend" />
		<widget source="key_red" render="Label" position="36,636" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
		<widget source="key_green" render="Label" position="246,636" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
		<widget source="key_yellow" render="Label" position="456,636" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
		<widget source="key_blue" render="Label" position="666,636" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
	</screen>"""

	TEXTWIDGETS = 12  # size of the widget pools in the skin
	PICWIDGETS = 6
	BLOCKGAP = 8  # vertical space around images
	MARKER = compile(r"\[(Link|Bild|Video)\u00a0(\d+)\]")  # markers in the text, joined by a no-break space so they never get wrapped
	COLORLINK = "\\c0092cbdf"  # eLabel color codes
	COLORSELECTED = "\\c00ffcc00"
	COLORRESET = "\\C"
	COLORCODE = "\\c00b8e0b8"
	COLORCODEHEAD = "\\c00909090"
	CODEWIDGETS = 4  # backgrounds of the visible code blocks
	CODEINDENT = "\u00a0" * 3

	def __init__(self, session, threadTitle, postId, favMenu, threadLinks):
		if self.RESOLUTION == "fHD":
			self.skin = self.skin.replace("_HD.png", "_fHD.png")
		Screen.__init__(self, session, self.skin)
		self.postId = postId
		self.threadTitle = threadTitle
		self.favMenu = favMenu
		self.threadLinks = threadLinks
		self.ready = False
		self.avatarDLlist = []  # is required, don't remove
		self.postNo = ""
		self.userName = ""
		self.links, self.images, self.videos = [], [], []
		self.content = ""
		self.imageFiles, self.videoThumbs, self.pixmapCache = {}, {}, {}  # {index: filePath} of images & video thumbnails, decoded pixmaps {(mediaType, index, width, height): pixmap}
		self.rows, self.topRow, self.lineHeight = [], 0, 0  # layout rows: ("text", line, height) or ("pic", (imageIndex, width, height), height)
		self.targets, self.selected = [], None  # images, videos & links which can be opened with OK: (rowNo, "image"|"video"|"link", index, occurrence in row)
		self.closed = False
		self["waiting"] = BlinkingLabel("bitte warten...")
		self["waiting"].startBlinking()
		self["waiting"].show()
		self["version"] = StaticText(self.VERSION)
		for widget in ["headline", "postid", "username", "usertitle", "postcnt", "thxgiven", "thxreceived", "registered", "residence", "datum", "key_green"]:
			self[widget] = StaticText()
		for widget in ["online", "avatar", "userrank", "button_green"]:
			self[widget] = Pixmap()
		self["button_green"].hide()
		self["textarea"] = Label()  # invisible: defines the text area and is used to measure the height of text blocks
		self["textarea"].hide()
		for widgetNo in range(self.TEXTWIDGETS):
			self[f"text{widgetNo}"] = Label()
		for widgetNo in range(self.PICWIDGETS):
			self[f"pic{widgetNo}"] = Pixmap()
			self[f"pic{widgetNo}"].hide()
			self[f"vidlabel{widgetNo}"] = Label()
			self[f"vidlabel{widgetNo}"].hide()
		for widget in ["scrollbar", "scrollthumb", "picframe"] + [f"codebg{widgetNo}" for widgetNo in range(self.CODEWIDGETS)]:
			self[widget] = Label()
			self[widget].hide()
		self["key_red"] = StaticText("Favorit hinzufügen")
		self["key_yellow"] = StaticText("Favoriten aufrufen")
		self["key_blue"] = StaticText("Startseite")
		self["NumberActions"] = ActionMap(["NumberActions", "OkCancelActions", "DirectionActions", "ChannelSelectBaseActions", "ColorActions"], {
			"ok": self.keyOk,
			"cancel": self.keyExit,
			"down": self.keyDown,
			"up": self.keyUp,
			"right": self.keyPageDown,
			"left": self.keyPageUp,
			"nextBouquet": self.keyPageDown,
			"prevBouquet": self.keyPageUp,
			"red": self.keyRed,
			"green": self.keyGreen,
			"yellow": self.keyYellow,
			"blue": self.keyBlue
		}, -1)
		self.onLayoutFinish.append(self.onLayoutFinished)
		self.onClose.append(self.setClosed)

	def onLayoutFinished(self):
		callInThread(self.makePost)

	def setClosed(self):
		self.closed = True  # running download threads must not touch the widgets anymore
		if hasattr(self, "thumbConsole"):
			self.thumbConsole.killAll()

	def makePost(self):
		errMsg, postDict = fparser.parsePost(self.postId)
		callFromThread(self.showPost, errMsg, postDict)  # the page layout has to be done in the main thread

	def showPost(self, errMsg, postDict):
		if self.closed:
			return
		self.ready = False
		if errMsg:
			self["waiting"].stopBlinking()
			self.ready = True  # otherwise the screen could not be closed anymore
			self.session.open(MessageBox, f"FEHLER: {errMsg}", type=MessageBox.TYPE_ERROR, timeout=5, close_on_any_key=True)
			return
		if postDict:
			self.postNo = postDict.get("postNumber", "")
			self.userName = postDict.get("userName", "")
			self.threadTitle = postDict.get("threadTitle", "") or self.threadTitle  # linked posts could be part of another thread
			self.links, self.images, self.videos = postDict.get("links", []), postDict.get("images", []), postDict.get("videos", [])
			if self.images or self.videos:
				self["key_green"].setText("Medien anzeigen")
				self["button_green"].show()
			_, filePath = self.handleAvatar(self["avatar"], postDict.get("avatarUrl", ""), self.handleAvatarShow)
			self.showPic(self["avatar"], f"{filePath if filePath and exists(filePath) else join(self.AVATARPATH, "unknown.png")}")
			userRank = postDict.get("userRank", "")
			self.handleIcon(self["userrank"], userRank, self.handleIconShow)
			online = postDict.get("online", "")
			self.showPic(self["online"], join(self.PLUGINPATH, f"{'icons/online' if online else 'icons/offline'}_{self.RESOLUTION}.png"), scale=False)
			self["waiting"].stopBlinking()
			self["headline"].setText(f"THEMA: {self.threadTitle}")
			self["postid"].setText(f"ID: {self.postId}")
			self["username"].setText(self.userName)
			self["usertitle"].setText(postDict.get("userTitle", ""))
			self["postcnt"].setText(postDict.get("postsCounter", "0"))
			self["thxgiven"].setText(postDict.get("thxGiven", "{keine}"))
			self["thxreceived"].setText(postDict.get("thxReceived", "{keine})"))
			self["residence"].setText(f"{postDict.get('residence', '{kein Wohnort benannt}')}")
			self["registered"].setText(f"Registriert seit {postDict.get('registered', '{unbekannt}').replace('Registriert: ', '')}")
			self["datum"].setText(f"Beitrag von {postDict.get('postTime', '')} Uhr")
			self.content = f"{self.postNo}: {postDict.get('fullContent', '{ohne Inhalt}')}"
			self.buildRows()
			self.showRows(0)
			if self.images:
				callInThread(self.loadImages)
			if self.videos:
				self.loadVideoThumbs()
		self.ready = True

	def loadImages(self):
		for index, url in enumerate(self.images):
			if self.closed:
				return
			filePath = self.findPostImage(url)
			if not filePath:
				errMsg, filePath = self.downloadPostImage(url)
				if errMsg:
					print(f"[{self.MODULE_NAME}] ERROR in module 'loadImages': {url}: {errMsg}!")
			if filePath:
				callFromThread(self.mediaLoaded, "image", index, filePath)

	def loadVideoThumbs(self, index=0):  # one ffmpeg after the other, runs asynchronously in the main loop
		while index < len(self.videos) and not self.closed:
			filePath = self.findVideoThumb(self.videos[index])
			if not filePath:
				self.createVideoThumb(self.videos[index], boundFunction(self.videoThumbCreated, index))
				return
			self.mediaLoaded("video", index, filePath)
			index += 1

	def videoThumbCreated(self, index, errMsg, filePath):
		if self.closed:
			return
		if errMsg:
			print(f"[{self.MODULE_NAME}] ERROR in module 'loadVideoThumbs': {self.videos[index]}: {errMsg}!")
		if filePath:
			self.mediaLoaded("video", index, filePath)
		self.loadVideoThumbs(index + 1)

	def mediaLoaded(self, mediaType, index, filePath):
		if self.closed:
			return
		(self.imageFiles if mediaType == "image" else self.videoThumbs)[index] = filePath
		topRowData = self.rows[self.topRow][1] if self.rows else None  # keep the position: look for the current top line again
		topRow = self.topRow
		selectedTarget = self.targets[self.selected][1:3] if self.selected is not None else None
		self.buildRows()
		self.selected = next((index for index, target in enumerate(self.targets) if target[1:3] == selectedTarget), None)
		if topRow:
			topRow = next((index for index, row in enumerate(self.rows) if row[1] == topRowData and index >= topRow - 5), topRow)
		self.showRows(topRow)

	def measureText(self, text):
		self["textarea"].setText(text)
		return self["textarea"].instance.calculateSize().height()

	def isSingleLine(self, text):
		return self.measureText(text) < self.lineHeight * 1.5

	def wrapParagraph(self, paragraph):  # split a paragraph into the lines the label would show
		if self.isSingleLine(paragraph):
			return [paragraph]
		lines, line = [], ""
		for word in paragraph.split(" "):
			candidate = f"{line} {word}" if line else word
			if self.isSingleLine(candidate):
				line = candidate
				continue
			if line:
				lines.append(line)
			while not self.isSingleLine(word):  # a single word wider than the text area (e.g. long URLs)
				low, high = 1, len(word)
				while low < high:  # find the longest fitting prefix
					middle = (low + high + 1) // 2
					if self.isSingleLine(word[:middle]):
						low = middle
					else:
						high = middle - 1
				lines.append(word[:low])
				word = word[low:]
			line = word
		return lines + [line]

	def wrapCode(self, line):  # split a code line into the lines the label would show, keeping all spaces
		line = f"{self.CODEINDENT}{line.replace(chr(9), '    ')}"
		lines = []
		while not self.isSingleLine(line):
			low, high = 1, len(line)
			while low < high:  # find the longest fitting prefix
				middle = (low + high + 1) // 2
				if self.isSingleLine(line[:middle]):
					low = middle
				else:
					high = middle - 1
			lines.append(line[:low])
			line = f"{self.CODEINDENT}{line[low:]}"
		return lines + [line]

	def buildRows(self):  # convert the content into rows of text lines, code lines and images for scrolling
		areaSize = self["textarea"].instance.size()
		areaWidth, areaHeight = areaSize.width(), areaSize.height()
		self.lineHeight = self.measureText("X\nX") - self.measureText("X")  # distance between two lines of the label
		self.rows = []
		text = ""

		def addText(text):
			text = sub(r"\\(?=[ntrcC])", lambda match: "\\\u200b", text)  # a zero width space keeps eLabel from interpreting e.g. '\\n' of the text
			text = sub(r"\[(Link|Bild|Video) (\d+)\]", "[\\1\u00a0\\2]", text)
			for paragraph in text.strip("\n").split("\n"):
				if paragraph.startswith(fpglobals.CODEHEAD):
					self.rows.append(("codehead", paragraph[1:], self.lineHeight))
				elif paragraph.startswith(fpglobals.CODELINE):
					for line in self.wrapCode(paragraph[1:]):
						self.rows.append(("code", line, self.lineHeight))
				else:
					for line in self.wrapParagraph(paragraph):
						self.rows.append(("text", line, self.lineHeight))

		parts = split(r"\[(Bild|Video) (\d+)\]", self.content)  # [text, kind, number, text, kind, number, ...]
		text = parts[0]
		for partNo in range(1, len(parts), 3):  # loaded images & video thumbnails become their own row, otherwise the marker remains in the text
			kind, number = parts[partNo], parts[partNo + 1]
			mediaType, index = "image" if kind == "Bild" else "video", int(number) - 1
			width, height = self.getImageSize((self.imageFiles if mediaType == "image" else self.videoThumbs).get(index, ""))
			if width and height:
				addText(text)
				text = ""
				scale = min(1.0, areaWidth / width, (areaHeight - self.BLOCKGAP) / height)
				width, height = max(1, int(width * scale)), max(1, int(height * scale))
				self.rows.append(("pic", (mediaType, index, width, height), height + self.BLOCKGAP))
			else:
				text += f"[{kind} {number}]"
			text += parts[partNo + 2]
		addText(text)
		self.targets = []
		for rowNo, (rowType, data, height) in enumerate(self.rows):
			if rowType == "pic":
				self.targets.append((rowNo, data[0], data[1], 0))
			elif rowType == "text":
				for occurrence, match in enumerate(self.MARKER.finditer(data)):
					targetType = {"Bild": "image", "Video": "video"}.get(match.group(1), "link")
					self.targets.append((rowNo, targetType, int(match.group(2)) - 1, occurrence))

	def visibleTargets(self):
		lastRow = self.topRow + self.visibleRows(self.topRow)
		return [index for index, target in enumerate(self.targets) if self.topRow <= target[0] < lastRow]

	def colorizeLine(self, rowNo, text):  # links/images in the text get colored, the selected one highlighted
		selected = self.targets[self.selected] if self.selected is not None else None
		occurrence = -1

		def color(match):
			nonlocal occurrence
			occurrence += 1
			isSelected = selected and selected[0] == rowNo and selected[3] == occurrence
			return f"{self.COLORSELECTED if isSelected else self.COLORLINK}{match.group(0)}{self.COLORRESET}"

		return self.MARKER.sub(color, text)

	def formatRow(self, rowNo, rowType, text):
		if rowType == "code":
			return f"{self.COLORCODE}{text}{self.COLORRESET}"
		if rowType == "codehead":
			return f"{self.COLORCODEHEAD}{text}{self.COLORRESET}"
		return self.colorizeLine(rowNo, text)

	def visibleRows(self, topRow):  # number of rows which fit completely into the text area, starting at 'topRow'
		areaHeight = self["textarea"].instance.size().height()
		used, count = 0, 0
		for row in self.rows[topRow:]:
			if used + row[2] > areaHeight:
				break
			used += row[2]
			count += 1
		return max(1, count)

	def maxTopRow(self):
		row, used = len(self.rows), 0
		areaHeight = self["textarea"].instance.size().height()
		while row > 0 and used + self.rows[row - 1][2] <= areaHeight:
			row -= 1
			used += self.rows[row][2]
		return min(row, max(0, len(self.rows) - 1))

	def showRows(self, topRow, selectLast=False):
		self.topRow = max(0, min(topRow, self.maxTopRow()))
		visible = self.visibleTargets()
		if self.selected not in visible:  # the selection follows the scrolling
			self.selected = (visible[-1] if selectLast else visible[0]) if visible else None
		selectedRow = self.targets[self.selected][0] if self.selected is not None else -1
		areaPos = self["textarea"].instance.position()
		areaSize = self["textarea"].instance.size()
		for widgetNo in range(self.TEXTWIDGETS):
			self[f"text{widgetNo}"].hide()
		for widgetNo in range(self.PICWIDGETS):
			self[f"pic{widgetNo}"].hide()
			self[f"vidlabel{widgetNo}"].hide()
		self["picframe"].hide()
		for widgetNo in range(self.CODEWIDGETS):
			self[f"codebg{widgetNo}"].hide()
		textNo, picNo, codeNo, posY, lines, codeStart = 0, 0, 0, 0, [], -1

		def flushCode():  # background of a code block (or of its visible part)
			nonlocal codeNo, codeStart
			if codeStart != -1 and codeNo < self.CODEWIDGETS:
				widget = self[f"codebg{codeNo}"]
				codeNo += 1
				widget.instance.resize(eSize(areaSize.width() + self.BLOCKGAP, posY - codeStart + self.BLOCKGAP // 2))
				widget.instance.move(ePoint(areaPos.x() - self.BLOCKGAP // 2, areaPos.y() + codeStart))
				widget.show()
			codeStart = -1

		def flushText():  # consecutive text lines share one label
			nonlocal textNo, lines
			if lines and textNo < self.TEXTWIDGETS:
				widget = self[f"text{textNo}"]
				textNo += 1
				widget.setText("\n".join(self.formatRow(rowNo, rowType, line) for rowNo, rowType, line in lines))
				widget.instance.resize(eSize(areaSize.width(), (len(lines) + 1) * self.lineHeight))
				widget.instance.move(ePoint(areaPos.x(), areaPos.y() + posY - len(lines) * self.lineHeight))
				widget.show()
			lines = []

		for rowNo in range(self.topRow, self.topRow + self.visibleRows(self.topRow)):
			rowType, data, height = self.rows[rowNo]
			if rowType in ("code", "codehead"):
				if codeStart == -1 or rowType == "codehead":
					flushCode()
					codeStart = posY
			elif codeStart != -1:
				flushCode()
			if rowType != "pic":
				lines.append((rowNo, rowType, data))
			else:
				flushText()
				mediaType, mediaIndex, width, picHeight = data
				pixmap = self.getScaledPixmap(mediaType, mediaIndex, width, picHeight)
				if pixmap and picNo < self.PICWIDGETS:
					widget = self[f"pic{picNo}"]
					widget.instance.resize(eSize(width, picHeight))
					widget.instance.move(ePoint(areaPos.x(), areaPos.y() + posY + self.BLOCKGAP // 2))
					widget.instance.setPixmap(pixmap)
					widget.show()
					if mediaType == "video":  # label on the thumbnail
						label = self[f"vidlabel{picNo}"]
						label.setText(f"\u25b6 Video {mediaIndex + 1}")
						labelHeight = label.instance.size().height()
						label.instance.move(ePoint(areaPos.x() + self.BLOCKGAP, areaPos.y() + posY + self.BLOCKGAP // 2 + picHeight - labelHeight - self.BLOCKGAP))
						label.show()
					picNo += 1
					if rowNo == selectedRow:
						frame = self.BLOCKGAP // 2
						self["picframe"].instance.resize(eSize(width + 2 * frame, picHeight + 2 * frame))
						self["picframe"].instance.move(ePoint(areaPos.x() - frame, areaPos.y() + posY))
						self["picframe"].show()
			posY += height
		flushText()
		flushCode()
		self.updateScrollbar()

	def updateScrollbar(self):
		areaHeight = self["textarea"].instance.size().height()
		totalHeight = sum(row[2] for row in self.rows)
		if totalHeight <= areaHeight:
			self["scrollbar"].hide()
			self["scrollthumb"].hide()
			return
		barPos = self["scrollbar"].instance.position()
		thumbWidth = self["scrollthumb"].instance.size().width()
		offset = sum(row[2] for row in self.rows[:self.topRow])
		thumbHeight = max(10, areaHeight * areaHeight // totalHeight)
		thumbPos = min(areaHeight - thumbHeight, offset * areaHeight // totalHeight)
		self["scrollthumb"].instance.resize(eSize(thumbWidth, thumbHeight))
		self["scrollthumb"].instance.move(ePoint(self["scrollthumb"].instance.position().x(), barPos.y() + thumbPos))
		self["scrollbar"].show()
		self["scrollthumb"].show()

	def getScaledPixmap(self, mediaType, index, width, height):
		key = (mediaType, index, width, height)
		if key not in self.pixmapCache:
			filePath = (self.imageFiles if mediaType == "image" else self.videoThumbs).get(index, "")
			self.pixmapCache[key] = self.loadScaledPixmap(filePath, width, height)
		return self.pixmapCache[key]

	def handleAvatarShow(self, widget, url, filePath):
		self.downloadAvatar(url, filePath)
		self.showPic(widget, filePath)

	def handleIcon(self, widget, iconUrl, callback=None):
		iconPix = None
		if iconUrl:
			if iconUrl.startswith("./"):  # in case it's an plugin icon
				filePath = join(self.AVATARPATH, iconUrl.replace("./", ""))
			else:
				fileName = f"{iconUrl[iconUrl.rfind('/') + 1:]}"
				filePath = join(self.AVATARPATH, fileName) if fileName else join(self.AVATARPATH, "unknown.png")
			if filePath and exists(filePath):
				iconPix = LoadPixmap(cached=True, path=filePath)
				self.showPic(widget, filePath)
			elif callback:
					callInThread(callback, widget, iconUrl, filePath)
		return iconPix

	def handleIconShow(self, widget, url, filePath):
		self.downloadIcon(url, filePath)
		self.showPic(widget, filePath)

	def downloadIcon(self, url, filePath):
		errMsg, binaryData = fparser.getBinaryData(url)
		if errMsg:
			print(f"[{self.MODULE_NAME}] ERROR in module 'downloadIcon': {errMsg}!")
			errText = f"Der OpenA.TV Server ist zur Zeit nicht erreichbar.\n{errMsg}"
			self.session.open(MessageBox, errText, MessageBox.TYPE_INFO, timeout=30, close_on_any_key=True)
			return
		if binaryData:
			try:
				with open(filePath, "wb") as f:
					f.write(binaryData)
			except OSError as errMsg:
				print(f"[{self.MODULE_NAME}] ERROR in module 'downloadIcon': {errMsg}!")
				self.session.open(MessageBox, errMsg, MessageBox.TYPE_INFO, timeout=30, close_on_any_key=True)
		fileParts = filePath.split(".")
		extension = {0: "png", 1: "jpg", 3: "gif", 4: "svg", 5: "webp"}.get(detectImageType(filePath), fileParts[1])
		if extension != fileParts[1]:  # Some avatars could be incorrectly listed in 'url' as .GIF although they are .JPG or .PNG
			newFname = f"{fileParts[0]}.{extension}"
			rename(filePath, newFname)  # rename with correct extension

	def getMedia(self):  # images and videos in the order of the post: [("image"|"video", url), ...]
		order = []
		for _, targetType, index, _ in self.targets:
			if targetType in ("image", "video") and (targetType, index) not in order:
				order.append((targetType, index))
		order += [("image", index) for index in range(len(self.images)) if ("image", index) not in order]
		order += [("video", index) for index in range(len(self.videos)) if ("video", index) not in order]
		return order, [(targetType, self.images[index] if targetType == "image" else self.videos[index]) for targetType, index in order]

	def openMedia(self, targetType="", index=-1):  # media viewer, starts with the given image/video, otherwise with the first one
		order, media = self.getMedia()
		if media:
			self.session.open(openATVImage, media, order.index((targetType, index)) if (targetType, index) in order else 0, self.threadTitle)

	def keyGreen(self):
		if self.ready:
			selected = self.targets[self.selected] if self.selected is not None else ("", "", -1)
			self.openMedia(selected[1], selected[2])

	def keyOk(self):
		if self.ready and self.selected is not None:
			self.openTarget(*self.targets[self.selected][1:3])

	def openTarget(self, targetType, index):
		if targetType == "image":
			self.openMedia(targetType, index)
			return
		if targetType == "video":
			self.playVideo(self.videos[index], self.threadTitle, f"Video {index + 1}")
			return
		link = self.links[index]
		if link["type"] == "post":
			self.session.openWithCallback(self.keyLinkCB, openATVPost, "", link["target"], self.favMenu, self.threadLinks)
		else:
			self.session.openWithCallback(self.keyLinkCB, openATVMain, threadLinks=self.threadLinks, favlink=link["target"], favMenu=True)

	def keyLinkCB(self, home=False):
		if home:
			self.close(True)

	def keyYellow(self):
		if self.favMenu:
			self.session.open(MessageBox, "Dieses Fenster wurde bereits als Favorit geöffnet!\nUm auf die Favoritenliste zurückzukommen, bitte 2x 'Verlassen/Exit' drücken!\n", type=MessageBox.TYPE_INFO, timeout=5, close_on_any_key=True)
		else:
			self.session.openWithCallback(self.keyYellowCB, openATVFav, self.threadLinks)

	def keyYellowCB(self, home=False):
		if home:
			self.close(True)

	def keyRed(self):
		favname = f"BEITRAG {self.postNo} von '{self.userName}' in '{self.threadTitle}'"
		favlink = fparser.createPostUrl(self.postId)
		if self.favoriteExists(self.session, favname, favlink):
			self.session.open(MessageBox, f"ABBRUCH!\n\n'{favname}'\n\nist bereits in den Favoriten vorhanden.\n", type=MessageBox.TYPE_ERROR, timeout=5, close_on_any_key=True)
		else:
			self.session.openWithCallback(boundFunction(self.keyRedCB, favname, favlink), MessageBox, f"'{favname}'\n\nzu den Favoriten hinzufügen?\n", MessageBox.TYPE_YESNO, timeout=30)

	def keyBlue(self):
		self.close(True)

	def keyRedCB(self, favname, favlink, answer):
		if answer is True:
			self.writeFavorite(self.session, favname, favlink)

	def keyDown(self):
		if self.ready:
			if self.selected is not None and self.selected + 1 in self.visibleTargets():
				self.selected += 1
				self.showRows(self.topRow)
			else:
				self.showRows(self.topRow + 1)

	def keyUp(self):
		if self.ready:
			if self.selected is not None and self.selected - 1 in self.visibleTargets():
				self.selected -= 1
				self.showRows(self.topRow)
			else:
				self.showRows(self.topRow - 1, selectLast=True)

	def keyPageDown(self):
		if self.ready:
			self.showRows(self.topRow + self.visibleRows(self.topRow))

	def keyPageUp(self):
		if self.ready:
			row, used = self.topRow, 0
			areaHeight = self["textarea"].instance.size().height()
			while row > 0 and used + self.rows[row - 1][2] <= areaHeight:
				row -= 1
				used += self.rows[row][2]
			self.showRows(row if row < self.topRow else self.topRow - 1, selectLast=True)

	def keyExit(self):
		if self.ready:  # wait on thread was finished
			self.close()


class openATVImage(ATVhelper):
	skin = """
	<screen name="openATVImage" position="center,center" size="1233,680" backgroundColor="#1A0F0F0F" resolution="1280,720" title=" ">
		<ePixmap position="10,10" size="300,50" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/openATV_HD.png" alphatest="blend" zPosition="1" />
		<widget source="version" render="Label" position="290,36" size="43,21" font="Regular;16" halign="left" valign="center" foregroundColor="grey" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget source="headline" render="Label" position="330,28" size="630,30" font="Regular;24" halign="left" valign="center" wrap="ellipsis" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget name="waiting" position="340,29" size="750,30" font="Regular;20" halign="left" valign="bottom" backgroundColor="#1A0F0F0F" transparent="1" zPosition="2" />
		<ePixmap position="13,66" size="1200,1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/line_HD.png" zPosition="1" />
		<widget name="picture" position="13,72" size="1200,552" alphatest="blend" transparent="1" zPosition="1" />
		<widget source="picinfo" render="Label" position="13,300" size="1200,90" font="Regular;22" halign="center" valign="center" foregroundColor="grey" backgroundColor="#1A0F0F0F" transparent="1" zPosition="2" />
		<ePixmap position="13,630" size="1200,1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/line_HD.png" zPosition="1" />
		<widget source="key_page" render="Label" position="913,636" size="300,38" font="Regular;18" halign="right" valign="center" foregroundColor="grey" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
	</screen>"""

	def __init__(self, session, media, index=0, title=""):  # media: [("image"|"video", url), ...]
		if self.RESOLUTION == "fHD":
			self.skin = self.skin.replace("_HD.png", "_fHD.png")
		Screen.__init__(self, session, self.skin)
		self.media = media
		self.index = index
		self.mediaTitle = title
		self["waiting"] = BlinkingLabel("bitte warten...")
		self["version"] = StaticText(self.VERSION)
		for widget in ["headline", "picinfo"]:
			self[widget] = StaticText()
		self["key_page"] = StaticText("links/rechts: zurück/vor" if len(media) > 1 else "")
		self["picture"] = Pixmap()
		self.area = None
		self.closed = False
		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {
			"ok": self.keyOk,
			"cancel": self.close,
			"left": self.prevImage,
			"up": self.prevImage,
			"right": self.nextImage,
			"down": self.nextImage
		}, -1)
		self.onLayoutFinish.append(self.showImage)
		self.onClose.append(self.setClosed)

	def setClosed(self):
		self.closed = True

	def mediaNumber(self):  # e.g. 2 for the second video, counted separately for images and videos
		mediaType = self.media[self.index][0]
		return sum(1 for entry in self.media[:self.index + 1] if entry[0] == mediaType)

	def showImage(self):
		mediaType, url = self.media[self.index]
		name = f"{'Video' if mediaType == 'video' else 'Bild'} {self.mediaNumber()}"
		mixed = len({entry[0] for entry in self.media}) > 1
		self["headline"].setText(f"{name} ({self.index + 1} von {len(self.media)})" if mixed else f"{name} von {len(self.media)}")
		self["picinfo"].setText("")
		self["picture"].hide()
		if mediaType == "video":
			self["waiting"].stopBlinking()
			thumbPath = self.findVideoThumb(url)
			if thumbPath:
				self["headline"].setText(f"{self['headline'].getText()}  -  OK: Video abspielen")
				self.displayImage(thumbPath)
			else:
				self["picinfo"].setText(f"{name}\n\nOK: Video abspielen")
			return
		filePath = self.findPostImage(url)
		if filePath:
			self["waiting"].stopBlinking()
			self.displayImage(filePath)
		else:
			self["waiting"].startBlinking()
			self["waiting"].show()
			callInThread(self.downloadImage, self.index, url)

	def downloadImage(self, index, url):
		errMsg, filePath = self.downloadPostImage(url)
		callFromThread(self.imageLoaded, index, errMsg, filePath)

	def imageLoaded(self, index, errMsg, filePath):
		if self.closed or index != self.index:  # screen closed or user has already switched to another image
			return
		self["waiting"].stopBlinking()
		if filePath:
			self.displayImage(filePath)
		else:
			print(f"[{self.MODULE_NAME}] ERROR in module 'downloadImage': {errMsg}!")
			self["picinfo"].setText(f"Das Bild konnte nicht geladen werden:\n{errMsg}")

	def displayImage(self, filePath):  # scale the image to fit into the picture area (max. twice its size) and center it
		widget = self["picture"]
		if not self.area:  # the widget gets moved & resized, so remember its skin geometry
			pos, size = widget.instance.position(), widget.instance.size()
			self.area = (pos.x(), pos.y(), size.width(), size.height())
		areaX, areaY, areaWidth, areaHeight = self.area
		width, height = self.getImageSize(filePath)
		pixmap = None
		if width and height:
			scale = min(2.0, areaWidth / width, areaHeight / height)
			width, height = max(1, int(width * scale)), max(1, int(height * scale))
			pixmap = self.loadScaledPixmap(filePath, width, height)
		if pixmap:
			widget.instance.resize(eSize(width, height))
			widget.instance.move(ePoint(areaX + (areaWidth - width) // 2, areaY + (areaHeight - height) // 2))
			widget.instance.setPixmap(pixmap)
			widget.show()
		else:  # e.g. SVG: let enigma2 load and scale it
			widget.instance.resize(eSize(areaWidth, areaHeight))
			widget.instance.move(ePoint(areaX, areaY))
			self.showPic(widget, filePath)

	def keyOk(self):
		mediaType, url = self.media[self.index]
		if mediaType == "video":
			self.playVideo(url, self.mediaTitle, f"Video {self.mediaNumber()}")
		else:
			self.close()

	def prevImage(self):
		if len(self.media) > 1:
			self.index = (self.index - 1) % len(self.media)
			self.showImage()

	def nextImage(self):
		if len(self.media) > 1:
			self.index = (self.index + 1) % len(self.media)
			self.showImage()


class openATVMain(ATVhelper):
	skin = """
	<screen name="openATVMain" position="center,center" size="1233,680" backgroundColor="#1A0F0F0F" resolution="1280,720" title=" ">
		<ePixmap position="10,10" size="300,50" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/openATV_HD.png" alphatest="blend" zPosition="1" />
		<widget source="version" render="Label" position="290,36" size="43,21" font="Regular;16" halign="left" valign="center" foregroundColor="grey" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget source="headline" render="Label" position="330,28" size="630,30" font="Regular;24" halign="left" valign="center" wrap="ellipsis" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget name="waiting" position="340,29" size="750,30" font="Regular;20" halign="left" valign="bottom" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget source="global.CurrentTime" render="Label" position="1080,6" size="130,40" font="Regular;30" noWrap="1" halign="right" valign="top" foregroundColor="#00FFFFFF" backgroundColor="#1A0F0F0F" transparent="1">
			<convert type="ClockToText">Default</convert>
		</widget>
		<widget source="global.CurrentTime" render="Label" position="940,10" size="140,26" font="Regular;20" noWrap="1" halign="right" valign="bottom" foregroundColor="#00FFFFFF" backgroundColor="#1A0F0F0F" transparent="1">
			<convert type="ClockToText">Format:%A</convert>
		</widget>
		<widget source="global.CurrentTime" render="Label" position="940,34" size="140,26" font="Regular;20" noWrap="1" halign="right" valign="bottom" foregroundColor="#00FFFFFF" backgroundColor="#1A0F0F0F" transparent="1">
			<convert type="ClockToText">Format:%e. %B</convert>
		</widget>
		<widget source="pagecount" render="Label" position="1080,36" size="130,26" font="Regular;16" halign="right" valign="center" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget source="menu" render="Listbox" position="13,66" size="1200,560" scrollbarMode="showOnDemand" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1">
			<convert type="TemplatedMultiContent">
				{"templates":
					{"default": (80,[ # index
						MultiContentEntryPixmapAlphaTest(pos=(0,0), size=(1200,1), png=6), # line separator
						MultiContentEntryText(pos=(6,2), size=(914,34), font=0, color="grey", color_sel="white", flags=RT_HALIGN_LEFT|RT_ELLIPSIS, text=0),  # theme
						MultiContentEntryText(pos=(6,28), size=(914,32), font=1, color=0x003ca2c6, color_sel=0x00a6a6a6, flags=RT_HALIGN_LEFT, text=1),  # creation
						MultiContentEntryText(pos=(6,52), size=(914,32), font=1, color=0x003ca2c6, color_sel=0x00a6a6a6, flags=RT_HALIGN_LEFT, text=2),  # forum
						MultiContentEntryText(pos=(922,2), size=(260,30), font=2, color=0x005fb300, color_sel=0x0088ff00, flags=RT_HALIGN_RIGHT, text=3),  # postTime
						MultiContentEntryText(pos=(922,24), size=(260,34), font=0, color=0x00b2b300, color_sel=0x00ffff00, flags=RT_HALIGN_RIGHT, text=4),  # user
						MultiContentEntryText(pos=(922,54), size=(260,30), font=2, color=0x003ca2c6, color_sel=0x0092cbdf, flags=RT_HALIGN_RIGHT, text=5)  # statistic
						]),
						"thread": (93,[
						MultiContentEntryPixmapAlphaTest(pos=(0,0), size=(1200,1), png=4), # line separator
						MultiContentEntryPixmapAlphaBlend(pos=(6,2), size=(70,70), flags=BT_HALIGN_LEFT|BT_VALIGN_CENTER|BT_SCALE|BT_KEEP_ASPECT_RATIO, png=5),  # avatar
						MultiContentEntryPixmapAlphaBlend(pos=(9,72), size=(64,16), png=6),  # online
						MultiContentEntryText(pos=(106,6), size=(904,80), font=1, color=0x003ca2c6, color_sel=0x0092cbdf, flags=RT_HALIGN_LEFT|RT_WRAP, text=0), # description
						MultiContentEntryText(pos=(1022,6), size=(160,30), font=2, color=0x005fb300, color_sel=0x0088ff00, flags=RT_HALIGN_RIGHT, text=1),  # postTime
						MultiContentEntryText(pos=(1022,30), size=(160,34), font=0, color=0x00b2b300, color_sel=0x00ffff00, flags=RT_HALIGN_RIGHT, text=2),  # user
						MultiContentEntryText(pos=(1022,60), size=(160,30), font=2, color=0x003ca2c6, color_sel=0x0092cbdf, flags=RT_HALIGN_RIGHT, text=3)  # postcount
						])
					},
				"fonts": [gFont("Regular",22), gFont("Regular",20), gFont("Regular",18)]
				}
			</convert>
		</widget>
		<ePixmap position="13,630" size="1200,1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/line_HD.png" zPosition="1" />
		<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_red_HD.png" position="14,636" size="26,38" alphatest="blend" />
		<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_green_HD.png" position="224,636" size="26,38" alphatest="blend" />
		<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_yellow_HD.png" position="434,636" size="26,38" alphatest="blend" />
		<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_blue_HD.png" position="644,636" size="26,38" alphatest="blend" />
		<widget source="key_red" render="Label" position="36,636" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
		<widget source="key_green" render="Label" position="246,636" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
		<widget source="key_yellow" render="Label" position="456,636" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
		<widget source="key_blue" render="Label" position="666,636" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
		<widget name="button_page" position="823,646" size="43,20" alphatest="blend" zPosition="1" />
		<widget source="key_page" render="Label" position="873,636" size="200,38" font="Regular;18" foregroundColor="grey" backgroundColor="#1A0F0F0F" transparent="1" halign="left" valign="center" />
		<widget name="button_keypad" position="1026,643" size="35,25" alphatest="blend" zPosition="1" />
		<widget source="key_keypad" render="Label" position="1066,636" size="200,38" font="Regular;18" foregroundColor="grey" backgroundColor="#1A0F0F0F" transparent="1" halign="left" valign="center" />
	</screen>"""

	def __init__(self, session, threadLinks=None, favlink="", favMenu=False):
		if self.RESOLUTION == "fHD":
			self.skin = self.skin.replace("_HD.png", "_fHD.png")
		Screen.__init__(self, session, self.skin)
		self.threadLinks = threadLinks or []  # required when called by OpenATVFav
		self.favlink = favlink
		self.favMenu = favMenu
		self.ready = False
		self.threadLink, self.oldthreadLink = "", ""
		self.currPage, self.maxPages = 1, 1
		self.oldmenuindex, self.menuindex, self.threadindex = 0, 0, 0
		self.postList, self.mainTexts, self.threadTexts, self.menuPics, self.threadPics, self.avatarDLlist = [], [], [], [], [], []
		self.skinLock = Lock()  # avatar download threads and page loads update the list concurrently
		self.currMode = "menu"
		self["version"] = StaticText(self.VERSION)
		self["waiting"] = BlinkingLabel("bitte warten...")
		self["waiting"].startBlinking()
		self["waiting"].show()
		for widget in ["headline", "button_yellow", "key_yellow", "key_blue", "pagecount", "key_page", "key_keypad"]:
			self[widget] = StaticText()
		for widget in ["button_page", "button_keypad"]:
			self[widget] = Pixmap()
			self[widget].hide()
		self["key_red"] = StaticText("Favorit hinzufügen")
		self["key_green"] = StaticText("Aktualisieren")
		self["menu"] = List([])
		self["NumberActions"] = NumberActionMap(["NumberActions", "WizardActions", "ChannelSelectBaseActions", "PreviousNextActions", "ColorActions"], {
			"ok": self.keyOk,
			"back": self.keyExit,
			"red": self.keyRed,
			"green": self.keyGreen,
			"yellow": self.keyYellow,
			"blue": self.keyBlue,
			"up": self.keyUp,
			"down": self.keyDown,
			"right": self.keyPageDown,
			"left": self.keyPageUp,
			"nextBouquet": self.prevPage,
			"prevBouquet": self.nextPage,
			"previous": self.prevPage,
			"next": self.nextPage,
			"0": self.gotoPage,
			"1": self.gotoPage,
			"2": self.gotoPage,
			"3": self.gotoPage,
			"4": self.gotoPage,
			"5": self.gotoPage,
			"6": self.gotoPage,
			"7": self.gotoPage,
			"8": self.gotoPage,
			"9": self.gotoPage
		}, -1)
		self.checkFiles()
		linefile = join(self.PLUGINPATH, f"icons/line_{self.RESOLUTION}.png")
		self.linePix = LoadPixmap(cached=True, path=linefile) if exists(linefile) else None
		statusFile = join(self.PLUGINPATH, f"icons/online_{self.RESOLUTION}.png")
		self.online = LoadPixmap(cached=True, path=statusFile) if exists(statusFile) else None
		statusFile = join(self.PLUGINPATH, f"icons/offline_{self.RESOLUTION}.png")
		self.offline = LoadPixmap(cached=True, path=statusFile) if exists(statusFile) else None
		copy2(join(self.PLUGINPATH, "icons/user_stat.png"), self.AVATARPATH)
		copy2(join(self.PLUGINPATH, "icons/unknown.png"), self.AVATARPATH)
		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		errMsg = fparser.checkServerStatus()
		if errMsg:
			self.terminateTimer = eTimer()  # delayed in order to avoid E2 modal open screen error
			self.terminateTimer.callback.append(boundFunction(self.terminatePlugin, errMsg))
			self.terminateTimer.start(200, True)
		else:
			self.showPic(self["button_page"], join(self.PLUGINPATH, f"icons/key_updown_{self.RESOLUTION}.png"), show=False, scale=False)
			self.showPic(self["button_keypad"], join(self.PLUGINPATH, f"icons/keypad_{self.RESOLUTION}.png"), show=False, scale=False)
			self.updateYellowButton()
			if self.favlink or self.threadLink and self.threadLinks:
				callInThread(self.makeThread, self.displayHTMLerror)
			else:
				callInThread(self.makeLatest, self.displayHTMLerror)

	def terminatePlugin(self, errMsg):
		self.displayHTMLerror(errMsg)
		self.keyExit()

	def displayHTMLerror(self, errMsg=""):
		if errMsg:
			self.session.open(MessageBox, f"Fehler beim Zugriff auf die Forumsseite:\n\n{errMsg}\n\n", type=MessageBox.TYPE_ERROR, timeout=5, close_on_any_key=True)

	def makeLatest(self, errorCallBack, index=None):
		self["menu"].style = "default"
		self["menu"].updateList([])
		self["waiting"].setText("bitte warten...")
		self["waiting"].startBlinking()
		self["waiting"].show()
		self["headline"].setText("")
		self["pagecount"].setText("")
		self["key_blue"].setText("")
		self.currMode = "menu"
		self.oldmenuindex = 0
		self.menuPics, self.mainTexts, self.threadLinks = [], [], []
		self.threadLink = ""
		self.ready = False
		userList = []
		for startPage in range(5):  # load the first five pages only
			errMsg, latestDict = fparser.parseLatest(int(startPage * self.POSTSPERMAIN))
			if errMsg:
				errorCallBack(errMsg=errMsg)
			for post in latestDict.get("threads", []):
				userName = post.get("userName", "")
				if userName not in userList:
					userList.append(userName)
				title = post.get("title", "")
				sourceLine = post.get("sourceLine", "") or "neues Thema erstellt"
				if "» in" in sourceLine:
					creation, forum = sourceLine.split("» in")
					forum = f"in {forum}"
				else:
					creation, forum = "", ""
				latestLine = post.get("latestLine", "")
				postTime = latestLine[latestLine.find("« ") + 2:] or "{kein Datum}"
				views, posts = post.get("views", ""), post.get("posts", "")
				stats = f"{views}, {posts}"
				postsInt = posts.replace(" Antworten", "")
				postsInt = int(postsInt) if postsInt.isdigit() else 0
				threadId = post.get("threadId", "")
				self.mainTexts.append([title, creation, forum, postTime, userName, stats])
				self.menuPics.append([None, False])  # 'avatar' and 'online' are not available on starting page
				startPage = postsInt // self.POSTSPERTHREAD * self.POSTSPERTHREAD
				self.threadLinks.append(fparser.createThreadUrl(threadId, startPage if threadId else 0))
				self.updateSkin()
		userList = ", ".join(userList)
		userList = f"{userList[:200]}…" if len(userList) > 200 or userList.endswith(",") else userList
		self.mainTexts.append(["beteiligte Benutzer", userList, "", "", "", ""])
		self.menuPics.append(["./user_stat.png", False])
		self["waiting"].stopBlinking()
		self["headline"].setText("aktuelle Themen")
		self.ready = True
		self.updateSkin()
		if index:
			self["menu"].setCurrentIndex(index)

	def makeThread(self, errorCallBack, index=None, movetoend=False):
		self.currMode = "thread"
		self["menu"].style = "thread"
		self["menu"].updateList([])
		self["waiting"].setText("bitte warten...")
		self["waiting"].startBlinking()
		self["waiting"].show()
		self["headline"].setText("")
		self["key_blue"].setText("Startmenu")
		with self.skinLock:
			self.postList, self.threadPics, self.threadTexts = [], [], []
		self.ready = False
		errMsg, threadDict = fparser.parseThread(threadUrl=self.favlink if self.favlink else self.threadLink)
		if errMsg:
			errorCallBack(errMsg=errMsg)
		threadTitle = threadDict.get("threadTitle", "{kein Titel gefunden}")
		self.currPage, self.maxPages = threadDict.get("currPage", 1), threadDict.get("maxPages", 1)
		threadId = threadDict.get("threadId")
		if threadId:  # keep the link of the current page, so paging & refresh also work for favorites and linked threads
			self.threadLink = fparser.createThreadUrl(threadId, (self.currPage - 1) * self.POSTSPERTHREAD)
		self["waiting"].stopBlinking()
		self["headline"].setText(f"THEMA: {threadTitle}")
		self["pagecount"].setText(f"Seite {self.currPage} von {self.maxPages}")
		# build the lists locally first: avatar download threads call 'updateSkin' meanwhile and must never see half-filled lists
		postList, threadPics, threadTexts, avatarUrls = [], [], [], []
		for post in threadDict.get("posts", []):
			postId, postNo, online = post.get("postId", ""), post.get("postNumber", ""), post.get("online", "")
			avatarUrl = post.get("avatarUrl", "")
			avatarUrls.append(avatarUrl)
			userName = post.get("userName", "")
			if "gelöschter benutzer" in userName.lower():
				userName = "{gelöscht}"
			postCnt = post.get("postsCounter", "0")
			postTime = post.get("postTime", "{kein Datum/Uhrzeit}")
			shortCont = post.get("shortContent", "")
			shortCont = f"{postNo}: {shortCont[:280]}{shortCont[280:shortCont.find(' ', 280)]}…" if len(shortCont) > 280 else f"{postNo}: {shortCont}"
			threadTexts.append([shortCont, postTime, userName, postCnt])
			threadPics.append([avatarUrl, online])
			postList.append((threadTitle, postId, postNo, avatarUrl, online, userName))
		userList = ", ".join(threadDict.get("user", []))
		userList = f"beteiligte Benutzer\n{userList[:200]}…" if len(userList) > 200 or userList.endswith(",") else f"beteiligte Benutzer\n{userList}"
		threadTexts.append([userList, "", "", ""])
		threadPics.append(["./user_stat.png", False])
		with self.skinLock:
			self.postList, self.threadPics, self.threadTexts = postList, threadPics, threadTexts
		for avatarUrl in avatarUrls:
			self.handleAvatar(None, avatarUrl, callback=self.handleAvatarUpdate)  # trigger download & update of avatar
		self.ready = True
		self.updateSkin()
		if self.favMenu and self.favlink:
			favid = parse_qs(urlparse(self.favlink).query)["p"][0] if "p=" in self.favlink else ""
			hitlist = [item for item in self.postList if item[1] == favid]
			index = self.postList.index(hitlist[0]) if hitlist else 0
			self.favlink = ""
		if index:
			self["menu"].setCurrentIndex(index)
		elif movetoend:
			self["menu"].goBottom()
			self["menu"].goLineUp()  # last entry is always the summary 'beteiligte Benutzer'

	def updateSkin(self):
		with self.skinLock:  # serialize concurrent calls, otherwise an outdated (shorter) list could overwrite the complete one
			skinPix = []
			for menuPic in self.menuPics if self.currMode == "menu" else self.threadPics:
				if self.currMode == "thread":
					avatarPix, _ = self.handleAvatar(None, menuPic[0])
					statuspix = self.online if menuPic[1] else self.offline
				else:
					avatarPix = None
					statuspix = None
				skinPix.append([self.linePix, avatarPix, statuspix])
			skinlist = []
			for menulist, pixlist in zip(self.mainTexts if self.currMode == "menu" else self.threadTexts, skinPix):
				skinlist.append(tuple(menulist + pixlist))
			self["menu"].updateList(skinlist)
		if self.currMode == "thread" and self.maxPages > 1:
			self["button_page"].show()
			self["button_keypad"].show()
			self["key_page"].setText("Seite vor/zurück")
			self["key_keypad"].setText("direkt zur Seite…")
		else:
			self["button_page"].hide()
			self["button_keypad"].hide()
			self["key_page"].setText("")
			self["key_keypad"].setText("")

	def updateYellowButton(self):
		if self.favMenu:
			self["key_yellow"].setText("")
		else:
			self["key_yellow"].setText("Favoriten aufrufen")

	def handleAvatarUpdate(self, widget, url, filePath):  # don't remove 'widget' here
		self.downloadAvatar(url, filePath)
		self.updateSkin()

	def keyOk(self):
		current = self["menu"].getCurrentIndex()
		if self.currMode == "menu" and len(self.threadLinks) > current:
			self.threadLink = self.threadLinks[current]
			if self.threadLink:
				self.oldmenuindex = current
				callInThread(self.makeThread, self.displayHTMLerror, movetoend=True)
		else:
			if current < len(self.postList):
				postDetails = self.postList[current]
				if postDetails:
					# postList: (threadTitle, postId, postNo, avatarUrl, online, userName)
					self.session.openWithCallback(self.keyOkCB, openATVPost, postDetails[0], postDetails[1], self.favMenu, self.threadLinks)

	def keyOkCB(self, home=False):
		if home:
			self["menu"].updateList([])
			callInThread(self.makeLatest, self.displayHTMLerror)

	def keyExit(self):
		if self.currMode == "menu":
			if exists(self.AVATARPATH):
				rmtree(self.AVATARPATH)
			self.close()
		if self.currMode == "thread":
			if self.favMenu:
				self.favMenu = False
				self.favlink = ""
				self.close()
			else:
				self.switchToMenuview()

	def keyRed(self):
		favname, favlink = self.makeFavdata()
		if self.favoriteExists(self.session, favname, favlink):
			self.session.open(MessageBox, f"ABBRUCH!\n\n'{favname}'\n\nist bereits in den Favoriten vorhanden.\n", type=MessageBox.TYPE_ERROR, timeout=5, close_on_any_key=True)
		else:
			self.session.openWithCallback(boundFunction(self.keyRedCB, favname, favlink), MessageBox, f"'{favname}'\n\nzu den Favoriten hinzufügen?\n", MessageBox.TYPE_YESNO, timeout=30)

	def keyRedCB(self, favname, favlink, answer):
		if answer is True:
			self.writeFavorite(self.session, favname, favlink)

	def keyGreen(self):
		if self.ready:
			if self.currMode == "menu":
				self.menuindex = self["menu"].getCurrentIndex()
				self["menu"].updateList([])
				callInThread(self.makeLatest, self.displayHTMLerror, index=self.menuindex)
			elif self.threadLink:
				self.threadindex = self["menu"].getCurrentIndex()
				self["menu"].updateList([])
				callInThread(self.makeThread, self.displayHTMLerror, index=self.threadindex)

	def keyYellow(self):
		if self.favMenu:
			self.session.open(MessageBox, "Dieses Fenster wurde bereits als Favorit geöffnet!\nUm auf die Favoritenliste zurückzukommen, bitte 1x 'Verlassen/Exit' drücken!\n", timeout=5, type=MessageBox.TYPE_INFO, close_on_any_key=True)
		else:
			self.favMenu = True
			self.oldthreadLink = self.threadLink
			self.session.openWithCallback(self.keyYellowCB, openATVFav, self.threadLinks)

	def keyYellowCB(self, home=False):
		self.favMenu = False
		self.favlink = ""
		self.threadLink = self.oldthreadLink
		self.updateYellowButton()
		if home:
			self["menu"].updateList([])
			callInThread(self.makeLatest, self.displayHTMLerror)

	def keyBlue(self):
		if self.favMenu:
			self.close(True)
		if self.currMode == "thread":
			self.switchToMenuview()

	def switchToMenuview(self):
		self.currMode = "menu"
		self["menu"].style = "default"
		self["headline"].setText("aktuelle Themen")
		self["pagecount"].setText("")
		self.updateSkin()
		self["menu"].setCurrentIndex(self.oldmenuindex)

	def makeFavdata(self):
		favname, favlink = "", ""
		curridx = self["menu"].getCurrentIndex()
		if self.currMode == "menu" and self.mainTexts:
			favname = f"THEMA: {self.mainTexts[curridx][0]}"
			favlink = self.threadLinks[curridx]  # threadLink, e.g. https://www.opena.tv/viewtopic.php?t=66608&start=0
		elif self.currMode == "thread" and self.postList:
			favname = f"BEITRAG {self.postList[curridx][2]} von '{self.postList[curridx][5]} 'in '{self.postList[curridx][0]}'"
			favlink = fparser.createPostUrl(self.postList[curridx][1])
		return favname, favlink

	def keyDown(self):
		self["menu"].down()

	def keyUp(self):
		self["menu"].up()

	def keyPageDown(self):
		self["menu"].pageDown()

	def keyPageUp(self):
		self["menu"].pageUp()

	def nextPage(self):
		if self.currMode == "menu":
			self.keyPageDown()
		elif self.currMode == "thread" and self.currPage < self.maxPages:
			self.currPage += 1
			# use url of previous entry when 'beteiligte Benutzer'
			threadLink = self.threadLink if self.threadLink else self.threadLinks[self["menu"].getCurrentIndex() - 1]
			threadid = parse_qs(urlparse(threadLink).query)["t"][0] if "t=" in threadLink else ""
			if threadid:
				self.threadLink = fparser.createThreadUrl(threadid, (self.currPage - 1) * self.POSTSPERTHREAD)
				callInThread(self.makeThread, self.displayHTMLerror)

	def prevPage(self):
		if self.currMode == "menu":
			self.keyPageUp()
		elif self.currMode == "thread" and self.currPage > 1:
			self.currPage -= 1
			# use url of previous entry when 'beteiligte Benutzer'
			threadLink = self.threadLink if self.threadLink else self.threadLinks[self["menu"].getCurrentIndex() - 1]
			threadid = parse_qs(urlparse(threadLink).query)["t"][0] if "t=" in threadLink else ""
			if threadid:
				self.threadLink = fparser.createThreadUrl(threadid, (self.currPage - 1) * self.POSTSPERTHREAD)
				callInThread(self.makeThread, self.displayHTMLerror, movetoend=True)

	def gotoPage(self, number):
		if self.currMode == "thread":
			self.session.openWithCallback(self.getKeypad, getNumber, number)

	def getKeypad(self, number):
		if number:
			if number > self.maxPages:
				number = self.maxPages
				self.session.open(MessageBox, f"\nEs sind nur {number} Seiten verfügbar, daher wird die letzte Seite aufgerufen.", MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
			if self.currMode == "thread" and self.threadLink:
				threadid = parse_qs(urlparse(self.threadLink).query)["t"][0] if "t=" in self.threadLink else ""
				if threadid:
					self.threadLink = fparser.createThreadUrl(threadid, (number - 1) * self.POSTSPERTHREAD)
					callInThread(self.makeThread, self.displayHTMLerror)

	def checkFiles(self):
		try:
			if not exists(self.AVATARPATH):
				makedirs(self.AVATARPATH)
		except OSError as errMsg:
			self.session.open(MessageBox, f"Dateipfad für Avatare konnte nicht neu angelegt werden:\n'{errMsg}'", type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)
		if not exists(self.FAVORITEN):
			try:
				with open(self.FAVORITEN, "w"):
					pass  # write empty file
			except OSError as errMsg:
				self.session.open(MessageBox, f"Favoriten konnten nicht neu angelegt werden:\n'{errMsg}'", type=MessageBox.TYPE_INFO, timeout=2, close_on_any_key=True)


def main(session, **kwargs):
	session.open(openATVMain)


def menu(menuid, **kwargs):
	return [(PLUGIN_NAME, main, "openatv_reader", 10)] if menuid == "support" else []


def Plugins(**kwargs):
	return [PluginDescriptor(name=PLUGIN_NAME,
				description=PLUGIN_DESCRIPTION,
				where=[PluginDescriptor.WHERE_PLUGINMENU],
				icon="plugin.png", fnc=main),
			PluginDescriptor(name=PLUGIN_NAME,
				description=PLUGIN_DESCRIPTION,
				where=[PluginDescriptor.WHERE_EXTENSIONSMENU],
				fnc=main),
			PluginDescriptor(name=PLUGIN_NAME,
				description=PLUGIN_DESCRIPTION,
				where=[PluginDescriptor.WHERE_MENU],
				fnc=menu)
			]
