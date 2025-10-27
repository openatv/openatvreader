#########################################################################################################
#  OpenATVreader, coded by Mr.Servo @ openATV 2024                                                      #
#  -----------------------------------------------------------------------------------------------------#
#  This plugin is licensed under the GNU version 3.0 <https://www.gnu.org/licenses/gpl-3.0.en.html>.    #
#  This plugin is NOT free software. It is open source, you are allowed to modify it (if you keep       #
#  the license), but it may not be commercially distributed. Advertise with this tool is not allowed.   #
#  For other uses, permission from the authors is necessary.                                            #
#########################################################################################################
from glob import glob
from os import rename, makedirs, linesep
from os.path import join, exists
from requests import get, exceptions
from shutil import copy2, rmtree
from twisted.internet.reactor import callInThread
from urllib.parse import urlparse, parse_qs
from enigma import getDesktop, eTimer, BT_SCALE, BT_KEEP_ASPECT_RATIO
from Components.ActionMap import ActionMap, NumberActionMap
from Components.ConditionalWidget import BlinkingWidget
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Components.ScrollLabel import ScrollLabel
from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Tools.BoundFunction import boundFunction
from Tools.Directories import resolveFilename, SCOPE_PLUGINS, SCOPE_CONFIG
from Tools.LoadPixmap import LoadPixmap
from . import __version__
from .forumparser import fparser

SUPPALLIMGS = True
try:
	from enigma import detectImageType  # new function in OpenATV 7.6.0 and newer
except ImportError:
	SUPPALLIMGS = False
	from imghdr import what  # DEPRECATED function in OpenATV 7.5.1 or older


class ATVglobals:
	VERSION = f"V{__version__}"
	AVATARPATH = "/tmp/avatare"
	PLUGINPATH = resolveFilename(SCOPE_PLUGINS, "Extensions/OpenATVreader/")
	FAVORITEN = resolveFilename(SCOPE_CONFIG, "openatvreader_fav.dat")
	RESOLUTION = "fHD" if getDesktop(0).size().width() > 1300 else "HD"
	POSTSPERMAIN = 5  # quantity of post in view 'latest posts'
	POSTSPERTHREAD = 20  # quantity of post in view 'thread'
	MODULE_NAME = __name__.split(".")[-2]


class ATVhelper(Screen, ATVglobals):
	def getHTMLdata(self, url):
		try:
			response = get(url, timeout=(3.05, 6))
			if response.ok:
				return response.text
			else:
				print(f"Website access ERROR, response code: {response.raise_for_status()}")
		except exceptions.RequestException as error:
			errMsg = f"Der opena.tv Server ist zur Zeit nicht erreichbar.\n{error}"
			print(f"[{self.MODULE_NAME}] ERROR in module 'getHTMLdata': {errMsg}")
			self.session.open(MessageBox, errMsg, MessageBox.TYPE_INFO, timeout=30, close_on_any_key=True)
			return ""

	def handleAvatar(self, widget, pixUrl, callback=None):
		avatarPix, filePath = None, join(self.AVATARPATH, "unknown.png")
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
			except Exception as error:
				print(f"[{self.MODULE_NAME}] ERROR in module 'handleAvatar': {error}!")
			if pixUrl in self.avatarDLlist:
				self.avatarDLlist.remove(pixUrl)
		elif pixUrl not in self.avatarDLlist:  # avoid multiple threaded downloads of equal avatars
			self.avatarDLlist.append(pixUrl)
			if callback:
				callInThread(callback, widget, pixUrl, join(self.AVATARPATH, urlFileName))
		return avatarPix, filePath

	def downloadAvatar(self, url, filePath):  # file extensions in url could be wrong
		try:
			response = get(url, timeout=(3.05, 6))
			if not response.ok:
				print(f"Website access ERROR, response code: {response.raise_for_status()}", "")
		except exceptions.RequestException as error:
			errMsg = f"Der opena.tv Server ist zur Zeit nicht erreichbar.\n{error}"
			print(f"[{self.MODULE_NAME}] ERROR in module 'downloadAvatar': {errMsg}!")
			self.session.open(MessageBox, errMsg, MessageBox.TYPE_INFO, timeout=30, close_on_any_key=True)
			return
		try:
			with open(filePath, "wb") as f:
				f.write(response.content)
		except OSError as errMsg:
			print(f"[{self.MODULE_NAME}] ERROR in module 'downloadAvatar': {errMsg}!")
			self.session.open(MessageBox, errMsg, MessageBox.TYPE_INFO, timeout=30, close_on_any_key=True)
		fileParts = filePath.split(".")
		if SUPPALLIMGS:  # use function 'detectImageType' in OpenATV 7.6.0 or newer
			extension = {0: "png", 1: "jpg", 3: "gif", 4: "svg", 5: "webp"}.get(detectImageType(filePath), fileParts[1])
		else:  # use DEPRECATED function 'what' in OpenATV 7.5.1 or OpenATV 7.5.1 or older
			extension = what(filePath).replace("jpeg", "jpg")
		if extension != fileParts[1]:  # Some avatars could be incorrectly listed in 'url' as .GIF although they are .JPG or .PNG
			newFname = f"{fileParts[0]}.{extension}"
			rename(filePath, newFname)  # rename with correct extension

	def showPic(self, widget, filePath, show=True, scale=True):
		if scale:
			widget.instance.setPixmapScaleFlags(BT_SCALE | BT_KEEP_ASPECT_RATIO)
		widget.instance.setPixmapFromFile(filePath)
		if show:
			widget.show()

	def favoriteExists(self, session, favname, favlink):
		self.session = session
		favfound = False
		if favname and favlink and exists(self.FAVORITEN):
			try:
				with open(self.FAVORITEN, "r") as f:
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
		self['actions'] = NumberActionMap(['OkCancelActions'], {
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
		<widget source="headline" render="Label" position="340,28" size="620,30" font="Regular;24" halign="left" valign="center" wrap="ellipsis" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
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
				with open(self.FAVORITEN, "r") as f:
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
				with open(self.FAVORITEN, "r") as f:
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
		<widget source="headline" render="Label" position="340,28" size="750,30" font="Regular;24" halign="left" valign="center" wrap="ellipsis" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget name="waiting" position="340,29" size="750,30" font="Regular;20" halign="left" valign="bottom" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget source="postid" render="Label" position="1100,6" size="100,21" font="Regular;16" halign="right" valign="center" foregroundColor="grey" transparent="1" zPosition="1" />
		<widget source="postnr" render="Label" position="1100,26" size="100,30" font="Regular;24" halign="right" valign="center" foregroundColor="grey" transparent="1" zPosition="1" />
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
		<widget name="textpage" position="26,186" size="1173,433" font="Regular;24" halign="left" foregroundColor="white" scrollbarMode="showOnDemand" transparent="1" zPosition="1" />
		<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_red_HD.png" position="14,636" size="26,38" alphatest="blend" />
		<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_yellow_HD.png" position="434,636" size="26,38" alphatest="blend" />
		<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/key_blue_HD.png" position="644,636" size="26,38" alphatest="blend" />
		<widget source="key_red" render="Label" position="36,636" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
		<widget source="key_yellow" render="Label" position="456,636" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
		<widget source="key_blue" render="Label" position="666,636" size="180,38" zPosition="1" valign="center" font="Regular;18" halign="left" foregroundColor="#00b3b3b3" backgroundColor="#1A0F0F0F" transparent="1" />
	</screen>"""

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
		self.threadTitle, self.postNo = "", ""
		self["waiting"] = BlinkingLabel("bitte warten...")
		self["waiting"].startBlinking()
		self["waiting"].show()
		self["version"] = StaticText(self.VERSION)
		for widget in ["headline", "postid", "postnr", "username", "usertitle", "postcnt", "thxgiven", "thxreceived", "registered", "residence", "datum"]:
			self[widget] = StaticText()
		for widget in ["online", "avatar", "userrank"]:
			self[widget] = Pixmap()
		self["textpage"] = ScrollLabel()
		self["key_red"] = StaticText("Favorit hinzufügen")
		self["key_yellow"] = StaticText("Favoriten aufrufen")
		self["key_blue"] = StaticText("Startseite")
		self["NumberActions"] = ActionMap(["NumberActions", "OkCancelActions", "DirectionActions", "ChannelSelectBaseActions", "ColorActions"], {
			"cancel": self.keyExit,
			"down": self.keyDown,
			"up": self.keyUp,
			"right": self.keyPageDown,
			"left": self.keyPageUp,
			"nextBouquet": self.keyPageDown,
			"prevBouquet": self.keyPageUp,
			"red": self.keyRed,
			"yellow": self.keyYellow,
			"blue": self.keyBlue
		}, -1)
		self.onLayoutFinish.append(self.onLayoutFinished)

	def onLayoutFinished(self):
		callInThread(self.makePost)

	def makePost(self):
		self.ready = False
		errMsg, postDict = fparser.parsePost(self.postId)
		if errMsg:
			self.session.open(MessageBox, f"FEHLER: {errMsg}", type=MessageBox.TYPE_ERROR, timeout=5, close_on_any_key=True)
			return
		self.postNo = postDict.get("postNo", "")
		self.userName = postDict.get("userName", "")
		avatarPix, filePath = self.handleAvatar(self["avatar"], postDict.get("avatarUrl", ""), self.handleAvatarShow)
		self.showPic(self["avatar"], f"{filePath if filePath and exists(filePath) else join(self.AVATARPATH, "unknown.png")}")
		userRank = postDict.get("userRank", "")
		self.handleIcon(self["userrank"], userRank, self.handleIconShow)
		online = postDict.get("online", "")
		self.showPic(self["online"], join(self.PLUGINPATH, f"{'icons/online' if online else 'icons/offline'}_{self.RESOLUTION}.png"), scale=False)
		self["waiting"].stopBlinking()
		self["headline"].setText(self.threadTitle)
		self["postid"].setText(f"ID: {self.postId}")
		self["postnr"].setText(self.postNo)
		self["username"].setText(self.userName)
		self["usertitle"].setText(postDict.get("userTitle", ""))
		self["postcnt"].setText(postDict.get("postsCounter", "0"))
		self["thxgiven"].setText(postDict.get("thxGiven", "{keine}"))
		self["thxreceived"].setText(postDict.get("thxReceived", "{keine})"))
		self["residence"].setText(f"{postDict.get('residence', '{kein Wohnort benannt}')}")
		self["registered"].setText(f"Registriert seit {postDict.get('registered', '{unbekannt}').strip("Registriert: ")}")
		self["datum"].setText(f"Beitrag von {postDict.get('postTime', '')} Uhr")
		self["textpage"].setText(postDict.get("fullContent", "{ohne Inhalt}"))
		self.ready = True

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
			elif callback:
					callInThread(callback, widget, iconUrl, filePath)
		return iconPix

	def handleIconShow(self, widget, url, filePath):
		self.downloadIcon(url, filePath)
		self.showPic(widget, filePath)

	def downloadIcon(self, url, filePath):
		try:
			response = get(url, timeout=(3.05, 6))
			if not response.ok:
				print(f"Website access ERROR, response code: {response.raise_for_status()}", "")
		except exceptions.RequestException as error:
			errMsg = f"Der opena.tv Server ist zur Zeit nicht erreichbar.\n{error}"
			print(f"[{self.MODULE_NAME}] ERROR in module 'downloadAvatar': {errMsg}!")
			self.session.open(MessageBox, errMsg, MessageBox.TYPE_INFO, timeout=30, close_on_any_key=True)
			return
		try:
			with open(filePath, "wb") as f:
				f.write(response.content)
		except OSError as errMsg:
			print(f"[{self.MODULE_NAME}] ERROR in module 'downloadAvatar': {errMsg}!")
			self.session.open(MessageBox, errMsg, MessageBox.TYPE_INFO, timeout=30, close_on_any_key=True)
		fileParts = filePath.split(".")
		if SUPPALLIMGS:  # use new function 'detectImageType' in OpenATV 7.6.0 or newer
			extension = {0: "png", 1: "jpg", 3: "gif", 4: "svg", 5: "webp"}.get(detectImageType(filePath), fileParts[1])
		else:  # use DEPRECATED function 'what' in OpenATV 7.5.1 or OpenATV 7.5.1 or older
			extension = what(filePath)
		if extension != fileParts[1]:  # Some avatars could be incorrectly listed in 'url' as .GIF although they are .JPG or .PNG
			newFname = f"{fileParts[0]}.{extension}"
			rename(filePath, newFname)  # rename with correct extension

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
			self["textpage"].pageDown()

	def keyUp(self):
		if self.ready:
			self["textpage"].pageUp()

	def keyPageDown(self):
		if self.ready:
			self["textpage"].pageDown()

	def keyPageUp(self):
		if self.ready:
			self["textpage"].pageUp()

	def keyExit(self):
		if self.ready:  # wait on thread was finished
			self.close()


class openATVMain(ATVhelper):
	skin = """
	<screen name="openATVMain" position="center,center" size="1233,680" backgroundColor="#1A0F0F0F" resolution="1280,720" title=" ">
		<ePixmap position="10,10" size="300,50" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/OpenATVreader/icons/openATV_HD.png" alphatest="blend" zPosition="1" />
		<widget source="version" render="Label" position="290,36" size="43,21" font="Regular;16" halign="left" valign="center" foregroundColor="grey" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget source="headline" render="Label" position="340,29" size="610,30" font="Regular;24" halign="left" valign="bottom" wrap="ellipsis" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget name="waiting" position="340,29" size="750,30" font="Regular;20" halign="left" valign="bottom" backgroundColor="#1A0F0F0F" transparent="1" zPosition="1" />
		<widget source="global.CurrentTime" render="Label" position="1080,10" size="130,28" font="Regular;28" noWrap="1" halign="right" valign="top" foregroundColor="#00FFFFFF" backgroundColor="#1A0F0F0F" transparent="1">
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
						MultiContentEntryText(pos=(922,2), size=(250,30), font=2, color=0x005fb300, color_sel=0x0088ff00, flags=RT_HALIGN_RIGHT, text=3),  # postTime
						MultiContentEntryText(pos=(922,24), size=(250,34), font=0, color=0x00b2b300, color_sel=0x00ffff00, flags=RT_HALIGN_RIGHT, text=4),  # user
						MultiContentEntryText(pos=(922,54), size=(250,30), font=2, color=0x003ca2c6, color_sel=0x0092cbdf, flags=RT_HALIGN_RIGHT, text=5)  # statistic
						]),
						"thread": (93,[
						MultiContentEntryPixmapAlphaTest(pos=(0,0), size=(1200,1), png=4), # line separator
						MultiContentEntryPixmapAlphaBlend(pos=(6,2), size=(70,70), flags=BT_HALIGN_LEFT|BT_VALIGN_CENTER|BT_SCALE|BT_KEEP_ASPECT_RATIO, png=5),  # avatar
						MultiContentEntryPixmapAlphaBlend(pos=(9,72), size=(64,16), png=6),  # online
						MultiContentEntryText(pos=(106,6), size=(904,80), font=1, color=0x003ca2c6, color_sel=0x0092cbdf, flags=RT_HALIGN_LEFT|RT_WRAP, text=0), # description
						MultiContentEntryText(pos=(1022,6), size=(150,30), font=2, color=0x005fb300, color_sel=0x0088ff00, flags=RT_HALIGN_RIGHT, text=1),  # postTime
						MultiContentEntryText(pos=(1022,30), size=(150,34), font=0, color=0x00b2b300, color_sel=0x00ffff00, flags=RT_HALIGN_RIGHT, text=2),  # user
						MultiContentEntryText(pos=(1022,60), size=(150,30), font=2, color=0x003ca2c6, color_sel=0x0092cbdf, flags=RT_HALIGN_RIGHT, text=3)  # postcount
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

	def __init__(self, session, threadLinks=[], favlink="", favMenu=False):
		if self.RESOLUTION == "fHD":
			self.skin = self.skin.replace("_HD.png", "_fHD.png")
		Screen.__init__(self, session, self.skin)
		self.threadLinks = threadLinks  # required when called by OpenATVFav
		self.favlink = favlink
		self.favMenu = favMenu
		self.ready = False
		self.threadLink, self.oldthreadLink = "", ""
		self.currPage, self.maxPages = 1, 1
		self.oldmenuindex, self.menuindex, self.threadindex = 0, 0, 0
		self.postList, self.mainTexts, self.threadTexts, self.menuPics, self.threadPics, self.avatarDLlist = [], [], [], [], [], []
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
		self["NumberActions"] = NumberActionMap(["NumberActions", "WizardActions", "ChannelSelectBaseActions", "ColorActions"], {
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
		self.onLayoutFinish.append(self.onLayoutFinished)

	def onLayoutFinished(self):
		self.showPic(self["button_page"], join(self.PLUGINPATH, f"icons/key_updown_{self.RESOLUTION}.png"), show=False, scale=False)
		self.showPic(self["button_keypad"], join(self.PLUGINPATH, f"icons/keypad_{self.RESOLUTION}.png"), show=False, scale=False)
		self.updateYellowButton()
		if self.favlink or self.threadLink and self.threadLinks:
			callInThread(self.makeThread)
		else:
			callInThread(self.makeLatest)

	def makeLatest(self, index=None):
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
				self.session.open(MessageBox, f"FEHLER: {errMsg}", type=MessageBox.TYPE_ERROR, timeout=5, close_on_any_key=True)
				return
			for post in latestDict.get("threads", []):
				userName = post.get("userName", "")
				if userName not in userList:
					userList.append(userName)
				title = post.get("title", "")
				sourceLine = post.get("sourceLine", "") or "neues Thema erstellt"
				if "» in" in sourceLine:
					creation, forum = sourceLine.split("» in")
					forum = f"in {forum}"
				latestLine = post.get("latestLine", "")
				postTime = latestLine[latestLine.find("« ") + 2:] or "{kein Datum}"
				views, posts = post.get("views", ""), post.get("posts", "")
				stats = ", ".join([views, posts])
				postsInt = posts.rstrip(" Antworten")
				postsInt = int(postsInt) if postsInt.isdigit() else 0
				threadId = post.get("threadId", "")
				self.mainTexts.append([title, creation, forum, postTime, userName, stats])
				self.menuPics.append([None, False])  # 'avatar' and 'online' are not available on starting page
				startPage = postsInt // self.POSTSPERTHREAD * self.POSTSPERTHREAD
				self.threadLinks.append(fparser.createThreadUrl(threadId, startPage if threadId else ""))
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

	def makeThread(self, index=None, movetoend=False):
		self.currMode = "thread"
		self["menu"].style = "thread"
		self["menu"].updateList([])
		self["waiting"].setText("bitte warten...")
		self["waiting"].startBlinking()
		self["waiting"].show()
		self["headline"].setText("")
		self["key_blue"].setText("Startmenu")
		self.postList, self.threadPics, self.threadTexts = [], [], []
		self.ready = False
		errMsg, threadDict = fparser.parseTread(threadUrl=self.favlink if self.favlink else self.threadLink)
		if errMsg:
			self.session.open(MessageBox, f"FEHLER: {errMsg}", type=MessageBox.TYPE_ERROR, timeout=5, close_on_any_key=True)
			return
		threadTitle = threadDict.get("threadTitle", "{kein Titel gefunden}")
		self.currPage, self.maxPages = threadDict.get("currPage", 1), threadDict.get("maxPages", 1)
		self["waiting"].stopBlinking()
		self["headline"].setText(f"THEMA: {threadTitle}")
		self["pagecount"].setText(f"Seite {self.currPage} von {self.maxPages}")
		for post in threadDict.get("posts", []):
			postId, postNo, online = post.get("postId", ""), post.get("postNumber", ""), post.get("online", "")
			avatarUrl = post.get("avatarUrl", "")
			self.handleAvatar(None, avatarUrl, callback=self.handleAvatarUpdate)  # trigger download & update of avatar
			userName = post.get("userName", "")
			if "gelöschter benutzer" in userName.lower():
				userName = "{gelöscht}"
			postCnt = post.get("postsCounter", "0")
			postTime = post.get("postTime", "{kein Datum/Uhrzeit}")
			shortCont = post.get("shortContent", "")
			shortCont = f"{postNo}: {shortCont[:280]}{shortCont[280:shortCont.find(' ', 280)]}…" if len(shortCont) > 280 else f"{postNo}: {shortCont}"
			self.threadTexts.append([shortCont, postTime, userName, postCnt])
			self.threadPics.append([avatarUrl, online])
			self.postList.append((threadTitle, postId, postNo, avatarUrl, online, userName))
		userList = ", ".join(threadDict.get("user", []))
		userList = f"beteiligte Benutzer\n{userList[:200]}…" if len(userList) > 200 or userList.endswith(",") else f"beteiligte Benutzer\n{userList}"
		self.threadTexts.append([userList, "", "", ""])
		self.threadPics.append(["./user_stat.png", False])
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
		skinPix = []
		for menuPic in self.menuPics if self.currMode == "menu" else self.threadPics:
			if self.currMode == "thread":
				avatarPix, filePath = self.handleAvatar(None, menuPic[0])
				statuspix = self.online if menuPic[1] else self.offline
			else:
				avatarPix = None
				statuspix = None
			skinPix.append([self.linePix, avatarPix, statuspix])
		skinlist = []
		for idx, menulist in enumerate(self.mainTexts if self.currMode == "menu" else self.threadTexts):
			skinlist.append(tuple(menulist + skinPix[idx]))
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
		if self.currMode == "menu":
			self.threadLink = self.threadLinks[current]
			if self.threadLink:
				self.oldmenuindex = current
				callInThread(self.makeThread, movetoend=True)
		else:
			if current < len(self.postList):
				postDetails = self.postList[current]
				if postDetails:
					# self.postList.append((threadTitle, postId, postNo, avatarUrl, online, userName))
					self.session.openWithCallback(self.keyOkCB, openATVPost, postDetails[0], postDetails[1], self.favMenu, self.threadLinks)

	def keyOkCB(self, home=False):
		if home:
			self["menu"].updateList([])
			callInThread(self.makeLatest)

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
				callInThread(self.makeLatest, index=self.menuindex)
			elif self.threadLink:
				self.threadindex = self["menu"].getCurrentIndex()
				self["menu"].updateList([])
				callInThread(self.makeThread, index=self.threadindex)

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
			callInThread(self.makeLatest)

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
				callInThread(self.makeThread)

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
				callInThread(self.makeThread, movetoend=True)

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
					callInThread(self.makeThread)

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


def Plugins(**kwargs):
	return [PluginDescriptor(name="OpenATV Reader",
				description="Das opena.tv Forum bequem auf dem TV mitlesen",
				where=[PluginDescriptor.WHERE_PLUGINMENU],
				icon="plugin.png", fnc=main),
			PluginDescriptor(name="OpenATV Reader",
				description="Das opena.tv Forum bequem auf dem TV mitlesen",
				where=[PluginDescriptor.WHERE_EXTENSIONSMENU],
				fnc=main)
			]
